#!/bin/bash
# TJ-DF-073 evidence probe — TERMINAL_JAIL_PYTHON pin fault classes on a
# firewall-on invocation, run against the WORKTREE wrapper.
#
# Arms: the three measured fault classes (missing path, not executable, bare
# name not on PATH), plus an executable-but-broken pin (executing it fails),
# a warn-mode arm (the a6 shape), and three controls (allow runs, good pin,
# block verdict) proving the firewall itself is alive on this box.
#
# Usage: probe_pins_0721.sh <out-dir> <wrapper-path> [bridge-path]
#
# The third argument is for the BUNDLED copy (plugin/terminal_jail/_bundled/
# terminal-jail): it is a data file inside an install layout, so it cannot
# resolve the bridge from SCRIPT_DIR — the staged layout passes it explicitly
# here instead, the way an installed wrapper resolves it.
set -u
OUT=${1:?out dir}
TJ=${2:?wrapper path}
TJ_BRIDGE=${3:-}
BASE=/usr/local/bin:/usr/bin:/bin
SCRATCH=${TMPDIR:-/tmp}/tj-df-073
rm -rf "$SCRATCH"; mkdir -p "$SCRATCH/home" "$SCRATCH/pin" "$SCRATCH/tmp"
# A pin that exists and is executable but is not a working interpreter.
printf '#!/bin/sh\nexit 3\n' > "$SCRATCH/pin/not-a-python"
chmod 0755 "$SCRATCH/pin/not-a-python"
# A pin that exists and is NOT executable.
printf '#!/bin/sh\nexit 0\n' > "$SCRATCH/pin/noexec-python"
chmod 0644 "$SCRATCH/pin/noexec-python"

mkdir -p "$OUT"

arm() { # arm <name> <cmd...>
  local name=$1; shift
  local rc
  local envargs=(-u TERMINAL_JAIL_PYTHON -u TERMINAL_JAIL_INTERRUPTOR_MODE
                 -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_COMPOSED
                 -u TERMINAL_JAIL_JAIL_BACKEND -u TERMINAL_JAIL_SECCOMP
                 -u TERMINAL_JAIL_PRIVATE_PROC)
  if [ -n "$TJ_BRIDGE" ]; then
    envargs+=(TERMINAL_JAIL_BRIDGE="$TJ_BRIDGE")
  else
    envargs+=(-u TERMINAL_JAIL_BRIDGE)
  fi
  env "${envargs[@]}" \
      PATH="$BASE" HOME="$SCRATCH/home" TMPDIR="$SCRATCH/tmp" \
      "$@" >"$OUT/$name.out" 2>"$OUT/$name.err"
  rc=$?
  echo "$rc" > "$OUT/$name.rc"
  printf 'ARM %-22s rc=%-4s stdout=%s\n' "$name" "$rc" \
    "'$(head -c 60 "$OUT/$name.out" | tr '\n' ' ')'"
}

arm a2-allow-baseline      "$TJ" /bin/echo ALLOW-PAYLOAD-RAN
arm a3-pin-missing         env TERMINAL_JAIL_PYTHON="$SCRATCH/nope/python3" "$TJ" /bin/echo PIN-ARM-RAN
arm a4-pin-notexec         env TERMINAL_JAIL_PYTHON="$SCRATCH/pin/noexec-python" "$TJ" /bin/echo PIN-ARM-RAN
arm a5-pin-notonpath       env TERMINAL_JAIL_PYTHON=no-such-python-here "$TJ" /bin/echo PIN-ARM-RAN
arm a5b-pin-exec-fails     env TERMINAL_JAIL_PYTHON="$SCRATCH/pin/not-a-python" "$TJ" /bin/echo PIN-ARM-RAN
arm a6-warn-broken-pin     env TERMINAL_JAIL_INTERRUPTOR_MODE=warn TERMINAL_JAIL_PYTHON="$SCRATCH/pin/noexec-python" "$TJ" /bin/echo WARN-PAYLOAD-RAN
arm a7-pin-good            env TERMINAL_JAIL_PYTHON=/usr/bin/python3 "$TJ" /bin/echo PINNED-PAYLOAD-RAN
arm a8-pin-empty           env TERMINAL_JAIL_PYTHON= "$TJ" /bin/echo EMPTY-PIN-PAYLOAD-RAN
arm a9-block-control       "$TJ" rm -rf /

echo
for name in a2-allow-baseline a3-pin-missing a4-pin-notexec a5-pin-notonpath \
            a5b-pin-exec-fails a6-warn-broken-pin a7-pin-good a8-pin-empty \
            a9-block-control; do
  echo "=== $name rc=$(cat "$OUT/$name.rc")"
  echo "--- stdout:"; sed 's/^/    /' "$OUT/$name.out"
  echo "--- stderr:"; sed 's/^/    /' "$OUT/$name.err"
done
echo DONE-PINS
