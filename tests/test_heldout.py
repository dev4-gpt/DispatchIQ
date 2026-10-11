"""heldout.py run-once rules. These tests never score held-out days: split() is patched to dev seeds."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import heldout  # noqa: E402
from dispatchiq.sandbox import Evaluation  # noqa: E402

PUBLISHED = (ROOT / "HELDOUT_HASH.txt").read_text().strip()
NAIVE = (ROOT / "dispatchiq/policies/naive.py").read_text()
INSERTION = (ROOT / "dispatchiq/policies/insertion.py").read_text()


def run_file(tmp, name, code, val, agents=6, mode="llm"):
    doc = {"id": name, "mode": mode, "agents": agents, "heldout_hash": PUBLISHED, "champion_code": code,
           "rounds": [{"round": 1, "champion_val": val}], "rounds_requested": 1}
    (tmp / f"{name}.json").write_text(json.dumps(doc))


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(heldout, "RUNS", tmp_path)
    monkeypatch.setattr(heldout, "split", lambda name: [0, 1])  # dev seeds, never the held-out days
    monkeypatch.setattr(heldout, "heldout_hash", lambda: PUBLISHED)
    run_file(tmp_path, "random", NAIVE, 1700.0, mode="random_search")
    run_file(tmp_path, "llm-plain", INSERTION, 1300.0)
    run_file(tmp_path, "llm-team", NAIVE, 1250.0)  # lowest 6-agent LLM validation: the final solution
    run_file(tmp_path, "llm-team-v2-1agent", NAIVE, 1000.0, agents=1)  # lower, but 1 agent: not eligible
    return tmp_path


def test_scores_all_champions_and_marks_the_final_solution(setup, capsys):
    assert heldout.main([]) == 0
    out = capsys.readouterr().out
    assert out.index("Final solution, named before scoring") < out.index("Policy")  # named before any score
    doc = json.loads((setup / "heldout_result.json").read_text())
    assert doc["final_solution"] == "LLM team v1" and doc["format"] == 2
    assert [r["policy"] for r in doc["results"]] == ["naive (reference)", "insertion (reference)", "random search",
                                                     "LLM plain", "LLM team v1"]
    assert [r["final_solution"] for r in doc["results"]] == [False, False, False, False, True]
    assert "LLM team v2, 1 agent" not in out and "<- final solution" in out
    # Once: a second invocation refuses.
    assert heldout.main([]) == 1 and "Not repeating" in capsys.readouterr().out


def test_failure_prints_no_scores_and_writes_nothing(setup, capsys, monkeypatch):
    calls = []

    def flaky(code, days, timeout):
        calls.append(code)
        if len(calls) == 3:  # third policy times out after two succeeded
            return Evaluation(100000.0, len(days), ["timeout after 300s"])
        from dispatchiq.sandbox import evaluate
        return evaluate(code, days, timeout=timeout)

    monkeypatch.setattr(heldout, "evaluate", flaky)
    assert heldout.main([]) == 2
    out = capsys.readouterr().out
    assert "NO HELD-OUT SCORES PRINTED" in out
    assert "vs naive" not in out and "<- final solution" not in out  # no score table at all
    assert not (setup / "heldout_result.json").exists()  # not a run: may be retried
    monkeypatch.setattr(heldout, "evaluate", lambda code, days, timeout: __import__("dispatchiq.sandbox").sandbox.evaluate(code, days))
    assert heldout.main([]) == 0  # the retry is the run


def test_dry_run_scores_nothing(setup, capsys, monkeypatch):
    monkeypatch.setattr(heldout, "evaluate", lambda *a, **k: pytest.fail("dry run must not score"))
    assert heldout.main(["--dry-run"]) == 0
    assert "LLM team v1" in capsys.readouterr().out and not (setup / "heldout_result.json").exists()


def test_refuses_on_hash_mismatch_or_no_eligible_run(setup, capsys, monkeypatch):
    monkeypatch.setattr(heldout, "heldout_hash", lambda: "different")
    assert heldout.main([]) == 1
    monkeypatch.setattr(heldout, "heldout_hash", lambda: PUBLISHED)
    for name in ("llm-plain", "llm-team"):
        (setup / f"{name}.json").unlink()
    assert heldout.main([]) == 1 and "names no final solution" in capsys.readouterr().out
