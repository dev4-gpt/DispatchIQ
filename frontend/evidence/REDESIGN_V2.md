# Dispatch Board refinement audit

Inspected the current committed frontend against the new brief on 2026-10-11. Captured the actual API-connected app at 1440×900, 1280×800, 1024×768 and 390×844 in `redesign-v2-before/`; all four report no page exceptions or document overflow. Preserve the existing React/TypeScript/Vite/Tailwind/Radix/Leaflet stack, typed transport, selection reducer, real preview/approval/reject/reset, frozen markers, and all populated navigation pages. No backend or API changes are authorized here.

| Priority | Observed gap | Implementation |
|---|---|---|
| High | Main KPIs show progress/completion instead of promise risk and emergencies | Four accurate operational summaries; disclose the precise risk definition |
| High | Mobile hides assignment counts and would hide alerts | Keep all four summaries readable on mobile |
| High | Proposal shows changed jobs only; there is no all-jobs comparison | Default changed rows; toggle all rows, explicit current/proposed placement and unchanged label |
| Medium | Desktop rail collapses only at a breakpoint | Manual keyboard-accessible collapse/expand with named icon destinations |
| Medium | Expand map exists, but timeline cannot be prioritized | Timeline focus and restore split view; retain mobile map/timeline tabs |
| Medium | Proposal summary omits emergency priority and location | Show contract-backed priority and synthetic grid coordinates, plus qualified skills |

Tool discovery in this turn exposes no shadcn, Figma, Context7 or Playwright MCP. Use installed Radix controls and project-local Playwright/Chromium. Sites local-preview guidance applies to the named Git checkout; no hosting migration. Screenshot and workflow verification follow implementation.

## Implemented changes and refinement

Added `OperationalSummary.tsx`, `ScheduleComparison.tsx`, and Radix-backed `ui/tooltip.tsx`. Modified `App.tsx`, `ProposalPanel.tsx`, `RouteMap.tsx`, `state/dispatch.ts`, and `styles/index.css`. Updated browser helpers/integration tests, Playwright configuration commentary, capture script, README, design notes, and the generated static fixture demo. Dependency manifests, API types/contracts, and all backend/optimization files remain unchanged.

Four summaries use committed data: technician availability within the shift, the day's assigned/unassigned counts, unique jobs with observed promise/deadline/accounting/validation risk, and active emergencies plus this client's one pending ready proposal. They stay visible on mobile. A focused tooltip explains risk; no prediction or invented score is presented.

Comparison defaults to actual changed jobs, including the new emergency. Show all jobs adds unchanged rows; technician and full start/end intervals come from explicit server schedules. Changed rows show signed time shifts and non-color labels. Priority, synthetic location, required skills, recommended technician and deadline remain above comparison. Runtime, displacement, response metrics, travel impact, explanation and alternative evidence remain available through disclosure.

Inspected the first pass and final actual screenshots. Refinements made from observed issues:

1. Six proposal facts initially pushed changed intervals below the decision footer; paired facts and moved technical impact metrics into details. Both emergency and changed routine intervals are visible initially at 1440×900 and in the mobile sheet.
2. Closing the inspector cleared the selected job, so map restoration lost its highlight; close now preserves selection while hiding details.
3. A long Leaflet cluster popup clipped/shifted within the compact map and blocked clicks; replaced it with a scrollable Radix appointment dialog. Keyboard dismissal returns focus to the map, and selecting a job links its exact marker and technician row.
4. The first tooltip import caused a transient development optimizer reload (`useRef` startup error recorded in first-pass inspection); restarted the preview after dependency optimization. Final clean-start inspection reports zero exceptions at all four widths.
5. Lazy map CSS temporarily overrode the neutral background; scoped the product Leaflet style to its service-map container, then repeated all four responsive workflows/screenshots.
6. The tooltip import initially grew the main bundle beyond Vite's 500 kB threshold; lazy-load the map module/CSS. Production main JS is 367.15 kB (115.03 kB gzip), separate map JS 155.12 kB (45.64 kB gzip). These are bundle sizes, not measured browser latency claims.

## Verification

- Complete Playwright run: **26 passed**, zero failures, skips or flaky results, **44.2 seconds**. Ten labeled fixture checks, one missing-API check, fifteen actual API checks. Machine-readable results: `redesign-v2-browser-results.json`.
- After the final scoped map-style change: all **four** viewport API workflows passed again (10.0 seconds), with refreshed baseline/proposal screenshots.
- Real integration checks include server-interval equality for changed rows, all/changed toggles, KPI source values, travel-impact evidence, actual pending-request loading, preview/reject immutability, approve/reset, stale/expired approval protection, cluster dialog/focus return, navigation/search/empty states, and error recovery.
- Final `npm.cmd run build`: passed with no chunk warning. `npm.cmd run build:demo`: passed; its intentionally combined fixture JS is 539.32 kB and retains Vite's size warning. The real API build splits the map.
- Final capture: no page exceptions or document overflow at 1440×900, 1280×800, 1024×768, 390×844. See `redesign-v2-after/inspection.json`. Desktop/mobile baseline and proposal screenshots inspected, including 1280/1024 drawer behavior.
- Backend untouched. QA used real FastAPI/optimizer on a separate in-memory store at port 8001 and Vite 5180, preserving the user's existing service/state. No new dependencies or remote design/font/map/model assets.

## Limits and startup

No design MCP tools were available or called; local Playwright/Chromium successfully performed browser inspection/testing. No Figma design was supplied. Existing Radix components, tokens, system fonts and Leaflet were reused.

Synthetic coordinates and travel remain estimates. Risk is observed lateness/unassigned/validation information, not a forecast; “scheduled” counts the whole day's assigned work, including completed appointments. Pending review describes this client rather than all dispatchers. Smaller desktop timelines scroll within their panel; mobile horizontally scrolls within the schedule. Accessibility checks cover keyboard, focus, labels, motion and responsive behavior, not formal certification. Authentication, production hosting and missing backend editing/audit endpoints were not added.

Run the backend from the repository root with `.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`. In another terminal run `cd frontend`, `npm.cmd ci`, then `npm.cmd run dev -- --host 127.0.0.1`; open `http://127.0.0.1:5173`. Full isolated QA commands are in `../README.md`. The local QA services were stopped after verification.
