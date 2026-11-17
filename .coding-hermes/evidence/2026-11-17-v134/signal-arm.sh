#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 8: signal fidelity, done properly.
# Job control ON (set -m) so an async job does NOT inherit SIG_IGN for SIGINT -
# that was the rig bug in arm 7 (bash ignores SIGINT in async jobs without job control).
set -u -m
B=/tmp/tj-1117-pub/home/.local/bin/terminal-jail
export HOME=/tmp/tj-1117-pub/home
unset TERMINAL_JAIL_INTERRUPTOR_RULES TERMINAL_JAIL_LANDLOCK TERMINAL_JAIL_LANDLOCK_NET
MARKER=60

probe() { # $1=signal
  local sig="$1"
  local t0=$(date +%s.%N)
  setsid "$B" sleep "$MARKER" > /tmp/tj-1117-pub/sig.out 2> /tmp/tj-1117-pub/sig.err &
  local pid=$!
  sleep 2
  # a user's Ctrl-C hits the foreground PROCESS GROUP; emulate with the group
  kill -"$sig" -- -"$pid" 2>/dev/null || kill -"$sig" "$pid" 2>/dev/null
  local waited=0
  while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 12 ]; do sleep 0.5; waited=$((waited+1)); done
  wait "$pid" 2>/dev/null; local rc=$?
  local t1=$(date +%s.%N)
  local elapsed
  elapsed=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')
  sleep 1
  local surv
  surv=$(pgrep -fc "sleep $MARKER" || true)
  echo "[SIG$sig to the wrapper's process group] rc=$rc elapsed=${elapsed}s surviving_payload=$(printf '%s' "${surv:-0}")"
  if [ "${surv:-0}" -gt 0 ]; then pgrep -af "sleep $MARKER" | head -3 | sed 's/^/    survivor: /'; fi
  pkill -f "sleep $MARKER" 2>/dev/null
}

echo "== baseline: the same SIGINT to a bare sleep in a setsid group =="
t0=$(date +%s.%N)
setsid sleep "$MARKER" >/dev/null 2>&1 &
p=$!
sleep 1; kill -INT -- -"$p" 2>/dev/null; wait "$p" 2>/dev/null; echo "[bare sleep] rc=$? elapsed=$(awk -v a="$t0" -v b="$(date +%s.%N)" 'BEGIN{printf "%.1f", b-a}')s"
sleep 1; echo "bare survivors: $(pgrep -fc "sleep $MARKER" || true)"; pkill -f "sleep $MARKER" 2>/dev/null; sleep 0.5

echo "== wrapped: SIGINT =="
probe INT
echo "== wrapped: SIGTERM (what a supervisor sends) =="
probe TERM
