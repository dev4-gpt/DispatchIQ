"""Run ONCE: score every saved champion on the 50 held-out days nobody tuned on.

    python heldout.py --dry-run   # what would be scored, and the named final solution (no held-out scoring)
    python heldout.py             # the run

The final solution is named BEFORE scoring, by the README rule (lowest-validation 6-agent LLM run,
dispatchiq.scoreboard.final_pick), and printed first. Every other saved champion and the two reference
policies are scored beside it in the same invocation, under the same conditions.

"Once" (README): a crash or timeout that prints no held-out scores is not a run and may be retried.
This script scores everything first and prints only when every policy completed all 50 days, so a
failure prints no scores. Any run that prints scores is final; it writes runs/heldout_result.json and a
second invocation refuses to run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dispatchiq import scoreboard
from dispatchiq.generator import heldout_hash, split
from dispatchiq.sandbox import evaluate

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
# Whole 50-day batch per policy. The slowest saved champion uses a 0.42 s/day wall-clock budget (~21 s);
# a timeout prints nothing and may be retried, so the margin only has to be generous.
TIMEOUT_S = 300.0
REFERENCE_ROWS = [("naive (reference)", "dispatchiq/policies/naive.py"),
                  ("insertion (reference)", "dispatchiq/policies/insertion.py")]
CHAMPION_ROWS = ("random search", "LLM plain", "LLM team v1", "LLM team v2")


def policies(runs: dict) -> list[dict]:
    rows = [{"policy": label, "source": path, "code": (ROOT / path).read_text()} for label, path in REFERENCE_ROWS]
    for label in CHAMPION_ROWS:
        run = runs.get(label)
        if run is None or not run.get("rounds"):
            continue
        rows.append({"policy": label, "source": f"runs/{scoreboard.RUN_NAMES[label]}.json", "code": run["champion_code"],
                     "run_id": run.get("id"), "rounds": len(run["rounds"]),
                     "validation_cost": run["rounds"][-1]["champion_val"], "heldout_hash": run.get("heldout_hash")})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="list what would be scored; score nothing")
    args = ap.parse_args(argv)

    out_path = RUNS / "heldout_result.json"
    if out_path.exists():
        done = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"Held-out scoring already ran at {done.get('finished_at')}; it is run once. Not repeating.")
        return 1

    h = heldout_hash()
    published = (ROOT / "HELDOUT_HASH.txt").read_text().strip()
    if h != published:
        print("Held-out days differ from the published hash. Refusing to run.")
        return 1
    runs = scoreboard.load_runs(RUNS)
    rows = policies(runs)
    bad = [r["policy"] for r in rows if r.get("heldout_hash") not in (None, h)]
    if bad:
        print(f"Run files recorded a different held-out hash: {bad}. Refusing to run.")
        return 1
    pick = scoreboard.final_pick(runs)
    if pick is None:
        print("No eligible 6-agent LLM run is saved, so the README rule names no final solution. Refusing to run.")
        return 1

    days = split("heldout")
    print(f"Held-out: {len(days)} days, hash {h[:12]}...")
    print(f"Final solution, named before scoring by the README rule: {pick['run']} "
          f"(validation {pick['val_cost']:.1f}; candidates {pick['candidates']})")
    print("Also scored beside it: " + ", ".join(r["policy"] for r in rows if r["policy"] != pick["run"]))
    if args.dry_run:
        print("Dry run: nothing scored.")
        return 0

    # Score everything first. Print only if every policy completed all days.
    results, started = [], time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for r in rows:
        t0 = time.time()
        ev = evaluate(r["code"], days, timeout=TIMEOUT_S)
        if len(ev.per_seed) != len(days):  # runner crash, timeout or bad output: not a held-out score
            print(f"\nNO HELD-OUT SCORES PRINTED. {r['policy']} did not complete: {'; '.join(ev.errors)[:300]}")
            print("Under the README definition this was not a run; fix the cause and run again.")
            return 2
        results.append({**{k: v for k, v in r.items() if k != "code"}, **ev.summary(),
                        "seconds": round(time.time() - t0, 1), "final_solution": r["policy"] == pick["run"]})

    def f(x, spec):
        return "-" if x is None else format(x, spec)

    naive = results[0]["mean_cost"]
    lines = [f"\n{'Policy':26s} {'held-out':>9s} {'vs naive':>9s} {'on-time':>8s} {'missed':>7s} {'bumped':>7s} "
             f"{'moved':>6s} {'fail':>5s} {'validation':>10s}"]
    for r in results:  # build every line before printing any, so nothing is printed half-way
        r["vs_naive_pct"] = round(100 * (naive - r["mean_cost"]) / naive, 1)
        lines.append(f"{r['policy']:26s} {r['mean_cost']:9.1f} {r['vs_naive_pct']:+8.1f}% {f(r['on_time_pct'], '7.1f'):>7s}% "
                     f"{r['missed_promises']:3d}/{r['emergencies']:<3d} {r['bumped_booked']:7d} {r['moved_healthy']:6d} "
                     f"{r['infeasible']:5d} {f(r.get('validation_cost'), '10.1f'):>10s}"
                     + ("  <- final solution" if r["final_solution"] else ""))
    print("\n".join(lines))
    doc = {"format": 2, "hash": h, "started_at": started, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "final_solution": pick["run"], "final_rule_candidates": pick["candidates"], "results": results}
    RUNS.mkdir(exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, out_path)
    print(f"\nSaved {out_path}. This was the held-out run; it is final.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
