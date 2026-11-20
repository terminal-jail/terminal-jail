#!/bin/bash
# DECISIVE ARMS — does the auto-sandbox launch deliver the fs tier on this host?
# canary: mode-600 file at /run/user/1000 (ungranted by the tier layout).
#   launch tiered  -> cat fails EACCES (rc 1, payload's own failure)
#   launch untiered -> cat prints SECRET-CANARY (rc 0)
# d-arms: the TJ-REVIEW-074 repro with a REAL-FILE interpreter (not a symlink)
# under the fake home's credential surface (~/.hermes is carved out of grants).
ROOT=/tmp/tj-df-1120
TJ=$ROOT/home-a/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin
HOSTILE=$ROOT/home-a/.hermes/bin
OUT=$ROOT/arms

printf 'SECRET-CANARY\n' > /run/user/1000/tj-canary
chmod 0600 /run/user/1000/tj-canary
cp "$(readlink -f /usr/bin/python3)" "$HOSTILE/python3-real"
chmod 0755 "$HOSTILE/python3-real"

cat > "$ROOT/mk/Makefile" <<'EOF'
ok:
	@echo MODIFY-PAYLOAD-RAN
canary:
	@cat /run/user/1000/tj-canary
EOF

arm() { local name="$1" note="$2" mpath="$3"; shift 3
  local envs=(); while [ "$1" != "--" ]; do envs+=("$1"); shift; done; shift
  local mout=$OUT/$name.out merr=$OUT/$name.err mrc=$OUT/$name.rc
  ( cd "$ROOT/mk" && env -u TERMINAL_JAIL_PYTHON -u TERMINAL_JAIL_INTERRUPTOR_MODE \
        -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_JAIL_BACKEND -u TERMINAL_JAIL_COMPOSED \
        "${envs[@]}" PATH="$mpath" HOME="$ROOT/home-a" "$@" >"$mout" 2>"$merr" )
  echo "$?" >"$mrc"
  printf 'ARM %s | note=%s | rc=%s | stdout=%s\n' "$name" "$note" "$(cat "$mrc")" "'$(head -c 80 "$mout" | tr '\n' ' ')'"
}

# e1: canary through the auto-sandbox launch (clean PATH)
arm e1-canary-tier-decision "DENIED=launch tiered / SECRET-CANARY=untiered" "$BASE" -- "$TJ" make canary
# e2: same with tier off (control — must read)
arm e2-canary-notier "expect SECRET-CANARY rc0" "$BASE" -- env TERMINAL_JAIL_LANDLOCK=0 "$TJ" make canary

# d1: TJ-REVIEW-074 repro, REAL-FILE interpreter under the credential surface
arm d1-realfile-hostile "expect rc2 named auto-sandbox modify unavailable" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_PYTHON= "$TJ" make ok
# d2: remedy pin
arm d2-realfile-pin "expect rc0 PAYLOAD-RAN" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_PYTHON=/usr/bin/python3 "$TJ" make ok
# d3: remedy tier-off
arm d3-realfile-notier "expect rc0 PAYLOAD-RAN" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_LANDLOCK=0 "$TJ" make ok

echo '--- e1 stderr ---'; cat "$OUT/e1-canary-tier-decision.err"
echo '--- e2 stdout ---'; cat "$OUT/e2-canary-notier.out"; echo '--- e2 stderr ---'; cat "$OUT/e2-canary-notier.err"
echo '--- d1 stderr ---'; cat "$OUT/d1-realfile-hostile.err"
echo '--- d1 stdout ---'; cat "$OUT/d1-realfile-hostile.out"
echo DONE-DECISIVE
