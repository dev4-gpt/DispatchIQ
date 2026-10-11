"""Parametric insertion + local-search re-plan policy.

Used by the no-LLM random-search baseline (proposers.RandomSearchProposer), which only
changes the PARAMS line. LLM agents write free-form code instead.
"""

from dispatchiq.helpers import drop_until_feasible, route, route_cost, travel_min

PARAMS = {"emergency_by_start": 0, "regret": 0, "resequence": 0, "relocate_iters": 0, "postpone_factor": 1.0}

CHURN = 20
UNASSIGNED = 150


def _churn(state, jid, tid):
    mt = state["jobs"][jid]["morning_tech"]
    sick = {t["id"] for t in state["techs"] if t["sick"]}
    return CHURN if (mt and mt != tid and mt not in sick) else 0


def _best_insert(state, techs, plan, jid):
    """Return sorted list of (delta, tid, seq) feasible insertions."""
    job = state["jobs"][jid]
    out = []
    for tid, t in techs.items():
        if t["sick"] or job["skill"] not in t["skills"]:
            continue
        base = route_cost(state, t, plan[tid])
        for pos in range(len(plan[tid]) + 1):
            seq = plan[tid][:pos] + [jid] + plan[tid][pos:]
            c = route_cost(state, t, seq)
            if c < 1e5:
                out.append((c - base + _churn(state, jid, tid), tid, seq))
    out.sort(key=lambda x: x[0])
    return out


def replan(state):
    P = PARAMS
    techs = {t["id"]: t for t in state["techs"]}
    jobs = state["jobs"]
    plan = {tid: ([] if t["sick"] else list(t["remaining"])) for tid, t in techs.items()}

    if P["resequence"]:
        for tid, t in techs.items():
            if plan[tid]:
                alt = sorted(plan[tid], key=lambda j: (jobs[j]["latest"], jobs[j]["earliest"]))
                if route_cost(state, t, alt) < route_cost(state, t, plan[tid]):
                    plan[tid] = alt

    # Emergencies: go first, to the front of a route; bump routine jobs if needed.
    for jid in sorted((j for j in jobs if jobs[j]["emergency"]), key=lambda j: jobs[j]["release"]):
        job = jobs[jid]
        best = None
        for tid, t in techs.items():
            if t["sick"] or job["skill"] not in t["skills"]:
                continue
            seq, dropped = drop_until_feasible(state, t, [jid] + plan[tid])
            if not route(state, t, seq)["feasible"]:
                continue
            d = travel_min(state, t["loc"], job["loc"])
            key = (t["free_at"] + d) if P["emergency_by_start"] else d
            key += sum(UNASSIGNED * jobs[x]["priority"] for x in dropped) / 1000.0
            if best is None or key < best[0]:
                best = (key, tid, seq)
        if best:
            plan[best[1]] = best[2]

    # Orphaned jobs from sick techs.
    orphans = [j for t in state["techs"] if t["sick"] for j in t["remaining"]]
    orphans.sort(key=lambda j: (-jobs[j]["priority"], jobs[j]["latest"]))
    while orphans:
        if P["regret"]:
            scored = []
            for j in orphans:
                opts = _best_insert(state, techs, plan, j)
                regret = (opts[1][0] - opts[0][0]) if len(opts) > 1 else 1e9 if opts else -1
                scored.append((regret, j, opts))
            scored.sort(key=lambda x: -x[0])
            _, jid, opts = scored[0]
        else:
            jid = orphans[0]
            opts = _best_insert(state, techs, plan, jid)
        orphans.remove(jid)
        if opts and opts[0][0] < P["postpone_factor"] * UNASSIGNED * jobs[jid]["priority"]:
            plan[opts[0][1]] = opts[0][2]

    # Relocate local search between healthy techs.
    for _ in range(P["relocate_iters"]):
        improved = False
        for tid in list(plan):
            for jid in list(plan[tid]):
                if jobs[jid]["emergency"]:
                    continue
                t = techs[tid]
                without = [j for j in plan[tid] if j != jid]
                gain = route_cost(state, t, plan[tid]) - route_cost(state, t, without) - _churn(state, jid, tid)
                plan_wo = dict(plan)
                plan_wo[tid] = without
                opts = [o for o in _best_insert(state, techs, plan_wo, jid) if o[1] != tid]
                if opts and opts[0][0] < gain - 1e-6:
                    plan[tid] = without
                    plan[opts[0][1]] = opts[0][2]
                    improved = True
        if not improved:
            break
    return plan
