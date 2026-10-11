"""Critic v2: fixed approach families, one refinement each, one wildcard, coding fixes as lessons."""

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import evolve  # noqa: E402
from dispatchiq import proposers, team_v2  # noqa: E402
from dispatchiq.proposers import STRATEGIES  # noqa: E402

INSERTION = (ROOT / "dispatchiq/policies/insertion.py").read_text()
BROKEN = "def replan(state):\n    raise ValueError('stub failure')\n"


class Stub:
    calls: list[dict] = []
    critic_reply = None  # function(user_prompt) -> dict

    def __init__(self, **kw):
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, **kw):
        system, user = kw["messages"][0]["content"], kw["messages"][1]["content"]
        critic = system.startswith("You are the critic")
        Stub.calls.append({"critic": critic, "system": system, "user": user})
        if critic:
            text = json.dumps(Stub.critic_reply(user))
        else:  # the load-balance family always fails, so it becomes the weakest
            text = "```python\n" + (BROKEN if STRATEGIES[5] in user else INSERTION) + "\n```"
        msg = types.SimpleNamespace(content=text)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)],
                                     usage=types.SimpleNamespace(total_tokens=10))


@pytest.fixture
def stub(monkeypatch, tmp_path):
    import openai
    monkeypatch.setattr(openai, "OpenAI", Stub)
    monkeypatch.setattr(proposers, "providers_from_env", lambda: [proposers.Provider("stub", "http://x", "k", "m")])
    monkeypatch.setattr(evolve, "RUNS", tmp_path)
    Stub.calls = []
    Stub.critic_reply = lambda user: {"lessons": [], "refinements": {}, "wildcard": None}
    return tmp_path


def test_six_agents_fixed_families_refinements_and_coding_fixes(stub):
    def reply(user):
        return {"lessons": ["Unscheduled jobs dominate the breakdown."],
                "refinements": {"F1": "Compare start times including travel.", "F2": "Try or-opt moves too.",
                                "F3": "Fix the crash: set changed size during iteration, use a fresh list.",
                                "F4": "Sort by latest start, then 2-opt.", "F5": "Bump only priority-1 jobs."},
                # F6 omitted: it keeps its previous (empty) refinement and is not deleted
                "wildcard": None}
    Stub.critic_reply = reply
    evolve.main(["--rounds", "2", "--agents", "6", "--team", "--critic", "v2", "--name", "v2"])
    run = json.loads((stub / "v2.json").read_text())
    assert run["critic_version"] == "v2" and len(run["families"]) == 6
    for rec in run["rounds"]:
        fams = rec["families_per_agent"]
        assert len(fams) == 6 == run["agents"]  # hints always equal agents
        assert [f["family"] for f in fams] == ["F1", "F2", "F3", "F4", "F5", "F6"]  # one fixed family per slot
    c1 = run["rounds"][0]["critic"]
    assert c1["coding_fixes_moved_to_lessons"] == ["F3"] and c1["missing_refinements"] == ["F6"]
    assert any("set changed size" in l for l in run["lessons"])  # coding fix became a shared lesson
    fam = {f["id"]: f for f in run["families"]}
    assert fam["F3"]["refinement"] == "" and "crash" not in team_v2.hint(fam["F3"])  # never in a hint slot
    assert fam["F2"]["refinement"] == "Try or-opt moves too."
    # Round 2 prompts: each agent's hint is its family base plus the refinement; lessons are shared.
    round2 = [c for c in Stub.calls if not c["critic"]][6:]
    assert any(STRATEGIES[1] + " Refinement: Try or-opt moves too." in c["user"] for c in round2)
    assert all("set changed size" in c["user"] for c in round2)
    # The critic got the champion's dev cost breakdown, and its parts sum to the champion's dev cost.
    bd = c1["champion_breakdown_dev"]
    assert set(bd) == {"travel", "lateness", "unassigned", "churn", "emergency_wait", "overtime"}
    assert abs(sum(bd.values()) - run["rounds"][0]["champion_dev"]) < 1.0
    first_critic = next(c for c in Stub.calls if c["critic"])
    assert "Champion mean cost per dev day, by term: travel" in first_critic["user"]
    assert "APPROACH FAMILY" in first_critic["system"]


def test_one_agent_rotates_through_families(stub):
    evolve.main(["--rounds", "7", "--agents", "1", "--team", "--critic", "v2", "--name", "one"])
    run = json.loads((stub / "one.json").read_text())
    assert [r["families_per_agent"][0]["family"] for r in run["rounds"]] == ["F1", "F2", "F3", "F4", "F5", "F6", "F1"]
    assert all(len(r["families_per_agent"]) == 1 for r in run["rounds"])


