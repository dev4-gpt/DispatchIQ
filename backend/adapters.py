"""Share the legacy travel estimator, without changing benchmark semantics."""

from decimal import Decimal, ROUND_CEILING
from math import ceil, isfinite

from dispatchiq.model import travel

from .schemas import Assignment, Location, Snapshot, Technician


def travel_minutes(a: Location, b: Location) -> int:
    estimate = travel((a.x_km, a.y_km), (b.x_km, b.y_km))
    if isfinite(estimate):
        return ceil(estimate)
    # Finite but enormous inputs must produce an infeasible route, not an overflow crash.
    distance = abs(Decimal(str(a.x_km)) - Decimal(str(b.x_km))) + abs(Decimal(str(a.y_km)) - Decimal(str(b.y_km)))
    return int((distance * 2).to_integral_value(rounding=ROUND_CEILING))


def route_assignments(snapshot: Snapshot, technician_id: str) -> list[Assignment]:
    return sorted((a for a in snapshot.schedule.assignments if a.technician_id == technician_id),
                  key=lambda a: a.sequence)


def frozen_assignment(a: Assignment, now_min: int) -> bool:
    return a.start_min <= now_min


def free_context(snapshot: Snapshot, tech: Technician) -> tuple[int, Location]:
    jobs = {j.id: j for j in snapshot.jobs}
    prefix = [a for a in route_assignments(snapshot, tech.id) if frozen_assignment(a, snapshot.now_min)]
    if prefix:
        last = prefix[-1]
        return max(snapshot.now_min, last.end_min, tech.shift_start_min), jobs[last.job_id].location
    return max(snapshot.now_min, tech.shift_start_min), tech.location


def refresh_derived(snapshot: Snapshot) -> None:
    """Status and assigned ID lists are derived from explicit intervals, never optimizer flags."""
    assignments = {a.job_id: a for a in snapshot.schedule.assignments}
    for job in snapshot.jobs:
        a = assignments.get(job.id)
        if job.status == "cancelled":
            continue
        job.status = ("unassigned" if a is None else "completed" if a.end_min <= snapshot.now_min
                      else "in_progress" if a.start_min <= snapshot.now_min else "scheduled")
    for tech in snapshot.technicians:
        tech.assigned_job_ids = [a.job_id for a in route_assignments(snapshot, tech.id)]
