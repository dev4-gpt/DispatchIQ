"""Scoreboard built only from saved run files (runs/<name>.json). Nothing is evaluated here.

    python -m dispatchiq.scoreboard          # print the comparison table

Every number comes from a run file: reference policies (naive, insertion) from the `references`
block that evolve.py scores on the same dev/validation days, champions from each run's last round.
A run that has not been saved yet is shown as missing, never estimated.
"""

from __future__ import annotations

import json
from pathlib import Path

from .proposers import STRATEGIES

RUNS = Path(__file__).resolve().parent.parent / "runs"

# Label -> run name (evolve.py --name). Order is the table order.
RUN_NAMES = {
    "random search": "random",
    "LLM plain": "llm-plain",
    "LLM team": "llm-team",
    "LLM team, 1 agent x 48 rounds": "llm-team-1agent",
    "LLM team, 1 agent x 8 rounds": "llm-team-1agent-8r",
    "LLM team, insertion start": "llm-team-insertion",
}
CURVE_RUNS = ("random search", "LLM plain", "LLM team")
FINAL_RULE_RUNS = ("LLM plain", "LLM team", "LLM team, insertion start")  # README: final-solution rule
PARALLEL_RUNS = ("LLM team", "LLM team, 1 agent x 8 rounds", "LLM team, 1 agent x 48 rounds")


def run_status(run: dict) -> str:
    """'saved', 'stopped at N rounds' (deadline), or 'in progress k/n rounds' (still running, or killed)."""
    rounds, wanted = len(run.get("rounds", [])), run.get("rounds_requested")
    if run.get("stopped"):
        return f"stopped at {run['stopped'].get('rounds_completed', rounds)} rounds (of {wanted}, deadline {run['stopped'].get('stop_at')})"
    if isinstance(wanted, int) and rounds < wanted:
        return f"in progress {rounds}/{wanted} rounds"
    return "saved"


def load_runs(runs_dir: Path = RUNS) -> dict[str, dict | None]:
    out = {}
    for label, name in RUN_NAMES.items():
        path = runs_dir / f"{name}.json"
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            out[label] = doc if isinstance(doc, dict) and isinstance(doc.get("rounds"), list) else None
        except (OSError, ValueError):
            out[label] = None
    return out


def references(runs: dict[str, dict | None]) -> tuple[dict, bool]:
    """Reference scores from the run files, and whether every run file agrees on them."""
    refs = [r["references"] for r in runs.values() if r and r.get("references")]
    if not refs:
        return {}, True
    return refs[0], all(r == refs[0] for r in refs)


def _row(policy: str, val: dict | None, **extra) -> dict:
    val = val or {}
    missed, emerg = val.get("missed_promises"), val.get("emergencies")
    return {"policy": policy, "val_cost": val.get("mean_cost"), "on_time_pct": val.get("on_time_pct"),
            "missed_promises": missed, "emergencies": emerg, "infeasible_days": val.get("infeasible"), **extra}


def scoreboard(runs: dict[str, dict | None]) -> list[dict]:
    refs, _ = references(runs)
    rows = [_row(f"{name} (reference)", refs.get(name, {}).get("val"), status="reference" if name in refs else "missing")
            for name in ("naive", "insertion")]
    for label, run in runs.items():
        if run is None:
            rows.append(_row(label, None, status="not run"))
            continue
        rounds = run["rounds"]
        last = rounds[-1] if rounds else {}
        critic = [r["critic"] for r in rounds if isinstance(r.get("critic"), dict)]
        rows.append(_row(label, last.get("champion"), status=run_status(run),
                         agents=run.get("agents"), rounds=len(rounds),
                         proposals=(run.get("agents") or 0) * len(rounds), start=run.get("start"),
                         proposer_tokens=last.get("tokens"),
                         critic_tokens=sum(c.get("tokens") or 0 for c in critic) if critic else None))
    return rows


def curves(runs: dict[str, dict | None]) -> dict[str, list[tuple[int, float]]]:
    """Champion validation cost after each round (round 0 = the starting policy)."""
    out = {}
    for label in CURVE_RUNS:
        run = runs.get(label)
        if run is None:
            continue
        pts = [(0, run["baseline"]["val"]["mean_cost"])]
        pts += [(r["round"], r["champion_val"]) for r in run["rounds"]]
        out[label] = pts
    return out


def critic_rounds(run: dict) -> list[dict]:
    return [{"round": r["round"], **r["critic"]} for r in run.get("rounds", []) if isinstance(r.get("critic"), dict)]


