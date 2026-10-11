"""Round-0 seed policy: what a busy human dispatcher does.

Everyone keeps their remaining jobs. Each orphaned job (from the sick tech) and each
emergency goes to the nearest healthy tech with the right skill: emergencies to the
front of that tech's list, other jobs to the end. If that would push the tech past the
overtime limit, the job is left for tomorrow; an emergency instead bumps that
tech's lowest-priority jobs to tomorrow.
"""

from dispatchiq.helpers import drop_until_feasible, route, travel_min


def replan(state):
    plan = {t["id"]: ([] if t["sick"] else list(t["remaining"])) for t in state["techs"]}
    healthy = [t for t in state["techs"] if not t["sick"]]
    orphans = [j for t in state["techs"] if t["sick"] for j in t["remaining"]]
    emergencies = [jid for jid, j in state["jobs"].items() if j["emergency"]]
    for jid in emergencies + orphans:
        job = state["jobs"][jid]
        options = sorted((travel_min(state, t["loc"], job["loc"]), t["id"]) for t in healthy
                         if job["skill"] in t["skills"])
        for _, tid in options:
            tech = next(t for t in healthy if t["id"] == tid)
            seq = [jid] + plan[tid] if job["emergency"] else plan[tid] + [jid]
            if job["emergency"]:
                seq, _ = drop_until_feasible(state, tech, seq)  # bump routine jobs to tomorrow
            if route(state, tech, seq)["feasible"]:
                plan[tid] = seq
                break
    return plan
