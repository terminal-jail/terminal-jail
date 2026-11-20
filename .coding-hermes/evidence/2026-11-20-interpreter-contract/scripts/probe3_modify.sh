#!/bin/bash
# Dogfood arm set 3 — auto-sandbox MODIFY path, the TJ-REVIEW-074 shape.
# Contract under test (README:842, fix 8789f05/73413f2):
#   tier applies + head interpreter cannot start under the tier ->
#   exit 2, 'auto-sandbox modify unavailable (...)' naming the interpreter,
#   stating the command was not run. Remedies: pin /usr/bin/python3 or LANDLOCK=0.
ROOT=/tmp/tj-df-1120
TJ=$ROOT/home-a/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin
HOSTILE=$ROOT/hostile/dark/bin
OUT=$ROOT/arms
mkdir -p "$OUT"

arm() { # arm <name> <note> <cwd> <path> -- envassign... -- cmd...
  local name="$1" note="$2" cwd="$3" mpath="$4"; shift 4
  local envs=()
  while [ "$1" != "--" ]; do envs+=("$1"); shift; done
  shift
  local mout=$OUT/$name.out merr=$OUT/$name.err mrc=$OUT/$name.rc
  ( cd "$cwd" && env -u TERMINAL_JAIL_PYTHON -u TERMINAL_JAIL_INTERRUPTOR_MODE \
        -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_COMPOSED -u TERMINAL_JAIL_JAIL_BACKEND \
        PATH="$mpath" HOME="$ROOT/home-a" "$@" >"$mout" 2>"$merr" )
  echo "$?" >"$mrc"
  printf 'ARM %s | note=%s | rc=%s | stdout=%s | stderr_first=%s\n' \
    "$name" "$note" "$(cat "$mrc")" \
    "'$(head -c 140 "$mout" | tr '\n' ' ')'" \
    "'$(head -2 "$merr" | tr '\n' ' | ' | head -c 200)'"
}

# b1 clean PATH baseline: make runs inside the auto-sandbox, tier on
arm b1-modify-clean "modify verdict + payload RAN rc0" \
  "$ROOT/mk" "$BASE" -- "$TJ" make ok

# b2 THE REPRO: python3 first on PATH resolves under a 0700 parent (mapped payload uid cannot traverse)
arm b2-modify-hostile-python "expect rc2 auto-sandbox modify unavailable naming interpreter, NOT-run" \
  "$ROOT/mk" "$HOSTILE:$BASE" -- "$TJ" make ok

# b3 remedy 1: pin a world-readable interpreter
arm b3-remedy-pin "expect rc0 PAYLOAD-RAN (documented remedy TERMINAL_JAIL_PYTHON)" \
  "$ROOT/mk" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_PYTHON=/usr/bin/python3 "$TJ" make ok

# b4 remedy 2: drop the fs tier
arm b4-remedy-notier "expect rc0 PAYLOAD-RAN (documented remedy LANDLOCK=0)" \
  "$ROOT/mk" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_LANDLOCK=0 "$TJ" make ok

# b5 control: clean PATH, tier off
arm b5-clean-notier "expect rc0 PAYLOAD-RAN (tier is the only variable between b1 and b4+hostile)" \
  "$ROOT/mk" "$BASE" -- env TERMINAL_JAIL_LANDLOCK=0 "$TJ" make ok

# b6 explicit pin pointing AT the hostile interpreter (pin is -x for caller, unreachable for mapped uid)
arm b6-pin-hostile "pin exists+exec for caller but ungrantable under tier -> same named refusal" \
  "$ROOT/mk" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_PYTHON=$HOSTILE/python3 "$TJ" make ok

echo DONE-MODIFY
