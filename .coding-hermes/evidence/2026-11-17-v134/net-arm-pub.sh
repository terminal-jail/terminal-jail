#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 5: egress tier A/B from a WORLD-TRAVERSABLE home (/tmp, 1777)
# so the net loader and the payload script are reachable by the launch's payload uid.
# Rig fix for arm 4 (scratch home under a 0700 parent) - not a product change.
set -u
BASE=/tmp/tj-1117-pub
H="$BASE/home"
REPO=/home/kara/terminal-jail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
mkdir -p "$H" "$BASE/policy"
cp /home/kara/.hermes/cache/scratch/tj-1117/connect_probe.py "$BASE/connect_probe.py"
chmod 755 "$BASE" "$BASE/connect_probe.py"
echo "python3 -> $(command -v python3)"
echo "=== install into /tmp home (documented source channel) ==="
cd "$REPO" && env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
  HOME="$H" ./install.sh --no-path > "$BASE/install.out" 2> "$BASE/install.err"
echo "install_rc=$?"
tail -2 "$BASE/install.out"; cat "$BASE/install.err"
BIN="$H/.local/bin/terminal-jail"
"$BIN" --version
echo
echo "=== baseline (no jail) ==="
python3 "$BASE/connect_probe.py" 2>&1
echo
echo "=== ARM A: tier OFF, through the wrapper (expect same as baseline) ==="
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_LANDLOCK_NET \
    HOME="$H" "$BIN" python3 "$BASE/connect_probe.py" > "$BASE/off.out" 2> "$BASE/off.err"
echo "rc=$?"; echo "stdout:"; cat "$BASE/off.out"; echo "stderr:"; cat "$BASE/off.err"
echo
echo "=== ARM B: tier ON, default allowlist 22,53,80,443 (expect 4444 DENIED by kernel) ==="
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_LANDLOCK_NET_ALLOW \
    TERMINAL_JAIL_LANDLOCK_NET=1 HOME="$H" "$BIN" python3 "$BASE/connect_probe.py" > "$BASE/on.out" 2> "$BASE/on.err"
echo "rc=$?"; echo "stdout:"; cat "$BASE/on.out"; echo "stderr:"; cat "$BASE/on.err"
echo
echo "=== ARM C: tier ON, deny-ALL (empty allowlist; expect BOTH denied) ==="
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK \
    TERMINAL_JAIL_LANDLOCK_NET=1 TERMINAL_JAIL_LANDLOCK_NET_ALLOW= \
    HOME="$H" "$BIN" python3 "$BASE/connect_probe.py" > "$BASE/deny.out" 2> "$BASE/deny.err"
echo "rc=$?"; echo "stdout:"; cat "$BASE/deny.out"; echo "stderr:"; cat "$BASE/deny.err"
