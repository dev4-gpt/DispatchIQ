"""Acceptance tests for hard constraints, measured tradeoffs and approval lifecycle."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event as ThreadEvent

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.adapters import refresh_derived, travel_minutes
from backend.app import create_app
from backend.metrics import diff_metrics, schedule_metrics
from backend.optimizer import optimize
from backend.scenario import demo_emergency, make_scenario
from backend.schemas import (Assignment, BaseRequest, Customer, EmergencyEvent, Job, JobInput, Location,
                             OptimizeRequest, PreviewRequest, ProposalRequest, Schedule, Snapshot, Technician,
                             UnavailableEvent)
from backend.store import APIError, StateStore
from backend.validator import validate_schedule


def base(snapshot):
    return {"scenario_id": snapshot.scenario_id, "scenario_epoch": snapshot.scenario_epoch,
            "base_revision": snapshot.revision}


def request(snapshot, event=None, strategy="stable_insertion"):
    return PreviewRequest(**base(snapshot), event=event or demo_emergency(), strategy=strategy)


def approval(proposal):
    return ProposalRequest(scenario_id=proposal.scenario_id, scenario_epoch=proposal.scenario_epoch,
                           base_revision=proposal.base_revision, proposal_id=proposal.proposal_id)


def tiny():
    s = Snapshot(scenario_id="tiny", scenario_epoch="11111111-1111-4111-8111-111111111111", revision=0, now_min=690,
                 technicians=[Technician(id="A", name="Mike", skills=["hvac"], location=Location(x_km=0, y_km=0),
                                         shift_start_min=480, shift_end_min=1020, max_service_min=480)],
                 jobs=[Job(id="J1", customer=Customer(id="C1", name="Taylor", site_name="Residence"),
                           location=Location(x_km=1, y_km=1), required_skills=["hvac"], priority=1, duration_min=30,
                           earliest_start_min=700, latest_start_min=760, window_end_min=800, status="scheduled")],
                 schedule=Schedule(assignments=[Assignment(job_id="J1", technician_id="A", sequence=0,
                                   start_min=700, end_min=730, travel_min=4, frozen=False)]))
    refresh_derived(s)
    s.validation = validate_schedule(s)
    assert s.validation.valid
    s.metrics = schedule_metrics(s)
    return s


def codes(snapshot, original=None):
    return {v.code for v in validate_schedule(snapshot, original).violations}


def test_baseline_accounts_for_25_jobs_with_started_boundary_and_multiple_skills():
    s = make_scenario()
    assert len(s.technicians) == 10 and len(s.jobs) == len(s.schedule.assignments) == 25
    assert s.validation.valid and not s.schedule.unassigned_job_ids
    assert any(j.status == "completed" for j in s.jobs)
    assert any(j.status == "in_progress" for j in s.jobs)
    assert any(len(j.required_skills) > 1 for j in s.jobs)
    assert any(a.start_min == s.now_min and a.frozen for a in s.schedule.assignments)
    assert s.metrics.hard_constraint_violations == 0 and s.metrics.travel_min == 60


def test_hand_computed_travel_waiting_and_emergency_deadline():
    assert travel_minutes(Location(x_km=0, y_km=0), Location(x_km=1.1, y_km=1)) == 5
    s = tiny()
    event = demo_emergency().model_copy(deep=True)
    event.job.location = Location(x_km=2, y_km=1)
    event.job.duration_min = 15
    event.job.deadline_start_min = 720
    result = optimize(s, event)
    assert result.snapshot is not None and result.validation.valid
    a = {a.job_id: a for a in result.snapshot.schedule.assignments}
    assert (a["E01"].start_min, a["E01"].end_min, a["E01"].travel_min) == (696, 711, 6)
    assert (a["J1"].start_min, a["J1"].end_min, a["J1"].travel_min) == (713, 743, 2)
    assert result.snapshot.metrics.travel_min == 8
    assert result.snapshot.metrics.emergencies[0].response_min == 6
    assert diff_metrics(s, result.snapshot).absolute_start_shift_min == 13
    late = result.snapshot.model_copy(deep=True)
    late.jobs[-1].deadline_start_min = 695
    assert "EMERGENCY_DEADLINE" in codes(late)


@pytest.mark.parametrize("mutation,expected", [
    ("skills", "SKILL_MISMATCH"), ("shift", "SHIFT_HOURS"), ("capacity", "CAPACITY"),
    ("travel", "TRAVEL_INFEASIBLE"), ("overlap", "OVERLAP"), ("window", "CUSTOMER_WINDOW"),
    ("duplicate_assignment", "DUPLICATE_ASSIGNMENT"), ("duplicate_job", "DUPLICATE_ID"),
    ("unknown_job", "UNKNOWN_JOB"), ("unknown_tech", "UNKNOWN_TECHNICIAN"),
    ("accounting", "JOB_ACCOUNTING"), ("status", "INVALID_STATUS"),
    ("frozen_flag", "INVALID_FROZEN_FLAG"), ("unavailable", "TECHNICIAN_UNAVAILABLE"),
    ("duration", "INVALID_DURATION"), ("release", "EARLIEST_START"),
])
def test_independent_validator_rejects_invalid_intervals_and_constraints(mutation, expected):
    s = make_scenario().model_dump()
    a = s["schedule"]["assignments"][2]
    if mutation == "skills":
        s["jobs"][2]["required_skills"] = ["plumbing", "hvac"]
    elif mutation == "shift":
        s["technicians"][0]["shift_end_min"] = 760
    elif mutation == "capacity":
        s["technicians"][0]["max_service_min"] = 1
    elif mutation == "travel":
        a["travel_min"] = 0
    elif mutation == "overlap":
        a["start_min"], a["end_min"] = 700, 760
    elif mutation == "window":
        a["start_min"], a["end_min"] = 900, 960
    elif mutation == "duplicate_assignment":
        s["schedule"]["assignments"].append(dict(a))
    elif mutation == "duplicate_job":
        s["jobs"].append(dict(s["jobs"][0]))
    elif mutation == "unknown_job":
        a["job_id"] = "unknown"
    elif mutation == "unknown_tech":
        a["technician_id"] = "unknown"
    elif mutation == "accounting":
        s["schedule"]["assignments"].pop()
    elif mutation == "status":
        s["jobs"][2]["status"] = "completed"
    elif mutation == "frozen_flag":
        a["frozen"] = True
    elif mutation == "unavailable":
        s["technicians"][0]["availability"] = "unavailable"
    elif mutation == "duration":
        a["end_min"] += 1
    elif mutation == "release":
        s["jobs"][2]["release_min"] = 751
    assert expected in codes(s)


def test_started_at_now_and_locked_future_intervals_are_immutable():
    original = make_scenario()
    for selected in (next(a for a in original.schedule.assignments if a.start_min == 690),
                     next(a for a in original.schedule.assignments if next(j for j in original.jobs if j.id == a.job_id).locked)):
        candidate = original.model_copy(deep=True)
        a = next(a for a in candidate.schedule.assignments if a.job_id == selected.job_id)
        a.start_min += 1
        a.end_min += 1
        refresh_derived(candidate)
        assert "PROTECTED_WORK" in codes(candidate, original)


def test_removed_started_work_and_weakened_requirements_are_rejected():
    original = make_scenario()
    candidate = original.model_copy(deep=True)
    first = candidate.schedule.assignments.pop(0)
    candidate.schedule.unassigned_job_ids.append(first.job_id)
    refresh_derived(candidate)
    assert "PROTECTED_WORK" in codes(candidate, original)
    candidate = original.model_copy(deep=True)
    candidate.jobs[2].latest_start_min += 1
    assert "JOB_MUTATION" in codes(candidate, original)
    candidate = original.model_copy(deep=True)
    candidate.technicians[0].max_service_min += 1
    assert "STATE_MUTATION" in codes(candidate, original)


@pytest.mark.parametrize("value", [[], {}, None, 123, True])
def test_malformed_job_identifiers_return_invalid_schema(value):
    s = make_scenario().model_dump()
    s["schedule"]["assignments"][0]["job_id"] = value
    assert "INVALID_SCHEMA" in codes(s)


def test_preview_grounded_comparison_and_reject_leave_committed_state_unchanged():
    store = StateStore()
    before = store.snapshot()
    proposal = store.preview(request(before))
    assert proposal.status == "ready" and proposal.validation.valid
    assert store.snapshot() == before
    by_strategy = {c.strategy: c for c in proposal.comparison}
    stable, first = by_strategy["stable_insertion"], by_strategy["first_feasible"]
    assert stable.diff_metrics.changed_existing_jobs == first.diff_metrics.changed_existing_jobs == 1
    assert stable.diff_metrics.absolute_start_shift_min == 17
    assert first.diff_metrics.absolute_start_shift_min == 38
    assert stable.metrics.emergencies[0].response_min == 28
    assert first.metrics.emergencies[0].response_min == 4
    assert all(c.runtime_ms > 0 and c.validation.valid for c in proposal.comparison)
    selected = next(c for c in proposal.candidates if c.id == proposal.selected_candidate_id)
    assert selected.valid and selected.ranking.absolute_start_shift_min == 17
    assert {c.job_id for c in proposal.changes} == {"E01", "J03"}
    assert all(c.evidence_candidate_id == selected.id for c in proposal.changes)
    store.reject(approval(proposal))
    assert store.snapshot() == before
    with pytest.raises(APIError) as rejected:
        store.commit(approval(proposal))
    assert rejected.value.code == "PROPOSAL_REJECTED"


def test_preview_output_and_get_snapshot_cannot_mutate_store():
    store = StateStore()
    s = store.snapshot()
    p = store.preview(request(s))
    p.proposed_snapshot.schedule.assignments.clear()
    s.schedule.assignments.clear()
    committed = store.commit(approval(p))
    assert len(committed.schedule.assignments) == 26 and committed.validation.valid


def test_commit_revalidate_consumed_sibling_stale_and_repeated_events():
    store = StateStore()
    before = store.snapshot()
    first, sibling = store.preview(request(before)), store.preview(request(before))
    committed = store.commit(approval(first))
    assert committed.revision == 1 and len(committed.jobs) == 26 and len(committed.events) == 1
    assert validate_schedule(committed, before).valid
    with pytest.raises(APIError) as consumed:
        store.commit(approval(first))
    assert consumed.value.code == "PROPOSAL_CONSUMED"
    with pytest.raises(APIError) as stale:
        store.commit(approval(sibling))
    assert stale.value.status == 409
    second = store.preview(request(committed, demo_emergency(job_id="E02")))
    assert second.status == "ready"
    again = store.commit(approval(second))
    assert again.revision == 2 and len(again.jobs) == 27 and len(again.events) == 2
    assert {j.id for j in committed.jobs} <= {j.id for j in again.jobs}


def test_commit_revalidates_internal_snapshot_tampering():
    store = StateStore()
    before = store.snapshot()
    p = store.preview(request(before))
    a = store.proposals[p.proposal_id].proposal.proposed_snapshot.schedule.assignments[0]
    a.end_min += 1
    with pytest.raises(APIError) as invalid:
        store.commit(approval(p))
    assert invalid.value.status == 422 and store.snapshot() == before


def test_expiry_and_reset_invalidate_proposals_and_replay_deterministically():
    clock = [datetime(2026, 10, 11, tzinfo=timezone.utc)]
    store = StateStore(clock=lambda: clock[0], proposal_ttl_seconds=60)
    before = store.snapshot()
    expired = store.preview(request(before))
    clock[0] += timedelta(seconds=60)
    with pytest.raises(APIError) as error:
        store.commit(approval(expired))
    assert error.value.code == "PROPOSAL_EXPIRED" and store.snapshot() == before
    pending = store.preview(request(before))
    reset = store.reset(BaseRequest(**base(before)))
    assert reset.revision == 1 and reset.scenario_epoch != before.scenario_epoch
    assert reset.schedule == before.schedule and reset.metrics == before.metrics
    with pytest.raises(APIError) as stale:
        store.commit(approval(pending))
    assert stale.value.code == "SCENARIO_CHANGED"
    replay = store.preview(request(reset))
    assert replay.proposed_snapshot.schedule == pending.proposed_snapshot.schedule
    assert replay.proposed_snapshot.metrics == pending.proposed_snapshot.metrics


@pytest.mark.parametrize("impossible_kind", ["deadline", "skills", "shift", "travel", "budget"])
def test_impossible_event_or_search_exhaustion_never_appears_successful(impossible_kind):
    store = StateStore(search_budget_seconds=0 if impossible_kind == "budget" else 2)
    before = store.snapshot()
    event = demo_emergency(impossible=impossible_kind == "deadline")
    if impossible_kind == "skills":
        event.job.required_skills = ["nuclear"]
    elif impossible_kind == "travel":
        event.job.location = Location(x_km=1000, y_km=1000)
    elif impossible_kind == "shift":
        event.job.duration_min = 700
    p = store.preview(request(before, event))
    assert p.status == "no_feasible_plan" and p.proposed_snapshot is None and not p.validation.valid
    assert store.snapshot() == before
    if impossible_kind == "budget":
        assert p.search.termination == "budget_exhausted" and not p.search.feasibility_proven_impossible
    with pytest.raises(APIError):
        store.commit(approval(p))
    assert store.snapshot() == before


def test_unavailability_reassigns_future_jobs_and_preserves_frozen_work():
    store = StateStore()
    before = store.snapshot()
    event = UnavailableEvent(at_min=690, technician_id="T00")
    p = store.preview(request(before, event))
    assert p.status == "ready" and p.validation.valid
    assert store.snapshot() == before
    after = store.commit(approval(p))
    assert next(t for t in after.technicians if t.id == "T00").availability == "unavailable"
    assert not any(a.technician_id == "T00" and a.start_min > 690 for a in after.schedule.assignments)
    assert validate_schedule(after, before).valid
    assert diff_metrics(before, after).forced_reassignments == 1
    assert all(c.forced for c in p.changes if c.kind == "reassigned")


def test_atomic_write_failure_retains_disk_state_memory_state_and_pending_proposal(tmp_path, monkeypatch):
    path = tmp_path / "operations.json"
    store = StateStore(path)
    before, disk = store.snapshot(), path.read_bytes()
    proposal = store.preview(request(before))
    with monkeypatch.context() as patch:
        patch.setattr("backend.store.os.replace", lambda *a: (_ for _ in ()).throw(PermissionError("simulated failure")))
        with pytest.raises(APIError) as failure:
            store.commit(approval(proposal))
        assert failure.value.code == "STATE_WRITE_FAILED"
        assert store.snapshot() == before and path.read_bytes() == disk
        assert not list(tmp_path.glob("*.tmp"))
        with pytest.raises(APIError):
            store.reset(BaseRequest(**base(before)))
        assert store.snapshot() == before
    committed = store.commit(approval(proposal))
    restored = StateStore(path).snapshot()
    assert restored == committed and restored.revision == 1


def test_corrupt_or_invalid_persisted_state_fails_closed(tmp_path):
    path = tmp_path / "operations.json"
    path.write_text('{"not":"a snapshot"}', encoding="utf-8")
    with pytest.raises(ValidationError):
        StateStore(path)
    bad = make_scenario()
    bad.schedule.assignments[0].end_min += 1
    path.write_text(bad.model_dump_json(), encoding="utf-8")
    with pytest.raises(RuntimeError):
        StateStore(path)


def test_concurrent_approvals_allow_exactly_one_commit():
    store = StateStore()
    before = store.snapshot()
    proposals = [store.preview(request(before)) for _ in range(2)]
    gate = Barrier(2)

    def approve(p):
        gate.wait(timeout=5)
        try:
            return store.commit(approval(p)).revision
        except APIError as e:
            return e.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, proposals))
    assert sorted(results) == [1, 409]
    assert store.snapshot().revision == 1 and len(store.snapshot().events) == 1


def test_preview_racing_reset_cannot_register_ready_stale_proposal(monkeypatch):
    import backend.store as module

    store = StateStore()
    before = store.snapshot()
    started, release = ThreadEvent(), ThreadEvent()
    real = module.optimize

    def delayed(*args, **kwargs):
        started.set()
        assert release.wait(timeout=5)
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "optimize", delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(store.preview, request(before))
        assert started.wait(timeout=5)
        store.reset(BaseRequest(**base(before)))
        release.set()
        with pytest.raises(APIError) as stale:
            task.result(timeout=5)
    assert stale.value.code == "SCENARIO_CHANGED" and not store.proposals


def test_optimizer_failure_preserves_committed_state(monkeypatch):
    store = StateStore()
    before = store.snapshot()
    monkeypatch.setattr("backend.store.optimize", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("internal")))
    with pytest.raises(APIError) as failure:
        store.preview(request(before))
    assert failure.value.code == "OPTIMIZER_FAILED" and store.snapshot() == before


def test_all_api_endpoints_preview_commit_reject_reset_and_openapi():
    store = StateStore()
    with TestClient(create_app(store)) as client:
        assert client.get("/api/health").json()["state_ready"]
        assert client.get("/openapi.json").status_code == 200
        snapshot = client.get("/api/scenario").json()
        s = Snapshot.model_validate(snapshot)
        for endpoint, key in (("technicians", "technicians"), ("jobs", "jobs"), ("schedule", "schedule"), ("metrics", "metrics")):
            response = client.get(f"/api/{endpoint}").json()
            assert response["revision"] == 0 and response[key] == snapshot[key]
        p = client.post("/api/events/preview", json=request(s).model_dump(mode="json")).json()
        assert p["status"] == "ready" and client.get("/api/scenario").json() == snapshot
        approve = {**base(s), "proposal_id": p["proposal_id"]}
        committed = client.post("/api/events/commit", json=approve)
        assert committed.status_code == 200 and committed.json()["revision"] == 1
        assert client.post("/api/events/commit", json=approve).status_code == 409
        current = Snapshot.model_validate(committed.json())
        optimized = client.post("/api/optimize", json=OptimizeRequest(**base(current)).model_dump()).json()
        assert optimized["status"] == "ready"
        assert client.post("/api/events/reject", json={**base(current), "proposal_id": optimized["proposal_id"]}).status_code == 200
        assert client.post("/api/reset", json=base(current)).json()["revision"] == 2


@pytest.mark.parametrize("invalid", ["duration_string", "bool_priority", "float_minute", "nan", "skill_case", "duplicate_skills", "code", "duplicate_id", "wrong_time", "coordinates"])
def test_api_strict_input_rejection_and_no_state_mutation(invalid):
    store = StateStore()
    before = store.snapshot()
    body = request(before).model_dump(mode="json")
    if invalid == "duration_string":
        body["event"]["job"]["duration_min"] = "45"
    elif invalid == "bool_priority":
        body["event"]["job"]["priority"] = True
    elif invalid == "float_minute":
        body["event"]["at_min"] = 690.0
    elif invalid == "nan":
        body["event"]["job"]["location"]["x_km"] = "NaN"
    elif invalid == "skill_case":
        body["event"]["job"]["required_skills"] = ["HVAC"]
    elif invalid == "duplicate_skills":
        body["event"]["job"]["required_skills"] = ["hvac", "hvac"]
    elif invalid == "code":
        body["policy_code"] = "print('must never execute')"
    elif invalid == "duplicate_id":
        body["event"]["job"]["id"] = "J01"
    elif invalid == "wrong_time":
        body["event"]["at_min"] = body["event"]["job"]["release_min"] = 691
    elif invalid == "coordinates":
        body["event"]["job"]["location"]["latitude"] = 40.7
    with TestClient(create_app(store)) as client:
        response = client.post("/api/events/preview", json=body)
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_INPUT"
    assert store.snapshot() == before


def test_api_malformed_json_unknown_event_tech_proposal_and_domain_no_plan():
    store = StateStore()
    before = store.snapshot()
    with TestClient(create_app(store)) as client:
        invalid = client.post("/api/events/preview", content="{", headers={"Content-Type": "application/json"})
        assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "INVALID_INPUT"
        body = {**base(before), "event": {"type": "technician_unavailable", "at_min": 690, "technician_id": "missing"}}
        assert client.post("/api/events/preview", json=body).status_code == 404
        body["event"]["type"] = "delete_all"
        assert client.post("/api/events/preview", json=body).status_code == 422
        assert client.post("/api/events/commit", json={**base(before), "proposal_id": "missing"}).status_code == 404
        impossible = client.post("/api/events/preview", json=request(before, demo_emergency(impossible=True)).model_dump(mode="json"))
        assert impossible.status_code == 200 and impossible.json()["status"] == "no_feasible_plan"
    assert store.snapshot() == before
