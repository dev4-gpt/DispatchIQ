# DispatchIQ: state of the repo (2026-10-11, ~15:20 ET)

Audit only. Everything below was read or run in this checkout (`C:\Users\hetp2\Desktop\c0mpiled_15_2\DispatchIQ`). No existing file was edited. Side effects of the runs: `runs/20261011-151607.json` and `runs/latest.json` were created by the requested `evolve.py --mode random` run.

**Main surprise:** the brief assumes there is no backend and no `docs/CONTRACTS.md`. Both exist. A tested FastAPI service with preview, approve, reject and revision checks is already built, but it lives only on `feature/optimization`. `origin/main` does not have it.

---

## 1. Repo state

### Branches
- **Checked out:** `feature/optimization`, which is level with `origin/feature/optimization` at `bef7193`.
- **`origin/main`** is at `5fe575e`. It has the frontend and worker types, but **no `backend/`**.
- **Local `main`** is at `3f47934`, behind `origin/main`.
- **The branches have diverged.** `feature/optimization` has the backend and the redesign, but not the worker-types commit `9f35479`. `origin/main` has worker types, but not the backend.

### Commit history (oldest first, times in ET)

| Commit | Author | Time | What it changed |
|---|---|---|---|
| `0e8fbc4` | Claude | 12:38 | Initial prototype, 22 files: `dispatchiq/` package (model, generator, simulate checker, sandbox, proposers, 3 policies), `evolve.py`, `heldout.py`, Streamlit `app.py`, tests, README/RUNBOOK/MARKET, `HELDOUT_HASH.txt` |
| `ddfd622` | HetPatel1978 | 13:08 | `docs/`: CONTRACTS.md (API v1), EXECUTION_PLAN.md, DEVELOPER_1/2_PROMPT.md, `audit/` (VERIFICATION.md, diagnostics.json, resolved requirements) |
| `466510e` | Claude | 13:24 | `sandbox.py`: guards `import resource`, passes SYSTEMROOT/TEMP to the child, checks result count. `simulate.check`: non-string ids become violations. `app.py`: works without a run. +3 tests (11 total) |
| `3f47934` | Claude | 13:25 | `evolve.py`: promotes a candidate only with 0 infeasible validation days; per-agent seeds fixed before threading |
| `dd5502f` | Claude | 13:42 | `frontend/`: React + TS + Vite command center, typed client, opt-in dev fixture, Playwright tests (40 files) |
| `6642555` | Claude | 14:05 | `frontend/demo` static fixture build, relative asset paths |
| `7892101` | HetPatel1978 | 14:10 | **`backend/`** (25 files): FastAPI app, strict schemas, fixture, validator, optimizer, metrics, explanations, store, 2 test files, examples/openapi |
| `90d67d4` | Aryaman Singh Dev | 14:11 | Merges PR #1 (`feature/operations-ui`) into main. Frontend only, no backend |
| `9f35479` | Claude | 14:24 | `docs/CONTRACTS_WORKER_TYPES.md` (v1.1 proposal: human/robot/agent workers), fixture and UI support in the frontend only. Backend not implemented |
| `5fe575e` | Aryaman Singh Dev | 14:27 | Merges PR #2 (worker types) into main |
| `bef7193` | HetPatel1978 | 14:58 | Frontend redesign (App, OperationsPages, ProposalPanel, RouteMap, CSS, tests, evidence). 50 files |

### Uncommitted work in the tree (not touched)
- **12 modified files under `frontend/`:** App.tsx, ProposalPanel.tsx, state/dispatch.ts, index.css, tests, screenshots and others.
- **Untracked:** `frontend/src/components/{OperationalSummary,ScheduleComparison}.tsx`, `ui/tooltip.tsx`, and `frontend/evidence/redesign-v2-*`.
- This looks like a "redesign v2" in progress (`frontend/evidence/REDESIGN_V2.md`).

