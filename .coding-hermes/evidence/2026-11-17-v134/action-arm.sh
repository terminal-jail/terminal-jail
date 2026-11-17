#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 11: v1.3.4 claim "unknown user-rule actions remain visible
# while preserving fail-safe behavior" + pack validator on an unknown match.type.
set -u
H=/tmp/tj-1117-pub/home
B="$H/.local/bin/terminal-jail"
RD="$H/.config/terminal-jail/rules.d"
REPO=/home/kara/terminal-jail
mkdir -p "$RD"
cat > "$RD/zz-badaction.yaml" <<'YAML'
rules:
  - id: user-badaction-probe
    description: unknown action probe (dogfood 2026-11-17)
    priority: 900
    match:
      type: pattern
      pattern: '^uptime$'
    action: quaranteen
YAML
echo "=== unknown action ARM (expect: visible warning, command NOT silently allowed?) ==="
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_LANDLOCK_NET \
    HOME="$H" "$B" uptime > /tmp/tj-1117-pub/act.out 2> /tmp/tj-1117-pub/act.err
echo "rc=$?"
echo "stdout: $(cat /tmp/tj-1117-pub/act.out)"
echo "stderr:"; cat /tmp/tj-1117-pub/act.err
mv "$RD/zz-badaction.yaml" /tmp/tj-1117-pub/zz-badaction.yaml.off
echo
echo "=== pack validator on an unknown match.type (expect exit 2, named reason) ==="
cat > /tmp/tj-1117-pub/policy/badtype-pack.yaml <<'YAML'
rules:
  - id: pack-badtype-pack-member
    description: pack rule with an unknown match type (dogfood 2026-11-17)
    priority: 950
    action: block
    match:
      type: regex
      pattern: '^uptime$'
YAML
python3 "$REPO/scripts/rule-pack-tool.py" validate /tmp/tj-1117-pub/policy/badtype-pack.yaml --pack-name badtype-pack
echo "validator_rc=$?"
