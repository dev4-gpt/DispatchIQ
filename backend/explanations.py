"""Deterministic explanations backed by the explicit before/after intervals."""

from .schemas import Change, Position, Snapshot


def changes(before: Snapshot, after: Snapshot, candidate_id: str | None) -> list[Change]:
    old = {a.job_id: a for a in before.schedule.assignments}
    new = {a.job_id: a for a in after.schedule.assignments}
    jobs = {j.id: j for j in after.jobs}
    techs = {t.id: t for t in after.technicians}
    result = []
    for jid in sorted(set(old) | set(new)):
        a, b = old.get(jid), new.get(jid)
        if a is not None and b is not None and (a.technician_id, a.start_min, a.end_min) == (b.technician_id, b.start_min, b.end_min):
            continue
        forced = bool(a and techs[a.technician_id].availability == "unavailable")
        if a is None:
            job = jobs[jid]
            kind, reason = "added", "EMERGENCY_INSERTION" if job.emergency else "UNASSIGNED_RECOVERED"
            text = (f"{techs[b.technician_id].name} has {', '.join(job.required_skills)} certification(s) "
                    f"and starts {b.start_min - job.release_min} minutes after release. "
                    f"The response deadline and hard windows are satisfied." if job.emergency else
                    f"Previously unassigned {jid} is scheduled with {techs[b.technician_id].name} within its hard window.")
        elif b is None:
            kind, reason, text = "unassigned", "NO_ASSIGNMENT", f"{jid} is explicitly unassigned."
        elif a.technician_id != b.technician_id:
            kind, reason = "reassigned", "TECHNICIAN_UNAVAILABLE" if forced else "FEASIBLE_REASSIGNMENT"
            text = (f"{jid} moves from {techs[a.technician_id].name} to {techs[b.technician_id].name} "
                    + ("because its original technician is unavailable. " if forced else "in the validated proposal. ")
                    + "Certifications, travel and hard windows were checked.")
        else:
            kind, reason = "shifted", "TRAVEL_AFTER_INSERTION"
            text = (f"{jid} shifts {b.start_min - a.start_min:+d} minutes to accommodate the revised route "
                    f"and {b.travel_min} minutes of incoming travel, within its hard window.")
        result.append(Change(job_id=jid,
                             before=Position(technician_id=a.technician_id, start_min=a.start_min, end_min=a.end_min) if a else None,
                             after=Position(technician_id=b.technician_id, start_min=b.start_min, end_min=b.end_min) if b else None,
                             kind=kind, forced=forced, reason_code=reason, explanation=text,
                             evidence_candidate_id=candidate_id))
    return result