### `frontend/`
- **Stack:** React 19, Vite, Tailwind 4, Radix, Leaflet `CRS.Simple`, Playwright.
- **Source:** `src/api/{client,types,devFixture}.ts`, `src/state/{dispatch,useDispatch}.ts`, components (ScheduleBoard, RouteMap, ProposalPanel, ScenarioControls, JobInspector, MetricsStrip, TechnicianList, OperationsPages), `tests/`.
- **Generated output:** `demo/` (fixture build), `dist/`, `evidence/`, `test-results/`.
- **Reported, not re-run by me:** `frontend/evidence/QA.md` reports 22/22 browser checks passing, 11 of them against the real API.

### `docs/`
- `CONTRACTS.md` **exists**. It is API contract v1.
- Also present: `EXECUTION_PLAN.md`, `DEVELOPER_1_PROMPT.md`, `DEVELOPER_2_PROMPT.md`, `audit/`.
- `CONTRACTS_WORKER_TYPES.md` exists only on `origin/main`.

### Backend
**It exists:** `backend/app.py` (`create_app`), `store.py` (`StateStore`), `optimizer.py` (`optimize`), `validator.py` (`validate_schedule`), `metrics.py`, `explanations.py`, `scenario.py` (`make_scenario`, `demo_emergency`), `schemas.py`, `adapters.py` and `demo.py`.
- **Endpoints:** `GET /api/{health,scenario,technicians,jobs,schedule,metrics}`, `POST /api/{events/preview,optimize,events/commit,events/reject,reset}`.
- **Store:** single process, `RLock`, atomic JSON persistence to `runs/operations-state.json`.
- **Optimizer:** insertion only. It does not call anything in `dispatchiq/` except `model.travel`.

### API calls the frontend makes
Source: `frontend/src/api/client.ts` (`httpTransport`). Types are in `frontend/src/api/types.ts`.

| Call | Request | Expected response |
|---|---|---|
| `GET /api/health` | none | `{status:"ok", schema_version:"1", optimizer:string, state_ready:boolean}` |
| `GET /api/scenario` | none | `Snapshot` (see below) |
| `POST /api/events/preview` | `{scenario_id, scenario_epoch, base_revision, event, strategy}` | `Proposal` (see below) |
| `POST /api/events/commit` | `{scenario_id, scenario_epoch, base_revision, proposal_id}` | `Snapshot` |
| `POST /api/events/reject` | same as commit | `{proposal_id, status:"rejected", revision}` |
| `POST /api/reset` | `{scenario_id, scenario_epoch, base_revision}` | `Snapshot` |
| errors | n/a | `{error:{code, message, current_revision?, details?}}`. 409/410 or the codes `STALE_PROPOSAL`, `PROPOSAL_CONSUMED`, `PROPOSAL_REJECTED`, `SCENARIO_CHANGED`, `PROPOSAL_EXPIRED` are treated as stale |

The UI never calls `/api/optimize`, `/technicians`, `/jobs`, `/schedule` or `/metrics`.

**Event shapes:**
- `event` is `{type:"emergency", at_min, job:JobInput}` or `{type:"technician_unavailable", at_min, technician_id}`.
- The UI only sends `emergency`. `ScenarioControls.submit` builds it from a preset form with fixed fields, and the deadline is `now + form.deadline`.
- `strategy` is `"stable_insertion"` or `"first_feasible"`.

**Snapshot fields:** `schema_version, scenario_id, scenario_epoch, revision, date, timezone, now_min, travel_model, technicians[], jobs[], schedule{assignments[], unassigned_job_ids[]}, validation{valid, violations[]}, metrics, events[]`.

**Proposal fields:** `proposal_id, scenario_id, scenario_epoch, base_revision, status ("ready"|"no_feasible_plan"|"failed"), event, proposed_snapshot|null, changes[], validation, candidates[], selected_candidate_id, comparison[{strategy, status, metrics, diff_metrics, runtime_ms, validation}], runtime_ms, search{termination, candidates_evaluated, feasibility_proven_impossible}, expires_at_utc, explanation`.

**Worker types:** on `origin/main`, `types.ts` adds optional `worker_type`, `certifications`, `allowed_worker_types` and `site_id`. The backend models use `extra="forbid"`, so the backend on this branch would reject events that carry those fields.

