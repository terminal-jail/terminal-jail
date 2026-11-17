#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 9: signal fidelity, third design (unique marker + PGID kill + cleanup).
set -u -m
B=/tmp/tj-1117-pub/home/.local/bin/terminal-jail
export HOME=/tmp/tj-1117-pub/home
unset TERMINAL_JAIL_INTERRUPTOR_RULES TERMINAL_JAIL_LANDLOCK TERMINAL_JAIL_LANDLOCK_NET
M=137

clean() { pkill -f "sleep $M" 2>/dev/null; sleep 0.3; }

arm() { # $1=label $2=binary-or-BARE $3=signal
  local label="$1" mode="$2" sig="$3"
  clean
  local t0 t1 rc pid waited
  t0=$(date +%s.%N)
  if [ "$mode" = BARE ]; then
    setsid sleep "$M" >/dev/null 2>&1 &
  else
    setsid "$B" sleep "$M" > /tmp/tj-1117-pub/sig.out 2> /tmp/tj-1117-pub/sig.err &
  fi
  pid=$!
  sleep 2
  kill -"$sig" -- -"$pid" 2>/dev/null
  waited=0
  while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 30 ]; do sleep 0.5; waited=$((waited+1)); done
  wait "$pid" 2>/dev/null; rc=$?
  t1=$(date +%s.%N)
  echo "[$label] wrapper_pid=$pid rc=$rc elapsed=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')s alive_after=$(kill -0 "$pid" 2>/dev/null && echo YES || echo no)"
  sleep 0.7
  local n
  n=$(pgrep -f "sleep $M" | wc -l)
  echo "    surviving payload processes: $n"
  if [ "$n" -gt 0 ]; then pgrep -af "sleep $M" | head -2 | cut -c1-150 | sed 's/^/      /'; fi
}

echo "== 1. BARE baseline: SIGINT to a process group =="
arm "bare sleep, SIGINT" BARE INT
echo "== 2. WRAPPED: SIGINT to the wrapper's process group (what Ctrl-C sends) =="
arm "wrapped sleep, SIGINT" WRAPPED INT
echo "== 3. WRAPPED: SIGTERM (what a supervisor sends) =="
arm "wrapped sleep, SIGTERM" WRAPPED TERM
clean
echo "final residual: $(pgrep -fc "sleep $M" || true)"
