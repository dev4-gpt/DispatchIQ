"""Independent checks of explicit full schedules, including protected original work."""

from __future__ import annotations

from pydantic import ValidationError

from .adapters import travel_minutes
from .schemas import EmergencyEvent, Snapshot, UnavailableEvent, Validation, Violation


def validate_schedule(snapshot: Snapshot | dict, original: Snapshot | None = None) -> Validation:
    violations: list[Violation] = []

    def fail(code, message, job_id=None, technician_id=None):
        violations.append(Violation(code=code, message=message, job_id=job_id, technician_id=technician_id))

    try:
        # Reparse even a Model: internal model_copy/update must not bypass strict field checks.
        snapshot = Snapshot.model_validate(snapshot.model_dump() if isinstance(snapshot, Snapshot) else snapshot)
    except (ValidationError, TypeError, ValueError):
        return Validation(valid=False, violations=[Violation(code="INVALID_SCHEMA", message="Invalid snapshot schema.")])

    jobs = {j.id: j for j in snapshot.jobs}
    techs = {t.id: t for t in snapshot.technicians}
    if len(jobs) != len(snapshot.jobs) or len(techs) != len(snapshot.technicians):
        fail("DUPLICATE_ID", "Job and technician IDs must be unique.")
    seen = set()
    for a in snapshot.schedule.assignments:
        if a.job_id in seen:
            fail("DUPLICATE_ASSIGNMENT", "A job is assigned more than once.", a.job_id)
        seen.add(a.job_id)
        if a.job_id not in jobs:
            fail("UNKNOWN_JOB", "Assignment references an unknown job.", a.job_id)
        if a.technician_id not in techs:
            fail("UNKNOWN_TECHNICIAN", "Assignment references an unknown technician.", a.job_id, a.technician_id)
    unassigned = snapshot.schedule.unassigned_job_ids
    if len(set(unassigned)) != len(unassigned) or seen.intersection(unassigned):
        fail("JOB_ACCOUNTING", "Assigned and unassigned jobs must be distinct and unique.")
    active = {j.id for j in snapshot.jobs if j.status != "cancelled"}
    if (seen | set(unassigned)) != active:
        fail("JOB_ACCOUNTING", "Every noncancelled job must be assigned or explicitly unassigned.")
    for jid in unassigned:
        if jid in jobs and jobs[jid].status != "unassigned":
            fail("INVALID_STATUS", "Unassigned job status is inconsistent.", jid)
    for job in snapshot.jobs:
        if job.emergency and job.status != "cancelled" and job.id not in seen:
            fail("EMERGENCY_UNASSIGNED", "Every emergency must be assigned.", job.id)

    for tid, tech in techs.items():
        route = sorted((a for a in snapshot.schedule.assignments if a.technician_id == tid), key=lambda a: a.sequence)
        if [a.sequence for a in route] != list(range(len(route))):
            fail("INVALID_SEQUENCE", "Route sequence must be contiguous from zero.", technician_id=tid)
        if tech.assigned_job_ids != [a.job_id for a in route]:
            fail("ASSIGNED_IDS", "Technician assigned IDs do not match route order.", technician_id=tid)
        previous_end, previous_location = tech.shift_start_min, tech.location
        service = 0
        for a in route:
            job = jobs.get(a.job_id)
            if job is None:
                continue
            service += job.duration_min
            if not set(job.required_skills).issubset(tech.skills):
                fail("SKILL_MISMATCH", "Technician lacks required certifications.", job.id, tid)
            expected_frozen = a.start_min <= snapshot.now_min
            if a.frozen != expected_frozen:
                fail("INVALID_FROZEN_FLAG", "Frozen flag must reflect already-started work.", job.id, tid)
            expected_status = ("completed" if a.end_min <= snapshot.now_min else
                               "in_progress" if expected_frozen else "scheduled")
            if job.status != expected_status:
                fail("INVALID_STATUS", "Job status does not match its interval.", job.id, tid)
            if tech.availability == "unavailable" and not expected_frozen:
                fail("TECHNICIAN_UNAVAILABLE", "Unavailable technician has future work.", job.id, tid)
            if a.end_min != a.start_min + job.duration_min:
                fail("INVALID_DURATION", "End must equal start plus service duration.", job.id, tid)
            if a.start_min < job.earliest_start_min or a.start_min < job.release_min:
                fail("EARLIEST_START", "Job starts before its availability or release.", job.id, tid)
            if a.start_min > job.latest_start_min or a.end_min > job.window_end_min:
                fail("CUSTOMER_WINDOW", "Job exceeds a hard customer window.", job.id, tid)
            if job.deadline_start_min is not None and a.start_min > job.deadline_start_min:
                fail("EMERGENCY_DEADLINE", "Job starts after its response deadline.", job.id, tid)
            if a.start_min < tech.shift_start_min or a.end_min > tech.shift_end_min + tech.max_overtime_min:
                fail("SHIFT_HOURS", "Assignment is outside authorized working hours.", job.id, tid)
            if a.start_min < previous_end:
                fail("OVERLAP", "Assignment overlaps the preceding job.", job.id, tid)
            expected_travel = travel_minutes(previous_location, job.location)
            # Emergency travel cannot start before the call is released. With an original
            # snapshot, formerly future work cannot claim a historical travel departure.
            was_future = original is not None and not any(
                old.job_id == a.job_id and old.start_min <= original.now_min for old in original.schedule.assignments)
            depart = max(previous_end, job.release_min,
                         snapshot.now_min if not expected_frozen or was_future else 0)
            if a.travel_min != expected_travel or a.start_min < depart + expected_travel:
                fail("TRAVEL_INFEASIBLE", "Incoming travel or arrival is inconsistent.", job.id, tid)
            previous_end, previous_location = a.end_min, job.location
        if service > tech.max_service_min:
            fail("CAPACITY", "Daily service capacity is exceeded.", technician_id=tid)

    if original is not None:
        original_jobs = {j.id: j for j in original.jobs}
        original_techs = {t.id: t for t in original.technicians}
        original_assigned = {a.job_id: a for a in original.schedule.assignments}
        assigned = {a.job_id: a for a in snapshot.schedule.assignments}
        new_events = snapshot.events[len(original.events):]
        if (snapshot.events[:len(original.events)] != original.events or len(new_events) > 1
                or snapshot.now_min != original.now_min or snapshot.date != original.date
                or snapshot.scenario_id != original.scenario_id or snapshot.scenario_epoch != original.scenario_epoch):
            fail("STATE_MUTATION", "Proposal changed its scenario or event history.")
        allowed_jobs = {e.job.id for e in new_events if isinstance(e, EmergencyEvent)}
        allowed_unavailable = {e.technician_id for e in new_events if isinstance(e, UnavailableEvent)}
        if set(jobs) - set(original_jobs) != allowed_jobs:
            fail("UNEXPECTED_JOB", "New jobs must originate in the previewed event.")
        for event in new_events:
            if event.at_min != snapshot.now_min:
                fail("EVENT_TIME", "Event time must equal the current simulation time.")
            if isinstance(event, EmergencyEvent):
                added = jobs.get(event.job.id)
                if (added is None or added.status == "cancelled"
                        or added.model_dump(exclude={"status"}) != event.job.model_dump()):
                    fail("EVENT_JOB_MUTATION", "Emergency job differs from the supplied event.", event.job.id)
        if set(techs) != set(original_techs):
            fail("STATE_MUTATION", "Proposal changed the technician roster.")
        for tid, before in original_techs.items():
            after = techs.get(tid)
            if after is None:
                continue
            if before.model_dump(exclude={"assigned_job_ids", "availability"}) != after.model_dump(exclude={"assigned_job_ids", "availability"}):
                fail("STATE_MUTATION", "Proposal changed technician skills, limits or location.", technician_id=tid)
            expected_availability = "unavailable" if tid in allowed_unavailable else before.availability
            if after.availability != expected_availability:
                fail("STATE_MUTATION", "Availability changed without a matching event.", technician_id=tid)
        for jid, before_job in original_jobs.items():
            after_job = jobs.get(jid)
            if (after_job is None or (before_job.status == "cancelled") != (after_job.status == "cancelled")
                    or before_job.model_dump(exclude={"status"}) != after_job.model_dump(exclude={"status"})):
                fail("JOB_MUTATION", "Existing job requirements cannot change during replanning.", jid)
            before_a, after_a = original_assigned.get(jid), assigned.get(jid)
            if before_a is not None and (before_a.start_min <= original.now_min or before_job.locked):
                if after_a is None or (before_a.technician_id, before_a.start_min, before_a.end_min) != (
                        after_a.technician_id, after_a.start_min, after_a.end_min):
                    fail("PROTECTED_WORK", "Started or locked work was removed or changed.", jid)
            if before_a is not None and after_a is None:
                fail("EXISTING_JOB_DROPPED", "Replanning cannot silently drop existing assigned work.", jid)
            if (after_a is not None and after_a.start_min < original.now_min
                    and (before_a is None or before_a.start_min > original.now_min)):
                fail("PAST_INSERTION", "Replanned work cannot start in the past.", jid)

    return Validation(valid=not violations, violations=violations)
