# Frontend transformation audit

Inspected the actual API-connected UI before editing at 1440×900, 1280×800, 1024×768 and 390×844. Screenshots and browser measurements are in `before/`. Existing stack: React 19 / TypeScript / Vite 6 / Tailwind 4; Radix dialog/tabs, Leaflet CRS.Simple; reducer with committed and proposed snapshots; typed fetch transport with opt-in fixture. Backend was healthy. No console exceptions or page horizontal overflow occurred in the baseline capture.

| Issue | Severity | Existing behavior | Proposed improvement |
|---|---|---|---|
| Navigation has no destinations | High | Map/Schedule buttons only move focus; technician directory occupies entire rail | Persistent product navigation; populated Overview, Jobs, Technicians, Activity; technician selection belongs to board/inspector |
| Timeline hides the end of the roster | High | Map and repeated metrics push rows below the viewport | Give schedule most space; compact horizontal service map; scroll inside timeline; fit all ten rows at desktop |
| Map obscures work locations | High | Technician bases overlap job dots; all routes shown together; schematic tiny in broad empty bands | Numbered job markers, selected route only, readable map context; label technician bases honestly |
| Completed and active jobs look identical | High | Both use grey and a lock | Separate completed/active/upcoming treatment with icons and accessible labels; locked commitments get lock even when future |
| Context stacks everything | High | Proposal plus full emergency inspector plus eligibility plus comparison | One contextual mode; key emergency/deadline/changes first; evidence disclosed on demand |
| Proposal cannot close | High | Inspector open condition always true while proposal exists, defeating Escape/drawer close | Keep review state separate from open panel; persistent Review action reopens it |
| Mobile spends space on diagnostics | High | Header badges and five metrics consume ~300px; no current-time scroll positioning | Compact header/status; two essential metrics; dedicated map/schedule tabs and sheet for detail/review |
| Technical labels dominate | Medium | `API · feasible_insertion`, hard violations, soft SLA, rev | Connected / schedule checked; customer promise alerts; revision secondary; precise diagnostics under details |
| Repeated identity and workforce information | Medium | Technician list and row names, numerous header badges, repeated revision | Product rail, compact status line and four essential operational metrics |
| Timeline bars expose only IDs | Medium | Tiny J01 labels, current time offscreen on mobile | Job ID plus customer where space permits; visible time/status in inspector, sticky tech column, initial scroll toward now |
| Axis endpoint and legend clip | Medium | Last tick clipped; mobile legend cut off | Inset labels, flexible compact legend, overflow scoped to timeline |
| Baseline name overstates provenance | Medium | `Start of day` is actually snapshot captured on load | Label `Loaded snapshot`; retain approved/proposed comparison |

## Direction and system

Neutral slate/white operational workspace, 200px product rail, compact header, restrained blue selection, amber schedule changes, red emergency/failure and green validation/completion. Four essential metrics; schedule takes most vertical space. Context appears on demand. Rounded 8px controls / 12px grouped panels, 4/8/12/16/24px spacing, 12/13/14/16/24px type scale, system font and tabular time values. No remote fonts or imagery required.

## Verified tool availability

Tool catalog has no shadcn, Figma, Context7 or Playwright MCP methods. Plugin discovery returned Figma as uninstalled/unconnected; no Figma reference was supplied. Optional Figma installation was suggested, implementation does not depend on it. Official [shadcn MCP](https://ui.shadcn.com/docs/mcp) and [Figma MCP](https://developers.figma.com/docs/figma-mcp-server/) documents were checked; documentation does not imply a connection. Reuse existing Radix-backed components and native accessible form controls rather than installing another catalog. Project-local Playwright launches installed Chromium using `CHROMIUM_PATH`; it captured all four real API views successfully. Sites local preview guidance was read; this task edits the specified Git checkout and local FastAPI client, with no hosting migration.

## Boundaries

No backend, scheduling algorithm, validator, fixture generator or API field changes. Activity displays only committed backend events: the contract has no audit timestamp, actor, rejected-event history or per-event prior snapshot. Daily schedule is read from the server; no initial scheduling creation endpoint exists. Do not invent these fields or imply live GPS/traffic.
