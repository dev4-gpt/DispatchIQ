# Frontend transformation verification

Local verification: 2026-10-11, Windows, Python 3.13.5, Node 24.14.0. The API, algorithms, models and validator were reused without edits. Approval/reset tests ran against `create_app(StateStore())` on port 8001 with an isolated in-memory store; the existing port-8000 schedule was not reset by these tests. The frontend test preview ran on port 5180.

## Visual loop

Before editing, Chromium captured and inspected the real UI at 1440×900, 1280×800, 1024×768 and 390×844. See [audit](AUDIT.md), `before/` screenshots and the measured `before/inspection.json`. The first implementation was captured again under `first-pass/` before refinement.

| Observed first-pass defect | Refinement |
|---|---|
| Wordmark caption wrapped onto two lines | Compact one-line product subtitle |
| Dense job/base markers overlapped | Zoom-dependent nearby-job clustering, per-job popup list, base-label collision offsets, selected jobs/emergencies individually shown, accessible marker names |
| John’s base marker was blocked by Mei’s | Screen-space label separation with lines back to the true base coordinates; real pointer-click test now passes |
| Final desktop technician row clipped | Compact map, smaller consistent schedule lanes, reduced outer gaps; timeline owns remaining height |
| Map was too small for detailed inspection | Expand/compact map control; zoom retained and nearby groups update with zoom |
| Changed bars hid their displacement behind customer labels | Changed bars prioritize job ID, change icon and signed minute shift; customer/time remain in hover/inspector |
| Mobile started far before the simulated present | Initial scroll toward 11:30, sticky technician names; horizontal scroll stays inside the timeline |
| Emergency could disappear into a location group | Keep emergency markers individually selectable |
| Keyboard close did not return focus to New Emergency | Use the Radix DialogTrigger so Escape restores the initiating control |
| Proposal could reopen indefinitely on Escape | Explicit panel-open state and persistent Review action; close does not lose the proposal |

Final screenshots are in `after/`: approved and actual API-proposal captures at all four requested viewports. They come from the real Python optimizer, not the in-browser fixture. Desktop and compact pages stay within the viewport; mobile scrolls inside its workspace. Tests assert document width/height equal the viewport. Selection links the technician row, route and contextual inspector. Compare visually with [comparison.html](comparison.html).

## Checks

- Production `npm.cmd run build`: passed typecheck and Vite build; 1,755 modules. Primary JS 481.33 kB / 146.36 kB gzip; CSS 75.79 kB / 17.88 kB gzip. Fixture logic remains a separate lazy-loaded chunk in real API mode.
- `npm.cmd ls --depth=0`: declared dependency versions installed with no extra/missing package errors. No dependency or API-contract changes were introduced.
- Browser checks: **22 passed, 0 skipped, 0 failed, 0 flaky** — 10 fixture workflows, 1 API-unavailable check, 11 real API workflows. Machine-readable final results are in [browser-results.json](browser-results.json).
- Python regression: **69 passed in 6.15s**, using `.\.venv\Scripts\python.exe -m pytest backend\tests tests -q --basetemp runs\frontend-regression-20261011`.
- Existing static fixture demo was regenerated using `npm.cmd run build:demo`. It stays clearly labeled as frontend fixture data.

Real integration asserts that preview and rejection leave the exact committed snapshot unchanged; a ready result must have independent validation and an actual existing start change. It compares displayed explanation and comparison values with the API response, checks the approved revision and stored event, and verifies reset returns the original schedule. Stale approval is rejected after an external reset; refresh uses the new revision. No integration success path is conditionally skipped when a proposal fails.

Additional browser checks cover keyboard entry and focus return, trapped dialog focus, client expiry disabling approval, server errors preserving the board, map/base/job linkage, one inspector mode, job/technician searches and empty states, real no-qualified/tight-deadline results, real malformed-input rejection, responsive sheets, mobile map selection, and no silent fixture fallback. One 503 path is intentionally intercepted to test frontend recovery; all ordinary scheduling flows call the real API.

## Files changed

- `src/App.tsx`: application shell, real navigation, concise operational strip, map expansion, contextual inspector, responsive workspace.
- `src/components/OperationsPages.tsx`: populated Overview, Jobs, Technicians and Activity; technician inspector.
- `src/components/{ScheduleBoard,RouteMap,ProposalPanel,ScenarioControls,JobInspector}.tsx`: schedule readability, selection, accurate grouped map, emergency intake/review, progressive evidence.
- `src/components/ui/{dialog,tabs}.tsx`: responsive sheet sizing and disabled-state styling; existing Radix primitives retained.
- `src/state/{dispatch,useDispatch}.ts`: inspector lifecycle, synchronized selection, reset/reject cleanup, stale refresh, StrictMode-safe transport initialization.
- `src/styles/index.css`: visual tokens, navigation/surfaces, schedule/map/inspector/page compositions and responsive rules.
- `playwright.config.ts`, `tests/{integration,fixture-ui,api-unavailable}.spec.ts`: actual workflow assertions and configurable isolated integration target.
- `scripts/capture-ui.cjs`, `evidence/**`, `README.md`, `test-results/screenshots/**`, generated `demo/**`: reproduction instructions and review artifacts. Test-result screenshots are labeled fixture evidence; `evidence/after/` is API evidence. HTML entry files have normalized line endings for reproducible generated output.

## Remaining limits

This is a polished synthetic operations demo, not a deployed multi-tenant service. No authentication, live GPS/traffic, morning-schedule creation endpoint, approval actor, wall-clock audit timestamp or rejection-history API is present. Activity reflects committed events only. Model-generated explanations and paid map services remain optional and unused. The scheduling heuristic’s measured tradeoffs are shown without claiming global optimality.

Map overview intentionally groups nearby jobs at compact zoom; expanded map, zoom controls, cluster job lists and the schedule provide precise selection. Small screens use a review sheet rather than displaying board and details simultaneously. Accessibility checks are targeted browser checks, not a full assistive-technology certification. Core workflows were verified locally on this Windows machine; no second-device or hosted deployment verification is claimed.

Run commands, isolated API setup and fixture distinctions are in [frontend README](../README.md). MCP discovery and official documentation links are in [audit](AUDIT.md); no unconnected design tool is credited with implementing the interface.
