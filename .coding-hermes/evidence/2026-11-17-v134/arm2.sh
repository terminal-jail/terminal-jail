#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 2: control with a non-allow-listed command + bundled-vs-standalone parity.
set -u
H="$1"
BIN="$H/.local/bin/terminal-jail"
RULES="$H/.config/terminal-jail/rules.d"
mkdir -p "$RULES"
cat > "$RULES/zz-badtype.yaml" <<'YAML'
rules:
  - id: user-block-probe
    description: supported match.type control on a non-allow-listed command (dogfood 2026-11-17)
    priority: 900
    match:
      type: pattern
      pattern: '^hostname$'
    action: block
YAML
echo "--- ARM control: block ^hostname\$ (expect BLOCK rc!=0) ---"
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_SANDBOX_HOME \
    HOME="$H" "$BIN" hostname > "$H/hostname.out" 2> "$H/hostname.err"
echo "hostname_rc=$?"
echo "stdout:"; cat "$H/hostname.out"
echo "stderr:"; cat "$H/hostname.err"
echo "--- ARM bad-type on the SAME command (expect WARNING + command runs) ---"
cat > "$RULES/zz-badtype.yaml" <<'YAML'
rules:
  - id: user-block-probe
    description: unknown match.type on a non-allow-listed command (dogfood 2026-11-17)
    priority: 900
    match:
      type: regex
      pattern: '^hostname$'
    action: block
YAML
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_SANDBOX_HOME \
    HOME="$H" "$BIN" hostname > "$H/hostname-bad.out" 2> "$H/hostname-bad.err"
echo "hostname_badtype_rc=$?"
echo "stdout:"; cat "$H/hostname-bad.out"
echo "stderr:"; cat "$H/hostname-bad.err"
echo "--- ARM bad-type via the BUNDLED copy (parity of the fix) ---"
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_SANDBOX_HOME \
    HOME="$H" /home/kara/terminal-jail/plugin/terminal_jail/_bundled/terminal-jail hostname \
    > "$H/bundled-bad.out" 2> "$H/bundled-bad.err"
echo "bundled_badtype_rc=$?"
echo "stdout:"; cat "$H/bundled-bad.out"
echo "stderr:"; cat "$H/bundled-bad.err"
echo "--- byte parity: standalone vs bundled CLI ---"
md5sum /home/kara/terminal-jail/standalone/terminal-jail \
       /home/kara/terminal-jail/plugin/terminal_jail/_bundled/terminal-jail
wc -c /home/kara/terminal-jail/standalone/terminal-jail \
      /home/kara/terminal-jail/plugin/terminal_jail/_bundled/terminal-jail
echo "--- byte parity: standalone vs bundled seccomp-loader ---"
md5sum /home/kara/terminal-jail/standalone/seccomp-loader.py \
       /home/kara/terminal-jail/plugin/terminal_jail/_bundled/seccomp-loader.py
echo "--- diff (first 20 lines) if any ---"
diff /home/kara/terminal-jail/standalone/terminal-jail \
     /home/kara/terminal-jail/plugin/terminal_jail/_bundled/terminal-jail | head -20
