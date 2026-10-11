"""Self-improving agent team: N agents propose re-plan code each round; the checker decides.

    python evolve.py --rounds 8 --agents 6            # LLM agents (Luminal first, see README)
    python evolve.py --rounds 8 --agents 6 --mode random   # no-LLM random-search baseline / offline test

Selection is honest:
- candidates are scored on DEV days; the best is promoted only if it also beats the
  champion on VALIDATION days;
- HELD-OUT days are never touched here (see heldout.py), and their hash is checked
  against the committed HELDOUT_HASH.txt.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dispatchiq.generator import heldout_hash, split
from dispatchiq.proposers import LLMProposer, RandomSearchProposer
from dispatchiq.sandbox import Evaluation, evaluate

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"


def feedback(ev: Evaluation, k: int = 3) -> str:
    worst = sorted(ev.per_seed.items(), key=lambda kv: -kv[1].cost)[:k]
    lines = [f"Mean cost on dev days: {ev.mean_cost:.0f} (infeasible days: {ev.infeasible})"]
    for seed, s in worst:
        if s.feasible:
            lines.append(f"- day {seed}: cost {s.cost:.0f}; travel {s.travel:.0f}; weighted lateness "
                         f"{s.weighted_late:.0f}; late jobs {s.late_jobs}; unscheduled {s.unassigned}; "
                         f"moved {s.moved}; emergency response {s.emergency_response:.0f} min; overtime {s.overtime:.0f}")
        else:
            lines.append(f"- day {seed}: INFEASIBLE: {'; '.join(s.violations[:3])}")
    return "\n".join(lines)


def log_mongo(doc: dict) -> None:
    import os
    uri = os.getenv("MONGODB_URI")
    if not uri:
        return
    try:
        from pymongo import MongoClient
        MongoClient(uri, serverSelectionTimeoutMS=3000)["dispatchiq"]["rounds"].insert_one(dict(doc))
    except Exception as e:
        print(f"[mongo] skipped: {e}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--agents", type=int, default=4)
    ap.add_argument("--mode", choices=["llm", "random"], default="llm")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--start", default="dispatchiq/policies/naive.py", help="round-0 champion")
    args = ap.parse_args()

    published = ROOT / "HELDOUT_HASH.txt"
    h = heldout_hash()
    if published.exists() and published.read_text().strip() != h:
        sys.exit("Held-out days changed since the hash was published. Refusing to run.")

    proposer = LLMProposer() if args.mode == "llm" else RandomSearchProposer()
    if args.mode == "llm" and not proposer.available():
        sys.exit("No LLM provider configured (set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL). Use --mode random to test offline.")
    rng = random.Random(args.seed)
    dev, val = split("dev"), split("validation")

    champ_code = (ROOT / args.start).read_text()
    champ_dev, champ_val = evaluate(champ_code, dev), evaluate(champ_code, val)
    run = {"id": time.strftime("%Y%m%d-%H%M%S"), "mode": proposer.kind, "agents": args.agents,
           "heldout_hash": h, "baseline": {"dev": champ_dev.summary(), "val": champ_val.summary()},
           "rounds": [], "champion_code": champ_code, "round0_code": champ_code}
    print(f"round 0  dev {champ_dev.mean_cost:7.1f}  val {champ_val.mean_cost:7.1f}  (start: {args.start})")

    for r in range(1, args.rounds + 1):
        fb = feedback(champ_dev)
        t0 = time.time()

        def one(i: int):
            try:
                code, note = proposer.propose(i, champ_code, fb, random.Random(rng.random()))
            except Exception as e:
                return {"agent": i, "error": f"proposal failed: {e}"[:300]}
            ev = evaluate(code, dev)
            return {"agent": i, "note": note, "code": code, "dev": ev, "error": "; ".join(ev.errors[:2])}

        with ThreadPoolExecutor(max_workers=args.agents) as pool:
            cands = list(pool.map(one, range(args.agents)))
        ok = [c for c in cands if "dev" in c and c["dev"].infeasible == 0]
        accepted = False
        best = min(ok, key=lambda c: c["dev"].mean_cost) if ok else None
        if best and best["dev"].mean_cost < champ_dev.mean_cost:
            best_val = evaluate(best["code"], val)
            if best_val.mean_cost < champ_val.mean_cost:
                champ_code, champ_dev, champ_val, accepted = best["code"], best["dev"], best_val, True
        rec = {
            "round": r, "seconds": round(time.time() - t0, 1), "accepted": accepted,
            "champion_dev": round(champ_dev.mean_cost, 1), "champion_val": round(champ_val.mean_cost, 1),
            "champion": champ_val.summary(), "tokens": proposer.tokens,
            "candidates": [{"agent": c["agent"], "note": c.get("note", ""),
                            "dev_cost": round(c["dev"].mean_cost, 1) if "dev" in c else None,
                            "infeasible": c["dev"].infeasible if "dev" in c else None,
                            "error": c.get("error", "")} for c in cands],
        }
        run["rounds"].append(rec)
        run["champion_code"] = champ_code
        log_mongo({"run": run["id"], **{k: v for k, v in rec.items()}})
        print(f"round {r}  dev {champ_dev.mean_cost:7.1f}  val {champ_val.mean_cost:7.1f}  "
              f"{'ACCEPTED' if accepted else 'kept    '}  feasible {len(ok)}/{len(cands)}  {rec['seconds']}s")
        RUNS.mkdir(exist_ok=True)
        for path in (RUNS / f"{run['id']}.json", RUNS / "latest.json"):
            path.write_text(json.dumps(run, indent=1))
    print(f"saved runs/{run['id']}.json")


if __name__ == "__main__":
    main()
