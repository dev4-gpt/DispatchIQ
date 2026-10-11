"""DispatchIQ demo UI.   streamlit run app.py

Shows one held-out day: the morning schedule, the 2 PM disruption, and the re-plan from
the round-0 dispatcher policy vs. the evolved champion, plus the improvement curve.
All numbers come from the checker (dispatchiq/simulate.py) via the sandbox.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

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
if run is None:
    st.warning("No run yet. Run `python evolve.py` (or `--mode random` offline) first.")
    st.stop()

seed = st.sidebar.selectbox("Held-out day", split("heldout"), index=0)
day = make_day(seed)
names = {t.id: t.name for t in day.techs}
jobs = day.all_jobs()
t_dis = day.disruption.time
clock = lambda m: (BASE + timedelta(minutes=float(m))).strftime("%H:%M")

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

triggered = st.toggle(f"Trigger the {clock(t_dis)} disruption", value=True)
if not triggered:
    gantt(morning_rows, "Morning schedule")
    st.stop()


@st.cache_data(show_spinner="Re-planning with the checker...")
def replan_rows(code: str, seed: int):
    ev = evaluate(code, [seed])
    score = ev.per_seed[seed]
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


left, right = st.columns(2)
results = {}
for col, (label, code) in zip((left, right), [("Round 0: dispatcher-style re-plan", run["round0_code"]),
                                              ("Evolved champion", run["champion_code"])]):
    with col:
        rows, score = replan_rows(code, seed)
        results[label] = score
        st.subheader(label)
        if not score["feasible"]:
            st.error("Infeasible: " + "; ".join(score["violations"][:3]))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cost (lower is better)", f"{score['cost']:.0f}")
        c2.metric("Jobs on time", f"{score['on_time_pct']:.0f}%")
        c3.metric("Emergency response", f"{score['emergency_response']:.0f} min")
        c4.metric("Customers moved", f"{score['moved']}")
        gantt(rows, "")

st.subheader("Improvement over rounds (validation days)")
curve = [{"round": 0, "validation cost": run["baseline"]["val"]["mean_cost"]}] + [
    {"round": r["round"], "validation cost": r["champion_val"]} for r in run["rounds"]]
st.line_chart(pd.DataFrame(curve).set_index("round"))
st.caption(f"Run {run['id']} · mode: {run['mode']} · agents per round: {run['agents']} · "
           f"held-out hash {run['heldout_hash'][:12]}…")
hold = ROOT / "runs" / "heldout_result.json"
if hold.exists():
    st.subheader("Held-out result (50 unseen days, run once)")
    st.dataframe(pd.DataFrame(json.loads(hold.read_text())["results"]), use_container_width=True)