---

## 2. What runs

### Environment
- Windows 11, build 10.0.26200.
- Python 3.13.5 (project `.venv`), pip 25.1.1.

### Dependencies
- `pip install --dry-run -r requirements.txt -r backend/requirements.txt` exits 0 with nothing to install. Everything is already installed.
- `pip check` reports: "No broken requirements found."
- Root `requirements.txt` is unpinned: openai, streamlit, plotly, pandas, pymongo, pytest.
- `backend/requirements.txt` is pinned: fastapi 0.143.0, pydantic 2.14.0, uvicorn 0.54.0, httpx 0.28.1, pytest 9.1.1.

### `pytest -q` (exactly as asked) fails during collection
```
ERROR runs/backend-tests-1 - PermissionError: [WinError 5] Access is denied: ...
ERROR runs/backend-tests-2 - PermissionError: [WinError 5] Access is denied: ...
ERROR runs/backend-tests-3 - PermissionError: [WinError 5] Access is denied: ...
ERROR runs/backend-tests-4 - PermissionError: [WinError 5] Access is denied: ...
ERROR runs/commit-check-20261011 - PermissionError: [WinError 5] Access is de...
ERROR runs/frontend-regression-20261011 - PermissionError: [WinError 5] Acces...
!!!!!!!!!!!!!!!!!!! Interrupted: 6 errors during collection !!!!!!!!!!!!!!!!!!!
2 warnings, 6 errors in 0.42s
```
- These six `runs/` folders are leftover pytest `--basetemp` folders, and my user cannot read them (`icacls`: Access is denied).
- `.pytest_cache` is also not writable.

### With explicit test paths, everything passes
`pytest -q tests backend/tests -p no:cacheprovider --basetemp <scratch>`:
```
69 passed in 5.67s
```
Split: `tests/` has 11 passed, `backend/tests/` has 58 passed.

### `python evolve.py --rounds 2 --agents 2 --mode random`
```
round 0  dev  1911.4  val  2039.7  (start: dispatchiq/policies/naive.py)
round 1  dev  1649.9  val  1742.2  ACCEPTED  feasible 2/2  0.2s
round 2  dev  1649.9  val  1742.2  kept      feasible 2/2  0.2s
saved runs/20261011-151607.json
```
- `runs/latest.json` **is written** (8337 bytes).
- The champion is the parametric policy with `PARAMS = {"emergency_by_start": 0, "regret": 0, "resequence": 0, "relocate_iters": 2, "postpone_factor": 0.5}`.
- **Before this run there was no evolve run in `runs/`.** The six locked folders could not be inspected.

### Reference scores (same `sandbox.evaluate`, not held-out)

| Policy | dev mean cost | validation mean cost | val on-time | val emergency min |
|---|---|---|---|---|
| naive (round 0) | 1911.4 | 2039.7 | 52.3% | 56.3 |
| insertion (textbook) | 1663.5 | 1801.2 | 57.9% | 67.1 |
| parametric with default PARAMS | 1730.3 | 1860.7 | 54.4% | 56.3 |
| random-search champion above | 1649.9 | **1742.2** | 57.6% | 59.6 |

- After one round, random search already beats insertion on validation (1742.2 vs 1801.2).
- The README's held-out table (1589 / 1377 / 1397) was **not reproduced**. `heldout.py` was not run, and no `runs/heldout_result.json` exists.

### LLM
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `FALLBACK_1_*`, `FALLBACK_2_*` and `MONGODB_URI` are **all unset**, in the process, user and machine scopes.
- There is no `.env` file, and the code does not load one (no dotenv).
- `python evolve.py --rounds 1 --agents 1` printed the following, exited 1, and left `latest.json` unchanged:
```
No LLM provider configured (set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL). Use --mode random to test offline.
```

### Windows and `resource`
- The host has no `resource` module (`No module named 'resource'`).
- `sandbox.RUNNER` now wraps the import in `try/except`, so the child runs on Windows **without the 1 GB memory cap**.
- The only remaining Windows problems: the locked `runs/*` folders break bare `pytest`, and `.pytest_cache` is not writable.

