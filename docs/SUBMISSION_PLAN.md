# Submission plan (prepared 2026-10-11, not yet executed)

Run in order, from the repository root on `feature/optimization`, after 18:30.
- **Before step 6:** don't switch branches or merge while any `evolve.py` process is alive.
- **Steps 1 and 2:** held-out scoring and filling the README; the human runs these.
- **The rest:** the commands below.

## 0. Nothing else running
```bash
ps -ef | grep evolve.py | grep -v grep                                   # Git Bash: must print nothing
wmic process where "name='python.exe'" get ProcessId,CommandLine | grep -i evolve.py   # must print nothing
```

## 1. Held-out run (once)
```bash
python heldout.py --dry-run     # names the final solution by the validation rule; scores nothing
python heldout.py               # the run. A crash/timeout prints no scores and may be retried.
```

## 2. Fill the README blanks
```bash
python fill_readme.py --check   # held-out headline, held-out table, single-agent table
python fill_readme.py
```

## 3. Second commit: run files and results
`runs/` is gitignored, so these files are force-added:
```bash
git add -f runs/random.json runs/random.log runs/llm-plain.json runs/llm-plain.log \
           runs/llm-team.json runs/llm-team.log runs/llm-team-v2.json runs/llm-team-v2.log \
           runs/llm-team-v2-1agent.json runs/llm-team-v2-1agent.log \
           runs/heldout_result.json runs/backfill_metrics.json
git add README.md
git commit -m "Final run files, held-out result and filled README"
```

## 4. Secret scan (must be clean before any push)
```bash
bash tools/scan_secrets.sh      # working tree + every commit on every ref; matches are masked
```
- **If it finds a key:** don't push. Rotate the key in the Luminal dashboard regardless. It appeared in a chat transcript, though in no repository file as of this plan.

## 5. Merge `origin/main` into `feature/optimization`
`origin/main` (`5fe575e`) adds only frontend files and `docs/CONTRACTS_WORKER_TYPES.md`. A read-only `git merge-tree` dry run (no files touched) gives:
- **13 conflicts, all in `frontend/`:** `README.md`, `demo/index.html`, `src/App.tsx`, `src/components/{JobInspector,ProposalPanel,RouteMap,ScenarioControls,ScheduleBoard}.tsx`, `tests/fixture-ui.spec.ts`, and four screenshots in `test-results/screenshots/`.
- **Clean merges from `main`:**
  - `docs/CONTRACTS_WORKER_TYPES.md` (new)
  - `frontend/src/api/{types,devFixture}.ts`
  - `frontend/src/components/TechnicianList.tsx`
  - `frontend/src/components/WorkforcePanel.tsx` (new)
  - `frontend/src/lib/workers.ts` (new)
  - `frontend/demo/assets/index-DF-fBBYu.css` and `index-bVru0hzz.js` (new)

Rule: **keep our frontend where files conflict**; leave any uncommitted frontend files out.
```bash
git status --short -- frontend/                # if anything is listed: git stash push --include-untracked -- frontend/
git fetch origin
git merge --no-ff origin/main -m "Merge origin/main (worker-types frontend proposal, docs) into feature/optimization"
git checkout --ours -- frontend/README.md frontend/demo/index.html frontend/src/App.tsx \
  frontend/src/components/JobInspector.tsx frontend/src/components/ProposalPanel.tsx \
  frontend/src/components/RouteMap.tsx frontend/src/components/ScenarioControls.tsx \
  frontend/src/components/ScheduleBoard.tsx frontend/tests/fixture-ui.spec.ts \
  frontend/test-results/screenshots/desktop-1440-baseline.png frontend/test-results/screenshots/desktop-1440-proposal.png \
  frontend/test-results/screenshots/mobile-390.png frontend/test-results/screenshots/tablet-1024-proposal.png
git add frontend/
git rm frontend/demo/assets/index-DF-fBBYu.css frontend/demo/assets/index-bVru0hzz.js   # main's demo build; our index.html does not load them
(cd frontend && npm.cmd ci && npm.cmd run build)                                          # must pass
# If the build fails in main's clean-merged files, take ours for those too:
#   git checkout HEAD -- frontend/src/components/TechnicianList.tsx frontend/src/api/devFixture.ts frontend/src/api/types.ts
#   (and git rm WorkforcePanel.tsx / lib/workers.ts if nothing imports them), then rebuild.
.venv/Scripts/python.exe -m pytest -q
git commit                                     # completes the merge
git stash pop                                  # only if step 5 stashed frontend files; leaves them uncommitted
```

## 6. Fresh-clone check
```bash
bash tools/fresh_clone_check.sh                # clones this repo's feature/optimization into a temp folder,
                                               # installs, runs pytest, re-scores every saved champion
```
- **Expected:** every run matches except `llm-team`. Its champion has a 0.42 s/day search budget; the README documents 1251.2 saved against 1250.98 re-scored.

## 7. Push and open the pull request
```bash
git push origin feature/optimization
gh pr create --base main --head feature/optimization \
  --title "DispatchIQ: self-improving re-plan agents, critic v2, held-out result, dispatch app" \
  --body-file docs/PR_BODY.md                  # write from the README "Results at a glance" + held-out table
```
- **PR body:** ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- **After the merge:** re-run `bash tools/fresh_clone_check.sh https://github.com/dev4-gpt/DispatchIQ.git main`.
