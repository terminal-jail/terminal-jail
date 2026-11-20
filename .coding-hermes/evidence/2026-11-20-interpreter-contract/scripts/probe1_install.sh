#!/bin/bash
# Dogfood arm set 1 — documented fresh install into a throwaway HOME (stranger shape).
# Steps: installer --help (documented surface, must not touch FS), fresh install --no-path,
# time-to-first-success (install + first documented command + first verdict).
ROOT=/tmp/tj-df-1120
REPO=/home/kara/terminal-jail
OUT=$ROOT/arms
mkdir -p "$ROOT" "$OUT"

echo "== install.sh --help (documented: exits 0, touches nothing) =="
( cd "$REPO" && env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=$ROOT/home-a \
    /usr/bin/time -f 'wall=%e user=%U sys=%S' bash ./install.sh --help ) \
    >"$OUT/help.out" 2>"$OUT/help.err"
echo "help rc=$?  help.err_tail=$(tail -2 "$OUT/help.err" | tr '\n' ' ')"

echo "== fresh install --no-path into HOME=$ROOT/home-a =="
( cd "$REPO" && env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=$ROOT/home-a \
    /usr/bin/time -f 'wall=%e user=%U sys=%S' bash ./install.sh --no-path ) \
    >"$OUT/install.out" 2>"$OUT/install.err"
echo "install rc=$? (written after run)"
cat "$OUT/install.out"
echo "-- install stderr tail (timing line) --"; tail -3 "$OUT/install.err"

echo "== first documented command: --version =="
( cd "$ROOT" && env -i PATH=$ROOT/home-a/.local/bin:/usr/local/bin:/usr/bin:/bin HOME=$ROOT/home-a \
    /usr/bin/time -f 'wall=%e user=%U sys=%S' terminal-jail --version ) \
    >"$OUT/version.out" 2>"$OUT/version.err"
echo "version rc=$? out=$(cat "$OUT/version.out") err_tail=$(tail -1 "$OUT/version.err")"

echo "== first verdict: an allow =="
( cd "$ROOT" && env -i PATH=$ROOT/home-a/.local/bin:/usr/local/bin:/usr/bin:/bin HOME=$ROOT/home-a \
    /usr/bin/time -f 'wall=%e user=%U sys=%S' terminal-jail /bin/echo FIRST-VERDICT-PAYLOAD ) \
    >"$OUT/first.out" 2>"$OUT/first.err"
echo "first rc=$? out=$(cat "$OUT/first.out") err=$(tr '\n' '|' <"$OUT/first.err" | head -c 300)"
echo DONE-INSTALL
