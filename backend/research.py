"""Read-only summary of saved evolve.py runs. Parses JSON files only: no policy code is loaded,
returned or executed, and nothing is evaluated here."""

from __future__ import annotations

import json
from pathlib import Path

# Files in runs/ that are not evolve runs (or duplicate one).
NOT_RUNS = {"latest.json", "operations-state.json", "heldout_result.json"}


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def summarize_run(doc: dict, path: Path) -> dict:
    rounds = [r for r in doc.get("rounds", []) if isinstance(r, dict)]
    last = rounds[-1] if rounds else None
    critic = [r["critic"] for r in rounds if isinstance(r.get("critic"), dict)]
    return {
        "id": doc.get("id"), "file": path.name, "name": doc.get("name"), "mode": doc.get("mode"),
        "team": bool(doc.get("team", False)), "agents": doc.get("agents"), "start": doc.get("start"),
        "started_at": doc.get("started_at"), "rounds_requested": doc.get("rounds_requested"),
        "rounds_completed": len(rounds), "rounds_accepted": sum(bool(r.get("accepted")) for r in rounds),
        "baseline": doc.get("baseline"),                       # round-0 champion, dev and validation
        "references": doc.get("references"),                   # naive / insertion, dev and validation
        "champion": None if last is None else {"dev_cost": _num(last.get("champion_dev")),
                                               "val_cost": _num(last.get("champion_val")),
                                               "val": last.get("champion")},
        "curve": [{"round": r.get("round"), "champion_val": _num(r.get("champion_val")),
                   "accepted": bool(r.get("accepted")), "seconds": _num(r.get("seconds")),
                   "proposer_tokens": _num(r.get("round_tokens")),
                   "critic_tokens": _num(r["critic"].get("tokens")) if isinstance(r.get("critic"), dict) else None,
                   "critic_seconds": _num(r["critic"].get("seconds")) if isinstance(r.get("critic"), dict) else None,
                   "critic_error": r["critic"].get("error") or None if isinstance(r.get("critic"), dict) else None}
                  for r in rounds],
        "proposer_tokens_total": _num(last.get("tokens")) if last else None,
        "critic_tokens_total": sum(_num(c.get("tokens")) or 0 for c in critic) if critic else None,
        "lessons": doc.get("lessons", []) if doc.get("team") else [],
        "strategies": doc.get("strategies") if doc.get("team") else None,
    }


def research_summary(runs_dir: Path) -> dict:
    runs, skipped = [], []
    files = sorted((p for p in runs_dir.glob("*.json") if p.name not in NOT_RUNS),
                   key=lambda p: p.stat().st_mtime, reverse=True) if runs_dir.is_dir() else []
    for path in files:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            skipped.append({"file": path.name, "reason": type(e).__name__})
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("rounds"), list) or "heldout_hash" not in doc:
            skipped.append({"file": path.name, "reason": "not an evolve run"})
            continue
        runs.append(summarize_run(doc, path))
    heldout = None
    hp = runs_dir / "heldout_result.json"
    if hp.is_file():
        try:
            heldout = json.loads(hp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            skipped.append({"file": hp.name, "reason": "unreadable"})
    return {"runs": runs, "latest_id": runs[0]["id"] if runs else None, "heldout": heldout, "skipped": skipped}
