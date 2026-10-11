#!/usr/bin/env bash
# Scan the working tree AND every commit on every ref for API keys and bearer tokens.
# Matches are MASKED (first 9 characters only); this script never prints a full secret.
#
#   bash tools/scan_secrets.sh        # exit 0 = nothing found, 1 = something found
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

PATTERN='lum_live_[A-Za-z0-9]{8,}|[Bb]earer [A-Za-z0-9._~+/=-]{16,}|sk-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,}|(api[_-]?key|secret|token)["'"'"' ]*[:=] *["'"'"'][A-Za-z0-9._-]{16,}["'"'"']'
mask() { sed -E 's/(lum_live_|[Bb]earer |sk-|gsk_)?([A-Za-z0-9._~+\/=-]{0,9})[A-Za-z0-9._~+\/=-]*/\1\2…[masked]/'; }
found=0

echo "== working tree (tracked + untracked, excluding .venv, node_modules, .git) =="
while IFS= read -r -d '' f; do
  if grep -IEn "$PATTERN" "$f" >/dev/null 2>&1; then
    grep -IEon "$PATTERN" "$f" | while IFS= read -r m; do echo "  $f:${m%%:*}: $(echo "${m#*:}" | mask)"; done
    found=1
  fi
done < <(find . -type f -not -path './.git/*' -not -path './.venv/*' -not -path '*/node_modules/*' -print0 2>/dev/null)

echo "== history (every commit on every ref) =="
revs=$(git rev-list --all)
hits=$(git grep -IEo "$PATTERN" $revs -- 2>/dev/null | sort -u)
if [ -n "$hits" ]; then
  found=1
  echo "$hits" | while IFS= read -r line; do
    rev=${line%%:*}; rest=${line#*:}; file=${rest%%:*}; match=${rest#*:}
    echo "  ${rev:0:7} $file: $(echo "$match" | mask)"
  done
fi

echo "== commit messages =="
if git log --all --format='%h %B' | grep -IEq "$PATTERN"; then
  found=1
  git log --all --format='%h %B' | grep -IEo "$PATTERN" | mask | sed 's/^/  /'
fi

if [ "$found" -eq 0 ]; then echo "RESULT: no API keys or bearer tokens found"; else echo "RESULT: FOUND (see masked lines above)"; fi
exit "$found"
