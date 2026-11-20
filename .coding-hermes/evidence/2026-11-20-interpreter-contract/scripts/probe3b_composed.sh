#!/bin/bash
# Dogfood arm set 3b — TJ-REVIEW-074 mechanism in COMPOSED mode (the operator shape
# where the fs tier still engages on this host, whose AppArmor now denies setgroups
# in unprivileged userns so the auto-sandbox namespace rewrite degrades).
# Contract under test (README:842): tier applies + head interpreter cannot start
# under the tier -> exit 2, 'auto-sandbox modify unavailable (…)' naming the
# interpreter, stating the command was not run.
ROOT=/tmp/tj-df-1120
TJ=$ROOT/home-a/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin
HOSTILE=$ROOT/home-a/.hermes/bin
OUT=$ROOT/arms

arm() { # arm <name> <note> <path> -- envassign... -- cmd...
  local name="$1" note="$2" mpath="$3"; shift 3
  local envs=()
  while [ "$1" != "--" ]; do envs+=("$1"); shift; done
  shift
  local mout=$OUT/$name.out merr=$OUT/$name.err mrc=$OUT/$name.rc
  ( cd "$ROOT/mk" && env -u TERMINAL_JAIL_PYTHON -u TERMINAL_JAIL_INTERRUPTOR_MODE \
        -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_JAIL_BACKEND \
        "${envs[@]}" PATH="$mpath" HOME="$ROOT/home-a" "$@" >"$mout" 2>"$merr" )
  echo "$?" >"$mrc"
  printf 'ARM %s | note=%s | rc=%s | stdout=%s\n' "$name" "$note" "$(cat "$mrc")" "'$(head -c 60 "$mout" | tr '\n' ' ')'"
}

# c1 composed baseline: clean PATH, tier should APPLY in composed (uid stays caller)
arm c1-composed-clean "composed layers report + payload RAN" "$BASE" \
  -- TERMINAL_JAIL_COMPOSED=on "$TJ" make ok

# c2 THE MECHANISM: hostile interpreter inside the fake home's credential surface
arm c2-composed-hostile "expect rc2 named refusal (tier applies, interpreter ungrantable)" \
  "$HOSTILE:$BASE" \
  -- TERMINAL_JAIL_COMPOSED=on "$TJ" make ok

# c3 tier-off control: same hostile PATH, tier dropped
arm c3-composed-hostile-notier "expect rc0 PAYLOAD-RAN (tier is the only variable)" \
  "$HOSTILE:$BASE" \
  -- TERMINAL_JAIL_COMPOSED=on TERMINAL_JAIL_LANDLOCK=0 "$TJ" make ok

# c4 documented remedy: pin a world-readable interpreter
arm c4-composed-hostile-pin "expect rc0 PAYLOAD-RAN (documented remedy pin)" \
  "$HOSTILE:$BASE" \
  -- TERMINAL_JAIL_COMPOSED=on TERMINAL_JAIL_PYTHON=/usr/bin/python3 "$TJ" make ok

echo '--- c1 stderr ---'; cat "$OUT/c1-composed-clean.err"
echo '--- c2 stderr ---'; cat "$OUT/c2-composed-hostile.err"
echo '--- c2 stdout ---'; cat "$OUT/c2-composed-hostile.out"
echo DONE-COMPOSED
