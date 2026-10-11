"""GET /api/research/latest: read-only summary of saved run files. Values below are test fixtures."""

import json
import os

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.store import StateStore


def run_doc(run_id, team=False):
    rnd = {"round": 1, "seconds": 2.5, "accepted": True, "champion_dev": 90.0, "champion_val": 95.0,
           "champion": {"mean_cost": 95.0, "missed_promises": 1}, "tokens": 300, "round_tokens": 300}
    if team:
        rnd["critic"] = {"lessons": ["l1"], "strategies": None, "tokens": 40, "seconds": 1.5, "provider": "x", "error": ""}
    doc = {"id": run_id, "name": run_id, "mode": "llm", "team": team, "agents": 2, "start": "s.py",
           "heldout_hash": "h", "baseline": {"val": {"mean_cost": 100.0}},
           "references": {"insertion": {"val": {"mean_cost": 97.0}}}, "rounds": [rnd],
           "champion_code": "import os\ndef replan(state):\n    raise SystemExit('executed!')\n", "round0_code": "x"}
    if team:
        doc.update(lessons=["l1"], strategies=["s"], memory=[])
    return doc


def test_summary_is_read_only_and_never_returns_code(tmp_path, monkeypatch):
    import dispatchiq.sandbox
    monkeypatch.setattr(dispatchiq.sandbox, "evaluate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("executed")))
    (tmp_path / "plain.json").write_text(json.dumps(run_doc("plain")))
    (tmp_path / "team.json").write_text(json.dumps(run_doc("team", team=True)))
    os.utime(tmp_path / "plain.json", (1, 1))  # team is newer
    (tmp_path / "latest.json").write_text(json.dumps(run_doc("dup")))  # duplicate pointer, ignored
    (tmp_path / "broken.json").write_text("{not json")
    (tmp_path / "other.json").write_text(json.dumps({"hello": 1}))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    with TestClient(create_app(StateStore(None), runs_dir=tmp_path)) as c:
        r = c.get("/api/research/latest")
    assert r.status_code == 200
    body = r.json()
    assert "replan" not in r.text and "champion_code" not in r.text
    assert [x["id"] for x in body["runs"]] == ["team", "plain"] and body["latest_id"] == "team"
    team = body["runs"][0]
    assert team["champion"]["val_cost"] == 95.0 and team["references"]["insertion"]["val"]["mean_cost"] == 97.0
    assert team["lessons"] == ["l1"] and team["critic_tokens_total"] == 40
    assert team["curve"][0] == {"round": 1, "champion_val": 95.0, "accepted": True, "seconds": 2.5,
                                "proposer_tokens": 300, "critic_tokens": 40, "critic_seconds": 1.5, "critic_error": None}
    assert body["runs"][1]["lessons"] == [] and body["runs"][1]["critic_tokens_total"] is None
    assert sorted(s["file"] for s in body["skipped"]) == ["broken.json", "other.json"]
    assert body["heldout"] is None
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before  # nothing written


def test_empty_or_missing_runs_dir(tmp_path):
    with TestClient(create_app(StateStore(None), runs_dir=tmp_path / "nope")) as c:
        assert c.get("/api/research/latest").json() == {"runs": [], "latest_id": None, "heldout": None, "skipped": []}