### Backend smoke test
In process, using `TestClient(create_app(StateStore(None)))`, so nothing persisted:
- **Health:** ok.
- **Scenario:** 10 techs, 25 jobs, `now_min` 690, valid, revision 0.
- **`demo_emergency()` preview:** `ready` in 12.2 ms. E01 goes to T00 at 718, and J03 shifts 750 → 767. `first_feasible` shifts 38 minutes against 17 for `stable_insertion`.
- **Impossible event:** `no_feasible_plan` with `feasibility_proven_impossible: true`.
- **`technician_unavailable` T03:** `ready`, 1 change.
- **Commit with an unknown proposal:** 404 `UNKNOWN_PROPOSAL`.
- Uvicorn itself was not started.

---

## 3. The AI loop today

### `TASK` prompt (verbatim, `dispatchiq/proposers.py:21-43`)
```
You are improving a field-service dispatcher's RE-PLAN function.

Situation: it is mid-day. One or two technicians just called out sick and 1-3 emergency jobs arrived.
Write `def replan(state) -> dict` returning {tech_id: [job_id, ...]} in visiting order for the OPEN jobs.

state = {
  "time": minute of day, "min_per_km": float,
  "techs": [{"id","name","skills":[...],"sick":bool,"free_at":minute,"loc":[x,y],
             "shift_end":minute,"max_overtime":minutes,"remaining":[job ids from the morning plan]}],
  "jobs": {job_id: {"loc":[x,y],"skill":str,"duration":min,"earliest":min,"latest":min,
                    "priority":1|2|3|5,"emergency":bool,"release":min,"morning_tech":tech id or null}}
}
HARD rules (any violation = the whole day fails): sick techs get no jobs; tech must have the job's skill;
each job at most once; every emergency assigned; a tech may not finish more than max_overtime past shift_end.
COST to minimise (checker, lower is better): travel minutes + sum(lateness_minutes * priority) + overtime minutes
  + 150 * priority for each job left unscheduled + 20 per job moved from one healthy tech to another
  + minutes from each emergency's release to its start.
You may `from dispatchiq.helpers import route, route_cost, travel_min, drop_until_feasible`:
  route(state, tech, seq) -> {"travel","weighted_late","overtime","end","emergency_wait","feasible"}
  route_cost(state, tech, seq) -> float (route part of the cost; 1e6 if infeasible)
  drop_until_feasible(state, tech, seq) -> (kept_seq, dropped_ids)
Only the Python standard library is available. Must run in well under 1 second per day. Deterministic.
Return ONLY one ```python code block containing the full module.
```

### `STRATEGIES` (`proposers.py:45-53`)
Agent *i* always gets `STRATEGIES[i % 6]`.
1. "Make emergencies faster: choose the tech who can START the emergency soonest, not the nearest one."
2. "Add a local-search pass after insertion: try relocating and swapping open jobs within and between healthy techs, keeping a move only if total estimated cost (including the churn penalty) drops."
3. "Use regret insertion: insert first the job whose best and second-best insertion costs differ most."
4. "Re-sequence each healthy tech's remaining jobs (e.g. by time window and 2-opt) to cut lateness and travel."
5. "Reduce unscheduled high-priority jobs: allow bumping a priority-1 job to tomorrow to fit a priority-3 job."
6. "Balance load: prefer techs with slack before shift_end; avoid stacking overtime on one tech."

### What an agent receives each round
From `LLMProposer.propose` and `evolve.feedback`:
- the full current champion code;
- `feedback(champ_dev)`: the champion's dev mean cost, its infeasible-day count, and its **3 worst dev days** (cost, travel, weighted lateness, late jobs, unscheduled, moved, emergency response, overtime, or the first 3 violations if infeasible);
- its fixed strategy line.

Settings: temperature 0.7, a single user turn, no tools.

### What an agent does NOT receive
- Other agents' code or scores from this round or earlier rounds. These are recorded in `rec["candidates"]` but never fed back.
- Errors or violations from rejected candidates, including its own previous attempt.
- Any history or memory of what was tried. Each call is stateless, and the champion is the only thing carried forward.
- Validation results, or how far the champion is from insertion or random search.

### Roles
- Only one role: the proposer (`LLMProposer`, or `RandomSearchProposer` for ablation).
- Selection is plain code in `evolve.main`: best dev cost wins if it also improves validation with 0 infeasible days.
- There is no critic, planner or summarizer.

### `sandbox.py` isolation
- **How it runs:** `evaluate(code, seeds, timeout=60)` writes the code to a temp file and runs `python -I -c RUNNER` in a subprocess.
- **Environment:** only PATH, SYSTEMROOT, TEMP, TMP and WINDIR are passed through, so API keys do not reach the child.
- **Inputs and outputs:** day states go in on stdin and plans come back as JSON. The parent checks the result count, then scores each plan in-process with `simulate.check`.

Limits, checked by probes in this audit:
- **Filesystem:** a candidate **can read repo files**. My probe read `README.md` (4057 chars) and listed the child env keys `['PATH','SYSTEMROOT','TEMP','TMP','WINDIR']`. Network access is also unrestricted (from the code; no network probe was run).
- **Memory:** the 1 GB cap is Unix-only, so there is none on Windows.
- **Timeout:** works. `sleep(5)` with `timeout=2` returned `['timeout after 2s']` after 2.0 s. The timeout covers the whole batch of days, not each day.
- **Inputs:** `evaluate` accepts **seed numbers only**. It rebuilds states from `generator.make_day`, so it cannot run a policy on an arbitrary or live state.
- **Execution:** candidate code is `exec`'d with full Python, so this is not a security sandbox. The module docstring and the audit both say so.

### Tokens and seconds per round
- Only the random run exists: 0.2 s per round, `tokens: 0`.
- No LLM round has ever run, so there is no LLM token or latency data.
- Policy evaluation alone is about 0.05–0.13 s per 30 days.

---

## 4. The checker (`dispatchiq/simulate.py`, `check`)

**HARD rules.** Any one of these makes the day infeasible, with cost `INFEASIBLE_COST = 100_000` (line 109):
1. The proposal is not a dict (line 115).
2. Unknown tech id (124).
3. A tech's value is not a list (127).
4. A sick tech is given any job (130).
5. A job id is not a string (133).
6. A job is not an open job, for example a frozen or unknown job (136).
7. A job is assigned twice (138).
8. The tech lacks the job's single `skill` (140).
9. An emergency is not assigned (143).
10. A tech finishes more than `max_overtime` past `shift_end` (154). The default is 90 min, from `model.Tech.max_overtime`.

**SOFT rules.** These only add cost (line 175):
- travel minutes (weight 1);
- lateness past `latest` (latest *start*), times priority;
- overtime minutes, weight 1, up to the 90-minute hard cap;
- each unassigned open job: `W_UNASSIGNED × priority`;
- each job moved between healthy techs: `W_CHURN`;
- each emergency's minutes from release to start: `W_EMERGENCY`.

**Not checked at all:**
- completion before a window end (there is no such field);
- shift start;
- capacity;
- locked jobs;
- frozen jobs (the policy never sees them);
- the emergency 2-hour promise as a hard rule.

### Emergency late on its promise: still accepted
The generator sets `latest = release + 120` (`generator.py:55`).
- **Hand-built probe:** one tech at (0,0) free at 600, emergency at (75,0) with release 600 and latest 720.
- `check(st, {"T0":["E0"]})` gives:
```
feasible=True cost=450 violations=[] routes={'T0': [{'job': 'E0', 'start': 750.0, 'end': 810.0, 'late': 30.0}]}
```
- So the emergency starts 30 minutes after its promise and is still accepted. Cost = travel 150 + lateness 30×5 + wait 150.

On generated days, every one of these days is feasible:

| Policy | Split | Emergencies | Started after the 2-hour promise |
|---|---|---|---|
| naive | dev | 64 | 13 (e.g. seed 5 E0, 84 min late) |
| naive | validation | 57 | 5 |
| insertion | dev | 64 | 8 (e.g. seed 8 E2, 105 min late) |
| insertion | validation | 57 | 6 (e.g. seed 100 E0, 180 min late) |

By contrast, `backend/validator.py` treats this as HARD (`EMERGENCY_DEADLINE`, `CUSTOMER_WINDOW`).

### Cost weights
- **Main definition, `simulate.py:16-18`:** `W_UNASSIGNED = 150`, `W_CHURN = 20`, `W_EMERGENCY = 1.0`. Travel, lateness×priority and overtime have an implicit weight of 1.
- **Copies elsewhere:**
  - `policies/insertion.py:12` (`UNASSIGNED = 150`);
  - `policies/parametric.py:11-12` (`CHURN = 20`, `UNASSIGNED = 150`);
  - hardcoded in the `TASK` text;
  - `helpers.route_cost` uses `1e6` for infeasible.
- **The backend has no weights.** It uses the lexicographic ranking in `backend/schemas.py` (`Ranking.key()`) and `optimizer._rank`.

---

## 5. Fit for a live app

| Need | Existing function(s) | Notes |
|---|---|---|
| Build the morning plan | Legacy: `simulate.morning_plan(day)`. Operational: `backend.scenario.make_scenario()` | `morning_plan` uses soft windows and can leave jobs unassigned or late. `make_scenario` is a fixed fixture with hard-coded starts, not a planner. There is no operational morning-planning function or endpoint (also listed in `frontend/evidence/QA.md`) |
| Apply a disruption | Legacy: `simulate.freeze`, `simulate.replan_state(day, plan)`. Operational: `backend.optimizer.optimize(snapshot, event, strategy)`, used by `StateStore.preview` | The operational path handles `emergency` and `technician_unavailable` on a private copy |
| Run a policy | Legacy: `sandbox.evaluate(code, seeds)` (seeds only), or in-process `exec` plus `replan(state)` | Nothing runs a policy on a live `Snapshot` |
| Score a schedule | Legacy: `simulate.check(state, plan)`. Operational: `backend.validator.validate_schedule(snapshot, original)` and `backend.metrics.schedule_metrics(snapshot)` | Different semantics: soft vs hard windows and deadlines, float vs int minutes |
| Diff two schedules | `backend.metrics.diff_metrics(before, after)`, `backend.explanations.changes(before, after, candidate_id)` | Legacy only has `Score.moved` |

### Can `champion_code` from `runs/latest.json` be the live re-plan policy?
**What works:**
- It loads. `exec` gives a callable `replan`.
- It runs through `sandbox.evaluate` on dev seeds 0–2 (mean cost 1712.5, 0 infeasible).

**What is missing:**
1. **Input adapter.** Nothing converts `Snapshot` to the legacy `state` format. Differences:
   - `required_skills` is a list, while legacy has a single `skill`;
   - `availability` vs `sick`;
   - `window_end_min`, `deadline_start_min`, `max_service_min` and `locked` have no legacy fields;
   - frozen and locked work must be excluded from the open jobs, but locked future jobs must keep their owner and time.
2. **A run-on-state entry point in the sandbox.** `evaluate` only takes seeds.
3. **Output adapter.** Plan to `Snapshot`. `backend.optimizer._rebuild(snapshot, plan)` already does this (private helper), then `validate_schedule`.
4. **Fallback.** The champion was selected under soft semantics, so its plans can fail hard validation (late emergencies, window end, capacity). Each live output needs validation and a fallback to `stable_insertion`. It has never been evaluated on the 10/25 fixture.
5. **Contract change.** `Strategy` (`schemas.py:17`) and frontend `types.ts` only allow `stable_insertion` and `first_feasible`. `HealthResponse.optimizer` is fixed to `"feasible_insertion"`. Adding an `evolved` strategy needs both owners to agree (see CONTRACTS.md and the developer prompts).
6. **Policy.** `DEVELOPER_1_PROMPT.md` says operational endpoints must never accept policy code. Loading a server-side champion is different, but it still executes generated code next to the API, and the sandbox is not a security boundary.
7. **It is not LLM output.** The current `latest.json` champion is a random-search parametric policy.

---

## 6. Gaps and estimates (one developer; hours are estimates, not measurements)

### a. Evolve loop with a real LLM, beating insertion on validation
- **Exists:** `LLMProposer` (OpenAI-compatible, fallbacks), `evolve.py` with dev, validation, the held-out guard and Mongo logging.
- **Missing:**
  - Provider credentials. No LLM call has ever succeeded here.
  - Insertion is not reported in the run. Random search already beats insertion on validation (1742.2 vs 1801.2), so the meaningful bar is beating the random-search champion.
  - No live check that `extract_code` handles real model output.
- **Estimate:** 2–4 h once credentials exist. About 0.5 h to connect and smoke-test, the rest on prompt and feedback iteration. Whether it wins is not knowable in advance.

### b. Critic role plus a memory of lessons
- **Exists:** `evolve.feedback()` (3 worst champion days) and per-round candidate notes and errors stored in the run JSON.
- **Missing:** a second LLM role that reads failing candidates' violations and costs and writes next-round hints. Also a persisted memory of tried ideas and results, passed into `propose`, plus logging of critic tokens and time.
- **Estimate:** 3–5 h.

### c. FastAPI service where live re-plan uses the evolved champion
- **Exists:** the full FastAPI service, store and validator.
- **Missing:** everything listed in §5 (adapters both ways, sandbox run-on-state, validation plus fallback, new strategy value, tests). The frontend type change is owned by the frontend developer.
- **Estimate:** 4–6 h. More if the champion has to be re-evolved against hard rules to pass validation.

### d. Preview / approve / reject with revision checks
- **Exists, done:** `StateStore.preview/commit/reject/reset` with epoch and revision checks, TTL expiry, consumed/stale/rejected states, revalidation on commit, and atomic persistence. 58 backend tests pass, and QA.md reports UI integration tests passing.
- **Missing:**
  - It is not on `main`. `feature/optimization` and `origin/main` need merging, and worker types (v1.1) have no backend support.
  - No approver identity and no rejection history.
- **Estimate:** 0.5–1.5 h to merge and re-verify. Worker types in the backend would add about 3–4 h.

### e. Natural-language event intake to a validated structured event
- **Exists:** strict Pydantic `EmergencyEvent`, `UnavailableEvent` and `JobInput` (`extra="forbid"`, strict types). The UI uses a preset form, not free text.
- **Missing:** an endpoint, for example `POST /api/events/parse`, a server-side LLM call that fills the schema, validation against the snapshot (unique id, `at_min == now_min`, known tech, known skills), a clarification/error path, tests, and the UI text box (frontend owner).
- **Estimate:** 3–4 h backend, plus about 2 h UI.

---

## 7. Questions to answer before planning

1. **Base branch.** Which branch do we build on? `feature/optimization` has the backend and redesign but not worker types; `origin/main` has worker types but no backend. Who merges, and when?
2. **Uncommitted frontend work** (redesign v2, 12 modified plus several untracked files). Whose is it, and will it be committed before anyone else touches `frontend/`?
3. **LLM provider.** Luminal (or other) base URL, model and rate limits: when will they be available, and is there a fallback key?
4. **Judged claim.** Is it the research result (evolved policy beats insertion and random search on held-out days), the live app, or both? EXECUTION_PLAN flags a Track 1 vs "1B" mismatch: which track and rules apply?
5. **Hard deadlines in research.** Should the evolve loop keep the legacy soft checker, which accepts late emergencies, or be scored by the strict backend validator? This decides whether an evolved champion can ever pass live validation.
6. **Generated code in the live server.** Is running the evolved champion inside the API process acceptable for the demo, given the sandbox can read files and has no memory cap on Windows? Or must live re-plan stay in a subprocess, or stay insertion-only with the champion shown as research?
7. **Worker types (contract v1.1).** In scope for the backend, or frontend-only?
8. **Locked `runs/` folders.** May the six access-denied folders be removed or have their permissions fixed so that plain `pytest -q` works? They block collection.
