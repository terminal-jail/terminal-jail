# Verdict: TJ-DF-035

**Task:** Pack-authoring schema discoverable from documented material only
**Evaluated:** 2026-09-29T16:05:12.667609
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ A pack author following only README + --help produces a valid pack in <=2 attempts; documented example carries action, priority, match.type=pattern, pattern, message: README.md §'Authoring a pack' (~lines 118-146) documents `scripts/rule-pack-tool.py schema`, the shipped example `plugin/terminal_jail/rules/packs/example-pack.yaml`, the minimal YAML shape (id/action/priority/block_message/match.type=pattern/pattern), and explicitly warns `match.type: regex` is invalid — the one mistake that would cost an attempt. `python3 scripts/rule-pack-tool.py --help` (exit 0) lists the `schema` subcommand; `python3 scripts/rule-pack-tool.py schema` (exit 0) prints all rule fields, all 9 valid match.type values with per-type fields (derived at runtime from matcher.py:143-158 dispatch table), a minimal valid pack example carrying action: block, priority: 950, block_message, match.type: pattern, pattern: "^rm -rf /", and a pointer to specs/interruptor.md §3.4. The shipped example-pack.yaml carries id, description, priority: 950, action: block, block_message, match.type: pattern, pattern: "^rm -rf /". `python3 scripts/rule-pack-tool.py validate plugin/terminal_jail/rules/packs/example-pack.yaml --pack-name example` => exit 0, 'rule-pack-tool: pack 'example' valid — 1 rule(s) (1 block)'. Tests: `.venv/bin/python -m pytest plugin/test_rule_packs.py -x --tb=short -q` => '60 passed in 2.40s', exit 0, including TestValidatorSchema (schema lists every valid match type, prints minimal example + pointer, takes no arguments, --help mentions schema, shipped example pack validates first try). Note: the message field is named `block_message` in the engine (rules.py:24,72,146) and in all docs/schema/example output — the documented example does carry a message field.
README authoring section + `rule-pack-tool.py schema`/`--help` fully document the pack schema (including the regex-vs-pattern trap), the shipped example pack validates first try, and all 60 rule-pack tests pass.

## Summary

Judge Result: TJ-DF-035

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ A pack author following only README + --help produces a valid pack in <=2 attempts; documented example carries action, priority, match.type=pattern, pattern, message: README.md §'Authoring a pack' (~lines 118-146) documents `scripts/rule-pack-tool.py schema`, the shipped example `plugin/terminal_jail/rules/packs/example-pack.yaml`, the minimal YAML shape (id/action/priority/block_message/match.type=pattern/pattern), and explicitly warns `match.type: regex` is invalid — the one mistake that would cost an attempt. `python3 scripts/rule-pack-tool.py --help` (exit 0) lists the `schema` subcommand; `python3 scripts/rule-pack-tool.py schema` (exit 0) prints all rule fields, all 9 valid match.type values with per-type fields (derived at runtime from matcher.py:143-158 dispatch table), a minimal valid pack example carrying action: block, priority: 950, block_message, match.type: pattern, pattern: "^rm -rf /", and a pointer to specs/interruptor.md §3.4. The shipped example-pack.yaml carries id, description, priority: 950, action: block, block_message, match.type: pattern, pattern: "^rm -rf /". `python3 scripts/rule-pack-tool.py validate plugin/terminal_jail/rules/packs/example-pack.yaml --pack-name example` => exit 0, 'rule-pack-tool: pack 'example' valid — 1 rule(s) (1 block)'. Tests: `.venv/bin/python -m pytest plugin/test_rule_packs.py -x --tb=short -q` => '60 passed in 2.40s', exit 0, including TestValidatorSchema (schema lists every valid match type, prints minimal example + pointer, takes no arguments, --help mentions schema, shipped example pack validates first try). Note: the message field is named `block_message` in the engine (rules.py:24,72,146) and in all docs/schema/example output — the documented example does carry a message field.
README authoring section + `rule-pack-tool.py schema`/`--help` fully document the pack schema (including the regex-vs-pattern trap), the shipped example pack validates first try, and all 60 rule-pack tests pass.

Overall: PASS ✓
