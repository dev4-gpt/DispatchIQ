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
import importlib.util, json, resource, sys
resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
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
                "travel": avg("travel"), "moved": avg("moved"), "unassigned": avg("unassigned")}


def evaluate(code: str, seeds: list[int], timeout: float = 60.0) -> Evaluation:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(code)
        try:
            proc = subprocess.run([sys.executable, "-I", "-c", RUNNER, str(path), str(PKG_ROOT)],
                                  input="[" + ",".join(_state(s) for s in seeds) + "]",
                                  capture_output=True, text=True, timeout=timeout,
                                  env={"PATH": os.environ.get("PATH", "")})
        except subprocess.TimeoutExpired:
            return Evaluation(INFEASIBLE_COST, len(seeds), [f"timeout after {timeout:.0f}s"])
    if proc.returncode != 0:
        return Evaluation(INFEASIBLE_COST, len(seeds), [proc.stderr.strip()[-600:] or "crashed"])
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return Evaluation(INFEASIBLE_COST, len(seeds), ["candidate printed to stdout or returned non-JSON"])
    ev = Evaluation(0.0, 0)
    for seed, res in zip(seeds, results):
        if not res["ok"]:
            sc = Score(False, INFEASIBLE_COST, [res["error"]])
        else:
            sc = check(state(seed), res["plan"])
        ev.per_seed[seed] = sc
        if not sc.feasible:
            ev.infeasible += 1
            ev.errors.extend(sc.violations[:2])
    ev.mean_cost = mean(s.cost for s in ev.per_seed.values())
    return ev
