# DispatchIQ frontend design system

The application’s system is implemented in `src/styles/index.css` and the existing `src/components/ui/` primitives. System fonts avoid network/font-loading dependencies. Icons use the existing Lucide package; dialogs and sheets retain Radix focus management.

| Token | Value / role |
|---|---|
| Canvas | `#f5f6f8` |
| Surface | White; sidebar `#fbfcfd` |
| Text / secondary | `#202b3d` / `#626f82` |
| Divider | `#e3e7ed`; one border per meaningful panel |
| Selected / approved | Blue `#285cd7`, pale `#edf2fd` |
| Proposed change | Amber `#965600`, pale `#fff3d9`; clock/arrow and dashed bar border |
| Emergency / failure | Red `#be303b`, pale `#fff0f1`; siren or error icon |
| Completed / checked / approved action | Green `#277452`, pale `#eaf6ef`; check icon and status text |
| Spacing | 4 / 8 / 12 / 16 / 24px tokens |
| Controls | 32–36px, 8px corners; visible keyboard focus |
| Grouped surfaces | 10–12px corners; subtle dividers; no decorative shadows |
| Headings | Page 22–24px; inspector 14–17px; section 12–14px |
| Body / metadata | 12–14px body, 10–12px metadata; 9px compact map annotations |
| Schedule | Sticky technician column, 38px lane, 29px bars; tabular time; completed/active/upcoming/locked treatment |
| Navigation | 200px rail; compact icon rail at 1280px; menu at ≤1024px |
| Inspector | 356px contextual desktop panel at ≥1360px; ≤420px Radix sheet on smaller screens |
| Mobile | 390px verified; map/schedule tabs, current-time scroll, contained timeline scroll, review sheet |

Operational summary always describes **approved** state. The board’s Loaded snapshot / Approved / Proposed selector affects map and timeline only. Proposal metrics explicitly describe the candidate. Loaded snapshot means the state captured on page load/reset; it is not mislabeled as a morning plan.

Proposal review prioritizes emergency site, response deadline, recommended technician, estimated start, actual impact and old/new placements. Explanation, strategy comparison and evaluated options are disclosed on demand. Approve and Reject remain accessible at the bottom. Invalid, expired and stale proposals cannot be approved. Color is paired with status text, icons, selected outlines or dashed borders.

Use native labels, searchable list inputs, native selects, accessible buttons, `aria-current` navigation, `aria-pressed` technician selection, announcements and Radix dialogs. Reduced-motion overrides disable continuous animation. No unnecessary component library was added.

The refinement adds manual rail collapse/expand, named icon tooltips, timeline focus/restore, and a Radix cluster appointment chooser outside the compact map canvas. All four operational summaries remain visible on mobile. The risk label discloses its precise source. Closing detail panels preserves selection.

Proposal facts form three paired rows. Current/proposed comparison comes first, with changed rows by default and an all-jobs toggle. Explicit unchanged/time-shift/reassignment/added labels accompany restrained colors; full start/end intervals use tabular numerals. Travel, total displacement, response and runtime remain in details. The map module/CSS loads separately; product background specificity survives the lazy stylesheet.
