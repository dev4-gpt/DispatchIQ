"""POST /api/events/parse: free text -> validated event, with a stubbed LLM. Never runs the optimizer."""

import json
import types

import pytest
from fastapi.testclient import TestClient

from backend import intake as intake_module
from backend import store as store_module
from backend.app import create_app
from backend.intake import IntakeUnavailable
from backend.store import StateStore

CLINIC = {"type": "emergency", "customer_name": "Civic Clinic", "site_name": "Plant room", "x_km": 4, "y_km": 2,
          "required_skills": ["HVAC"], "duration_min": 45, "respond_within_min": 40, "question": None}


def client_with(reply, prompts=None):
    """App whose LLM returns `reply` (a dict is sent as JSON text). Records the prompts it receives."""
    def complete(messages):
        if prompts is not None:
            prompts.append(messages)
        return reply if isinstance(reply, str) else "```json\n" + json.dumps(reply) + "\n```"
    return TestClient(create_app(StateStore(None), intake=lambda: complete))


def base(snapshot):
    return {"scenario_id": snapshot["scenario_id"], "scenario_epoch": snapshot["scenario_epoch"],
            "base_revision": snapshot["revision"]}


@pytest.fixture
def no_optimizer(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("parse must never call the optimizer")
    monkeypatch.setattr(store_module, "optimize", boom)


def parse(c, text="No heat at Civic Clinic plant room, 4 km east 2 km north, 45 min job, need someone within 40 min"):
    s = c.get("/api/scenario").json()
    return s, c.post("/api/events/parse", json={**base(s), "text": text})


def test_emergency_ready_and_previewable(no_optimizer):
    prompts = []
    with client_with({**CLINIC, "at_min": 5, "priority": 1}, prompts) as c:  # model cannot set fixed fields
        s, r = parse(c)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready" and body["missing_fields"] == [] and body["question"] is None
        job = body["event"]["job"]
        now = s["now_min"]
        assert body["event"]["at_min"] == now and body["base_revision"] == s["revision"]
        assert job["id"] == "E01" and job["priority"] == 5 and job["emergency"] and not job["locked"]
        assert job["release_min"] == now and job["earliest_start_min"] == now
        assert job["deadline_start_min"] == job["latest_start_min"] == now + 40
        assert job["window_end_min"] == now + 40 + 45 + 120 and job["required_skills"] == ["hvac"]
        assert job["location"] == {"x_km": 4.0, "y_km": 2.0, "latitude": None, "longitude": None}
        # The model saw the roster, skills and current time.
        system = prompts[0][0]["content"]
        assert "T00: John" in system and "hvac" in system and f"minute {now}" in system
        assert c.get("/api/scenario").json() == s  # nothing committed or changed


def test_parsed_event_is_accepted_by_preview():
    with client_with(CLINIC) as c:
        s, r = parse(c)
        p = c.post("/api/events/preview", json={**base(s), "event": r.json()["event"], "strategy": "stable_insertion"})
        assert p.status_code == 200 and p.json()["status"] == "ready"


def test_missing_fields_and_one_question(no_optimizer):
    reply = {**CLINIC, "x_km": None, "y_km": None, "respond_within_min": None, "question": "Where is the clinic?"}
    with client_with(reply) as c:
        _, r = parse(c, "Emergency at Civic Clinic, no heat")
        body = r.json()
        assert r.status_code == 200 and body["status"] == "needs_input" and body["event"] is None
        assert body["missing_fields"] == ["x_km", "y_km", "respond_within_min"]
        assert body["question"] == "Where is the clinic?"
    with client_with({**CLINIC, "duration_min": None}) as c:  # no model question: server asks
        _, r = parse(c)
        assert r.json()["missing_fields"] == ["duration_min"] and "duration_min" in r.json()["question"]


def test_unknown_skill_and_invalid_values(no_optimizer):
    with client_with({**CLINIC, "required_skills": ["elevator"]}) as c:
        _, r = parse(c)
        body = r.json()
        assert body["status"] == "needs_input" and body["issues"][0]["field"] == "required_skills"
        assert "elevator" in body["issues"][0]["message"]
    with client_with({**CLINIC, "x_km": -3}) as c:  # schema rejects negative grid coordinates
        _, r = parse(c)
        assert r.json()["status"] == "needs_input" and any("x_km" in i["field"] for i in r.json()["issues"])
    with client_with({"type": "something else"}) as c:
        _, r = parse(c)
        assert r.json()["missing_fields"] == ["type"]


def test_technician_unavailable(no_optimizer):
    with client_with({"type": "technician_unavailable", "technician_id": "T03"}) as c:
        s, r = parse(c, "Priya called in sick")
        assert r.json()["status"] == "ready"
        assert r.json()["event"] == {"type": "technician_unavailable", "at_min": s["now_min"], "technician_id": "T03"}
    with client_with({"type": "technician_unavailable", "technician_id": "T99"}) as c:
        _, r = parse(c, "Bob is out")
        assert r.json()["status"] == "needs_input" and r.json()["issues"][0]["field"] == "technician_id"
    with client_with({"type": "technician_unavailable", "technician_id": None}) as c:
        _, r = parse(c, "someone is out")
        assert r.json()["missing_fields"] == ["technician_id"]


def test_no_llm_configured_is_a_clear_error(monkeypatch):
    def unavailable():
        raise IntakeUnavailable()
    with TestClient(create_app(StateStore(None), intake=unavailable)) as c:
        _, r = parse(c)
        assert r.status_code == 503 and r.json()["error"]["code"] == "LLM_NOT_CONFIGURED"
    for k in ("LLM_API_KEY", "FALLBACK_1_API_KEY", "FALLBACK_2_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    with TestClient(create_app(StateStore(None))) as c:  # the real default reads the environment
        _, r = parse(c)
        assert r.status_code == 503 and r.json()["error"]["code"] == "LLM_NOT_CONFIGURED"


def test_bad_model_output_and_stale_base(no_optimizer):
    with client_with("I think it is an emergency.") as c:
        s, r = parse(c)
        assert r.status_code == 503 and r.json()["error"]["code"] == "LLM_FAILED"
        assert c.get("/api/scenario").json() == s
        stale = c.post("/api/events/parse", json={**base(s), "base_revision": s["revision"] + 1, "text": "x"})
        assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_PROPOSAL"
        assert c.post("/api/events/parse", json={**base(s), "text": ""}).status_code == 422


def test_real_provider_path_with_stubbed_openai(monkeypatch, no_optimizer):
    import openai
    seen = {}

    class FakeOpenAI:
        def __init__(self, **kw):
            seen["init"] = kw
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

        def create(self, **kw):
            seen["model"] = kw["model"]
            msg = types.SimpleNamespace(content=json.dumps(CLINIC))
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=None)

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    providers = [intake_module.Provider("stub", "http://llm.invalid", "k", "m1")]
    with TestClient(create_app(StateStore(None), intake=lambda: intake_module.llm_complete(providers))) as c:
        _, r = parse(c)
        assert r.status_code == 200 and r.json()["status"] == "ready"
    assert seen["model"] == "m1" and seen["init"]["base_url"] == "http://llm.invalid"
