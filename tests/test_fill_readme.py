"""fill_readme.py fills only the marked blocks, only from files that exist. Fixture data; README.md untouched."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fill_readme  # noqa: E402

TEXT = """# Title
keep this 123
<!-- BEGIN heldout-headline -->
pending
<!-- END heldout-headline -->
middle
<!-- BEGIN heldout-table -->
pending table
<!-- END heldout-table -->
<!-- BEGIN single-agent -->
pending single
<!-- END single-agent -->
tail
"""


def write_run(tmp, name, agents, vals, stopped=None):
    rounds = [{"round": i + 1, "champion_val": v, "elapsed_seconds": 100.0 * (i + 1), "champion": {"mean_cost": v}}
              for i, v in enumerate(vals)]
    doc = {"id": name, "mode": "llm", "agents": agents, "team": True, "critic_version": "v2", "rounds": rounds,
           "rounds_requested": 48 if agents == 1 else len(vals), "stopped": stopped,
           "baseline": {"val": {"mean_cost": 2000.0}},
           "references": {"insertion": {"val": {"mean_cost": 1800.0}}, "naive": {"val": {"mean_cost": 2000.0}}}}
    (tmp / f"{name}.json").write_text(json.dumps(doc))


def test_leaves_blanks_until_data_exists(tmp_path):
    write_run(tmp_path, "llm-team-v2", 6, [1400.0, 1300.0])
    write_run(tmp_path, "llm-team-v2-1agent", 1, [1500.0])  # still running: no stop record
    text, report = fill_readme.fill(TEXT, tmp_path)
    assert text == TEXT and set(report.values()) == {"no data yet; left blank"}


def test_fills_heldout_and_single_agent(tmp_path):
    write_run(tmp_path, "llm-team-v2", 6, [1400.0, 1300.0])
    write_run(tmp_path, "llm-team-v2-1agent", 1, [1500.0 - 10 * i for i in range(10)],
              stopped={"reason": "deadline", "stop_at": "18:30", "rounds_completed": 10})
    (tmp_path / "heldout_result.json").write_text(json.dumps({"format": 2, "final_solution": "LLM team v2",
        "finished_at": "t", "results": [
            {"policy": "naive (reference)", "mean_cost": 2000.0, "on_time_pct": 50.0, "missed_promises": 5,
             "emergencies": 90, "bumped_booked": 10, "moved_healthy": 0, "infeasible": 0, "final_solution": False},
            {"policy": "LLM team v2", "mean_cost": 1500.0, "on_time_pct": 70.0, "missed_promises": 2,
             "emergencies": 90, "bumped_booked": 40, "moved_healthy": 50, "infeasible": 0, "final_solution": True,
             "validation_cost": 1300.0}]}))
    text, report = fill_readme.fill(TEXT, tmp_path)
    assert set(report.values()) == {"filled"}
    assert "keep this 123" in text and "middle" in text and text.endswith("tail\n")  # outside markers untouched
    assert "**LLM team v2**" in text and "**1500.0**" in text and "25.0% lower than the naive baseline" in text
    assert "| **LLM team v2 (final solution)** | 1500.0 | +25.0% |" in text
    assert "| LLM team v2, 1 agent | 1 | 10 | 1430.0 | 800 s | 1410.0 | 1000 s |" in text
    assert "stopped at 10 rounds" in text
    again, _ = fill_readme.fill(text, tmp_path)
    assert again == text  # idempotent: markers survive
