# DispatchIQ operational backend

FastAPI contract-v1 implementation on `feature/optimization`. It adds strict operational scheduling alongside the preserved research prototype. No frontend files or original benchmark generator/held-out artifacts are changed.

## Start locally

From the repository root, PowerShell:

```powershell
python -m venv .venv  # only if not already created
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Use exactly **one backend worker**: operational state and proposal lifecycle are protected by an in-process lock. Do not use multiple workers or replicas with the local JSON store. Reload may be used for development; pending proposals are lost on restart and must be previewed again.

Health: `http://127.0.0.1:8000/api/health`. Interactive API documentation: `http://127.0.0.1:8000/docs`. OpenAPI: `http://127.0.0.1:8000/openapi.json`.

No API key, database, map service or internet connection is needed after dependencies are installed. The server persists synthetic committed state to ignored `runs/operations-state.json`. Startup fails closed for corrupt/invalid persisted state. Use the reset API to restore the baseline; do not delete arbitrary files. Backend-local dependencies are pinned to versions tested on Python 3.13.5/Windows. Research-only dependencies remain in the root requirements file.

## API and frontend integration

The existing [contract](../docs/CONTRACTS.md) is preserved: no fields or endpoint names were renamed. Pydantic rejects unknown fields, numeric coercion, malformed identifiers, invalid skills/coordinate pairs, and nonfinite numbers. Full snapshot responses expose explicit assignment intervals, statuses, travel and validation.

Implemented endpoints:

```text
GET  /api/health
GET  /api/scenario
GET  /api/technicians
GET  /api/jobs
GET  /api/schedule
GET  /api/metrics
POST /api/events/preview
POST /api/optimize
POST /api/events/commit
POST /api/events/reject
POST /api/reset
```

Frontend flow:

1. Load `/api/scenario`. Display this committed snapshot; capture its ID, epoch and revision.
2. Send preview with `scenario_id`, `scenario_epoch`, `base_revision`, `strategy`, and the event. Ready proposal contains the full `proposed_snapshot`, actual `changes`, `candidates`, `comparison`, `search`, and measured `runtime_ms`.
3. Keep the committed board unchanged. Display proposal bars and explanations separately. Preview does not persist the event or revise technician availability.
4. Approve explicitly using proposal ID and its base metadata; success returns a full new committed snapshot. Reject sends the same request to `/events/reject`. Never approve `no_feasible_plan`.
5. On 409/410 refresh the committed snapshot and preview again. On 422 show field/error details. On 503 preserve the last committed board.
6. Reset uses current base metadata; it creates a new epoch, increases revision and invalidates old proposals.

Collections include `schema_version`, `scenario_id`, `scenario_epoch` and `revision`. Prefer the full scenario endpoint when updating multiple panels to avoid mixing revisions. Vite should proxy `/api` to `127.0.0.1:8000`. Development CORS also permits localhost/127.0.0.1 port 5173; no browser credentials or secrets are required.

Examples under `backend/examples/` are captured from the running API and are **development fixtures**, not a network-error fallback. Proposal IDs/epochs/expiry/runtime values are specific to the capture. Rebuild live request metadata from GET scenario; don't paste an old example proposal ID into another session. `emergency-event.json`, `impossible-event.json`, and `unavailable-event.json` contain reusable event bodies for this simulated 11:30 scenario.

## Scheduling behavior

The explicit baseline has ten technicians, twenty-five assigned routine jobs, multiple certification sets and local km-grid locations. Completed/in-progress work is frozen; Priya has a job starting exactly at 11:30. One electrical job is locked. Strict overtime allowance is zero and daily service capacity is explicit.

Travel reuses `dispatchiq.model.travel` and rounds upward to whole minutes. Technician `location` is the route starting/base location; future routing derives free time/location from the last frozen job. Locations and routes are synthetic; there is no live GPS, traffic or road routing. Extremely distant finite input returns no feasible route rather than overflowing.

