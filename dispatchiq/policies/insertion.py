"""Reference policy: classic cheapest-insertion re-plan (a textbook OR heuristic).

Shown next to the evolved policy as an honest, non-AI reference point. Emergencies
first, then orphaned jobs by priority; each job goes to the position (any healthy,
skilled tech, any slot) that adds the least route cost (travel, weighted lateness,
overtime, emergency wait). Jobs that cost more to insert than to postpone are left
for tomorrow. Healthy techs' existing jobs are never moved (zero churn).
"""

from dispatchiq.helpers import drop_until_feasible, route_cost

UNASSIGNED = 150


def replan(state):
    techs = {t["id"]: t for t in state["techs"]}
    plan = {tid: ([] if t["sick"] else list(t["remaining"])) for tid, t in techs.items()}
    jobs = state["jobs"]
    orphans = [j for t in state["techs"] if t["sick"] for j in t["remaining"]]
    emergencies = [jid for jid, j in jobs.items() if j["emergency"]]
    todo = sorted(emergencies, key=lambda j: -jobs[j]["priority"]) + sorted(
        orphans, key=lambda j: (-jobs[j]["priority"], jobs[j]["latest"]))
    for jid in todo:
        job = jobs[jid]
        best = None
        for tid, t in techs.items():
            if t["sick"] or job["skill"] not in t["skills"]:
                continue
            base = route_cost(state, t, plan[tid])
            for pos in range(len(plan[tid]) + 1):
                seq = plan[tid][:pos] + [jid] + plan[tid][pos:]
                delta = route_cost(state, t, seq) - base
                if best is None or delta < best[0]:
                    best = (delta, tid, seq)
        if best is None:
            continue
        if job["emergency"] and best[0] >= 1e5:
            # Nowhere fits: put it first on the route where bumping routine jobs costs least.
            fits = []
            for tid, t in techs.items():
                if t["sick"] or job["skill"] not in t["skills"]:
                    continue
                seq, dropped = drop_until_feasible(state, t, [jid] + plan[tid])
                c = route_cost(state, t, seq) + UNASSIGNED * sum(jobs[d]["priority"] for d in dropped)
                fits.append((c, tid, seq))
            if fits:
                _, tid, seq = min(fits)
                plan[tid] = seq
        elif job["emergency"] or best[0] < UNASSIGNED * job["priority"]:
            plan[best[1]] = best[2]
    return plan
