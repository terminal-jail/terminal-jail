#!/bin/bash
# Rig D — fake home OUTSIDE /tmp so the tier's tmpdir write grants cannot cover it.
# Repro of the TJ-REVIEW-074 flagship shape: real-file interpreter under
# <home>/.hermes (a carved credential surface), resolved via PATH, auto-sandbox make.
ROOT=/home/kara/tj-df-1120
HOME_B=$ROOT/home-b
REPO=/home/kara/terminal-jail
TJ=$HOME_B/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin
HOSTILE=$HOME_B/.hermes/bin
OUT=/tmp/tj-df-1120/arms
mkdir -p "$ROOT" "$OUT"

echo "== fresh install into HOME_B (documented ./install.sh --no-path) =="
( cd "$REPO" && env -i PATH=$BASE HOME=$HOME_B bash ./install.sh --no-path ) >"$OUT/install-b.out" 2>"$OUT/install-b.err"
echo "install-b rc=$?"
tail -2 "$OUT/install-b.err"

mkdir -p "$HOSTILE" "$HOME_B/mk"
cp "$(readlink -f /usr/bin/python3)" "$HOSTILE/python3"
chmod 0755 "$HOSTILE/python3"
chmod 0700 "$HOME_B/.hermes"
mkdir -p "$ROOT/symdir/bin"
ln -sfn /usr/bin/python3 "$ROOT/symdir/bin/python3"
cat > "$HOME_B/mk/Makefile" <<'EOF'
ok:
	@echo MODIFY-PAYLOAD-RAN
canary:
	@cat /run/user/1000/tj-canary
EOF

arm() { local name="$1" note="$2" mpath="$3"; shift 3
  local envs=(); while [ "$1" != "--" ]; do envs+=("$1"); shift; done; shift
  local mout=$OUT/$name.out merr=$OUT/$name.err mrc=$OUT/$name.rc
  ( cd "$HOME_B/mk" && env -u TERMINAL_JAIL_PYTHON -u TERMINAL_JAIL_INTERRUPTOR_MODE \
        -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_JAIL_BACKEND -u TERMINAL_JAIL_COMPOSED \
        "${envs[@]}" PATH="$mpath" HOME="$HOME_B" "$@" >"$mout" 2>"$merr" )
  echo "$?" >"$mrc"
  printf 'ARM %s | note=%s | rc=%s | stdout=%s\n' "$name" "$note" "$(cat "$mrc")" "'$(head -c 80 "$mout" | tr '\n' ' ')'"
}

# f1: THE FLAGSHIP REPRO — real-file interpreter under the carved surface
arm f1-realfile-carved "expect rc2 auto-sandbox modify unavailable naming interpreter" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_PYTHON= "$TJ" make ok
# f2: pin remedy
arm f2-remedy-pin "expect rc0 PAYLOAD-RAN" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_PYTHON=/usr/bin/python3 "$TJ" make ok
# f3: tier-off remedy
arm f3-remedy-notier "expect rc0 PAYLOAD-RAN" "$HOSTILE:$BASE" -- env TERMINAL_JAIL_LANDLOCK=0 "$TJ" make ok
# f4: symlink control (target /usr is granted) -> runs
arm f4-symlink-granted-target "expect rc0 PAYLOAD-RAN (symlink resolves into granted /usr)" "$ROOT/symdir/bin:$BASE" -- env TERMINAL_JAIL_PYTHON= "$TJ" make ok
# f5: canary again under the new home (launch tiered?)
arm f5-canary "DENIED=tiered / SECRET=tier-failed" "$BASE" -- "$TJ" make canary

echo '--- f1 stderr ---'; cat "$OUT/f1-realfile-carved.err"
echo '--- f1 stdout ---'; cat "$OUT/f1-realfile-carved.out"
echo '--- f4 stderr tail ---'; tail -3 "$OUT/f4-symlink-granted-target.err"
echo '--- f5 stdout ---'; cat "$OUT/f5-canary.out"
echo DONE-RIGD
