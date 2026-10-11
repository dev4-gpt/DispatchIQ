# Audit verification record

Date: 2026-10-11. Checkout `main`, `0e8fbc48b1d86492a1693ddf3ef63714aca36382`.

| Check | Result |
|---|---|
| Clone and `git pull --ff-only` | Successful; already up to date |
| Host Python/Node | 3.13.5 / 24.14.0 |
| PowerShell npm | `npm.cmd` works; npm.ps1 blocked by execution policy |
| Clean `.venv` install of `requirements.txt` | Successful after network-enabled retry |
| Clean `.venv` `pip check` | No broken requirements |
| Global and clean pytest | Each reports 6 passed, 2 failed; Unix-only `resource` import breaks Windows policy subprocess |
| Compileall of original application/package/tests | Successful |
| Browser launch | Original Streamlit app, `127.0.0.1:8501`, headless Chromium through existing local JS Playwright |
| Rendered desktop/mobile | Screenshots saved at 1440×900 and 390×844; “No run yet” empty state |
| Clean Streamlit AppTest | Zero app exceptions; same empty-state warning; cold-start timeout increased from 3 to 30 seconds |
| Original held-out hash | Matches committed value; no final held-out scoring executed |
| Dev diagnostic comparison | Naive and insertion directly invoked on identical copied states for seeds 0–9; see diagnostics.json |
| Hard-deadline probe | Existing checker accepts a 9-minute-late emergency as feasible |
| Malformed job identifier probe | Existing checker raises TypeError |
| Live LLM/Mongo | Unconfigured and unverified; no provider request sent |
| Design MCP | No shadcn/Playwright MCP exposed; Figma discovered as uninstalled; no Figma design queried |
| Documentation local links | All resolve |
| Whitespace check | `git diff --check` passed for tracked change |

All application source was preserved. Local changes are planning/audit files and ignoring `.venv/`. The resolved dependency list is an environment snapshot, not proof of full research-dashboard compatibility or a universal lockfile. Diagnostic timing measures only trusted policy calls; no operational API/frontend was implemented or benchmarked.
