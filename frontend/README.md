# DispatchIQ operations frontend (Developer 2)

React + TypeScript + Vite command center for the emergency re-plan workflow in `docs/CONTRACTS.md`:
- **Load:** the committed schedule.
- **Inspect:** technicians and jobs on a synthetic-city map and a shift timeline.
- **Preview:** introduce an emergency and preview the server's proposal (changes, candidate evidence, strategy comparison, validation).
- **Decide:** approve or reject it. Reset when needed.

The Streamlit research view (`../app.py`) is unchanged and separate.

## Run

```bash
cd frontend
npm ci
npm run dev              # real API: proxies /api to 127.0.0.1:8000 (Developer 1's FastAPI)
npm run dev:fixture      # DEVELOPMENT FIXTURE: in-browser stand-in, orange banner, not backend results
npm run build            # typecheck + production build
npx playwright install chromium   # once (or set CHROMIUM_PATH to an existing Chromium)
npx playwright test      # runs the three test projects below
```

On Windows PowerShell use `npm.cmd` / `npx.cmd`. Set `DISPATCHIQ_API` to point the proxy somewhere other than `http://127.0.0.1:8000`.

## Status: what is and isn't verified

| Area | Status |
|---|---|
| Typed client + contract types (`src/api/types.ts`, `client.ts`) | Done; frozen from CONTRACTS.md v1 |
| Shell, metrics strip, technician list, map, timeline, job inspector, proposal panel, scenario controls | Done |
| Emergency preview → approve / reject / reset, stale and no-plan handling | Done; tested against the **development fixture** |
| Responsive 1440 / 1024 (drawer) / 390 (tabs) | Done; screenshots in `test-results/screenshots/` |
| No silent fallback when the API is down | Tested (`api-unavailable`): error + retry, no fixture data |
| **Integration with the real backend** | **Not yet verified.** The backend did not exist when this was built. `tests/integration.spec.ts` skips itself until `GET 127.0.0.1:8000/api/health` answers |

Test projects (`playwright.config.ts`):
- `fixture-ui`: 10 UI workflow tests against the labeled development fixture. They check UI behaviour and contract handling, **not** backend integration.
- `api-unavailable`: real-API mode with nothing behind the proxy.
- `integration`: the real FastAPI service. Start it first, then run `npx playwright test --project=integration`.

## Development fixture (`src/api/devFixture.ts`)
- **What it is:** opt-in only (`npm run dev:fixture` or `?fixture=dev`), with an orange banner while active. It's a synthetic 10-technician / 25-job day at 11:30 that follows the contract's units, statuses, hard windows, frozen work, revisions and proposal lifecycle.
- **It really computes:** insertion candidates, timings, validation, metrics and both strategies. Nothing is canned.
- **It is not the backend's optimizer or validator.** Its numbers must never be shown as product results.
- **Test hook:** `window.__dispatchiqFixture.simulateExternalCommit()` exists only in fixture mode, to test stale approvals.

## Design tooling (checked in this session)
- **shadcn:** no shadcn MCP was available. The official CLI (`npx shadcn add …`) failed with "not authorized" fetching `ui.shadcn.com/r/...` (network-restricted environment). Per the 10-minute timebox, `src/components/ui/` contains small hand-written shadcn-style components (Button, Badge, Tabs, Dialog/Sheet) on Radix primitives.
- **Figma:** no Figma MCP or design file was available.
- **Browser:** project-local `@playwright/test`.
- **Map:** Leaflet `CRS.Simple` over the synthetic km grid. No tiles or network, so it works offline. Lines show estimated visit order, not roads.

## Visual review (actual screenshots, fixed, recaptured)
1. Mobile: the page scrolled horizontally and "Introduce emergency" was cut off. Fixed: the header wraps and the root clips x-overflow (scrollWidth 390 = viewport).
2. Mobile: the schedule header was cramped ("Start of day" truncated). Fixed: shorter labels and title on mobile.
3. Desktop: the "Ready to review" badge wrapped onto two lines. Fixed: badges don't wrap.
4. Desktop: the map was a small square in empty bands. Fixed: a faint surrounding street grid plus an outlined service area.
5. The disclaimer label overlapped the zoom control or was clipped at the bottom. Fixed: moved top-right.
6. The strategy comparison table ran its column headers together. Fixed: spacing, right-aligned numbers, "(proposed)" marker.
7. The fixture showed an emergency starting "0 min after the call" (travel not applied after idle time). Fixed in the fixture: idle technicians depart no earlier than now.

## Notes for Developer 1 (contract questions, no fields renamed)
- `Proposal` doesn't echo the requested `strategy`. The UI tracks it locally to label the proposed row in `comparison`. Echoing it would remove the ambiguity.
- The UI only offers **Approve** when `status === "ready"`, `proposed_snapshot` is non-null and `validation.valid` is true. It treats 409/410 lifecycle codes as "outdated proposal".
- The UI sends emergency `JobInput` with `release_min = at_min = snapshot.now_min`, `priority: 5`, `locked: false` and a new `E##` ID. 422 responses are shown verbatim from `error.message`.
