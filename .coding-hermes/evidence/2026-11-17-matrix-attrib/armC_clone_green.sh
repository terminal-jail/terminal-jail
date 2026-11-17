#!/usr/bin/env bash
# Green control: a REAL git clone at the authoritative tip (has .git, unlike the
# git-archive tree the A/B used), unzip present. Expect zero failures.
set -u
BASE=/home/kara/.hermes/cache/scratch/tj-1117f
CLONE=$BASE/clone-tip
PY=$BASE/venv311/bin/python

if [ ! -d "$CLONE/.git" ]; then
  git clone --no-hardlinks --quiet /home/kara/terminal-jail "$CLONE" || exit 3
  git -C "$CLONE" checkout --quiet f00967df75a61fb3a3e47d8f3bdcdfb48342733b || exit 4
fi
echo "clone head: $(git -C "$CLONE" rev-parse HEAD)"
echo "unzip: $(command -v unzip)"
cd "$CLONE" || exit 5
PATH=/usr/local/bin:/usr/bin:/bin "$PY" -m pytest plugin/ tests/ -q --tb=line -m "not integration" \
  -p no:cacheprovider > "$BASE/armC-clone-green.log" 2>&1
echo "armC_rc=$?"
tail -4 "$BASE/armC-clone-green.log"
echo "armC_FAILED_count=$(grep -c '^FAILED' "$BASE/armC-clone-green.log")"
grep '^FAILED' "$BASE/armC-clone-green.log" | head -10
cat /proc/loadavg
