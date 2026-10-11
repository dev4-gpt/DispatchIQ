"""Re-score a saved run's champion with the checker. No LLM is called.

    python rescore.py runs/llm-team.json            # champion on dev and validation days
    python rescore.py runs/llm-team.json --code round0

The code saved in the run file is run in the sandbox subprocess and scored by simulate.check, the
same path evolve.py used. Dev and validation days are deterministic, so the scores must match the
values saved in the run file; a mismatch exits non-zero. Held-out days are deliberately not
available here: heldout.py is the only, run-once path to them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dispatchiq.generator import heldout_hash, split
from dispatchiq.sandbox import evaluate

ROOT = Path(__file__).resolve().parent


def saved_costs(run: dict, code: str) -> dict[str, float | None]:
    if code == "round0":
        base = run.get("baseline", {})
        return {"dev": base.get("dev", {}).get("mean_cost"), "validation": base.get("val", {}).get("mean_cost")}
    last = run["rounds"][-1] if run.get("rounds") else {}
    return {"dev": last.get("champion_dev"), "validation": last.get("champion_val")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="saved run file, e.g. runs/llm-team.json")
    ap.add_argument("--code", choices=["champion", "round0"], default="champion")
    args = ap.parse_args(argv)

    run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    if run.get("heldout_hash") and run["heldout_hash"] != heldout_hash():
        print("warning: the held-out hash differs from the one recorded in this run (generator changed?)")
    code = run["champion_code"] if args.code == "champion" else run["round0_code"]
    saved = saved_costs(run, args.code)
    ok = True
    print(f"{run.get('id')}: {args.code} code, {len(run.get('rounds', []))} rounds, mode {run.get('mode')}")
    for name in ("dev", "validation"):
        summary = evaluate(code, split(name)).summary()
        match = saved[name] is not None and abs(summary["mean_cost"] - saved[name]) < 0.05
        ok &= match
        print(f"  {name:10s} cost {summary['mean_cost']:8.1f}  saved {saved[name] if saved[name] is not None else '-':>8}  "
              f"{'match' if match else 'MISMATCH'}  on-time {summary['on_time_pct']}%  "
              f"missed {summary['missed_promises']}/{summary['emergencies']}  infeasible days {summary['infeasible']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
