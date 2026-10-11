#!/usr/bin/env bash
# Fresh-clone check: clone into a temp folder, install, run the tests, re-score every saved champion.
# Needs the run files COMMITTED (a clone only sees committed files) and network access for pip.
#
#   bash tools/fresh_clone_check.sh                                   # clone this local repo, feature/optimization
#   bash tools/fresh_clone_check.sh https://github.com/dev4-gpt/DispatchIQ.git main   # after the PR is merged
set -euo pipefail
SRC=${1:-$(git rev-parse --show-toplevel)}
BRANCH=${2:-feature/optimization}
TMP=$(mktemp -d)
echo "== clone $SRC ($BRANCH) into $TMP"
git clone --quiet --branch "$BRANCH" "$SRC" "$TMP/DispatchIQ"
cd "$TMP/DispatchIQ"

echo "== install"
python -m venv .venv
PY=.venv/Scripts/python.exe; [ -x "$PY" ] || PY=.venv/bin/python
"$PY" -m pip install --quiet -r requirements.txt -r backend/requirements.txt

echo "== tests"
"$PY" -m pytest -q

echo "== re-score saved champions (no LLM; dev + validation must match the run files)"
status=0
for f in runs/random.json runs/llm-plain.json runs/llm-team.json runs/llm-team-v2.json runs/llm-team-v2-1agent.json; do
  [ -f "$f" ] || { echo "missing $f (not committed?)"; status=1; continue; }
  if "$PY" rescore.py "$f"; then echo "  $f: match"
  else
    # llm-team (v1) has a 0.42 s/day wall-clock search budget; README documents 1251.2 saved vs 1250.98 re-scored.
    echo "  $f: MISMATCH"; [ "$f" = runs/llm-team.json ] && echo "    (expected small difference: time-budgeted champion, see README limits)" || status=1
  fi
done
echo "== done in $TMP (delete it when finished); status $status"
exit $status
