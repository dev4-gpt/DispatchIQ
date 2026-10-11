"""Bounded feasible insertion. Candidates propose; an independent validator decides."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .adapters import free_context, refresh_derived, route_assignments, travel_minutes
from .metrics import diff_metrics, schedule_metrics
from .schemas import (Assignment, Candidate, EmergencyEvent, Event, Job, Ranking, Schedule,
                      Search, Snapshot, Strategy, UnavailableEvent, Validation, Violation)
from .validator import validate_schedule


@dataclass
class Result:
    snapshot: Snapshot | None
    validation: Validation
    candidates: list[Candidate]
    selected_candidate_id: str | None
    runtime_ms: float
    search: Search
    explanation: str


def _rank(original: Snapshot, candidate: Snapshot) -> Ranking:
    diff = diff_metrics(original, candidate)
    return Ranking(unassigned_existing=len(set(candidate.schedule.unassigned_job_ids) & {j.id for j in original.jobs}),
                   voluntary_reassignments=diff.voluntary_reassignments, changed_existing_jobs=diff.changed_existing_jobs,
                   absolute_start_shift_min=diff.absolute_start_shift_min,
                   emergency_response_min=sum(e.response_min or 0 for e in candidate.metrics.emergencies),
                   added_travel_min=candidate.metrics.travel_min - original.metrics.travel_min,
                   overtime_min=candidate.metrics.overtime_min)


def _rebuild(snapshot: Snapshot, plan: dict[str, list[str]]) -> Snapshot | None:
    """Propagate route times while keeping started/locked work and existing flexible starts."""
    candidate = snapshot.model_copy(deep=True)
    jobs = {j.id: j for j in candidate.jobs}
    old = {a.job_id: a for a in snapshot.schedule.assignments}
    assignments = []
    for tech in candidate.technicians:
        previous_end, loc = tech.shift_start_min, tech.location
        for sequence, jid in enumerate(plan[tech.id]):
            job, existing = jobs[jid], old.get(jid)
            d = travel_minutes(loc, job.location)
            protected = existing is not None and (existing.start_min <= snapshot.now_min or job.locked)
            if protected:
                start, end = existing.start_min, existing.end_min
            else:
                start = max(previous_end, snapshot.now_min, tech.shift_start_min) + d
                start = max(start, job.earliest_start_min, job.release_min,
                            existing.start_min if existing is not None else 0)
                end = start + job.duration_min
            if start > 1440 or end > 1440:
                return None
            assignments.append(Assignment(job_id=jid, technician_id=tech.id, sequence=sequence,
                                          start_min=start, end_min=end, travel_min=d, frozen=start <= snapshot.now_min))
            previous_end, loc = end, job.location
    assigned = {a.job_id for a in assignments}
    candidate.schedule = Schedule(assignments=assignments,
                                  unassigned_job_ids=[j.id for j in candidate.jobs if j.id not in assigned and j.status != "cancelled"])
    refresh_derived(candidate)
    return candidate


def optimize(original: Snapshot, event: Event | None, strategy: Strategy = "stable_insertion", *, budget_seconds: float = 2.0) -> Result:
    t0 = perf_counter()
    base = original.model_copy(deep=True)
    candidates: list[Candidate] = []
    selected_id = None
    proven = False
    exhausted = False
    evaluated = 0
    if event is not None:
        base.events.append(event.model_copy(deep=True))
    if isinstance(event, EmergencyEvent):
        base.jobs.append(Job(**event.job.model_dump(), status="unassigned"))
        todo = [event.job.id]
    elif isinstance(event, UnavailableEvent):
        tech = next(t for t in base.technicians if t.id == event.technician_id)
        tech.availability = "unavailable"
        affected = [a for a in base.schedule.assignments if a.technician_id == tech.id and a.start_min > base.now_min]
        todo = [a.job_id for a in affected]
        base.schedule.assignments = [a for a in base.schedule.assignments if a not in affected]
        base.schedule.unassigned_job_ids.extend(todo)
        refresh_derived(base)
    else:
        todo = list(base.schedule.unassigned_job_ids)

    for jid in todo:
        job = next(j for j in base.jobs if j.id == jid)
        plan = {t.id: [a.job_id for a in route_assignments(base, t.id)] for t in base.technicians}
        best_snapshot, best_rank, best_id = None, None, None
        qualified = [t for t in base.technicians if t.availability == "available" and set(job.required_skills).issubset(t.skills)]
        # First-feasible orders technicians by earliest possible arrival, then visiting position.
        ordered = sorted(base.technicians, key=lambda t: (free_context(base, t)[0] + travel_minutes(free_context(base, t)[1], job.location), t.id))
        proven = not qualified
        if job.deadline_start_min is not None and qualified:
            proven = all(free_context(base, t)[0] + travel_minutes(free_context(base, t)[1], job.location) > job.deadline_start_min
                         for t in qualified)
        for tech in ordered:
            reasons = ([] if tech.availability == "available" else ["TECHNICIAN_UNAVAILABLE"])
            if not set(job.required_skills).issubset(tech.skills):
                reasons.append("SKILL_MISMATCH")
            if reasons:
                candidates.append(Candidate(id=f"CAND-{jid}-{tech.id}-excluded", technician_id=tech.id,
                                            insertion_position=0, eligible=False, valid=False, reasons=reasons))
                continue
            frozen_count = sum(a.start_min <= base.now_min for a in route_assignments(base, tech.id))
            for pos in range(frozen_count, len(plan[tech.id]) + 1):
                if perf_counter() - t0 >= budget_seconds:
                    exhausted = True
                    break
                cid = f"CAND-{jid}-{tech.id}-{pos}"
                alt = {tid: list(seq) for tid, seq in plan.items()}
                alt[tech.id].insert(pos, jid)
                proposed = _rebuild(base, alt)
                evaluated += 1
                # Partial sickness reassignment may leave other routine orphans unassigned.
                validation = validate_schedule(proposed, original if not isinstance(event, UnavailableEvent) else None) if proposed is not None else Validation(
                    valid=False, violations=[Violation(code="DAY_OVERFLOW", message="Route exceeds the scenario day.")])
                ranking = None
                emergency_start = None
                if proposed is not None and validation.valid:
                    proposed.validation = validation
                    proposed.metrics = schedule_metrics(proposed)
                    ranking = _rank(original, proposed)
                    if job.emergency:
                        emergency_start = next(a.start_min for a in proposed.schedule.assignments if a.job_id == jid)
                    if best_rank is None or ranking.key() < best_rank.key():
                        best_snapshot, best_rank, best_id = proposed, ranking, cid
                candidates.append(Candidate(id=cid, technician_id=tech.id, insertion_position=pos,
                                            eligible=True, valid=validation.valid, ranking=ranking,
                                            emergency_start_min=emergency_start,
                                            reasons=sorted({v.code for v in validation.violations})))
                if strategy == "first_feasible" and best_snapshot is not None:
                    break
            if exhausted or strategy == "first_feasible" and best_snapshot is not None:
                break
        if best_snapshot is None:
            if event is None and not job.emergency:
                # Existing explicit backlog may remain unassigned; it is never silently hidden.
                continue
            return Result(None, Validation(valid=False, violations=[Violation(code="NO_FEASIBLE_INSERTION",
                          job_id=jid, message="No feasible insertion found under this bounded search.")]),
                          candidates, None, (perf_counter() - t0) * 1000,
                          Search(termination="budget_exhausted" if exhausted else "completed",
                                 candidates_evaluated=evaluated, feasibility_proven_impossible=proven),
                          f"No feasible plan found for {jid}. The committed schedule is unchanged.")
        base, selected_id = best_snapshot, best_id
        if exhausted:
            # A valid incumbent is sufficient for one emergency; further tasks still require a solution.
            if jid != todo[-1]:
                return Result(None, Validation(valid=False, violations=[Violation(code="SEARCH_BUDGET", message="Reassignment budget exhausted.")]),
                              candidates, None, (perf_counter() - t0) * 1000,
                              Search(termination="budget_exhausted", candidates_evaluated=evaluated),
                              "No complete feasible plan found within the search budget.")
            break

    refresh_derived(base)
    validation = validate_schedule(base, original)
    if validation.valid:
        base.validation = validation
        base.metrics = schedule_metrics(base)
    diff = diff_metrics(original, base)
    text = (f"Independent validation passed. {diff.changed_existing_jobs} existing job(s) change; "
            f"total absolute start displacement is {diff.absolute_start_shift_min} minutes. "
            f"{evaluated} insertion candidate(s) evaluated using {strategy}. "
            "Completed, in-progress and locked work is preserved. Dispatcher approval is required."
            if validation.valid else "No independently valid complete schedule was found.")
    return Result(base if validation.valid else None, validation, candidates, selected_id,
                  (perf_counter() - t0) * 1000,
                  Search(termination="budget_exhausted" if exhausted else "completed", candidates_evaluated=evaluated), text)
