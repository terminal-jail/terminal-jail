#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 3: external rule-pack authoring -> install -> ENFORCEMENT -> refusal.
set -u
H="$1"
BIN="$H/.local/bin/terminal-jail"
RD="$H/.config/terminal-jail/rules.d"
REPO=/home/kara/terminal-jail
mkdir -p "$H/policy"
cat > "$H/policy/my-team-pack.yaml" <<'YAML'
rules:
  - id: pack-my-team-pack-guard
    description: dogfood 2026-11-17 - block whoami for this team
    priority: 950
    action: block
    match:
      type: pattern
      pattern: '^whoami$'
YAML
echo "=== 1. list shipped packs (checkout) ==="
env HOME="$H" "$REPO/install.sh" --list-rule-packs > "$H/list.out" 2> "$H/list.err"
echo "list_rc=$?"; cat "$H/list.out"; echo "list stderr:"; cat "$H/list.err"
echo "=== 2. install external pack file ==="
cd "$REPO" && env HOME="$H" ./install.sh --no-path --rule-pack-file "$H/policy/my-team-pack.yaml" > "$H/pack.out" 2> "$H/pack.err"
echo "pack_install_rc=$?"
grep -iE 'pack|skip|summary|installed' "$H/pack.out" | tail -6
echo "pack stderr:"; cat "$H/pack.err"
echo "--- installed pack file ---"
ls -l "$RD"/terminal-jail-pack-* 2>&1
echo "=== 3. ENFORCEMENT arm: does the pack rule actually fire? (expect BLOCK 126) ==="
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_SANDBOX_HOME \
    HOME="$H" "$BIN" whoami > "$H/whoami.out" 2> "$H/whoami.err"
echo "whoami_rc=$?"
echo "stdout:"; cat "$H/whoami.out"
echo "stderr:"; cat "$H/whoami.err"
echo "=== 4. control: same command with the pack removed ==="
env HOME="$H" "$REPO/install.sh" --uninstall-rule-pack-file "$H/policy/my-team-pack.yaml" > "$H/unpack.out" 2> "$H/unpack.err"
echo "uninstall_pack_rc=$?"; cat "$H/unpack.out"; cat "$H/unpack.err"
env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
    -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_SANDBOX_HOME \
    HOME="$H" "$BIN" whoami > "$H/whoami2.out" 2> "$H/whoami2.err"
echo "whoami_after_removal_rc=$?"; cat "$H/whoami2.out"; cat "$H/whoami2.err"
echo "=== 5. refusal arm: id outside the pack namespace (expect exit 2, nothing written) ==="
cat > "$H/policy/bad-pack.yaml" <<'YAML'
rules:
  - id: not-namespaced-rule
    description: dogfood 2026-11-17 refusal probe
    priority: 950
    action: block
    match:
      type: pattern
      pattern: '^whoami$'
YAML
before=$(ls "$RD" | wc -l)
env HOME="$H" "$REPO/install.sh" --no-path --rule-pack-file "$H/policy/bad-pack.yaml" > "$H/bad.out" 2> "$H/bad.err"
echo "bad_pack_rc=$?"
after=$(ls "$RD" | wc -l)
echo "rules_dir_files_before=$before after=$after"
echo "bad stderr:"; cat "$H/bad.err"
grep -iE 'skip|refus|invalid|namespace' "$H/bad.out" | tail -4
echo "=== 6. schema subcommand (does it name all 9 types?) ==="
python3 "$REPO/scripts/rule-pack-tool.py" schema 2>&1 | grep -cE 'pattern|command|pipeline|subcommand|path|composite|syscall|network|heredoc'
