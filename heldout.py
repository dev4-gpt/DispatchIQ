"""Run ONCE at the end: compare policies on held-out days nobody tuned on.

    python heldout.py                 # uses runs/latest.json
    python heldout.py runs/<id>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dispatchiq.generator import heldout_hash, split
from dispatchiq.sandbox import evaluate

ROOT = Path(__file__).resolve().parent


def main() -> None:
    run_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "runs" / "latest.json"
    run = json.loads(run_path.read_text())
    h = heldout_hash()
    if h != run["heldout_hash"]:
        sys.exit("Held-out hash differs from the one recorded at search time.")
    days = split("heldout")
    rows = [
        ("Dispatcher-style baseline (round 0)", run["round0_code"]),
        ("Textbook cheapest insertion (reference)", (ROOT / "dispatchiq/policies/insertion.py").read_text()),
        (f"Evolved champion ({run['mode']}, {len(run['rounds'])} rounds)", run["champion_code"]),
    ]
    results = []
    print(f"Held-out: {len(days)} unseen days, hash {h[:12]}...\n")
    print(f"{'Policy':45s} {'cost':>8s} {'on-time':>8s} {'emerg min':>9s} {'travel':>7s} {'moved':>6s} {'unsched':>7s} {'fail':>5s}")
    for name, code in rows:
        s = evaluate(code, days).summary()
        results.append({"policy": name, **s})
        print(f"{name:45s} {s['mean_cost']:8.0f} {s['on_time_pct']:7.1f}% {s['emergency_response']:9.0f} "
              f"{s['travel']:7.0f} {s['moved']:6.1f} {s['unassigned']:7.1f} {s['infeasible']:5d}")
    base, champ = results[0]["mean_cost"], results[-1]["mean_cost"]
    print(f"\nRelative improvement vs round 0 on held-out days: {100 * (base - champ) / base:.1f}%")
    (ROOT / "runs" / "heldout_result.json").write_text(json.dumps({"run": run["id"], "results": results}, indent=1))


if __name__ == "__main__":
    main()
