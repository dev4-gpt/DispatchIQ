import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dispatchiq.generator import heldout_hash, make_day, split  # noqa: E402
from dispatchiq.model import Job, route_eval  # noqa: E402
from dispatchiq.sandbox import evaluate  # noqa: E402
from dispatchiq.simulate import W_CHURN, check, replan_state  # noqa: E402

TINY = {
    "time": 600, "min_per_km": 2.0,
    "techs": [
        {"id": "A", "name": "A", "skills": ["hvac"], "sick": False, "free_at": 600, "loc": [0, 0],
         "shift_end": 1020, "max_overtime": 60, "remaining": ["J1"]},
        {"id": "B", "name": "B", "skills": ["hvac", "plumbing"], "sick": False, "free_at": 600, "loc": [10, 0],
         "shift_end": 1020, "max_overtime": 60, "remaining": []},
        {"id": "C", "name": "C", "skills": ["hvac"], "sick": True, "free_at": 600, "loc": [5, 5],
         "shift_end": 1020, "max_overtime": 60, "remaining": ["J2"]},
    ],
    "jobs": {
        "J1": {"loc": [5, 0], "skill": "hvac", "duration": 60, "earliest": 600, "latest": 620, "priority": 2,
               "emergency": False, "release": 0, "morning_tech": "A"},
        "J2": {"loc": [10, 5], "skill": "plumbing", "duration": 30, "earliest": 600, "latest": 900, "priority": 1,
               "emergency": False, "release": 0, "morning_tech": "C"},
        "E0": {"loc": [0, 5], "skill": "hvac", "duration": 60, "earliest": 600, "latest": 720, "priority": 5,
               "emergency": True, "release": 600, "morning_tech": None},
    },
}


def test_checker_hand_computed_cost():
    s = check(TINY, {"A": ["J1"], "B": ["J2", "E0"], "C": []})
    assert s.feasible
    # A: travel 10 min, starts J1 at 610 (on time). B: J2 is 5 km = 10 min (start 610),
    # then E0 is 10 km = 20 min after J2 ends at 640 -> start 660, emergency wait 60.
    assert s.travel == 40
    assert s.weighted_late == 0
    assert s.emergency_response == 60
    assert s.moved == 0  # J2 came from a sick tech, so it is not churn
    assert s.cost == 40 + 60


def test_checker_rules():
    assert not check(TINY, {"A": ["J1"], "C": ["J2", "E0"]}).feasible             # sick tech used
    assert not check(TINY, {"A": ["J1", "J2", "E0"]}).feasible                    # A lacks plumbing
    assert not check(TINY, {"A": ["J1"], "B": ["J2"]}).feasible                   # emergency missing
    assert not check(TINY, {"A": ["J1", "E0"], "B": ["J2", "J1"]}).feasible       # J1 twice
    assert not check(TINY, "not a plan").feasible
    moved = check(TINY, {"A": ["E0"], "B": ["J2", "J1"]})
    assert moved.feasible and moved.moved == 1                                    # J1 moved off healthy A
    assert moved.cost >= W_CHURN


def test_unassigned_penalty_and_overtime():
    s = check(TINY, {"A": ["J1", "E0"], "B": []})
    assert s.feasible and s.unassigned == 1 and s.cost >= 150
    r = route_eval(1000, (0, 0), 1020, ["J1"], {"J1": Job("J1", (50, 0), "hvac", 60, 0, 2000, 1)})
    assert r.overtime == 1000 + 100 + 60 - 1020


def test_generator_is_deterministic_and_splits_disjoint():
    assert make_day(3).to_dict() == make_day(3).to_dict()
    d, v, h = map(set, (split("dev"), split("validation"), split("heldout")))
    assert not (d & v or d & h or v & h)
    assert heldout_hash() == (ROOT / "HELDOUT_HASH.txt").read_text().strip()


def test_baselines_feasible_on_dev():
    for name in ("naive", "insertion"):
        ev = evaluate((ROOT / f"dispatchiq/policies/{name}.py").read_text(), split("dev")[:10])
        assert ev.infeasible == 0, ev.errors


def test_sandbox_contains_bad_code():
    assert evaluate("def replan(state):\n    while True: pass\n", [0], timeout=3).infeasible == 1
    assert evaluate("def replan(state):\n    raise ValueError('x')\n", [0]).infeasible == 1
    assert evaluate("print('hi')\ndef replan(state):\n    return {}\n", [0]).infeasible == 1
    # A candidate cannot score itself: returning nothing fails because emergencies are unassigned.
    assert evaluate("def replan(state):\n    return {}\n", [0]).infeasible == 1


def test_state_freezes_started_jobs():
    from dispatchiq.simulate import freeze, morning_plan
    day = make_day(0)
    st = replan_state(day)
    frozen = {j for f in freeze(day, morning_plan(day)).values() for j in f.seq}
    assert frozen and frozen.isdisjoint(st["jobs"])          # started jobs are not re-plannable
    for t in st["techs"]:
        assert set(t["remaining"]) <= set(st["jobs"])
        assert t["free_at"] >= st["time"]
    assert {e.id for e in day.disruption.emergencies} <= set(st["jobs"])


def test_llm_proposer_with_stub(monkeypatch):
    import types
    from dispatchiq import proposers
    naive = (ROOT / "dispatchiq/policies/naive.py").read_text()

    class FakeClient:
        def __init__(self, **kw):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

        def create(self, **kw):
            assert "replan" in kw["messages"][0]["content"]
            msg = types.SimpleNamespace(content="Here you go:\n```python\n" + naive + "\n```")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)],
                                         usage=types.SimpleNamespace(total_tokens=123))

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    p = proposers.LLMProposer([proposers.Provider("stub", "http://x", "k", "m")])
    code, note = p.propose(0, naive, "feedback", __import__("random").Random(0))
    assert "def replan" in code and p.tokens == 123 and note.startswith("stub")
    assert evaluate(code, [0]).infeasible == 0
