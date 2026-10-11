"""Metrics computed from schedules with a consistent future-work scope."""

from .schemas import DiffMetrics, EmergencyMetric, Metrics, Snapshot


def schedule_metrics(snapshot: Snapshot) -> Metrics:
    jobs = {j.id: j for j in snapshot.jobs}
    assignments = {a.job_id: a for a in snapshot.schedule.assignments}
    future = [a for a in snapshot.schedule.assignments if a.start_min > snapshot.now_min]
    lateness = [max(0, a.start_min - jobs[a.job_id].soft_promised_start_min)
                for a in future if jobs[a.job_id].soft_promised_start_min is not None]
    overtime = sum(max(0, max((a.end_min for a in snapshot.schedule.assignments
                              if a.technician_id == t.id), default=t.shift_end_min) - t.shift_end_min)
                   for t in snapshot.technicians)
    emergencies = []
    for job in snapshot.jobs:
        if not job.emergency or job.status == "cancelled":
            continue
        a = assignments.get(job.id)
        emergencies.append(EmergencyMetric(job_id=job.id, response_min=a.start_min - job.release_min if a else None,
                                           deadline_met=bool(a and job.deadline_start_min is not None
                                                             and a.start_min <= job.deadline_start_min)))
    return Metrics(travel_min=sum(a.travel_min for a in future),
                   unassigned_jobs=len(snapshot.schedule.unassigned_job_ids),
                   soft_sla_violations=sum(x > 0 for x in lateness), soft_sla_lateness_min=sum(lateness),
                   hard_constraint_violations=len(snapshot.validation.violations), overtime_min=overtime,
                   emergencies=emergencies)


def diff_metrics(before: Snapshot, after: Snapshot) -> DiffMetrics:
    old = {a.job_id: a for a in before.schedule.assignments}
    new = {a.job_id: a for a in after.schedule.assignments}
    unavailable = {t.id for t in after.technicians if t.availability == "unavailable"}
    result = DiffMetrics(new_jobs=len(set(new) - {j.id for j in before.jobs}),
                         newly_unassigned_jobs=len(set(after.schedule.unassigned_job_ids) - set(before.schedule.unassigned_job_ids)))
    result.changed_existing_jobs = len((set(new) - set(old)) & {j.id for j in before.jobs})
    for jid, a in old.items():
        b = new.get(jid)
        if b is None:
            result.changed_existing_jobs += 1
            continue
        owner_changed, time_changed = a.technician_id != b.technician_id, a.start_min != b.start_min
        if owner_changed or time_changed:
            result.changed_existing_jobs += 1
        if owner_changed:
            if a.technician_id in unavailable:
                result.forced_reassignments += 1
            else:
                result.voluntary_reassignments += 1
        if time_changed:
            result.start_changed_jobs += 1
            result.absolute_start_shift_min += abs(a.start_min - b.start_min)
    return result
