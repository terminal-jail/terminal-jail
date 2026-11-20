#!/bin/bash
# Dogfood arm set 2 — TERMINAL_JAIL_PYTHON pin enforcement on the installed CLI.
# Contract under test (standalone/terminal-jail:358-414, specs/cli.md:264):
#   explicit pin that cannot execute -> box 'COMMAND BLOCKED — interpreter-unavailable',
#   exit 126, fault reason named, payload NOT run, no silent fallback to python3.
#   warn mode -> WARNING + historical python3, payload runs.
ROOT=/tmp/tj-df-1120
TJ=$ROOT/home-a/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin
OUT=$ROOT/arms
mkdir -p "$OUT"

arm() { # arm <name> <expected-note> -- cmd...
  local name="$1"; shift
  local note="$1"; shift
  local mout=$OUT/$name.out merr=$OUT/$name.err mrc=$OUT/$name.rc
  env -u TERMINAL_JAIL_PYTHON -u TERMINAL_JAIL_INTERRUPTOR_MODE -u TERMINAL_JAIL_LANDLOCK \
      -u TERMINAL_JAIL_COMPOSED -u TERMINAL_JAIL_JAIL_BACKEND -u TERMINAL_JAIL_SECCOMP \
      PATH="$BASE" HOME="$ROOT/home-a" "$@" >"$mout" 2>"$merr"
  echo "$?" >"$mrc"
  printf 'ARM %s | note=%s | rc=%s | stdout=%s | stderr_first=%s\n' \
    "$name" "$note" "$(cat "$mrc")" \
    "'$(head -c 120 "$mout" | tr '\n' ' ')'" \
    "'$(head -1 "$merr" | head -c 120)'"
}

# a2 baseline allow: payload echoes -> proves it ran
arm a2-allow-baseline "allow path runs payload"
  "$TJ" /bin/echo ALLOW-PAYLOAD-RAN

# a3 pin missing file
arm a3-pin-missing "expect rc126 box interpreter-unavailable fault=no such file payload-NOT-run"
  env TERMINAL_JAIL_PYTHON=$ROOT/nope/python3 "$TJ" /bin/echo PIN-ARM-RAN

# a4 pin exists but not executable
arm a4-pin-notexec "expect rc126 fault=not executable payload-NOT-run"
  env TERMINAL_JAIL_PYTHON=$ROOT/pin/bad-python "$TJ" /bin/echo PIN-ARM-RAN

# a5 bare name not on PATH
arm a5-pin-notonpath "expect rc126 fault=not on PATH payload-NOT-run"
  env TERMINAL_JAIL_PYTHON=no-such-python-here "$TJ" /bin/echo PIN-ARM-RAN

# a6 warn mode with broken pin -> degrade loudly, run payload
arm a6-warn-broken-pin "expect WARNING + historical python3 + payload RAN rc0"
  env TERMINAL_JAIL_INTERRUPTOR_MODE=warn TERMINAL_JAIL_PYTHON=$ROOT/pin/bad-python \
      "$TJ" /bin/echo WARN-PAYLOAD-RAN

# a7 good pin
arm a7-pin-good "expect rc0 payload RAN under pinned interpreter"
  env TERMINAL_JAIL_PYTHON=/usr/bin/python3 "$TJ" /bin/echo PINNED-PAYLOAD-RAN

# a8 empty pin = historical python3
arm a8-pin-empty "unset/empty keeps historical python3 -> rc0 payload RAN"
  env TERMINAL_JAIL_PYTHON= "$TJ" /bin/echo EMPTY-PIN-PAYLOAD-RAN

# a9 blocked command still blocks (control: firewall alive at this install)
arm a9-block-control "expect rc126 COMMAND BLOCKED rm -rf payload-NOT-run"
  "$TJ" rm -rf /

echo DONE-PINS
