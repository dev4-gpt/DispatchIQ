"""Morning plan, disruption, re-plan state, and the deterministic rule checker.

The checker is the only judge. A re-plan policy (hand-written or agent-written) only
returns {tech_id: [job ids]} for the open jobs after the disruption; this module adds
the frozen part of the day, enforces every rule and computes the cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import MIN_PER_KM, Day, Job, Plan, route_eval, travel

# Cost weights (minutes-equivalent). Published in the README so judges can audit them.
W_UNASSIGNED = 150   # per priority point of a job left unscheduled today
W_CHURN = 20         # per customer moved off the tech they were promised (healthy techs only)
W_EMERGENCY = 1.0    # per minute from emergency call to tech starting the job


def morning_plan(day: Day) -> Plan:
    """Fixed, policy-independent morning schedule: cheapest feasible insertion, priority first."""
    jobs = {j.id: j for j in day.jobs}
    plan: Plan = {t.id: [] for t in day.techs}
    order = sorted(day.jobs, key=lambda j: (-j.priority, j.earliest, j.id))
    for j in order:
        best = None
        for t in day.techs:
            if j.skill not in t.skills:
                continue
            base = route_eval(t.shift_start, t.home, t.shift_end, plan[t.id], jobs)
            for pos in range(len(plan[t.id]) + 1):
                seq = plan[t.id][:pos] + [j.id] + plan[t.id][pos:]
                r = route_eval(t.shift_start, t.home, t.shift_end, seq, jobs)
                if r.overtime > 0:
                    continue
                delta = (r.travel + r.weighted_late) - (base.travel + base.weighted_late)
                if best is None or delta < best[0]:
                    best = (delta, t.id, seq)
        if best:
            plan[best[1]] = best[2]
    return plan


@dataclass
class Frozen:
    seq: list[str]
    free_at: float
    loc: tuple[float, float]


def freeze(day: Day, plan: Plan) -> dict[str, Frozen]:
    """Jobs started before the disruption stay where they are (done or in progress)."""
    t = day.disruption.time
    jobs = day.all_jobs()
    out = {}
    for tech in day.techs:
        r = route_eval(tech.shift_start, tech.home, tech.shift_end, plan[tech.id], jobs)
        done = [s for s in r.stops if s.start < t]
        if done:
            last = done[-1]
            out[tech.id] = Frozen([s.job for s in done], max(t, last.end), jobs[last.job].loc)
        else:
            out[tech.id] = Frozen([], max(t, tech.shift_start), tech.home)
    return out


def replan_state(day: Day, plan: Plan | None = None) -> dict[str, Any]:
    """JSON-safe snapshot handed to a re-plan policy at the moment of the disruption."""
    plan = plan or morning_plan(day)
    frozen = freeze(day, plan)
    jobs = day.all_jobs()
    owner = {jid: tid for tid, seq in plan.items() for jid in seq}
    frozen_ids = {j for f in frozen.values() for j in f.seq}
    open_ids = [j.id for j in day.jobs if j.id not in frozen_ids] + [e.id for e in day.disruption.emergencies]
    return {
        "time": day.disruption.time,
        "min_per_km": MIN_PER_KM,
        "techs": [{
            "id": t.id, "name": t.name, "skills": t.skills, "sick": t.id in day.disruption.sick,
            "free_at": frozen[t.id].free_at, "loc": list(frozen[t.id].loc),
            "shift_end": t.shift_end, "max_overtime": t.max_overtime,
            "remaining": [j for j in plan[t.id] if j not in frozen_ids],
        } for t in day.techs],
        "jobs": {jid: {
            "loc": list(jobs[jid].loc), "skill": jobs[jid].skill, "duration": jobs[jid].duration,
            "earliest": jobs[jid].earliest, "latest": jobs[jid].latest, "priority": jobs[jid].priority,
            "emergency": jobs[jid].emergency, "release": jobs[jid].release, "morning_tech": owner.get(jid),
        } for jid in open_ids},
    }


@dataclass
class Score:
    feasible: bool
    cost: float
    violations: list[str] = field(default_factory=list)
    travel: float = 0.0
    weighted_late: float = 0.0
    late_jobs: int = 0
    on_time_pct: float = 0.0
    overtime: float = 0.0
    unassigned: int = 0
    moved: int = 0
    emergency_response: float = 0.0  # average minutes, call to start
    routes: dict[str, Any] = field(default_factory=dict)


INFEASIBLE_COST = 100_000.0


def check(state: dict[str, Any], proposal: Any) -> Score:
    """Authoritative rule checker for a re-plan proposal."""
    v: list[str] = []
    if not isinstance(proposal, dict):
        return Score(False, INFEASIBLE_COST, ["proposal is not a dict of tech id -> job list"])
    techs = {t["id"]: t for t in state["techs"]}
    open_jobs = state["jobs"]
    jobs = {jid: Job(id=jid, loc=tuple(j["loc"]), skill=j["skill"], duration=j["duration"],
                     earliest=j["earliest"], latest=j["latest"], priority=j["priority"],
                     emergency=j["emergency"], release=j["release"]) for jid, j in open_jobs.items()}
    seen: set[str] = set()
    for tid, seq in proposal.items():
        if tid not in techs:
            v.append(f"unknown tech {tid}")
            continue
        if not isinstance(seq, list):
            v.append(f"{tid}: job list is not a list")
            continue
        if seq and techs[tid]["sick"]:
            v.append(f"{tid} is out sick but was given {len(seq)} jobs")
        for jid in seq:
            if jid not in open_jobs:
                v.append(f"{tid}: job {jid} is not an open job")
            elif jid in seen:
                v.append(f"job {jid} assigned twice")
            elif open_jobs[jid]["skill"] not in techs[tid]["skills"]:
                v.append(f"{tid} lacks skill {open_jobs[jid]['skill']} for {jid}")
            seen.add(jid)
    for jid, j in open_jobs.items():
        if j["emergency"] and jid not in seen:
            v.append(f"emergency {jid} not assigned")
    if v:
        return Score(False, INFEASIBLE_COST, v)

    s = Score(True, 0.0)
    resp, n_assigned, n_late = [], 0, 0
    for tid, t in techs.items():
        seq = [j for j in proposal.get(tid, []) if j in jobs]
        r = route_eval(t["free_at"], tuple(t["loc"]), t["shift_end"], seq, jobs)
        if r.overtime > t["max_overtime"]:
            v.append(f"{tid} ends {r.overtime:.0f} min past shift (max {t['max_overtime']})")
        s.travel += r.travel
        s.weighted_late += r.weighted_late
        s.overtime += r.overtime
        n_late += r.late_jobs
        n_assigned += len(seq)
        for stop in r.stops:
            if jobs[stop.job].emergency:
                resp.append(stop.start - jobs[stop.job].release)
            mt = open_jobs[stop.job]["morning_tech"]
            if mt and mt != tid and not techs[mt]["sick"]:
                s.moved += 1
        s.routes[tid] = [{"job": st.job, "start": st.start, "end": st.end, "late": st.late} for st in r.stops]
    if v:
        return Score(False, INFEASIBLE_COST, v)
    unassigned = [jid for jid in open_jobs if jid not in seen]
    s.unassigned = len(unassigned)
    s.late_jobs = n_late
    s.on_time_pct = 100.0 * (n_assigned - n_late) / max(1, len(open_jobs))
    s.emergency_response = sum(resp) / len(resp) if resp else 0.0
    s.cost = (s.travel + s.weighted_late + s.overtime
              + W_UNASSIGNED * sum(open_jobs[j]["priority"] for j in unassigned)
              + W_CHURN * s.moved + W_EMERGENCY * sum(resp))
    return s


def keep_morning(state: dict[str, Any]) -> Plan:
    """Helper: every healthy tech keeps their remaining morning jobs."""
    return {t["id"]: ([] if t["sick"] else list(t["remaining"])) for t in state["techs"]}


def dist(state: dict[str, Any], a: list[float], b: list[float]) -> float:
    return travel(tuple(a), tuple(b))
