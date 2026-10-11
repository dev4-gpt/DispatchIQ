"""evolve.py --team (shared memory + critic) and plain mode, driven by a stubbed OpenAI client."""

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import evolve  # noqa: E402
from dispatchiq import proposers  # noqa: E402

INSERTION = (ROOT / "dispatchiq/policies/insertion.py").read_text()
BROKEN = "def replan(state):\n    raise ValueError('stub failure')\n"


class Stub:
    """Fake OpenAI client. Records every prompt; answers as a proposer or as the critic."""

    calls: list[dict] = []
    critic_replies: list[str] = []

    def __init__(self, **kw):
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, **kw):
        system, user = kw["messages"][0]["content"], kw["messages"][1]["content"]
        critic = system.startswith("You are the critic")
        Stub.calls.append({"critic": critic, "user": user})
        if critic:
            text, tokens = Stub.critic_replies.pop(0), 50
        else:
            code = BROKEN if "FAIL on purpose" in user else INSERTION
            text, tokens = "```python\n" + code + "\n```", 100
        msg = types.SimpleNamespace(content=text)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)],
                                     usage=types.SimpleNamespace(total_tokens=tokens))


@pytest.fixture
def stub(monkeypatch, tmp_path):
    import openai
    monkeypatch.setattr(openai, "OpenAI", Stub)
    monkeypatch.setattr(proposers, "providers_from_env", lambda: [proposers.Provider("stub", "http://x", "k", "m")])
    monkeypatch.setattr(evolve, "RUNS", tmp_path)
    Stub.calls, Stub.critic_replies = [], []
    return tmp_path


def critic_json(lessons, strategies=None):
    return "Sure:\n```json\n" + json.dumps({"lessons": lessons, "strategies": strategies}) + "\n```"


def test_team_memory_critic_and_lessons(stub):
    Stub.critic_replies = [
        critic_json(["Insertion beats naive bumping.", "Keep emergencies first."],
                    ["FAIL on purpose", "Keep cheapest insertion and tune postponement."]),
        critic_json(["Raising errors fails every day."]),
    ]
    evolve.main(["--rounds", "2", "--agents", "2", "--team", "--name", "t"])
    run = json.loads((stub / "t.json").read_text())

    assert run["team"] is True and run["references"]["insertion"]["val"]["mean_cost"] > 0
    # Memory: one row per candidate per round, with strategy, cost, gap and failure detail.
    assert [(m["round"], m["agent"]) for m in run["memory"]] == [(1, 0), (1, 1), (2, 0), (2, 1)]
    r1 = run["memory"][0]
    assert r1["dev_cost"] is not None and r1["gap_to_champion"] < 0 and r1["errors"] == []
    failed = run["memory"][2]
    assert failed["strategy"] == "FAIL on purpose" and failed["dev_cost"] is None
    assert failed["infeasible_days"] == 30 and "stub failure" in failed["errors"][0]
    assert any(m["promoted"] for m in run["memory"] if m["round"] == 1)

    # Critic: per-round lessons, tokens and seconds; lessons carry forward; hints rewritten.
    c1, c2 = run["rounds"][0]["critic"], run["rounds"][1]["critic"]
    assert c1["tokens"] == 50 and c1["seconds"] >= 0 and c1["error"] == ""
    assert run["lessons"] == ["Insertion beats naive bumping.", "Keep emergencies first.", "Raising errors fails every day."]
    assert run["strategies"] == ["FAIL on purpose", "Keep cheapest insertion and tune postponement."]
    assert run["rounds"][0]["round_tokens"] == 200  # proposer tokens only; critic tokens are separate

    # Round-2 proposer prompts carry the lessons and the round-1 table, and use the rewritten hints.
    round2 = [c["user"] for c in Stub.calls if not c["critic"]][2:]
    assert all("Insertion beats naive bumping." in u and "round 1 agent 0" in u for u in round2)
    assert any("Your angle this round: FAIL on purpose" in u for u in round2)
    # The critic saw round 2's failure.
    assert "FAILED: 30 infeasible dev days" in [c["user"] for c in Stub.calls if c["critic"]][1]


def test_lessons_capped_and_critic_failure_recorded(stub):
    Stub.critic_replies = [critic_json([f"r1 lesson {i}" for i in range(7)]),  # only 5 kept per round
                           critic_json([f"r2 lesson {i}" for i in range(5)]),
                           "not json at all",
                           critic_json([f"r4 lesson {i}" for i in range(5)])]
    evolve.main(["--rounds", "4", "--agents", "1", "--team", "--name", "cap"])
    run = json.loads((stub / "cap.json").read_text())
    assert len(run["rounds"][0]["critic"]["lessons"]) == 5
    bad = run["rounds"][2]["critic"]
    assert bad["error"].startswith("critic failed") and bad["tokens"] == 0 and bad["lessons"] == []
    assert len(run["lessons"]) == 10 and run["lessons"][-1] == "r4 lesson 4" and "r1 lesson 0" not in run["lessons"]
    assert len(run["rounds"]) == 4  # a failed critic does not stop the run


def test_plain_mode_unchanged(stub):
    evolve.main(["--rounds", "1", "--agents", "2", "--name", "plain"])
    run = json.loads((stub / "plain.json").read_text())
    assert run["team"] is False and "memory" not in run and "critic" not in run["rounds"][0]
    assert not any(c["critic"] for c in Stub.calls)
    assert all("Team lessons" not in c["user"] for c in Stub.calls)
    assert run["rounds"][0]["accepted"] and run["rounds"][0]["round_tokens"] == 200


def test_team_requires_llm_mode(stub):
    with pytest.raises(SystemExit):
        evolve.main(["--rounds", "1", "--mode", "random", "--team"])


def test_parse_critic_validates():
    out = proposers.parse_critic('{"lessons": ["a", "", "b"], "strategies": ["x"]}')
    assert out == {"lessons": ["a", "b"], "strategies": ["x"]}
    assert proposers.parse_critic('{"lessons": [], "strategies": []}')["strategies"] is None
    with pytest.raises(ValueError):
        proposers.parse_critic("no json")
    with pytest.raises(ValueError):
        proposers.parse_critic('{"lessons": "not a list"}')


def test_stop_at_deadline_records_rounds(stub):
    evolve.main(["--rounds", "3", "--agents", "1", "--mode", "random", "--name", "past", "--stop-at", "00:00"])
    run = json.loads((stub / "past.json").read_text())
    assert run["stopped"]["rounds_completed"] == 0 and run["stopped"]["stop_at"] == "00:00" and run["rounds"] == []
    from dispatchiq.scoreboard import run_status
    assert run_status(run).startswith("stopped at 0 rounds")
    evolve.main(["--rounds", "2", "--agents", "1", "--mode", "random", "--name", "future", "--stop-at", "23:59"])
    run = json.loads((stub / "future.json").read_text())
    assert run["stopped"] is None and len(run["rounds"]) == 2 and run["rounds"][1]["elapsed_seconds"] >= 0
    with pytest.raises(SystemExit):
        evolve.main(["--rounds", "1", "--mode", "random", "--name", "bad", "--stop-at", "6:30pm"])
