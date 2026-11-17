#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 7: script-facing fidelity - exit codes, stdin/stdout/stderr,
# signals. A user who wraps commands in scripts depends on every one of these.
set -u
B=/tmp/tj-1117-pub/home/.local/bin/terminal-jail
export HOME=/tmp/tj-1117-pub/home
unset TERMINAL_JAIL_INTERRUPTOR_RULES TERMINAL_JAIL_LANDLOCK TERMINAL_JAIL_LANDLOCK_NET
run() { # label, then command...
  local label="$1"; shift
  "$@" > /tmp/tj-1117-pub/f.out 2> /tmp/tj-1117-pub/f.err
  local rc=$?
  echo "[$label] rc=$rc stdout=$(wc -c < /tmp/tj-1117-pub/f.out)B stderr=$(wc -c < /tmp/tj-1117-pub/f.err)B"
  head -c 120 /tmp/tj-1117-pub/f.out | tr -d '\n'; echo " |out|"
}
echo "== exit-code fidelity =="
"$B" true  >/dev/null 2>&1; echo "[true] rc=$?"
"$B" false >/dev/null 2>&1; echo "[false] rc=$?"
"$B" sh -c 'exit 42' >/dev/null 2>&1; echo "[sh -c exit 42] rc=$?"
"$B" ls /nonexistent-dir-dogfood >/dev/null 2>&1; echo "[ls missing dir] rc=$?"
echo
echo "== stdin / stdout / stderr =="
printf 'abc' | "$B" wc -c > /tmp/tj-1117-pub/o1 2> /tmp/tj-1117-pub/e1
echo "[pipe-in wc -c] rc=$? stdout=$(cat /tmp/tj-1117-pub/o1 | tr -d ' \n') stderr_bytes=$(wc -c < /tmp/tj-1117-pub/e1)"
"$B" sh -c 'echo OUT-LINE; echo ERR-LINE >&2' > /tmp/tj-1117-pub/o2 2> /tmp/tj-1117-pub/e2
echo "[split streams] rc=$? stdout=$(cat /tmp/tj-1117-pub/o2 | tr -d '\n') stderr_has_ERR=$(grep -c ERR-LINE /tmp/tj-1117-pub/e2) stderr_has_OUT=$(grep -c OUT-LINE /tmp/tj-1117-pub/e2)"
printf 'line1\nline2\n' | "$B" cat > /tmp/tj-1117-pub/o3 2>/dev/null
echo "[pipe-in cat] rc=$? lines=$(wc -l < /tmp/tj-1117-pub/o3)"
echo
echo "== signal propagation (SIGINT to a wrapped sleep) =="
"$B" sleep 30 > /tmp/tj-1117-pub/s.out 2> /tmp/tj-1117-pub/s.err &
wpid=$!
sleep 2
kill -INT "$wpid" 2>/dev/null
wait "$wpid"; rc=$?
echo "[wrapped sleep + SIGINT to wrapper] rc=$rc (shell convention for SIGINT is 130)"
sleep 1
echo "residual sleep processes: $(pgrep -fc 'sleep 30' || true)"
echo
echo "== end-of-options (docs/quarterly-review checklist shape) =="
"$B" -- echo hello > /tmp/tj-1117-pub/o4 2> /tmp/tj-1117-pub/e4; echo "[-- echo hello] rc=$?"; head -2 /tmp/tj-1117-pub/e4