def pct_better(cost: float | None, base: float | None) -> float | None:
    """Percent cost reduction relative to `base` (positive = cheaper than base)."""
    if cost is None or not base:
        return None
    return round(100.0 * (base - cost) / base, 1)


def with_improvement(rows: list[dict]) -> list[dict]:
    naive = next((r["val_cost"] for r in rows if r["policy"] == "naive (reference)"), None)
    return [{**r, "val_vs_naive_pct": pct_better(r["val_cost"], naive)} for r in rows]


def heldout_rows(runs_dir: Path, runs: dict[str, dict | None]) -> tuple[list[dict], str | None]:
    """Rows of runs/heldout_result.json with % vs its round-0 row; None if heldout.py has not run.

    heldout.py's first row is the run's round-0 code. It is naive only if that run started from
    naive.py, so the baseline is named from the run file, not assumed.
    """
    path = runs_dir / "heldout_result.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], None
    results = doc.get("results") or []
    if not results:
        return [], None
    source = next((r for r in runs.values() if r and r.get("id") == doc.get("run")), None)
    start = (source or {}).get("start")
    base_label = ("naive" if start and start.endswith("naive.py") else f"round 0 ({start})" if start
                  else "round 0 (start policy unknown)")
    base = results[0].get("mean_cost")
    rows = [{**r, "vs_round0_pct": pct_better(r.get("mean_cost"), base)} for r in results]
    return rows, f"run {doc.get('run')}, baseline = {base_label}"


def timeline(run: dict) -> tuple[list[tuple[float, float]], str]:
    """(cumulative wall-clock seconds, champion validation cost) after each round.

    Uses the recorded elapsed_seconds when present (whole round, critic included). Older run files only
    have per-round `seconds` (+ critic seconds), so those are summed and labelled as such.
    """
    rounds = run.get("rounds", [])
    if rounds and all("elapsed_seconds" in r for r in rounds):
        return [(0.0, run["baseline"]["val"]["mean_cost"])] + [(r["elapsed_seconds"], r["champion_val"]) for r in rounds], "recorded"
    total, pts = 0.0, [(0.0, run["baseline"]["val"]["mean_cost"])]
    for r in rounds:
        total += (r.get("seconds") or 0) + ((r.get("critic") or {}).get("seconds") or 0)
        pts.append((round(total, 1), r["champion_val"]))
    return pts, "summed per-round seconds"


def seconds_to_beat(points: list[tuple[float, float]], target: float | None) -> float | None:
    if target is None:
        return None
    return next((t for t, cost in points if cost < target), None)


def parallelism(runs: dict[str, dict | None]) -> list[dict]:
    refs, _ = references(runs)
    insertion = refs.get("insertion", {}).get("val", {}).get("mean_cost")
    rnd = runs.get("random search")
    random_val = rnd["rounds"][-1]["champion_val"] if rnd and rnd.get("rounds") else None
    out = []
    for label in PARALLEL_RUNS:
        run = runs.get(label)
        if run is None:
            out.append({"run": label, "status": "not run"})
            continue
        pts, source = timeline(run)
        out.append({"run": label, "status": run_status(run),
                    "agents": run.get("agents"), "rounds": len(run["rounds"]),
                    "points": pts, "timing": source, "total_seconds": pts[-1][0],
                    "seconds_to_beat_insertion": seconds_to_beat(pts, insertion),
                    "seconds_to_beat_random": seconds_to_beat(pts, random_val),
                    "insertion_val": insertion, "random_val": random_val})
    return out


def _strategy_from_note(note: str) -> str:
    return note.split(" | ", 1)[1] if " | " in note else note


def loop_evidence(run: dict) -> list[dict]:
    """For each accepted round: the agent and hint that produced the new champion, and whether the
    critic had rewritten that hint. All derived from the saved round records."""
    hints, source = list(STRATEGIES), None  # hints in effect for the next round, and the critic round that set them
    memory = {(m["round"], m["agent"]): m for m in run.get("memory") or []}
    out = []
    for r in run.get("rounds", []):
        if r.get("accepted"):
            agent, how = r.get("promoted_agent"), "recorded"
            if agent is None:  # older files: same rule as evolve.py (lowest dev cost among fully feasible)
                ok = [c for c in r["candidates"] if c.get("infeasible") == 0 and c.get("dev_cost") is not None]
                best = min(ok, key=lambda c: c["dev_cost"]) if ok else None
                agent, how = (best["agent"] if best else None), "derived from candidate costs"
            cand = next((c for c in r["candidates"] if c["agent"] == agent), {})
            mem = memory.get((r["round"], agent))
            hint = mem["strategy"] if mem else _strategy_from_note(cand.get("note", ""))
            team = bool(run.get("team"))
            out.append({"round": r["round"], "agent": agent, "strategy": hint, "dev_cost": cand.get("dev_cost"),
                        "champion_val": r.get("champion_val"), "agent_source": how,
                        "hint_rewritten_by_critic": (hint not in STRATEGIES) if team else None,
                        "hints_set_in_round": source if team else None})
        crit = r.get("critic") or {}
        if crit.get("strategies"):
            hints, source = crit["strategies"], r["round"]
    return out


