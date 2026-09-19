# Verdict: TJ-GAP-061

**Task:** Rule-pack system: opt-in curated rule sets (rules/packs/*.yaml) selectable at install time, explicit precedence contract
**Evaluated:** 2026-09-19T05:04:59.693440
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh accepts repeatable --rule-pack <name>, --unrule-pack <name> and --list-rule-packs; a scratch-prefix install writes <resolved rules dir>/terminal-jail-pack-<name>.yaml: install.sh:98-124 parses --rule-pack/--unrule-pack (both `--flag val` and `--flag=val`) and --list-rule-packs; add_rule_pack/add_unrule_pack (lines 43-62) accumulate repeatable names. Live: `TERMINAL_JAIL_INSTALL_DIR=/tmp/tjtest/prefix/bin ./install.sh --rule-pack db` exit 0, wrote /tmp/tjtest/prefix/config/terminal-jail/rules.d/terminal-jail-pack-db.yaml (5563 bytes). `./install.sh --list-rule-packs` exit 0 printed `db	.../packs/db.yaml	3`.
  ✓ the engine loads the installed pack: a live intercept/bridge probe returns the pack rule id (pack-<name>-*) with the pack installed, and does not without it: With pack installed (TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=<scratch rules.d>), live intercept() returned: 'psql ... DROP DATABASE prod_app' -> block pack-db-drop-database; 'mysql -e DROP TABLE customers' -> block pack-db-drop-table; 'pg_dump mydb' -> modify pack-db-dump-restore. With an empty rules dir the same commands returned allow/None (no pack-* id).
  ✓ id-collision contract: a pack rule whose id collides with an engine builtin id, or with an already-installed pack, is REFUSED (non-zero exit, no file written): Builtin collision: pack with id 'builtin-rm-rf-root' -> install.sh exit 2, stderr 'collide with engine builtin ids', no shadow.yaml written. Already-installed collision: pack 'dup2' with id 'pack-dup2-drop-database' already present in zz-handwritten.yaml -> exit 2, 'are already installed in ... refusing to shadow them', no dup2 file written. Enforced by scripts/rule-pack-tool.py cmd_validate collision oracles before install.sh:355-360 cp.
  ✓ schema-invalid pack is refused at install time (non-zero exit, nothing written); --unrule-pack removes only that pack file and leaves other rules intact: Schema-invalid pack (rule missing 'match') -> install.sh exit 2, 'has no 'match' mapping', no file written. `--unrule-pack dup` exit 0 removed only terminal-jail-pack-dup.yaml; 00-builtins.yaml, terminal-jail-pack-db.yaml and zz-handwritten.yaml remained, and the db pack still fired through intercept() (block pack-db-drop-database).
  ✓ each shipped pack has its own test file exercising its rules through intercept(); full suite green via .venv/bin/python -m pytest -q: Only one shipped pack (plugin/terminal_jail/rules/packs/db.yaml); plugin/test_rule_packs.py TestShippedDbPack (lines 105-160) drives each rule through intercept() with parametrized positives, benign controls, and a no-pack control. `.venv/bin/python -m pytest -q` -> '860 passed, 5 skipped in 27.67s' (exit 0); pack file alone 27 passed.
  ✓ README documents the packs (what each blocks + opt-in stance) and specs/cli.md installer-inputs table documents the new flags: README.md:447-500 '### Rule packs (opt-in)' documents the db pack (blocks DROP DATABASE/DROP TABLE, sandboxes dump/restore tooling), the opt-in stance, validation/collision contract and precedence. specs/cli.md:374-384 'Installer inputs and defaults' table has rows for --rule-pack, --unrule-pack and --list-rule-packs; specs/cli.md:394 adds the 'Rule packs (--rule-pack, TJ-GAP-061)' section.
All six criteria pass: installer flags work end-to-end (scratch-prefix install writes terminal-jail-pack-db.yaml), the engine loads the pack via intercept() and not without it, builtin/installed id collisions and schema-invalid packs are refused with exit 2 and nothing written, --unrule-pack removes only its own file, the shipped db pack has an intercept()-driven test file, the full suite is green (860 passed, 5 skipped), and README + specs/cli.md document the packs and flags.

## Summary

Judge Result: TJ-GAP-061

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ install.sh accepts repeatable --rule-pack <name>, --unrule-pack <name> and --list-rule-packs; a scratch-prefix install writes <resolved rules dir>/terminal-jail-pack-<name>.yaml: install.sh:98-124 parses --rule-pack/--unrule-pack (both `--flag val` and `--flag=val`) and --list-rule-packs; add_rule_pack/add_unrule_pack (lines 43-62) accumulate repeatable names. Live: `TERMINAL_JAIL_INSTALL_DIR=/tmp/tjtest/prefix/bin ./install.sh --rule-pack db` exit 0, wrote /tmp/tjtest/prefix/config/terminal-jail/rules.d/terminal-jail-pack-db.yaml (5563 bytes). `./install.sh --list-rule-packs` exit 0 printed `db	.../packs/db.yaml	3`.
  ✓ the engine loads the installed pack: a live intercept/bridge probe returns the pack rule id (pack-<name>-*) with the pack installed, and does not without it: With pack installed (TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=<scratch rules.d>), live intercept() returned: 'psql ... DROP DATABASE prod_app' -> block pack-db-drop-database; 'mysql -e DROP TABLE customers' -> block pack-db-drop-table; 'pg_dump mydb' -> modify pack-db-dump-restore. With an empty rules dir the same commands returned allow/None (no pack-* id).
  ✓ id-collision contract: a pack rule whose id collides with an engine builtin id, or with an already-installed pack, is REFUSED (non-zero exit, no file written): Builtin collision: pack with id 'builtin-rm-rf-root' -> install.sh exit 2, stderr 'collide with engine builtin ids', no shadow.yaml written. Already-installed collision: pack 'dup2' with id 'pack-dup2-drop-database' already present in zz-handwritten.yaml -> exit 2, 'are already installed in ... refusing to shadow them', no dup2 file written. Enforced by scripts/rule-pack-tool.py cmd_validate collision oracles before install.sh:355-360 cp.
  ✓ schema-invalid pack is refused at install time (non-zero exit, nothing written); --unrule-pack removes only that pack file and leaves other rules intact: Schema-invalid pack (rule missing 'match') -> install.sh exit 2, 'has no 'match' mapping', no file written. `--unrule-pack dup` exit 0 removed only terminal-jail-pack-dup.yaml; 00-builtins.yaml, terminal-jail-pack-db.yaml and zz-handwritten.yaml remained, and the db pack still fired through intercept() (block pack-db-drop-database).
  ✓ each shipped pack has its own test file exercising its rules through intercept(); full suite green via .venv/bin/python -m pytest -q: Only one shipped pack (plugin/terminal_jail/rules/packs/db.yaml); plugin/test_rule_packs.py TestShippedDbPack (lines 105-160) drives each rule through intercept() with parametrized positives, benign controls, and a no-pack control. `.venv/bin/python -m pytest -q` -> '860 passed, 5 skipped in 27.67s' (exit 0); pack file alone 27 passed.
  ✓ README documents the packs (what each blocks + opt-in stance) and specs/cli.md installer-inputs table documents the new flags: README.md:447-500 '### Rule packs (opt-in)' documents the db pack (blocks DROP DATABASE/DROP TABLE, sandboxes dump/restore tooling), the opt-in stance, validation/collision contract and precedence. specs/cli.md:374-384 'Installer inputs and defaults' table has rows for --rule-pack, --unrule-pack and --list-rule-packs; specs/cli.md:394 adds the 'Rule packs (--rule-pack, TJ-GAP-061)' section.
All six criteria pass: installer flags work end-to-end (scratch-prefix install writes terminal-jail-pack-db.yaml), the engine loads the pack via intercept() and not without it, builtin/installed id collisions and schema-invalid packs are refused with exit 2 and nothing written, --unrule-pack removes only its own file, the shipped db pack has an intercept()-driven test file, the full suite is green (860 passed, 5 skipped), and README + specs/cli.md document the packs and flags.

Overall: PASS ✓
