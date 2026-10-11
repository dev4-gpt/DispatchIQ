# DispatchIQ operations frontend

React / TypeScript / Vite / Tailwind command center connected to the existing contract-v1 FastAPI service. The dispatch board pairs the approved schedule with a synthetic service map. A dispatcher previews an emergency, checks the actual deadline and appointment changes, and approves or rejects the proposal.

Overview, searchable Jobs, searchable Technicians and Activity all use committed server data. Details appear contextually. Desktop uses a side inspector; smaller screens use accessible Radix sheets, with map/timeline tabs on mobile. There are no empty navigation destinations.

The sidebar can collapse manually. Focus timeline hides the map; restore the split view or expand the map when geography matters. Map clusters open a keyboard-accessible appointment chooser. Closing details preserves selection. Proposal comparison defaults to changed appointments and can show every job, with explicit current/proposed technician and time intervals.

Four summaries show the committed day's available technicians, scheduled/unassigned jobs, observed at-risk appointments, and active emergencies with this client's pending review. The risk tooltip explains the source; preview does not replace committed KPI values. Runtime, travel and displacement appear in expandable review details.

## Run from the repository root

First terminal:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Second terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. Vite proxies `/api` to port 8000. `DISPATCHIQ_API` can point the proxy to another backend. Production build: `npm.cmd run build` (typecheck + build). Preview serves only static assets; an API reverse proxy is needed for a deployed app.

## Verify

```powershell
npx.cmd playwright install chromium
npx.cmd playwright test
```

An installed browser may be supplied via `CHROMIUM_PATH`. Real integration checks require a healthy backend and fail when it is absent; a passing fixture suite cannot substitute for integration. Tests reset and approve the synthetic scenario, so use an isolated service during development:

```powershell
# Repository root, dedicated terminal: actual API/optimizer, isolated in-memory store.
.\.venv\Scripts\python.exe -c "from backend.app import create_app; from backend.store import StateStore; import uvicorn; uvicorn.run(create_app(StateStore()), host='127.0.0.1', port=8001)"
```

```powershell
# frontend, dedicated preview terminal
$env:DISPATCHIQ_API='http://127.0.0.1:8001'
npm.cmd run dev -- --port 5180 --strictPort
```

```powershell
# frontend, test terminal
$env:DISPATCHIQ_API='http://127.0.0.1:8001'
$env:DISPATCHIQ_UI='http://127.0.0.1:5180'
npx.cmd playwright test
```

Three projects: ten fixture UI tests, one API-unavailable test and fifteen real API integration tests. All 26 passed in the latest complete run. They cover evidence equality, all-jobs comparison, compact-map cluster selection, collapse/focus controls, real request loading, visible changes, preview/reject immutability, commit/reset, selection linkage, stale approval, keyboard/focus return, expiry protection, server error recovery, navigation/search/empty states, and all four screen sizes.

## Design and evidence

- [Latest refinement audit, changed files, validation and limits](evidence/REDESIGN_V2.md)
- [Latest before/after browser screenshots](evidence/redesign-v2-comparison.html)
- [Prioritized audit, design direction and verified MCP availability](evidence/AUDIT.md)
- [Visual refinements, tests, files changed and limitations](evidence/QA.md)
- [Before/after browser screenshot comparison](evidence/comparison.html)
- [Design system](evidence/DESIGN_SYSTEM.md)

`evidence/redesign-v2-before/` and `evidence/redesign-v2-after/` are the latest actual API captures at 1440×900, 1280×800, 1024×768 and 390×844, with proposal views. `redesign-v2-first-pass/` preserves the refinement critique. Original `before/`, `after/` and `first-pass/` capture the previous redesign. `test-results/screenshots/` comes from the labeled frontend fixture and must not be presented as backend evidence.

## Fixture and static demo

`npm.cmd run dev:fixture` or `?fixture=dev` explicitly enables the in-browser development fixture and its amber banner. There is no automatic fixture fallback when the API fails. `npm.cmd run build:demo` rebuilds the committed static fixture under `demo/`; serve it with `python -m http.server 8080 --directory demo`. These demo results come from the frontend fixture, not the Python optimizer.

## Limits

Synthetic km-grid locations and estimated visit-order routes are not live GPS, traffic or roads. Nearby jobs cluster at the current map zoom; emergencies and selected jobs remain individual. Expand/zoom the map or open a cluster’s appointment dialog. All appointment timings, changes, metrics, options and explanations in real API mode come from server state. At-risk counts describe observed commitments, not predictive scoring. Pending review is the one ready proposal held by this client, not a server-wide approval queue.

The backend supplies the initial daily fixture; there is no endpoint for creating a custom morning schedule. Activity exposes only committed disruption events, with no actor/wall-clock audit timestamps or rejection history. Authentication, production hosting and a backend migration are outside this frontend change. Scheduling algorithms, API fields and independent validation are preserved.
