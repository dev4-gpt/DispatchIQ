"""Helpers that re-plan policies (including agent-written ones) may import.

    from dispatchiq.helpers import route, travel_min

These only *estimate*; the checker in simulate.py remains the judge.
"""

from __future__ import annotations

from typing import Any


def travel_min(state: dict[str, Any], a, b) -> float:
    return (abs(a[0] - b[0]) + abs(a[1] - b[1])) * state["min_per_km"]


def route(state: dict[str, Any], tech: dict[str, Any], seq: list[str]) -> dict[str, float]:
    """Simulate `tech` driving `seq` from its free time and location."""
    jobs = state["jobs"]
    t, loc = tech["free_at"], tech["loc"]
    travel = wlate = 0.0
    emergency_wait = 0.0
    for jid in seq:
        j = jobs[jid]
        d = travel_min(state, loc, j["loc"])
        start = max(t + d, j["earliest"], j["release"])
        late = max(0.0, start - j["latest"])
        travel += d
        wlate += late * j["priority"]
        if j["emergency"]:
            emergency_wait += start - j["release"]
        t, loc = start + j["duration"], j["loc"]
    overtime = max(0.0, t - tech["shift_end"])
    return {"travel": travel, "weighted_late": wlate, "overtime": overtime, "end": t,
            "emergency_wait": emergency_wait, "feasible": overtime <= tech["max_overtime"]}


def route_cost(state: dict[str, Any], tech: dict[str, Any], seq: list[str]) -> float:
    """Same weighting as the checker for one route (excluding unassigned and churn terms)."""
    r = route(state, tech, seq)
    return r["travel"] + r["weighted_late"] + r["overtime"] + r["emergency_wait"] + (0 if r["feasible"] else 1e6)


def drop_until_feasible(state: dict[str, Any], tech: dict[str, Any], seq: list[str]) -> tuple[list[str], list[str]]:
    """Bump routine jobs (lowest priority, latest in the day first) until the route fits the overtime limit.

    Returns (kept sequence, dropped job ids). Emergencies are never dropped.
    """
    seq = list(seq)
    dropped: list[str] = []
    jobs = state["jobs"]
    while not route(state, tech, seq)["feasible"]:
        candidates = [(jobs[j]["priority"], -i, j) for i, j in enumerate(seq) if not jobs[j]["emergency"]]
        if not candidates:
            break
        _, _, victim = min(candidates)
        seq.remove(victim)
        dropped.append(victim)
    return seq, dropped
