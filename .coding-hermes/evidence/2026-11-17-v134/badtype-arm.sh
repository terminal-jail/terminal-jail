#!/usr/bin/env bash
# Dogfood 2026-11-17: verify v1.3.4 claim "unsupported user-rule match.type is surfaced".
set -u
H="$1"
BIN="$H/.local/bin/terminal-jail"
RULES="$H/.config/terminal-jail/rules.d"
mkdir -p "$RULES"
cat > "$RULES/zz-badtype.yaml" <<'YAML'
rules:
  - id: user-badtype-probe
    description: unknown match.type probe (dogfood 2026-11-17)
    priority: 900
    match:
      type: regex
      pattern: '^echo MARKER-BADTYPE$'
    action: block
YAML
echo "--- rule file ---"; cat "$RULES/zz-badtype.yaml"
echo "--- unsupported type ARM (bad type, expect loud warning + command allowed) ---"
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_SANDBOX_HOME \
    HOME="$H" "$BIN" echo MARKER-BADTYPE > "$H/badtype.out" 2> "$H/badtype.err"
echo "badtype_rc=$?"
echo "stdout:"; cat "$H/badtype.out"
echo "stderr (all $(: ; wc -l < "$H/badtype.err") lines):"; cat "$H/badtype.err"
echo "--- control ARM (same rule, supported type: pattern, expect BLOCK) ---"
cat > "$RULES/zz-badtype.yaml" <<'YAML'
rules:
  - id: user-badtype-probe
    description: supported match.type control (dogfood 2026-11-17)
    priority: 900
    match:
      type: pattern
      pattern: '^echo MARKER-BADTYPE$'
    action: block
YAML
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_SANDBOX_HOME \
    HOME="$H" "$BIN" echo MARKER-BADTYPE > "$H/pattern.out" 2> "$H/pattern.err"
echo "pattern_rc=$?"
echo "stdout:"; cat "$H/pattern.out"
echo "stderr:"; cat "$H/pattern.err"
echo "--- clean arm (no probe rule staged) ---"
mv "$RULES/zz-badtype.yaml" "$H/zz-badtype.yaml.off"
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_SANDBOX_HOME \
    HOME="$H" "$BIN" echo MARKER-BADTYPE > "$H/clean.out" 2> "$H/clean.err"
echo "clean_rc=$?"
echo "stdout:"; cat "$H/clean.out"
echo "stderr:"; cat "$H/clean.err"
