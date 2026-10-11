"""Re-score a saved run's champion with the checker. No LLM is called.

    python rescore.py runs/llm-team.json            # champion on dev and validation days
    python rescore.py runs/llm-team.json --code round0
    python rescore.py --backfill                    # reporting counts for older run files (see below)

The code saved in the run file is run in the sandbox subprocess and scored by simulate.check, the
same path evolve.py used. Dev and validation days are deterministic, so the scores must match the
values saved in the run file; a mismatch exits non-zero. Held-out days are deliberately not
available here: heldout.py is the only, run-once path to them.

--backfill re-scores the saved champion of every named run (and the naive/insertion references)
on validation days and writes runs/backfill_metrics.json. Run files saved before a reporting field
existed (e.g. bumped_booked, moved_healthy) get it from there; the scoreboard only uses an entry
whose saved validation cost and round count still match the run file. If the re-scored cost differs
from the saved one (e.g. a champion with a wall-clock time budget), both are recorded and shown.
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


def backfill(runs_dir: Path) -> dict:
    from dispatchiq.scoreboard import RUN_NAMES

    from evolve import REFERENCES
    days = split("validation")
    out = {"references": {name: evaluate((ROOT / path).read_text(), days).summary() for name, path in REFERENCES.items()},
           "runs": {}}
    for name in RUN_NAMES.values():
        path = runs_dir / f"{name}.json"
        if not path.exists():
            continue
        run = json.loads(path.read_text(encoding="utf-8"))
        if not run.get("rounds"):
            continue
        summary = evaluate(run["champion_code"], days).summary()
        saved = run["rounds"][-1]["champion_val"]
        matches = abs(summary["mean_cost"] - saved) < 0.05
        # A champion whose search stops on a wall-clock budget can score slightly differently under a different
        # machine load. Record both costs and flag it instead of hiding the difference.
        out["runs"][name] = {"champion_val": saved, "rounds": len(run["rounds"]), "val": summary,
                             "rescored_val": summary["mean_cost"], "cost_matches": matches}
        print(f"  {name:22s} rounds {len(run['rounds']):2d}  val {saved:.1f}  bumped {summary['bumped_booked']}  "
              f"moved {summary['moved_healthy']}"
              + ("" if matches else f"  WARNING: re-scored cost {summary['mean_cost']:.1f} != saved {saved:.1f}"))
    for name, s in out["references"].items():
        print(f"  {name + ' (reference)':22s}           val {s['mean_cost']:.1f}  bumped {s['bumped_booked']}  "
              f"moved {s['moved_healthy']}")
    target = runs_dir / "backfill_metrics.json"
    target.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {target}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?", help="saved run file, e.g. runs/llm-team.json")
    ap.add_argument("--code", choices=["champion", "round0"], default="champion")
    ap.add_argument("--backfill", action="store_true", help="write runs/backfill_metrics.json for all named runs")
    args = ap.parse_args(argv)
    if args.backfill:
        backfill(ROOT / "runs")
        return 0
    if not args.run:
        ap.error("give a run file, or --backfill")

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
