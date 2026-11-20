#!/bin/bash
# Dogfood arm set 2 (v2) — TERMINAL_JAIL_PYTHON pin enforcement on the installed CLI.
ROOT=/tmp/tj-df-1120
TJ=$ROOT/home-a/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin
OUT=$ROOT/arms
mkdir -p "$OUT"

arm() { # arm <name> <note> cmd...
  local name="$1"; local note="$2"; shift 2
  local mout=$OUT/$name.out merr=$OUT/$name.err mrc=$OUT/$name.rc
  env -u TERMINAL_JAIL_PYTHON -u TERMINAL_JAIL_INTERRUPTOR_MODE -u TERMINAL_JAIL_LANDLOCK \
      -u TERMINAL_JAIL_COMPOSED -u TERMINAL_JAIL_JAIL_BACKEND -u TERMINAL_JAIL_SECCOMP \
      PATH="$BASE" HOME="$ROOT/home-a" "$@" >"$mout" 2>"$merr"
  echo "$?" >"$mrc"
  printf 'ARM %s | note=%s | rc=%s | stdout=%s\n' "$name" "$note" "$(cat "$mrc")" "'$(head -c 100 "$mout" | tr '\n' ' ')'"
}

arm a2-allow-baseline "allow runs payload" "$TJ" /bin/echo ALLOW-PAYLOAD-RAN
arm a3-pin-missing "expect126 interpreter-unavailable no-such-file" env TERMINAL_JAIL_PYTHON=$ROOT/nope/python3 "$TJ" /bin/echo PIN-ARM-RAN
arm a4-pin-notexec "expect126 not-executable" env TERMINAL_JAIL_PYTHON=$ROOT/pin/bad-python "$TJ" /bin/echo PIN-ARM-RAN
arm a5-pin-notonpath "expect126 not-on-PATH" env TERMINAL_JAIL_PYTHON=no-such-python-here "$TJ" /bin/echo PIN-ARM-RAN
arm a6-warn-broken-pin "warn degrades runs" env TERMINAL_JAIL_INTERRUPTOR_MODE=warn TERMINAL_JAIL_PYTHON=$ROOT/pin/bad-python "$TJ" /bin/echo WARN-PAYLOAD-RAN
arm a7-pin-good "pinned runs" env TERMINAL_JAIL_PYTHON=/usr/bin/python3 "$TJ" /bin/echo PINNED-PAYLOAD-RAN
arm a8-pin-empty "empty=historical" env TERMINAL_JAIL_PYTHON= "$TJ" /bin/echo EMPTY-PIN-PAYLOAD-RAN
arm a9-block-control "firewall alive" "$TJ" rm -rf /

echo '--- a3 stderr ---'; cat "$OUT/a3-pin-missing.err"
echo '--- a6 stderr ---'; cat "$OUT/a6-warn-broken-pin.err"
echo DONE-PINS
