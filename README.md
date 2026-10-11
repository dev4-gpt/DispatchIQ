# DispatchIQ

**A team of LLM agents keeps rewriting a field-service re-planning policy; a deterministic checker, not the AI, decides what is better.**

Entry for **c0mpiled-15, Track 1, Challenge A**. LLM: **`deepseek-ai/DeepSeek-V4.1-Flash`** on Luminal (`https://flash.luminal.cloud/v1`, OpenAI-compatible, streamed).

## Results at a glance

All numbers below come from saved files: `runs/heldout_result.json` (held-out) and the run files in `runs/`, read by `python -m dispatchiq.scoreboard`. Lower cost is better.

### Held-out: 50 days no one tuned on, scored once

<!-- BEGIN heldout-headline -->
**Held-out (50 unseen days):** the final solution, **LLM team v1**, costs **987.6**, **37.9% lower than the naive baseline** (validation: 1251.2).
<!-- END heldout-headline -->

On the held-out days the final solution also beats every other policy:
- 28.3% lower cost than textbook cheapest insertion (1377.0);
- 29.5% lower than random search (1401.6);
- 2.8% lower than LLM plain (1015.6);
- 3.5% lower than LLM team v2 (1023.3).

It is on time for 74.1% of jobs (naive: 58.9%) and misses 4 of 105 emergency promises (naive: 13).

<!-- BEGIN heldout-table -->
| Policy | Held-out cost | vs naive | On-time | Missed promises | Booked bumped | Moved | Infeasible days | Validation cost |
|---|---|---|---|---|---|---|---|---|
| naive (reference) | 1589.1 | +0.0% | 58.9% | 13/105 | 30 | 0 | 0 | - |
| insertion (reference) | 1377.0 | +13.3% | 62.9% | 9/105 | 11 | 0 | 0 | - |
| random search | 1401.6 | +11.8% | 63.3% | 13/105 | 30 | 63 | 0 | 1717.7 |
| LLM plain | 1015.6 | +36.1% | 72.9% | 4/105 | 77 | 76 | 0 | 1301.9 |
| **LLM team v1 (final solution)** | 987.6 | +37.9% | 74.1% | 4/105 | 66 | 121 | 0 | 1251.2 |
| LLM team v2 | 1023.3 | +35.6% | 73.2% | 4/105 | 69 | 89 | 0 | 1308.7 |

50 held-out days (seeds 1000-1049), scored once by `heldout.py`: final solution LLM team v1 (named before scoring by the validation rule); baseline = naive; finished 2026-10-11T17:41:55-0400.
<!-- END heldout-table -->

