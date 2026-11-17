#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 4: egress tier A/B (kernel-real?) on the installed 1.3.4.
set -u
H="$1"
BIN="$H/.local/bin/terminal-jail"
P=/home/kara/.hermes/cache/scratch/tj-1117/connect_probe.py
echo "python3 resolves to: $(command -v python3)"
echo "=== baseline (no jail): probe directly ==="
python3 "$P" 2>&1
echo
echo "=== ARM A: tier OFF (default) through the wrapper ==="
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_LANDLOCK_NET \
    HOME="$H" "$BIN" python3 "$P" > "$H/netoff.out" 2> "$H/netoff.err"
echo "rc=$?"
echo "stdout:"; cat "$H/netoff.out"
echo "stderr:"; cat "$H/netoff.err"
echo
echo "=== ARM B: tier ON (TERMINAL_JAIL_LANDLOCK_NET=1) through the wrapper ==="
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_LANDLOCK_NET_ALLOW \
    TERMINAL_JAIL_LANDLOCK_NET=1 HOME="$H" "$BIN" python3 "$P" > "$H/neton.out" 2> "$H/neterr.out"
echo "rc=$?"
echo "stdout:"; cat "$H/neton.out"
echo "stderr:"; cat "$H/neterr.out"
echo
echo "=== ARM C: tier ON with deny-ALL (empty allowlist) ==="
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK \
    TERMINAL_JAIL_LANDLOCK_NET=1 TERMINAL_JAIL_LANDLOCK_NET_ALLOW= \
    HOME="$H" "$BIN" python3 "$P" > "$H/netdeny.out" 2> "$H/netdenyerr.out"
echo "rc=$?"
echo "stdout:"; cat "$H/netdeny.out"
echo "stderr:"; cat "$H/netdenyerr.out"
