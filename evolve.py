"""Self-improving agent team: N agents propose re-plan code each round; the checker decides.

    python evolve.py --rounds 8 --agents 6            # LLM agents (Luminal first, see README)
    python evolve.py --rounds 8 --agents 6 --mode random   # no-LLM random-search baseline / offline test
    python evolve.py --rounds 8 --agents 6 --name llm-plain  # saved as runs/llm-plain.json, never overwritten

Selection is honest:
- candidates are scored on DEV days; the best is promoted only if it also beats the
  champion on VALIDATION days;
- HELD-OUT days are never touched here (see heldout.py), and their hash is checked
  against the committed HELDOUT_HASH.txt.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dispatchiq.generator import heldout_hash, split
from dispatchiq import team_v2
from dispatchiq.proposers import STRATEGIES, Critic, LLMProposer, RandomSearchProposer
from dispatchiq.sandbox import Evaluation, cost_breakdown, evaluate

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
REFERENCES = {"naive": "dispatchiq/policies/naive.py", "insertion": "dispatchiq/policies/insertion.py"}
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
MAX_LESSONS = 10  # lessons carried across rounds in team mode (most recent kept)


def save_json(path: Path, doc: dict) -> None:
    """Write via a temp file and rename, so a reader (or a parallel run) never sees half a file."""
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1))
    os.replace(tmp, path)


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
    uri = os.getenv("MONGODB_URI")
    if not uri:
        return
    try:
        from pymongo import MongoClient
        MongoClient(uri, serverSelectionTimeoutMS=3000)["dispatchiq"]["rounds"].insert_one(dict(doc))
    except Exception as e:
        print(f"[mongo] skipped: {e}", file=sys.stderr)


def memory_rows(r: int, cands: list[dict], beat: float, strategies: list[str], winner: dict | None,
                families: list[str] | None = None) -> list[dict]:
    """One row per candidate: what was tried, how it scored on dev, and why it failed if it did.
    `strategies` is the hint list (agent i used strategies[i mod n]); `families` the v2 family id per agent."""
    rows = []
    for c in cands:
        ev = c.get("dev")
        if ev is None:
            errors = [c.get("error", "")]
        else:
            errors = ev.errors[:2]
        cost = round(ev.mean_cost, 1) if ev is not None and ev.infeasible == 0 else None
        rows.append({"round": r, "agent": c["agent"],
                     "strategy": strategies[c["agent"] % len(strategies)] if strategies else "",
                     "note": c.get("note", ""), "dev_cost": cost,
                     "gap_to_champion": round(cost - beat, 1) if cost is not None else None,
                     "infeasible_days": ev.infeasible if ev is not None else None,
                     "errors": [e[:200] for e in errors if e], "promoted": c is winner,
                     **({"family": families[c["agent"]]} if families else {})})
    return rows


def format_memory(rows: list[dict]) -> str:
    lines = []
    for m in rows:
        if m["dev_cost"] is not None:
            result = f"dev cost {m['dev_cost']:.1f} (gap {m['gap_to_champion']:+.1f} vs champion)"
            result += ", PROMOTED" if m["promoted"] else ""
        elif m["infeasible_days"] is not None:
            result = f"FAILED: {m['infeasible_days']} infeasible dev days: {' | '.join(m['errors']) or 'no detail'}"
        else:
            result = f"FAILED before scoring: {' | '.join(m['errors']) or 'no detail'}"
        lines.append(f"- round {m['round']} agent {m['agent']} [{m['strategy']}]: {result}")
    return "\n".join(lines) or "(none)"


def team_context(memory: list[dict], lessons: list[str], r: int) -> str:
    recent = [m for m in memory if m["round"] >= r - 2]
    return ("Team lessons so far:\n" + ("\n".join(f"- {x}" for x in lessons) or "(none yet)")
            + "\n\nWhat the team tried in the last two rounds (gap < 0 means better than the champion it faced):\n"
            + format_memory(recent))


def run_critic(critic: Critic, fb: str, table: str, lessons: list[str], strategies: list[str]) -> dict:
    """A failed critic call is recorded and the round continues with the previous lessons and hints."""
    t0 = time.time()
    try:
        out, tokens, who = critic.review(fb, table, lessons, strategies)
        return {"lessons": out["lessons"], "strategies": out["strategies"], "tokens": tokens,
                "seconds": round(time.time() - t0, 1), "provider": who, "error": ""}
    except Exception as e:
        return {"lessons": [], "strategies": None, "tokens": 0, "seconds": round(time.time() - t0, 1),
                "provider": None, "error": f"critic failed: {e}"[:300]}


def run_critic_v2(providers, families, memory, table, fb, breakdown, lessons, r):
    """Critic v2 call; on failure the families and lessons stay as they were."""
    t0 = time.time()
    try:
        new_families, rec = team_v2.review(providers, families, memory, table, fb, breakdown, lessons, r)
        rec.update(seconds=round(time.time() - t0, 1), error="")
        return new_families, rec
    except Exception as e:
        return families, {"lessons": [], "refinements": None, "tokens": 0, "seconds": round(time.time() - t0, 1),
                          "provider": None, "error": f"critic failed: {e}"[:300]}


def stop_deadline(hhmm: str) -> float:
    """Today's local HH:MM as a Unix time."""
    try:
        hour, minute = (int(x) for x in hhmm.split(":"))
        t = time.localtime()
        return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, 0, 0, -1))
    except (ValueError, OverflowError):
        sys.exit(f"--stop-at must be HH:MM (24-hour local time), got {hhmm!r}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--agents", type=int, default=4)
    ap.add_argument("--mode", choices=["llm", "random"], default="llm")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--start", default="dispatchiq/policies/naive.py", help="round-0 champion")
    ap.add_argument("--name", help="save as runs/<name>.json (refuses to overwrite) instead of a timestamp; "
                                   "runs/latest.json is only written for unnamed runs")
    ap.add_argument("--stop-at", metavar="HH:MM",
                    help="local-time deadline: do not start a round that would likely end after it "
                         "(estimated from the slowest round so far); the run records where it stopped")
    ap.add_argument("--team", action="store_true",
                    help="LLM team mode: shared memory of attempts in every prompt, plus a critic call per round")
    ap.add_argument("--critic", choices=["v1", "v2"], default="v1",
                    help="team critic: v1 may rewrite all hints; v2 keeps six fixed approach families (one per slot, "
                         "rotating when agents < 6), one refinement per family, one wildcard (see dispatchiq/team_v2.py)")
    args = ap.parse_args(argv)
    if args.critic == "v2" and not args.team:
        sys.exit("--critic v2 needs --team.")
    deadline = stop_deadline(args.stop_at) if args.stop_at else None
    if args.team and args.mode != "llm":
        sys.exit("--team needs --mode llm (the critic is an LLM call).")
    if args.name is not None:
        if not NAME_RE.match(args.name) or args.name in ("latest", "heldout_result"):
            sys.exit(f"Invalid run name {args.name!r}: use letters, digits, '-', '_' or '.'.")
        if (RUNS / f"{args.name}.json").exists():
            sys.exit(f"runs/{args.name}.json already exists. Pick another --name; runs are never overwritten.")

    published = ROOT / "HELDOUT_HASH.txt"
    h = heldout_hash()
    if published.exists() and published.read_text().strip() != h:
        sys.exit("Held-out days changed since the hash was published. Refusing to run.")

    proposer = LLMProposer() if args.mode == "llm" else RandomSearchProposer()
    if args.mode == "llm" and not proposer.available():
        sys.exit("No LLM provider configured (set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL). Use --mode random to test offline.")
    rng = random.Random(args.seed)
    dev, val = split("dev"), split("validation")

    run_t0 = time.time()  # wall clock for the whole run, including scoring the start and references
    champ_code = (ROOT / args.start).read_text()
    champ_dev, champ_val = evaluate(champ_code, dev), evaluate(champ_code, val)
    # Fixed, non-evolved reference policies scored on the same dev/validation days, so every run
    # file carries its own scoreboard (held-out days are never touched here).
    references = {}
    for ref, path in REFERENCES.items():
        code = (ROOT / path).read_text()
        references[ref] = {"path": path, "dev": evaluate(code, dev).summary(), "val": evaluate(code, val).summary()}
    run = {"id": args.name or time.strftime("%Y%m%d-%H%M%S"), "name": args.name, "mode": proposer.kind,
           "agents": args.agents, "rounds_requested": args.rounds, "seed": args.seed, "start": args.start,
           "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "heldout_hash": h,
           "baseline": {"dev": champ_dev.summary(), "val": champ_val.summary()}, "references": references,
           "rounds": [], "champion_code": champ_code, "round0_code": champ_code}
    paths = [RUNS / f"{run['id']}.json"] + ([] if args.name else [RUNS / "latest.json"])
    run["team"] = args.team
    if args.team:
        critic = Critic(proposer.providers)
        lessons, strategies = [], list(STRATEGIES)
        run.update(memory=[], lessons=lessons, strategies=strategies, critic_version=args.critic)
        if args.critic == "v2":
            families = team_v2.initial_families()
            run["families"] = families
    print(f"round 0  dev {champ_dev.mean_cost:7.1f}  val {champ_val.mean_cost:7.1f}  (start: {args.start})")
    print("         reference insertion  dev {:7.1f}  val {:7.1f}".format(
        references["insertion"]["dev"]["mean_cost"], references["insertion"]["val"]["mean_cost"]))

    run["stop_at"], run["stopped"] = args.stop_at, None
    slowest = 0.0
    for r in range(1, args.rounds + 1):
        if deadline is not None and time.time() + slowest > deadline:
            run["stopped"] = {"reason": "deadline", "stop_at": args.stop_at, "rounds_completed": r - 1,
                              "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
            print(f"stopped at {r - 1} rounds: next round would likely end after {args.stop_at}")
            for path in paths:
                save_json(path, run)
            break
        fb = feedback(champ_dev)
        t0, tokens0 = time.time(), proposer.tokens

        agent_seeds = [rng.random() for _ in range(args.agents)]  # fixed per agent, independent of thread timing
        fam_ids = None
        if args.team and args.critic == "v2":
            assigned = team_v2.assign(families, args.agents, r)
            hints, fam_ids = [team_v2.hint(f) for f in assigned], [f["id"] for f in assigned]
        elif args.team:
            hints = [strategies[i % len(strategies)] for i in range(args.agents)]

        def one(i: int):
            try:
                if args.team:
                    code, note = proposer.propose(i, champ_code, fb, random.Random(agent_seeds[i]),
                                                  strategy=hints[i],
                                                  team_context=team_context(run["memory"], lessons, r))
                else:
                    code, note = proposer.propose(i, champ_code, fb, random.Random(agent_seeds[i]))
            except Exception as e:
                return {"agent": i, "error": f"proposal failed: {e}"[:300]}
            ev = evaluate(code, dev)
            return {"agent": i, "note": note, "code": code, "dev": ev, "error": "; ".join(ev.errors[:2])}

        with ThreadPoolExecutor(max_workers=args.agents) as pool:
            cands = list(pool.map(one, range(args.agents)))
        seconds = round(time.time() - t0, 1)
        beat = champ_dev.mean_cost  # the champion this round's candidates were trying to beat
        ok = [c for c in cands if "dev" in c and c["dev"].infeasible == 0]
        accepted = False
        best = min(ok, key=lambda c: c["dev"].mean_cost) if ok else None
        if best and best["dev"].mean_cost < champ_dev.mean_cost:
            best_val = evaluate(best["code"], val)
            if best_val.infeasible == 0 and best_val.mean_cost < champ_val.mean_cost:
                champ_code, champ_dev, champ_val, accepted = best["code"], best["dev"], best_val, True
        critic_rec = None
        if args.team:
            rows = memory_rows(r, cands, beat, hints, best if accepted else None, fam_ids)
            run["memory"].extend(rows)
            if args.critic == "v2":
                breakdown = cost_breakdown(champ_dev)
                families, critic_rec = run_critic_v2(proposer.providers, families, run["memory"], format_memory(rows),
                                                     feedback(champ_dev), breakdown, lessons, r)
                critic_rec["champion_breakdown_dev"] = breakdown
                run["families"] = families
            else:
                critic_rec = run_critic(critic, feedback(champ_dev), format_memory(rows), lessons, strategies)
                if critic_rec["strategies"]:
                    strategies = critic_rec["strategies"]
            lessons = (lessons + [x for x in critic_rec["lessons"] if x not in lessons])[-MAX_LESSONS:]
            run["lessons"], run["strategies"] = lessons, strategies
        rec = {
            "round": r, "seconds": seconds, "accepted": accepted,
            "promoted_agent": best["agent"] if accepted else None,
            # seconds = proposals + dev scoring; wall/elapsed also include validation scoring and the critic.
            "wall_seconds": round(time.time() - t0, 1), "elapsed_seconds": round(time.time() - run_t0, 1),
            "champion_dev": round(champ_dev.mean_cost, 1), "champion_val": round(champ_val.mean_cost, 1),
            "champion": champ_val.summary(), "tokens": proposer.tokens, "round_tokens": proposer.tokens - tokens0,
            "candidates": [{"agent": c["agent"], "note": c.get("note", ""),
                            "dev_cost": round(c["dev"].mean_cost, 1) if "dev" in c else None,
                            "infeasible": c["dev"].infeasible if "dev" in c else None,
                            "error": c.get("error", "")} for c in cands],
        }
        slowest = max(slowest, rec["wall_seconds"])
        if critic_rec is not None:
            rec["critic"] = critic_rec
        if fam_ids is not None:
            rec["families_per_agent"] = [{"agent": i, "family": fam_ids[i], "name": assigned[i]["name"],
                                          "origin": assigned[i]["origin"], "hint": hints[i]} for i in range(args.agents)]
        run["rounds"].append(rec)
        run["champion_code"] = champ_code
        log_mongo({"run": run["id"], **{k: v for k, v in rec.items()}})
        print(f"round {r}  dev {champ_dev.mean_cost:7.1f}  val {champ_val.mean_cost:7.1f}  "
              f"{'ACCEPTED' if accepted else 'kept    '}  feasible {len(ok)}/{len(cands)}  {rec['seconds']}s  "
              f"tokens {rec['round_tokens']}"
              + (f"  critic {critic_rec['seconds']}s/{critic_rec['tokens']} tok"
                 f"{' ERROR' if critic_rec['error'] else ''}" if critic_rec else ""))
        for path in paths:
            save_json(path, run)
    print(f"saved runs/{run['id']}.json")


if __name__ == "__main__":
    main()
