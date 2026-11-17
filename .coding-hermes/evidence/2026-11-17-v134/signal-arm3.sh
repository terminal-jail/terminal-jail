#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 10: signal fidelity, fourth design.
# FIX vs arms 7-9: no setsid (setsid(1) FORKS, so $! is a short-lived parent and the
# process-group kill missed both the baseline and the wrapper). With `set -m` an async
# job IS its own process-group leader, so $! == PGID and kill -- -$! is a true Ctrl-C.
set -u -m
B=/tmp/tj-1117-pub/home/.local/bin/terminal-jail
export HOME=/tmp/tj-1117-pub/home
unset TERMINAL_JAIL_INTERRUPTOR_RULES TERMINAL_JAIL_LANDLOCK TERMINAL_JAIL_LANDLOCK_NET
M=143

clean() { pkill -f "sleep $M" 2>/dev/null; sleep 0.3; }

arm() { # $1=label $2=BARE|WRAPPED $3=signal $4=kill-target(pid|group)
  local label="$1" mode="$2" sig="$3" target="$4"
  clean
  local t0 t1 rc pid waited n
  t0=$(date +%s.%N)
  if [ "$mode" = BARE ]; then sleep "$M" >/dev/null 2>&1 & else "$B" sleep "$M" > /tmp/tj-1117-pub/sig.out 2> /tmp/tj-1117-pub/sig.err & fi
  pid=$!
  sleep 2
  if [ "$target" = group ]; then kill -"$sig" -- -"$pid" 2>/dev/null; else kill -"$sig" "$pid" 2>/dev/null; fi
  waited=0
  while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 40 ]; do sleep 0.5; waited=$((waited+1)); done
  wait "$pid" 2>/dev/null; rc=$?
  t1=$(date +%s.%N)
  sleep 0.7
  n=$(pgrep -f "sleep $M" | wc -l)
  echo "[$label] pid=$pid kill=$target rc=$rc elapsed=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')s wrapper_alive=$(kill -0 "$pid" 2>/dev/null && echo YES || echo no) surviving_payload=$n"
  if [ "$n" -gt 0 ]; then pgrep -af "sleep $M" | head -3 | cut -c1-120 | sed 's/^/      /'; fi
}

echo "== 1. BARE baseline: SIGINT to the bare sleep's group =="
arm "bare sleep + SIGINT(group)" BARE INT group
echo "== 2. WRAPPED: SIGINT to the wrapper's group (Ctrl-C) =="
arm "wrapped sleep + SIGINT(group)" WRAPPED INT group
echo "== 3. WRAPPED: SIGTERM to the wrapper PID (supervisor) =="
arm "wrapped sleep + SIGTERM(pid)" WRAPPED TERM pid
clean
echo "final residual: $(pgrep -fc "sleep $M" || true)"
