"""Run untrusted policy code in a separate process, then score it with the checker here.

The candidate only ever sees re-plan states and returns plans. Scoring happens in this
process, so a candidate cannot report its own score or touch the checker.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from statistics import mean
from typing import Any

from .generator import make_day
from .simulate import INFEASIBLE_COST, Score, check, replan_state

PKG_ROOT = Path(__file__).resolve().parent.parent

RUNNER = r"""
import importlib.util, json, sys
try:  # memory cap where supported (Unix). This is a resource guard, not a security sandbox.
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
except (ImportError, ValueError, OSError):
    pass
sys.path.insert(0, sys.argv[2])
spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
states = json.load(sys.stdin)
out = []
for st in states:
    try:
        out.append({"ok": True, "plan": mod.replan(st)})
    except Exception as e:
        out.append({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]})
json.dump(out, sys.stdout)
"""


def _child_env() -> dict[str, str]:
    """Minimal environment for the child. Windows needs SYSTEMROOT for Python to start."""
    keep = ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "WINDIR")
    return {k: v for k, v in os.environ.items() if k in keep}


@lru_cache(maxsize=512)
def _state(seed: int) -> str:
    return json.dumps(replan_state(make_day(seed)))


def state(seed: int) -> dict[str, Any]:
    return json.loads(_state(seed))


@dataclass
class Evaluation:
    mean_cost: float
    infeasible: int
    errors: list[str] = field(default_factory=list)
    per_seed: dict[int, Score] = field(default_factory=dict)

    def summary(self) -> dict[str, float]:
        ok = [s for s in self.per_seed.values() if s.feasible]
        def avg(attr):
            return round(mean(getattr(s, attr) for s in ok), 2) if ok else None
        return {"mean_cost": round(self.mean_cost, 1), "infeasible": self.infeasible,
                "on_time_pct": avg("on_time_pct"), "emergency_response": avg("emergency_response"),
                "travel": avg("travel"), "moved": avg("moved"), "unassigned": avg("unassigned"),
                # Totals over feasible days: emergencies that started after their promised latest start.
                "emergencies": sum(s.emergencies for s in ok), "missed_promises": sum(s.missed_promises for s in ok),
                # Reporting only (not in the cost): customers booked with a healthy tech this morning who are
                # left unscheduled, and jobs moved from one healthy tech to another.
                "bumped_booked": sum(_bumped_booked(seed, s) for seed, s in self.per_seed.items() if s.feasible),
                "moved_healthy": sum(s.moved for s in ok)}


def cost_breakdown(ev: Evaluation) -> dict[str, float] | None:
    """Mean per-day cost split into the checker's terms, over feasible days. The parts sum to the
    checker's cost; computed from the scored routes, so the checker itself is unchanged."""
    from .simulate import W_CHURN, W_EMERGENCY, W_UNASSIGNED
    ok = {seed: s for seed, s in ev.per_seed.items() if s.feasible}
    if not ok:
        return None
    tot = dict(travel=0.0, lateness=0.0, unassigned=0.0, churn=0.0, emergency_wait=0.0, overtime=0.0)
    for seed, s in ok.items():
        jobs = state(seed)["jobs"]
        assigned = {stop["job"] for stops in s.routes.values() for stop in stops}
        tot["travel"] += s.travel
        tot["lateness"] += s.weighted_late
        tot["overtime"] += s.overtime
        tot["churn"] += W_CHURN * s.moved
        tot["emergency_wait"] += W_EMERGENCY * s.emergency_response * s.emergencies
        tot["unassigned"] += W_UNASSIGNED * sum(j["priority"] for jid, j in jobs.items() if jid not in assigned)
    return {k: round(v / len(ok), 1) for k, v in tot.items()}


def _bumped_booked(seed: int, score: Score) -> int:
    st = state(seed)
    sick = {t["id"] for t in st["techs"] if t["sick"]}
    assigned = {stop["job"] for stops in score.routes.values() for stop in stops}
    return sum(1 for jid, j in st["jobs"].items()
               if j["morning_tech"] and j["morning_tech"] not in sick and jid not in assigned)


def evaluate(code: str, seeds: list[int], timeout: float = 60.0) -> Evaluation:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(code)
        try:
            proc = subprocess.run([sys.executable, "-I", "-c", RUNNER, str(path), str(PKG_ROOT)],
                                  input="[" + ",".join(_state(s) for s in seeds) + "]",
                                  capture_output=True, text=True, timeout=timeout,
                                  env=_child_env())
        except subprocess.TimeoutExpired:
            return Evaluation(INFEASIBLE_COST, len(seeds), [f"timeout after {timeout:.0f}s"])
    if proc.returncode != 0:
        return Evaluation(INFEASIBLE_COST, len(seeds), [proc.stderr.strip()[-600:] or "crashed"])
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return Evaluation(INFEASIBLE_COST, len(seeds), ["candidate printed to stdout or returned non-JSON"])
    if not isinstance(results, list) or len(results) != len(seeds):
        return Evaluation(INFEASIBLE_COST, len(seeds), ["runner returned the wrong number of results"])
    ev = Evaluation(0.0, 0)
    for seed, res in zip(seeds, results):
        if not isinstance(res, dict) or not res.get("ok"):
            sc = Score(False, INFEASIBLE_COST, [res.get("error", "bad result") if isinstance(res, dict) else "bad result"])
        else:
            sc = check(state(seed), res["plan"])
        ev.per_seed[seed] = sc
        if not sc.feasible:
            ev.infeasible += 1
            ev.errors.extend(sc.violations[:2])
    ev.mean_cost = mean(s.cost for s in ev.per_seed.values())
    return ev
