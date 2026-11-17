#!/usr/bin/env bash
# Arm driver v2: PARAMETERISED interpreter, so version-independence can be measured.
# Variable under test: presence of the `unzip` binary on PATH. Everything else fixed.
set -u
BASE=/home/kara/.hermes/cache/scratch/tj-1117f
TIP=$BASE/tip
NOZIP=$BASE/nozip-all
PY="${PY:?set PY}"
TAG="${TAG:?set TAG}"

mkdir -p "$NOZIP"
for d in /usr/local/bin /usr/bin /bin /usr/sbin /sbin; do
  for f in "$d"/*; do
    b=$(basename "$f")
    case "$b" in unzip|zipinfo) continue;; esac
    [ -e "$NOZIP/$b" ] || ln -s "$f" "$NOZIP/$b" 2>/dev/null
  done
done

echo "PY=$PY"; "$PY" -V
echo "nozip entries: $(ls "$NOZIP" | wc -l)"
echo "unzip under nozip PATH? $(PATH=$NOZIP command -v unzip >/dev/null 2>&1 && echo YES || echo NO)"
echo "unzip under normal PATH? $(command -v unzip)"
cd "$TIP" || exit 3

echo "=================== ARM A ($TAG, no unzip) ==================="
PATH="$NOZIP" "$PY" -m pytest plugin/ tests/ -v --tb=short -m "not integration" \
  -p no:cacheprovider > "$BASE/armA-$TAG.log" 2>&1
echo "armA_rc=$?"
tail -4 "$BASE/armA-$TAG.log"
echo "armA_FAILED_count=$(grep -c '^FAILED' "$BASE/armA-$TAG.log")"
grep '^FAILED' "$BASE/armA-$TAG.log" | head -20

echo "=================== ARM B ($TAG, unzip present) ==================="
PATH=/usr/local/bin:/usr/bin:/bin "$PY" -m pytest plugin/ tests/ -v --tb=short -m "not integration" \
  -p no:cacheprovider > "$BASE/armB-$TAG.log" 2>&1
echo "armB_rc=$?"
tail -4 "$BASE/armB-$TAG.log"
echo "armB_FAILED_count=$(grep -c '^FAILED' "$BASE/armB-$TAG.log")"
grep '^FAILED' "$BASE/armB-$TAG.log" | head -20

echo "=================== HOST ==================="
cat /proc/loadavg; nproc
git -C /home/kara/terminal-jail rev-parse origin/main