def test_wildcard_replaces_only_the_weakest_after_two_rounds(stub):
    def reply(user):
        return {"lessons": [], "refinements": {},
                "wildcard": {"replace": "F6", "why_different": "a new idea",
                             "approach": "Solve each tech's remaining route exactly with dynamic programming over subsets."}}
    Stub.critic_reply = reply
    evolve.main(["--rounds", "3", "--agents", "6", "--team", "--critic", "v2", "--name", "wild"])
    run = json.loads((stub / "wild.json").read_text())
    w1, w2 = (run["rounds"][i]["critic"]["wildcard"] for i in (0, 1))
    assert not w1["accepted"] and w1["reason"] == "no family eligible this round"  # F6 tried in 1 round only
    assert w2["accepted"] and w2["replaced"] == "F6" and w2["new_id"] == "W2"  # F6 failed twice: weakest
    assert [f["family"] for f in run["rounds"][2]["families_per_agent"]] == ["F1", "F2", "F3", "F4", "F5", "W2"]
    assert len(run["families"]) == 6 and sum(f["origin"] != "original" for f in run["families"]) == 1


def _memory(rows):
    return [{"round": r, "agent": 0, "family": fid, "dev_cost": None if gap is None else 100 + gap,
             "gap_to_champion": gap, "promoted": False} for r, fid, gap in rows]


def test_wildcard_rules_unit():
    fams = team_v2.initial_families()
    mem = _memory([(1, f"F{i}", -5.0 * i) for i in range(1, 7)])
    assert team_v2.wildcard_eligible(fams, mem) is None  # nobody has 2 rounds yet
    mem += _memory([(2, f"F{i}", -5.0 * i) for i in range(1, 7)])
    assert team_v2.wildcard_eligible(fams, mem) == "F1"  # best gap -5 is the weakest
    mem += _memory([(3, "F2", None), (4, "F2", None)])
    eligible = team_v2.wildcard_eligible(fams, mem)
    assert eligible == "F1"  # F2 has a feasible -10 from rounds 1-2, so F1 stays weakest

    new = "Solve each technician's remaining route exactly with dynamic programming over subsets."
    ok = {"lessons": [], "refinements": {}, "wildcard": {"replace": "F1", "approach": new}}
    fams2, rec = team_v2.apply_critic(fams, ok, "F1", 3)
    assert rec["wildcard"]["accepted"] and [f["id"] for f in fams2][0] == "W3" and len(fams2) == 6
    # wrong target, a near-copy of another family, and a coding fix are all refused
    for wild, reason in (({"replace": "F2", "approach": new}, "only F1"),
                         ({"replace": "F1", "approach": STRATEGIES[2]}, "too similar"),
                         ({"replace": "F1", "approach": "Fix the KeyError crash in insertion."}, "coding fix")):
        _, rec = team_v2.apply_critic(fams, {"lessons": [], "refinements": {}, "wildcard": wild}, "F1", 3)
        assert not rec["wildcard"]["accepted"] and reason in rec["wildcard"]["reason"]
    # With a wildcard already in place, an original family cannot become a second one.
    mem2 = _memory([(4, "W3", 0.0), (5, "W3", -100.0)]) + mem
    assert team_v2.wildcard_eligible(fams2, mem2) is None  # weakest is an original; would be a second wildcard
    # Unknown keys are ignored, never added as families; families cannot be deleted.
    fams3, rec = team_v2.apply_critic(fams, {"lessons": [], "refinements": {"F9": "x"}, "wildcard": None}, None, 1)
    assert [f["id"] for f in fams3] == [f["id"] for f in fams] and rec["ignored_keys"] == ["F9"]


def test_critic_v2_needs_team_and_failure_keeps_families(stub):
    with pytest.raises(SystemExit):
        evolve.main(["--rounds", "1", "--agents", "1", "--critic", "v2", "--name", "x"])
    Stub.critic_reply = lambda user: "not json"  # json.dumps of a str is a JSON string, not an object
    evolve.main(["--rounds", "2", "--agents", "6", "--team", "--critic", "v2", "--name", "fail"])
    run = json.loads((stub / "fail.json").read_text())
    assert run["rounds"][0]["critic"]["error"].startswith("critic failed")
    assert [f["id"] for f in run["families"]] == ["F1", "F2", "F3", "F4", "F5", "F6"] and len(run["rounds"]) == 2
