"""DispatchIQ demo UI.   streamlit run app.py

Tab 1 shows one held-out day: the morning schedule, the 2 PM disruption, and the re-plan from
the round-0 dispatcher policy vs. the evolved champion. All numbers come from the checker
(dispatchiq/simulate.py) via the sandbox.
Tab 2 shows the research runs saved by evolve.py (runs/<name>.json): improvement curves, the
ablation table, missed promises and the critic's lessons. It only reads run files.
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dispatchiq import scoreboard

# Streamlit re-runs this script on every page load but keeps imported modules cached, so a server started
# before a scoreboard change would call functions that no longer match. Reload it so the tab is always current.
scoreboard = importlib.reload(scoreboard)
from dispatchiq.generator import make_day, split
from dispatchiq.model import route_eval
from dispatchiq.sandbox import evaluate
from dispatchiq.simulate import morning_plan

ROOT = Path(__file__).resolve().parent
BASE = datetime(2026, 10, 11)

st.set_page_config(page_title="DispatchIQ", layout="wide")
st.title("DispatchIQ: re-plan the whole crew in one click")
st.caption("Agents write the re-plan logic; a deterministic rule checker scores every schedule. "
           "Days shown are held-out: never used during search.")

run_path = ROOT / "runs" / "latest.json"
run = json.loads(run_path.read_text()) if run_path.exists() else None
POLICIES = ROOT / "dispatchiq" / "policies"

day_tab, research_tab = st.tabs(["Held-out day", "Research runs"])


def held_out_day() -> None:
    if run is None:
        st.info("No evolution run saved yet, so the right panel shows the textbook cheapest-insertion reference "
                "instead of an evolved champion. Run `python evolve.py` (or `--mode random` offline) to compare a champion.")
        pair = [("Round 0: dispatcher-style re-plan", (POLICIES / "naive.py").read_text()),
                ("Textbook cheapest insertion (reference, not evolved)", (POLICIES / "insertion.py").read_text())]
    else:
        pair = [("Round 0: dispatcher-style re-plan", run["round0_code"]), ("Evolved champion", run["champion_code"])]

    seed = st.sidebar.selectbox("Held-out day", split("heldout"), index=0)
    day = make_day(seed)
    names = {t.id: t.name for t in day.techs}
    jobs = day.all_jobs()
    t_dis = day.disruption.time
    clock = lambda m: (BASE + timedelta(minutes=float(m))).strftime("%H:%M")  # noqa: E731

    st.sidebar.markdown(f"**Disruption at {clock(t_dis)}**")
    st.sidebar.markdown("Out sick: " + ", ".join(names[s] for s in day.disruption.sick))
    for e in day.disruption.emergencies:
        st.sidebar.markdown(f"Emergency {e.id}: {e.skill}, promised by {clock(e.latest)}")

    def gantt(rows: list[dict], title: str):
        if not rows:
            st.info("No jobs.")
            return
        df = pd.DataFrame(rows)
        fig = px.timeline(df, x_start="start", x_end="end", y="tech", color="kind", text="job", title=title,
                          color_discrete_map={"routine": "#94a3b8", "late": "#f59e0b", "emergency": "#dc2626",
                                              "moved": "#6366f1", "done/in progress": "#cbd5e1"})
        fig.add_vline(x=BASE + timedelta(minutes=t_dis), line_dash="dash", line_color="#dc2626")
        fig.update_yaxes(categoryorder="category descending")
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

    # Morning plan as booked.
    mplan = morning_plan(day)
    morning_rows = []
    for t in day.techs:
        r = route_eval(t.shift_start, t.home, t.shift_end, mplan[t.id], jobs)
        for s in r.stops:
            morning_rows.append({"tech": names[t.id], "job": s.job, "start": BASE + timedelta(minutes=s.start),
                                 "end": BASE + timedelta(minutes=s.end), "kind": "late" if s.late > 0 else "routine"})

    if not st.toggle(f"Trigger the {clock(t_dis)} disruption", value=True):
        gantt(morning_rows, "Morning schedule")
        return

    @st.cache_data(show_spinner="Re-planning with the checker...")
    def replan_rows(code: str, seed: int):
        ev = evaluate(code, [seed])
        score = ev.per_seed.get(seed)
        if score is None:  # the policy runner itself failed (crash, timeout, bad output)
            return None, {"feasible": False, "violations": ev.errors or ["policy evaluation failed"]}
        owner = {jid: tid for tid, seq in mplan.items() for jid in seq}
        rows = [{**r, "kind": "done/in progress"} for r in morning_rows
                if r["start"] < BASE + timedelta(minutes=t_dis)]
        for tid, stops in score.routes.items():
            for s in stops:
                j = jobs[s["job"]]
                kind = ("emergency" if j.emergency else "moved" if owner.get(j.id) not in (tid, None)
                        and owner.get(j.id) not in day.disruption.sick else "late" if s["late"] > 0 else "routine")
                rows.append({"tech": names[tid], "job": s["job"], "start": BASE + timedelta(minutes=s["start"]),
                             "end": BASE + timedelta(minutes=s["end"]), "kind": kind})
        return rows, score.__dict__

    for col, (label, code) in zip(st.columns(2), pair):
        with col:
            rows, score = replan_rows(code, seed)
            st.subheader(label)
            if rows is None:
                st.error("Re-plan unavailable: " + "; ".join(score["violations"][:3]))
                continue
            if not score["feasible"]:
                st.error("Infeasible: " + "; ".join(score["violations"][:3]))
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Cost (lower is better)", f"{score['cost']:.0f}")
            c2.metric("Jobs on time", f"{score['on_time_pct']:.0f}%")
            c3.metric("Emergency response", f"{score['emergency_response']:.0f} min")
            c4.metric("Missed promises", f"{score.get('missed_promises', 0)}/{score.get('emergencies', 0)}")
            c5.metric("Customers moved", f"{score['moved']}")
            gantt(rows, "")


def research_runs() -> None:
    runs = scoreboard.load_runs(ROOT / "runs")
    refs, consistent = scoreboard.references(runs)
    missing = [label for label, r in runs.items() if r is None]
    st.caption("Read from saved run files only; nothing is re-run here. Scores are on the 30 validation days "
               "(seeds 100-129), which pick the champion. Held-out days are not used.")
    if missing:
        st.info("Not run yet: " + ", ".join(f"{label} (`runs/{scoreboard.RUN_NAMES[label]}.json`)" for label in missing))
    if not consistent:
        st.warning("Run files disagree on the reference scores; showing the first one found.")

    rows = scoreboard.with_improvement(scoreboard.scoreboard(runs, scoreboard.load_backfill(ROOT / "runs")))
    st.subheader("Headline: improvement over naive")
    saved = [r for r in rows if r["val_vs_naive_pct"] is not None and r["policy"] != "naive (reference)"]
    if saved:
        for col, r in zip(st.columns(min(4, len(saved))), saved[:4]):
            col.metric(r["policy"], f"{r['val_vs_naive_pct']:+.1f}%", help=f"Validation cost {r['val_cost']:.1f} "
                       f"vs naive; {r['status']}")
        if len(saved) > 4:
            st.caption("More rows in the comparison table below.")
    st.caption("Percent lower cost than the naive dispatcher policy on the 30 validation days.")
    held, held_note = scoreboard.heldout_rows(ROOT / "runs", runs)
    if held:
        st.markdown(f"**Held-out (50 unseen days, run once)**: {held_note}")
        st.dataframe(pd.DataFrame([{"policy": r["policy"], "final solution": bool(r.get("final_solution")),
                                    "held-out cost": r["mean_cost"],
                                    "vs baseline %": r["vs_round0_pct"], "on-time %": r.get("on_time_pct"),
                                    "missed promises": f"{r.get('missed_promises')}/{r.get('emergencies')}"
                                    if r.get("missed_promises") is not None else None} for r in held]),
                     use_container_width=True, hide_index=True)
    else:
        st.caption("Held-out: not run yet. `python heldout.py` scores every saved champion once and names the final "
                   "solution by the validation rule before scoring.")

    st.subheader("Improvement over rounds (validation cost, lower is better)")
    curves = scoreboard.curves(runs)
    if curves:
        series = {label: pd.Series(dict(pts)) for label, pts in curves.items()}
        df = pd.DataFrame(series).sort_index()
        if "insertion" in refs:
            df["insertion (reference, flat)"] = refs["insertion"]["val"]["mean_cost"]
        df.index.name = "round"
        st.line_chart(df)
        st.caption("Round 0 is each run's starting policy. Insertion is a fixed, non-evolved reference.")
    else:
        st.info("No random, LLM-plain or LLM-team run saved yet.")

    st.subheader("Ablation and comparison")
    table = pd.DataFrame([{
        "policy": r["policy"], "status": r["status"], "validation cost": r["val_cost"],
        "vs naive %": r["val_vs_naive_pct"], "on-time %": r["on_time_pct"],
        "missed promises": None if r["missed_promises"] is None else f"{r['missed_promises']}/{r['emergencies']}",
        "booked customers bumped": r["bumped_booked"], "moved between healthy techs": r["moved_healthy"],
        "agents": r.get("agents"), "rounds": r.get("rounds"), "proposals": r.get("proposals"),
        "proposer tokens": r.get("proposer_tokens"), "critic tokens": r.get("critic_tokens"), "note": r.get("note"),
    } for r in rows])
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption("Missed promises: emergencies that started after their promised latest start, out of all "
               "emergencies on validation days. Reported only; the checker does not treat them as a hard rule.")
    st.caption("Booked customers bumped: jobs booked with a healthy technician this morning but left unscheduled. "
               "Moved between healthy techs: jobs reassigned from one healthy technician to another. Totals over the "
               "30 validation days, reporting only: the cost charges every unscheduled job the same and 20 per move. "
               "Older run files get these counts from `python rescore.py --backfill`, used only while it matches the run.")

    st.subheader("Missed promises per policy (validation days)")
    missed = pd.DataFrame([{"policy": r["policy"], "missed promises": r["missed_promises"]}
                           for r in rows if r["missed_promises"] is not None]).set_index("policy")
    if len(missed):
        st.bar_chart(missed)

    st.subheader("Single agent vs LLM team v2: champion vs wall-clock time")
    par = scoreboard.parallelism(runs)
    have = [p for p in par if p["status"] != "not run"]
    if have:
        df = pd.DataFrame([{"run": p["run"], "seconds": t, "validation cost": c} for p in have for t, c in p["points"]])
        fig = px.line(df, x="seconds", y="validation cost", color="run", markers=True, line_shape="hv")
        ref = have[0]
        if ref["insertion_val"] is not None:
            fig.add_hline(y=ref["insertion_val"], line_dash="dash", annotation_text="insertion")
        if ref["random_val"] is not None:
            fig.add_hline(y=ref["random_val"], line_dash="dot", annotation_text="random search (final)")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="cumulative wall-clock seconds")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pd.DataFrame([{
        "run": p["run"], "status": p["status"], "agents": p.get("agents"), "rounds": p.get("rounds"),
        "validation at round 8": p.get("val_at_round_8"), "seconds at round 8": p.get("seconds_at_round_8"),
        "final validation": p["points"][-1][1] if p.get("points") else None,
        "total seconds": p.get("total_seconds"), "seconds to beat insertion": p.get("seconds_to_beat_insertion"),
        "seconds to beat random search": p.get("seconds_to_beat_random"), "timing": p.get("timing"),
    } for p in par]), use_container_width=True, hide_index=True)
    st.caption("Empty 'seconds to beat' = not beaten in this run. Random search target = its final validation cost. "
               "'recorded' timing is the run's own wall clock including the critic; older files sum per-round seconds.")

    st.subheader("Families per round (critic v2)")
    fam_runs = [(label, scoreboard.families_per_round(r)) for label, r in runs.items() if r]
    fam_runs = [(label, rows) for label, rows in fam_runs if rows]
    if not fam_runs:
        st.info("No critic v2 run saved yet. Critic v2 keeps six fixed approach families, one per agent slot.")
    for label, frows in fam_runs:
        st.markdown(f"**{label}**")
        grid = pd.DataFrame([{"round": x["round"], "agent": x["agent"],
                              "cell": f"{x['family']} {x['name']}: " + ("failed" if x["dev_cost"] is None
                                      else f"{x['dev_cost']:.1f}") + (" (promoted)" if x["promoted"] else "")}
                             for x in frows]).pivot(index="round", columns="agent", values="cell")
        grid.columns = [f"agent {c}" for c in grid.columns]
        st.dataframe(grid, use_container_width=True)
    if fam_runs:
        st.caption("Each cell: approach family worked on and its dev cost. Six agents keep one family each; a single "
                   "agent rotates through the families by round. W<n> marks a wildcard family that replaced the "
                   "weakest one.")

    st.subheader("Loop evidence: where each new champion came from")
    evidence = [{"run": label, **e} for label, r in runs.items() if r and r.get("mode") != "random_search"
                for e in scoreboard.loop_evidence(r)]
    if evidence:
        st.dataframe(pd.DataFrame([{
            "run": e["run"], "round": e["round"], "agent": e["agent"], "strategy hint": e["strategy"],
            "dev cost": e["dev_cost"], "validation cost after": e["champion_val"],
            "hint rewritten by critic": e["hint_rewritten_by_critic"], "hints set in round": e["hints_set_in_round"],
            "agent identified": e["agent_source"],
        } for e in evidence]), use_container_width=True, hide_index=True)
        st.caption("Only accepted rounds. 'Hint rewritten by critic' is blank for runs without a critic.")
    else:
        st.info("No accepted LLM round saved yet.")

    st.subheader("Critic lessons by round")
    team_runs = [(label, r) for label, r in runs.items() if r and r.get("team")]
    if not team_runs:
        st.info("No team run saved yet, so there are no critic lessons.")
    for label, r in team_runs:
        with st.expander(f"{label}: {len(r['rounds'])} rounds, lessons carried at the end: {len(r.get('lessons', []))}"):
            for c in scoreboard.critic_rounds(r):
                st.markdown(f"**Round {c['round']}** · critic {c.get('tokens')} tokens, {c.get('seconds')} s")
                if c.get("error"):
                    st.warning(c["error"])
                for lesson in c.get("lessons") or []:
                    st.markdown(f"- {lesson}")
                if c.get("strategies"):
                    st.caption("Rewrote the strategy hints: " + " | ".join(c["strategies"]))
            if r.get("lessons"):
                st.markdown("**Lessons carried after the last round**")
                for lesson in r["lessons"]:
                    st.markdown(f"- {lesson}")


with day_tab:
    held_out_day()
with research_tab:
    research_runs()
