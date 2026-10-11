"""Scoreboard and research tab, built from saved run files only. Numbers here are test fixtures."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dispatchiq import scoreboard  # noqa: E402

REFS = {"naive": {"val": {"mean_cost": 200.0, "on_time_pct": 50.0, "missed_promises": 5, "emergencies": 10}},
        "insertion": {"val": {"mean_cost": 180.0, "on_time_pct": 55.0, "missed_promises": 4, "emergencies": 10}}}


def run(agents, vals, team=False):
    rounds = [{"round": i + 1, "champion_val": v, "tokens": 100 * (i + 1),
               "champion": {"mean_cost": v, "on_time_pct": 60.0, "missed_promises": 3, "emergencies": 10, "infeasible": 0}}
              for i, v in enumerate(vals)]
    if team:
        for r in rounds:
            r["critic"] = {"lessons": [f"lesson {r['round']}"], "strategies": None, "tokens": 10, "seconds": 1.0, "error": ""}
    return {"agents": agents, "team": team, "start": "s", "baseline": {"val": {"mean_cost": 200.0}},
            "references": REFS, "rounds": rounds, "lessons": ["lesson 2"] if team else None}


def write(tmp, name, doc):
    (tmp / f"{name}.json").write_text(json.dumps(doc))


def test_scoreboard_rows_curves_and_missing(tmp_path):
    write(tmp_path, "random", run(6, [190.0, 185.0]))
    write(tmp_path, "llm-team", run(6, [178.0, 170.0], team=True))
    write(tmp_path, "llm-team-v2-1agent", run(1, [195.0] * 12, team=True))
    runs = scoreboard.load_runs(tmp_path)
    assert runs["LLM plain"] is None
    rows = {r["policy"]: r for r in scoreboard.scoreboard(runs)}
    assert rows["insertion (reference)"]["val_cost"] == 180.0 and rows["naive (reference)"]["missed_promises"] == 5
    assert rows["LLM team v1"]["val_cost"] == 170.0 and rows["LLM team v1"]["proposals"] == 12
    assert rows["LLM team v1"]["critic_tokens"] == 20 and rows["LLM team v1"]["proposer_tokens"] == 200
    assert rows["LLM team v2, 1 agent"]["proposals"] == 12
    assert rows["LLM team v1"]["note"].startswith("critic v1 collapsed")
    assert rows["LLM plain"]["status"] == "not run" and rows["LLM plain"]["val_cost"] is None
    curves = scoreboard.curves(runs)
    assert curves["LLM team v1"] == [(0, 200.0), (1, 178.0), (2, 170.0)] and "LLM plain" not in curves
    assert "LLM team v2, 1 agent" not in curves  # the single-agent run is compared only with LLM team v2
    assert [c["lessons"] for c in scoreboard.critic_rounds(runs["LLM team v1"])] == [["lesson 1"], ["lesson 2"]]


def test_reference_mismatch_is_flagged(tmp_path):
    other = run(6, [190.0])
    other["references"] = {**REFS, "insertion": {"val": {"mean_cost": 1.0}}}
    write(tmp_path, "random", run(6, [190.0]))
    write(tmp_path, "llm-plain", other)
    assert scoreboard.references(scoreboard.load_runs(tmp_path))[1] is False


def test_research_tab_renders_from_run_files():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    assert not at.exception
    headers = [h.value for h in at.subheader]
    assert "Ablation and comparison" in headers and "Critic lessons by round" in headers
    saved = {label for label, r in scoreboard.load_runs().items() if r is not None}
    if len(saved) < len(scoreboard.RUN_NAMES):
        assert any(i.value.startswith("Not run yet") for i in at.info)


def test_improvement_parallelism_and_loop_evidence(tmp_path):
    team6 = run(6, [190.0, 175.0], team=True)
    team6["rounds"][0].update(accepted=True, promoted_agent=1, elapsed_seconds=100.0,
                              candidates=[{"agent": 0, "note": "x | hint A", "dev_cost": 300.0, "infeasible": 0},
                                          {"agent": 1, "note": "x | hint B", "dev_cost": 290.0, "infeasible": 0}])
    team6["rounds"][0]["critic"]["strategies"] = ["critic hint 0", "critic hint 1"]
    team6["rounds"][1].update(accepted=True, promoted_agent=0, elapsed_seconds=250.0,
                              candidates=[{"agent": 0, "note": "x | critic hint 0", "dev_cost": 280.0, "infeasible": 0}])
    team6["memory"] = [{"round": 1, "agent": 1, "strategy": scoreboard.STRATEGIES[1]},
                       {"round": 2, "agent": 0, "strategy": "critic hint 0"}]
    one48 = run(1, [199.0, 185.0, 170.0])  # older file: no elapsed_seconds -> summed per-round seconds
    for r, s in zip(one48["rounds"], (40.0, 40.0, 40.0)):
        r["seconds"] = s
    write(tmp_path, "random", run(6, [186.0]))
    write(tmp_path, "llm-team-v2", team6)
    write(tmp_path, "llm-team-v2-1agent", one48)
    runs = scoreboard.load_runs(tmp_path)

    rows = {r["policy"]: r for r in scoreboard.with_improvement(scoreboard.scoreboard(runs))}
    assert rows["naive (reference)"]["val_vs_naive_pct"] == 0.0
    assert rows["LLM team v2"]["val_vs_naive_pct"] == round(100 * (200 - 175) / 200, 1)

    par = {p["run"]: p for p in scoreboard.parallelism(runs)}
    assert par["LLM team v2"]["timing"] == "recorded" and par["LLM team v2"]["points"][-1] == (250.0, 175.0)
    # insertion = 180: team beats it at 250 s; random final = 186: team beats it at 250 s too (190 is not < 186)
    assert par["LLM team v2"]["seconds_to_beat_insertion"] == 250.0 and par["LLM team v2"]["seconds_to_beat_random"] == 250.0
    assert par["LLM team v2"]["val_at_round_8"] is None  # only 2 rounds
    p48 = par["LLM team v2, 1 agent"]
    assert p48["timing"] == "summed per-round seconds" and p48["points"][1:] == [(40.0, 199.0), (80.0, 185.0), (120.0, 170.0)]
    assert p48["seconds_to_beat_random"] == 80.0 and p48["seconds_to_beat_insertion"] == 120.0
    assert list(par) == ["LLM team v2", "LLM team v2, 1 agent"]

    ev = scoreboard.loop_evidence(runs["LLM team v2"])
    assert [(e["round"], e["agent"], e["hint_rewritten_by_critic"], e["hints_set_in_round"]) for e in ev] == [
        (1, 1, False, None), (2, 0, True, 1)]
    assert ev[0]["strategy"] == scoreboard.STRATEGIES[1] and ev[0]["agent_source"] == "recorded"
    # Without promoted_agent the winner is derived exactly as evolve.py picks it.
    plain = run(6, [190.0])
    plain["rounds"][0].update(accepted=True, candidates=[
        {"agent": 0, "note": "LLM:m | hint A", "dev_cost": 300.0, "infeasible": 0},
        {"agent": 1, "note": "LLM:m | hint B", "dev_cost": 100.0, "infeasible": 3},
        {"agent": 2, "note": "LLM:m | hint C", "dev_cost": 250.0, "infeasible": 0}])
    e = scoreboard.loop_evidence(plain)[0]
    assert (e["agent"], e["strategy"], e["agent_source"], e["hint_rewritten_by_critic"]) == (
        2, "hint C", "derived from candidate costs", None)


def test_heldout_rows_name_the_baseline(tmp_path):
    doc = run(6, [190.0])
    doc.update(id="llm-team", start="dispatchiq/policies/insertion.py")
    write(tmp_path, "llm-team", doc)
    assert scoreboard.heldout_rows(tmp_path, scoreboard.load_runs(tmp_path)) == ([], None)
    (tmp_path / "heldout_result.json").write_text(json.dumps({"run": "llm-team", "results": [
        {"policy": "round 0", "mean_cost": 200.0}, {"policy": "champion", "mean_cost": 150.0}]}))
    rows, note = scoreboard.heldout_rows(tmp_path, scoreboard.load_runs(tmp_path))
    assert [r["vs_round0_pct"] for r in rows] == [0.0, 25.0] and "insertion.py" in note and "naive" not in note


def test_rescore_matches_saved_scores(tmp_path):
    import rescore
    from dispatchiq.generator import heldout_hash
    naive = (ROOT / "dispatchiq/policies/naive.py").read_text()
    doc = {"id": "t", "mode": "llm", "heldout_hash": heldout_hash(), "champion_code": naive, "round0_code": naive,
           "baseline": {"dev": {"mean_cost": 1911.4}, "val": {"mean_cost": 2039.7}},
           "rounds": [{"champion_dev": 1911.4, "champion_val": 2039.7}]}
    path = tmp_path / "t.json"
    path.write_text(json.dumps(doc))
    assert rescore.main([str(path)]) == 0 and rescore.main([str(path), "--code", "round0"]) == 0
    doc["rounds"][0]["champion_val"] = 1000.0  # a tampered file is caught
    path.write_text(json.dumps(doc))
    assert rescore.main([str(path)]) == 1


def test_final_pick_follows_readme_rule(tmp_path):
    plain, team, one = run(6, [1500.0]), run(6, [1400.0], team=True), run(1, [1000.0], team=True)
    for d in (plain, team, one):
        d["mode"] = "llm"
    write(tmp_path, "llm-plain", plain)
    write(tmp_path, "llm-team", team)
    write(tmp_path, "llm-team-v2-1agent", one)  # lower cost but 1 agent: not eligible
    write(tmp_path, "random", {**run(6, [900.0]), "mode": "random_search"})  # not an LLM run
    pick = scoreboard.final_pick(scoreboard.load_runs(tmp_path))
    assert pick["run"] == "LLM team v1" and pick["file"] == "runs/llm-team.json" and pick["val_cost"] == 1400.0
    assert scoreboard.final_pick({}) is None


def test_bumped_and_moved_counts_and_backfill(tmp_path):
    from dispatchiq.generator import split
    from dispatchiq.sandbox import evaluate
    # Counted from routes by the summary; cost unchanged.
    s = evaluate((ROOT / "dispatchiq/policies/naive.py").read_text(), split("validation")[:3]).summary()
    assert isinstance(s["bumped_booked"], int) and s["moved_healthy"] == 0

    old = run(6, [190.0])  # older run file: champion summary has no bumped/moved fields
    write(tmp_path, "llm-plain", old)
    runs = scoreboard.load_runs(tmp_path)
    fresh = {"runs": {"llm-plain": {"champion_val": 190.0, "rounds": 1, "val": {"bumped_booked": 7, "moved_healthy": 3}}},
             "references": {"naive": {"bumped_booked": 18, "moved_healthy": 0}}}
    rows = {r["policy"]: r for r in scoreboard.scoreboard(runs, fresh)}
    assert (rows["LLM plain"]["bumped_booked"], rows["LLM plain"]["moved_healthy"]) == (7, 3)
    assert rows["LLM plain"]["report_source"].startswith("re-scored")
    assert rows["naive (reference)"]["bumped_booked"] == 18
    stale = {"runs": {"llm-plain": {"champion_val": 999.0, "rounds": 1, "val": {"bumped_booked": 7, "moved_healthy": 3}}}}
    row = {r["policy"]: r for r in scoreboard.scoreboard(runs, stale)}["LLM plain"]
    assert row["bumped_booked"] is None and row["report_source"] is None  # stale backfill is never used
    new = run(6, [190.0])
    new["rounds"][0]["champion"].update(bumped_booked=5, moved_healthy=2)
    write(tmp_path, "llm-plain", new)
    row = {r["policy"]: r for r in scoreboard.scoreboard(scoreboard.load_runs(tmp_path), fresh)}["LLM plain"]
    assert (row["bumped_booked"], row["report_source"]) == (5, "run file")  # run file wins over backfill


def test_v2_round8_checkpoint_and_families_table(tmp_path):
    one = run(1, [190.0 - i for i in range(10)], team=True)
    one["critic_version"] = "v2"
    for i, r in enumerate(one["rounds"]):
        r["elapsed_seconds"] = 60.0 * (i + 1)
        fam = f"F{i % 6 + 1}"
        r["families_per_agent"] = [{"agent": 0, "family": fam, "name": "n", "origin": "original", "hint": "h"}]
    one["memory"] = [{"round": i + 1, "agent": 0, "family": f"F{i % 6 + 1}", "dev_cost": 300.0 - i,
                      "gap_to_champion": -1.0, "promoted": i == 0} for i in range(10)]
    one["stopped"] = {"reason": "deadline", "stop_at": "18:30", "rounds_completed": 10}
    one["rounds_requested"] = 48
    write(tmp_path, "llm-team-v2-1agent", one)
    runs = scoreboard.load_runs(tmp_path)
    p = {x["run"]: x for x in scoreboard.parallelism(runs)}["LLM team v2, 1 agent"]
    assert p["val_at_round_8"] == 183.0 and p["seconds_at_round_8"] == 480.0 and p["points"][-1] == (600.0, 181.0)
    assert p["status"] == "stopped at 10 rounds (of 48, deadline 18:30)"
    fams = scoreboard.families_per_round(runs["LLM team v2, 1 agent"])
    assert [f["family"] for f in fams] == ["F1", "F2", "F3", "F4", "F5", "F6", "F1", "F2", "F3", "F4"]
    assert fams[0]["promoted"] and fams[0]["dev_cost"] == 300.0


def test_backfill_cost_mismatch_is_labelled_not_hidden(tmp_path):
    write(tmp_path, "llm-team", run(6, [1251.2]))
    bf = {"runs": {"llm-team": {"champion_val": 1251.2, "rounds": 1, "rescored_val": 1250.98, "cost_matches": False,
                                "val": {"bumped_booked": 41, "moved_healthy": 96}}}}
    row = {r["policy"]: r for r in scoreboard.scoreboard(scoreboard.load_runs(tmp_path), bf)}["LLM team v1"]
    assert (row["bumped_booked"], row["moved_healthy"]) == (41, 96)
    assert "re-scored cost 1251.0 vs saved 1251.2" in row["report_source"]