**How the held-out run was done:**
- **Final solution named first.** It is the 6-agent LLM run with the lowest validation cost, named before any held-out scoring (rule in [Reproduce](#final-solution-rule-fixed-2026-10-11-before-any-held-out-scoring)).
- **Run once, earlier than planned.** `heldout.py` ran a single time, from 17:41:33 to 17:41:55 local time, instead of the planned 18:30.
- **The pick was already settled.** All three candidate runs had finished before then: llm-plain at 16:26:59, team v1 at 16:58:08 and team v2 at 17:20:00. Running early did not change which run the rule picked.
- **Shared machine.** The single-agent run (`llm-team-v2-1agent`, not eligible and not scored) was active on the same machine during scoring. That matters only for team v1's champion, which stops its search on a 0.42 s-per-day wall clock (21.1 s for its 50 days here). With the CPU shared, it may have searched slightly less than on an idle machine, so its held-out cost may be a little higher than it would otherwise be. The other policies run fixed computations, so CPU load doesn't change their results.

### Validation: 30 days (seeds 100–129) that pick the champion

| Policy | Validation cost | vs naive | On-time | Missed promises | Booked bumped | Moved | Agents × rounds |
|---|---|---|---|---|---|---|---|
| naive (reference) | 2039.7 | +0.0% | 52.3% | 5/57 | 18 | 0 | fixed policy |
| insertion (reference) | 1801.2 | +11.7% | 57.9% | 6/57 | 4 | 0 | fixed policy |
| random search | 1717.7 | +15.8% | 58.1% | 6/57 | 18 | 49 | 6 × 8 |
| LLM plain | 1301.9 | +36.2% | 69.0% | 1/57 | 52 | 71 | 6 × 8 |
| **LLM team v1** | **1251.2** | **+38.7%** | 69.4% | 1/57 | 41 | 95 | 6 × 8 |
| LLM team v2 | 1308.7 | +35.8% | 69.2% | 2/57 | 46 | 54 | 6 × 8 |

- **On validation:** the best LLM run, LLM team v1, costs **1251.2**. That is **38.7% lower than the naive baseline**, 30.5% lower than textbook cheapest insertion and 27.2% lower than random search with the same 48-proposal budget.
- **Missed promises:** emergencies that started after their 2-hour promise, out of all emergencies on those days.
- **Booked bumped / Moved:** customers booked with a healthy technician but left unscheduled, and jobs moved between healthy technicians. Totals over 30 days, reported but not part of the cost (see [Honest limits](#honest-limits)). Older run files get these counts by re-scoring their champion (`rescore.py --backfill`). Team v1's champion has a time budget, so its re-scores vary slightly: moved was 96 in one re-score and 95 in another.

## Where the score comes from

Every re-planned day gets one number: its cost. Lower is better. The cost is computed by a rule checker (`dispatchiq/simulate.py`), which is plain code with no AI in it. The agents never score their own work.

**Step 1: hard rules.** If a plan breaks any of these, the whole day fails:

- a sick technician is given a job
- a technician lacks the skill a job needs
- a job is assigned twice
- an emergency is left unassigned
- a technician works more than 90 minutes past the end of their shift

**Step 2: cost.** For a plan that passes, the checker adds up:

| Part | How it's counted |
|---|---|
| Travel | 1 per minute of driving |
| Lateness | minutes late × the job's priority |
| Overtime | 1 per minute past shift end |
| Unscheduled jobs | 150 × priority for each job left undone |
| Moved jobs | 20 for each job moved between healthy technicians |
| Emergency wait | 1 per minute from the emergency call to the start of work |

**Step 3: average.** The score in our tables is the average cost per day across a set of simulated days. A failed day counts as 100,000, so a policy can't hide one; every run in the tables above had zero failed validation days. "vs naive" is how much lower that score is than the baseline dispatcher's.

**Example: the baseline vs the run the final-solution rule picks (team v1), average per validation day**

| Part | Baseline | Team v1 |
|---|---|---|
| Travel | 370.6 | 372.2 |
| Lateness | 599.2 | 89.7 |
| Unscheduled jobs | 830.0 | 560.0 |
| Moved jobs | 0.0 | 64.0 |
| Emergency wait | 113.3 | 80.9 |
| Overtime | 126.6 | 84.1 |
| **Total** | **2039.7** | **1251.0** |

Most of the gain is fewer late jobs. The rest is mainly fewer skipped jobs.

The breakdown comes from re-scoring the saved champion, which gives 1251.0. The results table shows 1251.2, the value saved during the run. The champion stops its search on a wall-clock budget, so its score moves slightly with machine load (see [Honest limits](#honest-limits)).

**The weights are our choices.** 150, 20 and 1 reflect what we think a shop cares about. Different weights would produce a different "best" plan. One known gap: a booked customer who gets bumped costs the same as a job that was never scheduled.

## The problem, and why it is hard

A small HVAC, plumbing and electrical shop has its day planned. Between 11:00 and 14:00 one or two technicians call in sick and one to three emergencies arrive, each promised a technician within 2 hours. Someone has to re-plan the whole crew, now.

Each simulated day (`dispatchiq/generator.py`) has:
- **Technicians:** 8–12, with one or two of three skills (hvac, plumbing, electrical) and a 08:00–17:00 shift.
- **Booked jobs:** 30–50, each needing one skill, with a 2–4 hour arrival window and priority 1, 2 or 3.
- **A disruption:** 1–2 technicians out sick and 1–3 priority-5 emergencies, all at one moment between 11:00 and 14:00. Work already started stays where it is.

A re-plan policy gets that moment's state and returns, for each technician, an ordered list of jobs. The checker then decides, using the hard rules and cost in [Where the score comes from](#where-the-score-comes-from). A policy with any failed validation day is never promoted.

What makes it hard:
- Every term pulls against another. Moving a job to fit an emergency adds travel, makes later customers late, can push overtime past the cap, and may leave a job unscheduled.
- Skills limit who can take what.
- One bad assignment fails the whole day.

## How the loop works

```
evolve.py   each round: N agents each write a full replan() module (LLM, Luminal)
            -> sandbox.py runs each candidate in a separate process on the 30 DEV days
            -> simulate.py (the checker) scores every day; the candidate never scores itself
            -> best candidate with 0 infeasible dev days is promoted only if it ALSO beats the
               champion on the 30 VALIDATION days with 0 infeasible days
            -> team mode: a critic (one extra LLM call) reads the round's results and writes
               lessons and hints for the next round; a shared memory of attempts goes into
               every agent's prompt
heldout.py  once, at the end: 50 HELD-OUT days, never seen during search
```

- **Three sets of days**, fixed by seed in `generator.py`: dev 0–29 (agents search on these), validation 100–129 (decides promotion and the final solution), held-out 1000–1049 (scored once).
- **Committed held-out hash.** `HELDOUT_HASH.txt` holds the SHA-256 of every held-out day (`cd2ba1f9b2a8…`). It was committed in the first commit (`0e8fbc4`, 12:38). `evolve.py` and `heldout.py` refuse to run if the days no longer match it.
- **Agents start from the same champion.** Each round every agent receives the current champion code, the checker's feedback on the champion's three worst dev days, and its own approach hint. Six hints exist (`dispatchiq/proposers.py`): emergency start time, local search, regret insertion, re-sequencing, bumping low-priority jobs, and load balancing.

## Evidence

### Measurable improvement
- **Validation:** every LLM run beat both non-LLM references after its first round. Round-1 validation costs were 1389.0 (plain), 1486.6 (team v1) and 1374.2 (team v2), against insertion at 1801.2 and random search's final 1717.7. The best run ends at 1251.2, 38.7% below naive.
- **Improvement curves** (validation cost after each round, round 0 = naive):

| Round | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| random search | 2039.7 | 1755.1 | 1752.2 | 1752.2 | 1732.2 | 1728.8 | 1728.8 | 1728.8 | 1717.7 |
| LLM plain | 2039.7 | 1389.0 | 1386.1 | 1360.1 | 1349.6 | 1349.6 | 1345.9 | 1344.9 | 1301.9 |
| LLM team v1 | 2039.7 | 1486.6 | 1426.6 | 1356.0 | 1325.5 | 1286.6 | 1286.6 | 1251.2 | 1251.2 |
| LLM team v2 | 2039.7 | 1374.2 | 1359.8 | 1340.2 | 1335.9 | 1330.8 | 1325.8 | 1308.7 | 1308.7 |

- **Held-out:** the final solution costs 987.6, 37.9% below naive (full table at the top).
  - The three LLM runs keep their validation order on held-out days: team v1, then plain, then team v2.
  - The two references swap places. Random search beat insertion on validation (1717.7 against 1801.2), but insertion beats it on held-out days (1377.0 against 1401.6).

### Improvement-loop design
- **Six approach families.** The six hints above give the agents different starting angles. Promotion is decided only by the checker, on dev and then validation days.
- **Critic v1 (`llm-team`).** The critic could rewrite every hint each round. What the run file shows:
  - It rewrote the hints in all 8 rounds, writing 8 hints each time for 6 agents, so 2 per round were never used.
  - After round 2, five of the six hints in use aimed at the same thing: fewer unscheduled jobs. The six approaches had collapsed into one.
  - Five of its six accepted champions came from critic-written hints.
  - It still finished with the lowest validation cost of any run (1251.2).
- **Critic v2 (`llm-team-v2`, `dispatchiq/team_v2.py`).** It enforces these rules in code:
  - One fixed family per agent slot, which the critic cannot delete.
  - Exactly one refinement line per family per round.
  - A single wildcard slot: only the weakest family, after 2 rounds, may be replaced, by an approach that differs from the other five.
  - Coding fixes go into shared lessons, never into a hint slot.
  - The critic sees the champion's dev-day cost breakdown.
- **What v2's run file shows:**
  - All 48 candidates were feasible (team v1: 3 failed, plain: 5).
  - The critic wrote 6 of 6 refinements in every round, with no critic errors.
  - New champions came from three families: local search 4 times, re-sequencing twice and regret insertion once.
  - The wildcard slot replaced the emergency-start family after round 2. Each wildcard was then itself replaced after 2 rounds: beam search, then route-pool selection, then an auction. The fourth, multi-start rebuilding, was chosen after round 8 and never ran. So no wildcard had more than two rounds.
  - By round 8 every family scored within 1231.3–1233.5 on dev days. All agents edit the same champion code, so outcomes converge even when the hints differ.
  - v2 ended at 1308.7, so it did not beat v1 in this one run.
- **Families per round, team v2** (dev cost of each agent's attempt; bold ✓ = promoted to champion; W = wildcard):

| Round | Agent 0 | Agent 1 | Agent 2 | Agent 3 | Agent 4 | Agent 5 |
|---|---|---|---|---|---|---|
| 1 | F1 emergency-start: 1459.1 | F2 local-search: 1310.4 | F3 regret-insertion: 1456.5 | **F4 resequence: 1257.1** ✓ | F5 bump-low-priority: 1377.2 | F6 load-balance: 1378.6 |
| 2 | F1 emergency-start: 1289.9 | F2 local-search: 1261.8 | F3 regret-insertion: 1360.8 | **F4 resequence: 1253.8** ✓ | F5 bump-low-priority: 1266.8 | F6 load-balance: 1254.9 |
| 3 | W2 wildcard: 1273.6 | **F2 local-search: 1241.9** ✓ | F3 regret-insertion: 1264.1 | F4 resequence: 1253.8 | F5 bump-low-priority: 1254.8 | F6 load-balance: 1251.7 |
| 4 | W2 wildcard: 1256.5 | **F2 local-search: 1241.2** ✓ | F3 regret-insertion: 1267.1 | F4 resequence: 1241.9 | F5 bump-low-priority: 1241.9 | F6 load-balance: 1241.9 |
| 5 | W4 wildcard: 1241.4 | **F2 local-search: 1239.3** ✓ | F3 regret-insertion: 1253.1 | F4 resequence: 1270.3 | F5 bump-low-priority: 1241.2 | F6 load-balance: 1243.9 |
| 6 | W4 wildcard: 1239.3 | **F2 local-search: 1238.0** ✓ | F3 regret-insertion: 1239.7 | F4 resequence: 1239.3 | F5 bump-low-priority: 1239.3 | F6 load-balance: 1239.3 |
| 7 | W6 wildcard: 1238.8 | F2 local-search: 1238.6 | **F3 regret-insertion: 1231.3** ✓ | F4 resequence: 1238.0 | F5 bump-low-priority: 1238.0 | F6 load-balance: 1243.5 |
| 8 | W6 wildcard: 1231.3 | F2 local-search: 1233.5 | F3 regret-insertion: 1232.2 | F4 resequence: 1231.3 | F5 bump-low-priority: 1231.3 | F6 load-balance: 1231.3 |

- **Cost of the loop** (tokens):
  - LLM plain: 1,368,714 proposer tokens.
  - Team v1: 1,550,887 proposer tokens plus 47,883 critic tokens.
  - Team v2: 1,237,322 proposer tokens plus 52,876 critic tokens.

### Effective parallelism
Six agents per round against one agent working alone, with the same critic v2; the single agent rotates through the six families by round. The single-agent run had a 48-round cap and an 18:30 deadline. It stopped at 33 rounds, at 18:26, because the next round would likely have ended after 18:30.
- **Same rounds:** after 8 rounds, six agents (48 proposals) reached 1308.7 in 1,312 s, and one agent (8 proposals) reached 1344.2 in 1,082 s.
- **Same wall-clock time:** when team v2 finished at 1,312 s, the single agent was at 1344.2 after 9 rounds.
- **Given three times the time:** the single agent kept going to 33 rounds (3,970 s) and reached 1272.3, lower than team v2's 1308.7. It passed team v2 at 1,771 s, in round 13.
- **Token cost:** the single agent used 1,053,081 proposer tokens plus 164,069 critic tokens, because its critic ran 33 times. Team v2 used 1,237,322 plus 52,876.
- **Reading:** in this one run each, parallel agents bought faster progress per round and per minute, and a lone agent given about 3× the time went further. Both runs beat insertion and random search in their first round.

<!-- BEGIN single-agent -->
| Run | Agents | Rounds | Validation at round 8 | Wall-clock at round 8 | Final validation | Wall-clock at end | First beat insertion | First beat random search | Status |
|---|---|---|---|---|---|---|---|---|---|
| LLM team v2 | 6 | 8 | 1308.7 | 1312 s | 1308.7 | 1312 s | 215 s | 215 s | saved |
| LLM team v2, 1 agent | 1 | 33 | 1344.2 | 1082 s | 1272.3 | 3970 s | 150 s | 150 s | stopped at 33 rounds (of 48, deadline 18:30) |
<!-- END single-agent -->

### Demo and clarity
```bash
streamlit run app.py            # open http://localhost:8501, then the "Research runs" tab
python -m dispatchiq.scoreboard # the same numbers as text
```
The "Research runs" tab reads only saved run files. It shows:
- the headline percentages;
- the improvement curves;
- the comparison table with missed promises, bumped and moved counts;
- the six-agent vs single-agent chart;
- where each new champion came from (agent, family, whether the critic had refined its hint);
- the families-per-round table;
- the critic's lessons for every round;
- the held-out table, once it exists.

The "Held-out day" tab replays one held-out day before and after the disruption.

## Honest limits
- **Simulated days.** Days are generated, not taken from a real shop. Travel is Manhattan distance at 2 minutes per km. The morning plan is fixed and identical for all policies; only the re-plan is evolved.
- **Cost-model gap.** The cost doesn't tell a booked customer apart from an unbooked one. A booked customer bumped off a healthy technician costs the same 150 × priority as a job that was never scheduled, and a move between healthy technicians costs only 20. The LLM champions bump 41–52 booked customers over 30 validation days, where insertion bumps 4. We report these counts but do not penalise them.
- **Time-budgeted champion.** Team v1's champion stops its search on a 0.42 s-per-day wall clock, so its score depends slightly on machine speed and load: 1251.2 on validation during the run, 1250.98 in one later re-score and 1251.2 again in another. `rescore.py` reports such differences. The held-out run shared the machine with the single-agent run (see [Results at a glance](#held-out-50-days-no-one-tuned-on-scored-once)).
- **One run per configuration.** LLM sampling is random (temperature 0.7). The gaps between plain, team v1 and team v2 (1251.2–1308.7) are single samples, not a measured ranking of the methods.
- **The live dispatch app still uses insertion.** The live re-plan in `backend/` uses validated feasible insertion. It never loads evolved code.
- **Late emergencies are soft in the research checker.** An emergency that starts after its 2-hour promise is penalised, not rejected; we report it as "missed promises". The live app's validator treats the deadline as a hard rule.
- **The sandbox is not a security boundary.** Candidates run in a separate process with a timeout and a stripped environment. They can still read files, and on Windows there is no memory cap.
- **Product choices.** The cost weights (150, 20, 1) are product choices. Different weights could pick a different "best" policy.
- **Market notes are unverified.** [MARKET.md](MARKET.md) collects search extracts and vendor claims that have not been checked.

## Reproduce

Every result is a file in `runs/<name>.json`, and `--name` refuses to overwrite one. The LLM runs used Luminal, `deepseek-ai/DeepSeek-V4.1-Flash`, with streamed responses: the gateway drops non-streamed requests that run longer than about 20 s.

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt -r backend/requirements.txt
export LLM_BASE_URL=https://flash.luminal.cloud/v1 LLM_MODEL=deepseek-ai/DeepSeek-V4.1-Flash LLM_API_KEY=...
# PowerShell: $env:LLM_BASE_URL="https://flash.luminal.cloud/v1"; $env:LLM_MODEL="deepseek-ai/DeepSeek-V4.1-Flash"; $env:LLM_API_KEY="..."

python evolve.py --mode random --rounds 8 --agents 6 --name random              # no LLM
python evolve.py               --rounds 8 --agents 6 --name llm-plain
python evolve.py --team        --rounds 8 --agents 6 --name llm-team           # critic v1 ("LLM team v1")
python evolve.py --team --critic v2 --rounds 8  --agents 6 --name llm-team-v2
python evolve.py --team --critic v2 --rounds 48 --agents 1 --name llm-team-v2-1agent \
                 --stop-at 18:30                                              # single agent, rotates families

python -m dispatchiq.scoreboard        # comparison table from the saved files (runs nothing)
pytest -q                              # tests: checker, sandbox, team/critic v1+v2, scoreboard, held-out rules, backend
```

`runs/llm-step1*.json` are one-round provider checks from setup, not results.

- **Random search is deterministic.** With the same `--seed` (default 0) it reproduces exactly.
- **LLM runs are not.** Sampling uses temperature 0.7, so a rerun writes different code and gets different scores. The saved file is the record.

**Re-score a saved champion without any LLM.** The code saved in the run file is run through the same sandbox and checker. Dev and validation days are fixed, so the scores must match the file; a mismatch exits non-zero.

```bash
python rescore.py runs/llm-team.json                 # champion on dev + validation
python rescore.py runs/llm-team.json --code round0   # the starting policy
python rescore.py --backfill                         # bumped/moved counts for older run files
```

**Held-out days are not in `rescore.py`.** `python heldout.py` scores every saved champion on the 50 held-out days once and writes `runs/heldout_result.json` (rules below).

### Final-solution rule (fixed 2026-10-11, before any held-out scoring)

The **final solution** is **the 6-agent LLM run with the lowest validation cost at 18:30 local time**.
- **Eligible runs:** `llm-plain`, `llm-team` (critic v1) and `llm-team-v2` (critic v2). Each must have `--agents 6` and use the LLM.
- **Not eligible:** random search and the single-agent run (`llm-team-v2-1agent`).
- **Which cost counts:** the champion's validation cost in the run file as saved at 18:30. A run still going at 18:30 counts with the rounds it had saved by then.
- **Named before scoring:** `heldout.py` applies this rule and prints the final solution before it scores anything.
- **Every champion scored beside it:** the same single invocation scores naive, insertion, random search, llm-plain, team v1 and team v2 on the same 50 held-out days. Those rows are reported alongside, for comparison only. A better held-out number on another row does not change which run is the final solution.
- **No other held-out runs:** no run is scored on held-out days outside this one invocation, and the rule is not changed after seeing held-out results.
- **As run:** `heldout.py` ran once, at 17:41:33–17:41:55. All three eligible runs had already finished (the last, team v2, at 17:20:00), so the rule names the same run at 17:41 as it would have at 18:30.

```bash
python heldout.py --dry-run         # names the final solution and lists the rows; scores nothing
python heldout.py                   # the held-out run (ran once: 17:41:33-17:41:55)
python fill_readme.py --check       # then fill the marked blanks in this README from the result files
```

**What "once" means:**
- **Not a run:** a crash or timeout that prints no held-out scores, and it may be retried. `heldout.py` scores every policy before printing anything and prints no table if any policy fails to complete all 50 days.
- **Final:** any invocation that prints held-out scores. It writes `runs/heldout_result.json`, and `heldout.py` refuses to run again while that file exists.

## What was built during the hackathon

All times are local (America/New_York) on 2026-10-11, from `git log`.

| Time | Commit | Who | What |
|---|---|---|---|
| 12:38 | `0e8fbc4` | Claude Code | Research prototype: generator, checker, sandbox, proposers, evolve, held-out split and committed hash, Streamlit app |
| 13:08 | `ddfd622` | HetPatel1978 | Audit, API contract and execution plan (`docs/`) |
| 13:24–13:25 | `466510e`, `3f47934` | Claude Code | Windows runner fix; promotion requires zero infeasible validation days |
| 13:42–14:05 | `dd5502f`, `6642555` | Claude Code | React dispatch frontend and its static demo build |
| 14:10 | `7892101` | HetPatel1978 | FastAPI dispatch backend with strict validator and preview/approve lifecycle |
| 14:11, 14:27 | `90d67d4`, `5fe575e` | Aryaman Singh Dev | Merged the frontend and the worker-types proposal into `main` |
| 14:24 | `9f35479` | Claude Code | Worker-types contract proposal (frontend only) |
| 14:58, 15:22 | `bef7193`, `c9acda4` | HetPatel1978 | Dispatch workspace redesign |
| 16:15 | `f181c1a` | HetPatel1978 | Team mode with critic, scoreboard, event-intake endpoint, streamed LLM calls, first saved runs |
| 16:35 | `b184ad9` | HetPatel1978 | Bumped / moved reporting |
| 16:50 | `9aadc05` | HetPatel1978 | Critic v2 (fixed approach families) |
| 17:08, 17:15 | `740e4f9`, `479ad99` | HetPatel1978 | Re-score backfill; held-out run preparation |

Later commits (this README, final run files) are in `git log`. **AI coding tools were used throughout.** Commits authored "Claude" were made by Claude Code sessions, and the other commits from 16:15 on were also written with Claude Code (`Co-Authored-By` trailers). The agents inside the product use the Luminal model named above.

## Frontend

The React, TypeScript and Vite frontend was built to turn scheduling decisions into a workflow a dispatcher can understand and control. It makes the day's work, the impact of an emergency and the next action visible, so a dispatcher can review changes before applying them.

The main **Dispatch Board** connects an interactive map with a technician timeline: selecting a job or technician highlights its location, route and schedule, with details in a contextual inspector. Overview, Jobs, Technicians and Activity provide views of the committed day. Operational summaries show available technicians, assigned/unassigned work, appointments at risk and emergencies.

For an emergency, the frontend calls the backend to preview a plan, shows current versus proposed assignments and times, and exposes the measured tradeoffs and validation evidence. **Approve Changes** commits the proposal; **Reject Proposal** keeps the approved schedule intact. Mobile uses map/timeline tabs and detail drawers. The map uses clearly labeled synthetic coordinates and estimated travel.

See [frontend/README.md](frontend/README.md) for frontend setup, browser tests and screenshots. The explicitly labeled development fixture is separate from the real API workflow.

## The dispatch app

The dispatch app is the product a dispatcher would use. It loads a synthetic day (10 technicians, 25 jobs, at 11:30) on a map and timeline, and lets you add an emergency. The backend proposes a validated insertion that the dispatcher approves or rejects before anything changes. A strict validator protects skills, travel, time windows, shifts and work already started, and stale proposals are refused by revision checks.

On Windows (PowerShell), from the repository root:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
# second terminal
cd frontend; npm.cmd ci; npm.cmd run dev        # then open http://127.0.0.1:5173
```