def final_pick(runs: dict[str, dict | None]) -> dict | None:
    """README rule: the 6-agent LLM run with the lowest saved validation cost."""
    eligible = [(r["rounds"][-1]["champion_val"], label, r) for label, r in runs.items()
                if label in FINAL_RULE_RUNS and r and r.get("rounds") and r.get("agents") == 6 and r.get("mode") == "llm"]
    if not eligible:
        return None
    val, label, r = min(eligible, key=lambda x: x[0])
    return {"run": label, "file": f"runs/{RUN_NAMES[label]}.json", "val_cost": val, "status": run_status(r),
            "candidates": {lbl: v for v, lbl, _ in eligible}}


def _fmt(x, spec):
    width = int(spec.split(".")[0].rstrip("df"))
    return "-".rjust(width) if x is None else format(x, spec)


def main() -> None:
    runs = load_runs()
    _, consistent = references(runs)
    print(f"{'Policy':34s} {'val cost':>9s} {'vs naive':>9s} {'on-time':>8s} {'missed':>8s} {'agents':>6s} {'rounds':>6s} {'props':>6s}  status")
    for r in with_improvement(scoreboard(runs)):
        missed = "-" if r["missed_promises"] is None else f"{r['missed_promises']}/{r['emergencies']}"
        vs = "-" if r["val_vs_naive_pct"] is None else f"{r['val_vs_naive_pct']:+.1f}%"
        print(f"{r['policy']:34s} {_fmt(r['val_cost'], '9.1f')} {vs:>9s} {_fmt(r['on_time_pct'], '7.1f')}{'%' if r['on_time_pct'] is not None else ' '} {missed:>8s} "
              f"{_fmt(r.get('agents'), '6d')} {_fmt(r.get('rounds'), '6d')} {_fmt(r.get('proposals'), '6d')}  {r['status']}")
    print("\nValidation days 100-129. vs naive = % lower cost than naive. "
          "missed = emergencies starting after their promised latest start / emergencies.")
    if not consistent:
        print("WARNING: run files disagree on reference scores; the table uses the first one found.")

    held, note = heldout_rows(RUNS, runs)
    print("\nHeld-out (50 days): " + ("not run yet (heldout.py)" if not held else note))
    for r in held:
        print(f"  {r['policy']:45s} {r['mean_cost']:8.1f}  {r['vs_round0_pct']:+.1f}% vs round 0")

    print("\nParallelism (cumulative wall-clock seconds):")
    for p in parallelism(runs):
        if p["status"] == "not run":
            print(f"  {p['run']:32s} not run")
            continue
        print(f"  {p['run']:32s} total {p['total_seconds']:7.1f}s  beat insertion at {_fmt(p['seconds_to_beat_insertion'], '7.1f')}s"
              f"  beat random at {_fmt(p['seconds_to_beat_random'], '7.1f')}s  ({p['timing']}; {p['status']})")

    pick = final_pick(runs)
    print("\nFinal-solution rule (README): lowest-validation 6-agent LLM run at 18:30.")
    print("  right now: " + ("no eligible run saved" if pick is None else
          f"{pick['run']} -> python heldout.py {pick['file']}  (val {pick['val_cost']:.1f}, {pick['status']}; "
          f"candidates {pick['candidates']})"))

    print("\nLoop evidence (accepted rounds):")
    for label, run in runs.items():
        if run is None or run.get("mode") == "random_search":
            continue
        for e in loop_evidence(run):
            crit = ("" if e["hint_rewritten_by_critic"] is None else
                    f"  critic hint (set round {e['hints_set_in_round']})" if e["hint_rewritten_by_critic"] else "  original hint")
            print(f"  {label:32s} round {e['round']:2d} agent {e['agent']}  val {e['champion_val']:.1f}  "
                  f"[{e['strategy'][:70]}]{crit}")


if __name__ == "__main__":
    main()
