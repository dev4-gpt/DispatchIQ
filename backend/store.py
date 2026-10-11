"""Single-process revisioned state with private proposals and atomic durable commits."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Callable
from uuid import uuid4

from .explanations import changes
from .metrics import diff_metrics, schedule_metrics
from .optimizer import optimize
from .scenario import make_scenario
from .schemas import (BaseRequest, Comparison, EmergencyEvent, Event, OptimizeRequest,
                      PreviewRequest, Proposal, ProposalRequest, Snapshot, UnavailableEvent)
from .validator import validate_schedule


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, revision: int | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.revision = status, code, message, revision

    def envelope(self):
        return {"error": {"code": self.code, "message": self.message, "current_revision": self.revision, "details": []}}


@dataclass
class StoredProposal:
    proposal: Proposal
    expires: datetime
    lifecycle: str = "pending"


class StateStore:
    def __init__(self, path: Path | None = None, *, clock: Callable[[], datetime] | None = None,
                 proposal_ttl_seconds: int = 900, search_budget_seconds: float = 2.0):
        self.path = path
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.ttl = proposal_ttl_seconds
        self.search_budget_seconds = search_budget_seconds
        self.lock = RLock()
        self.proposals: dict[str, StoredProposal] = {}
        if path is not None and path.exists():
            self.current = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
            validation = validate_schedule(self.current)
            if not validation.valid:
                raise RuntimeError("Persisted operational state failed independent validation.")
            self.current.validation = validation
            self.current.metrics = schedule_metrics(self.current)
        else:
            self.current = make_scenario()
            self._persist(self.current)

    def snapshot(self) -> Snapshot:
        with self.lock:
            return self.current.model_copy(deep=True)

    def snapshot_at(self, request: BaseRequest) -> Snapshot:
        """Copy of the committed snapshot, only if the caller's base metadata is current."""
        with self.lock:
            self._check_base(request)
            return self.current.model_copy(deep=True)

    def _check_base(self, request: BaseRequest):
        if request.scenario_id != self.current.scenario_id or request.scenario_epoch != self.current.scenario_epoch:
            raise APIError(409, "SCENARIO_CHANGED", "The scenario changed. Refresh and preview again.", self.current.revision)
        if request.base_revision != self.current.revision:
            raise APIError(409, "STALE_PROPOSAL", "The schedule changed. Preview this event again.", self.current.revision)

    def _check_event(self, snapshot: Snapshot, event: Event | None):
        if event is None:
            return
        if event.at_min != snapshot.now_min:
            raise APIError(422, "INVALID_INPUT", "Event time must equal the current simulation time.", snapshot.revision)
        if isinstance(event, EmergencyEvent) and event.job.id in {j.id for j in snapshot.jobs}:
            raise APIError(422, "INVALID_INPUT", "Emergency job ID already exists.", snapshot.revision)
        if isinstance(event, UnavailableEvent):
            tech = next((t for t in snapshot.technicians if t.id == event.technician_id), None)
            if tech is None:
                raise APIError(404, "UNKNOWN_TECHNICIAN", "Technician does not exist.", snapshot.revision)
            if tech.availability == "unavailable":
                raise APIError(422, "INVALID_INPUT", "Technician is already unavailable.", snapshot.revision)

    def preview(self, request: PreviewRequest | OptimizeRequest) -> Proposal:
        event = request.event if isinstance(request, PreviewRequest) else None
        with self.lock:
            self._check_base(request)
            original = self.current.model_copy(deep=True)
            self._check_event(original, event)
        t0 = perf_counter()
        try:
            result = optimize(original, event, request.strategy, budget_seconds=self.search_budget_seconds / 2)
            other = "first_feasible" if request.strategy == "stable_insertion" else "stable_insertion"
            comparison_result = optimize(original, event, other, budget_seconds=max(0, self.search_budget_seconds - (perf_counter() - t0)))
        except Exception as exc:
            raise APIError(503, "OPTIMIZER_FAILED", "Optimization failed. The committed schedule is unchanged.", original.revision) from exc
        comparison = []
        for strategy, item in ((request.strategy, result), (other, comparison_result)):
            comparison.append(Comparison(strategy=strategy, status="ready" if item.snapshot is not None else "no_feasible_plan",
                                         metrics=item.snapshot.metrics if item.snapshot else None,
                                         diff_metrics=diff_metrics(original, item.snapshot) if item.snapshot else None,
                                         runtime_ms=item.runtime_ms, validation=item.validation))
        expires = self.clock() + timedelta(seconds=self.ttl)
        proposal = Proposal(proposal_id=str(uuid4()), scenario_id=original.scenario_id,
                            scenario_epoch=original.scenario_epoch, base_revision=original.revision,
                            status="ready" if result.snapshot is not None else "no_feasible_plan",
                            event=event.model_copy(deep=True) if event is not None else None,
                            proposed_snapshot=result.snapshot,
                            changes=changes(original, result.snapshot, result.selected_candidate_id) if result.snapshot else [],
                            validation=result.validation, candidates=result.candidates,
                            selected_candidate_id=result.selected_candidate_id, comparison=comparison,
                            runtime_ms=result.runtime_ms, search=result.search, expires_at_utc=expires.isoformat(),
                            explanation=result.explanation)
        with self.lock:
            self._check_base(request)  # computation may have raced with a commit/reset
            self.proposals[proposal.proposal_id] = StoredProposal(proposal.model_copy(deep=True), expires)
        return proposal

    def _get_proposal(self, request: ProposalRequest) -> StoredProposal:
        record = self.proposals.get(request.proposal_id)
        if record is None:
            raise APIError(404, "UNKNOWN_PROPOSAL", "Proposal does not exist. Preview again.", self.current.revision)
        if record.lifecycle in ("consumed", "rejected"):
            code = "PROPOSAL_CONSUMED" if record.lifecycle == "consumed" else "PROPOSAL_REJECTED"
            raise APIError(409, code, "This proposal is no longer pending.", self.current.revision)
        self._check_base(request)
        proposal = record.proposal
        if record.lifecycle == "stale" or (proposal.scenario_id, proposal.scenario_epoch, proposal.base_revision) != (
                request.scenario_id, request.scenario_epoch, request.base_revision):
            raise APIError(409, "STALE_PROPOSAL", "The proposal is based on another schedule revision.", self.current.revision)
        if self.clock() >= record.expires:
            raise APIError(410, "PROPOSAL_EXPIRED", "Proposal expired. Preview again.", self.current.revision)
        return record

    def commit(self, request: ProposalRequest) -> Snapshot:
        with self.lock:
            record = self._get_proposal(request)
            proposal = record.proposal
            if proposal.status != "ready" or proposal.proposed_snapshot is None:
                raise APIError(422, "INVALID_INPUT", "Only a validated ready proposal can be approved.", self.current.revision)
            updated = proposal.proposed_snapshot.model_copy(deep=True)
            validation = validate_schedule(updated, self.current)
            if not validation.valid:
                raise APIError(422, "INVALID_INPUT", "Proposal failed independent revalidation.", self.current.revision)
            updated.validation = validation
            updated.metrics = schedule_metrics(updated)
            updated.revision = self.current.revision + 1
            self._persist(updated)  # never acknowledge a partial or undurable commit
            self.current = updated
            for sibling in self.proposals.values():
                if sibling.lifecycle == "pending":
                    sibling.lifecycle = "stale"
            record.lifecycle = "consumed"
            return self.current.model_copy(deep=True)

    def reject(self, request: ProposalRequest) -> dict:
        with self.lock:
            record = self._get_proposal(request)
            record.lifecycle = "rejected"
            return {"proposal_id": request.proposal_id, "status": "rejected", "revision": self.current.revision}

    def reset(self, request: BaseRequest) -> Snapshot:
        with self.lock:
            self._check_base(request)
            updated = make_scenario(revision=self.current.revision + 1)
            self._persist(updated)
            self.current = updated
            for record in self.proposals.values():
                if record.lifecycle == "pending":
                    record.lifecycle = "stale"
            return self.current.model_copy(deep=True)

    def _persist(self, snapshot: Snapshot):
        if self.path is None:
            return
        temp_path = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix="operations-", suffix=".tmp", dir=self.path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(snapshot.model_dump_json(indent=2))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
        except OSError as exc:
            raise APIError(503, "STATE_WRITE_FAILED", "State could not be saved. The previous schedule is retained.",
                           snapshot.revision - 1 if snapshot.revision else 0) from exc
        finally:
            if temp_path is not None:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    pass