Emergency insertion enumerates each qualified technician and allowed route position, preserving started/locked intervals and delaying flexible future starts only when needed. Every candidate passes a separate full-interval validator; final proposal and approval also validate against the original committed snapshot. Existing assigned jobs are never silently dropped. The stability objective is the documented lexicographic vector, not the legacy weighted benchmark cost.

First-feasible comparison sorts eligible technicians by earliest possible arrival from the frozen prefix, then scans route slots in order. Stable insertion examines all candidates within its budget and chooses the smallest disruption vector. Both strategies receive identical copies of the same post-event input. Their response-time versus disruption tradeoff is shown without claiming universal superiority or global optimality.

`/api/optimize` evaluates the current committed jobs without adding an event. An already valid fully assigned schedule can yield a valid unchanged proposal; this endpoint does not pretend that a no-op improved the schedule. It attempts insertion of any explicit backlog within the same constraints.

Technician-unavailable events are implemented as bounded sequential reassignment of that tech's future jobs. Started work is finished and retained. If reassignment cannot preserve all existing assignments or a locked commitment, the event produces no feasible plan and remains uncommitted. This MVP does not silently postpone customer work; richer backlog/drop approval is deferred.

Search budget defaults to two seconds shared across the requested strategy and its comparator. A complete valid incumbent may be offered if search ends early. `budget_exhausted` and candidate count are explicit. Failed insertion alone is not a proof of infeasibility; the proof flag is true only for a necessary-condition failure such as no qualified available technician or all earliest-arrival bounds exceeding the deadline.

Explanations are deterministic and derived from the actual assignments, candidate evidence and constraint checks. No live model was called. Live paraphrasing, OR-Tools and wider relocate/swap search remain optional and deferred.

## Test and rehearse

Backend-only tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q --basetemp runs\test-tmp-backend
```

Backend plus existing research tests (install root research requirements too):

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests tests -q --basetemp runs\test-tmp-all
```

The local test temp directory avoids the host's restricted default pytest temp root. Tests use isolated memory/temp stores; they do not commit changes to the running service. Coverage includes hard windows/deadlines, skills, capacity/shifts, travel/overlap, malformed inputs, duplicate accounting, exact-now frozen and locked work, past-departure/cancellation bypasses, preview/reject immutability, stale/consumed/expired/reset proposals, commit revalidation, concurrent approval, preview/reset races, persistence failure/restart, measured comparison, repeated events and all endpoints.

Preview-only HTTP rehearsal, while Uvicorn is running:

```powershell
.\.venv\Scripts\python.exe -m backend.demo
.\.venv\Scripts\python.exe -m backend.demo --impossible
```

Explicitly approve/reset only the synthetic demo when intended:

```powershell
.\.venv\Scripts\python.exe -m backend.demo --approve
.\.venv\Scripts\python.exe -m backend.demo --reset --approve
```

The demo command first asserts preview leaves committed state unchanged. It chooses an unused emergency ID, prints actual changes/validation/comparison, and commits only with `--approve`.

On the published baseline, the captured stable proposal assigns E01 to John at minute 718 and shifts J03 from 750 to 767. First-feasible assigns Mei at 694 and shifts her job by 38 minutes. Both validate, preserve all existing work, and add four estimated travel minutes. Stable insertion reduces start displacement at the cost of 24 extra response minutes in this fixture. Runtime is measured per execution and may vary; this single scenario is not a general benchmark.

## Limits and handoff status

The API is implemented and tested locally; actual React UI integration and joint rehearsal on the other developer's machine still require Developer 2. No frontend completion, live LLM, deployment, global solver optimality or final held-out result is claimed. Latest pulled commits already repair Windows research runner startup, malformed identifiers and validation promotion; they were reused unchanged.

The original `sandbox.py` remains process separation/resource guards, not secure arbitrary-code isolation. The operational API never accepts or executes policy code. Serve locally for this synthetic demo; authentication and multi-tenant persistence are outside scope.

Implementation references: [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [FastAPI typed error handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/).
