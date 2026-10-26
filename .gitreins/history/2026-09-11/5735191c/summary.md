# Verdict: TJ-GAP-051

**Task:** [P1] YAML mirror loaded as user rules weakens 12 engine verdicts
**Evaluated:** 2026-09-11T11:28:59.500444
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m6:28AM[0m [32mINF[0m [1mscanned ~4355228 bytes (4.36 MB) in 420ms[0m
[90m6:28AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ On kara-lair (host with ~/.config/terminal-jail/rules.d/00-builtins.yaml present from the documented install path), bare .venv/bin/python -m pytest -q passes with 0 failed (previously 12 failed / 295 passed / 13 skipped from user-rules override): Host file ~/.config/terminal-jail/rules.d/00-builtins.yaml exists and is byte-identical to the shipped plugin/terminal_jail/rules/00-builtins.yaml (diff returned IDENTICAL). Ran `.venv/bin/python -m pytest -q` -> exit_code=0, output tail: '308 passed, 13 skipped in 7.95s' (0 failed).
  ✓ plugin/test_packaging.py mirror test compares rule PATTERNS (or RuleLoader behavior parity), not just ids/counts — reverting any YAML pattern to its pre-fix weaker form fails the test: plugin/test_packaging.py:137 test_shipped_rules_yaml_patterns_match_engine_builtins loads rules via RuleLoader(system_dir=..., user_dir='/nonexistent') and compares engine_rule.match['pattern'] vs yaml_rule.match['pattern'] per rule id (lines 178-190). Mutation test: weakened the auto-script YAML pattern to its pre-fix form -> 'FAILED plugin/test_packaging.py::test_shipped_rules_yaml_patterns_match_engine_builtins ... 1 failed, 6 passed in 0.20s' with engine= vs yaml= pattern diff at test_packaging.py:188. File restored afterwards (diff vs backup = RESTORED_OK).
  ✓ scripts/yaml-mirror-parity-probe.py covers pattern equality across all shipped rules and exits non-zero on pattern drift: scripts/yaml-mirror-parity-probe.py check_patterns() iterates all ENGINE_RULES (30) comparing engine vs loaded YAML pattern strings; main() returns 0 if ok else 1. Clean run: `.venv/bin/python scripts/yaml-mirror-parity-probe.py` -> '[pattern] 30 shipped rules compared -> OK', 'ALL PROBES PASS', EXIT=0. Mutation run (weakened auto-script pattern) -> PROBE_EXIT=1, '[pattern] auto-script: DRIFT', '[pattern] 30 shipped rules compared -> MISMATCH', 'PROBE FAILURES: shipped YAML mirror is not parity-clean'.
  ✓ plugin/terminal_jail/rules/00-builtins.yaml header comment count matches the real rule/blocklist id counts: Header lines 6-7 state 'the same 30 rules hardcoded in the Python engine (12 blocklist / 8 sandbox / 10 allow)'. Verified real counts: YAML rules by action = 12 block / 8 sandbox / 10 allow / 30 total; engine BUILTIN_BLOCKLIST=12, BUILTIN_SANDBOX=8, BUILTIN_ALLOWLIST=10, total=30. Counts match exactly (also consistent with docs/quickstart.md:230).
All four criteria pass: full suite is green (308 passed, 13 skipped, 0 failed) on the host with the installed YAML mirror, and both the packaging mirror test and the parity probe were proven to fail/exit non-zero when a YAML pattern is reverted to its weaker pre-fix form, with the header counts matching the real 12/8/10 engine counts.

## Summary

Judge Result: TJ-GAP-051

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m6:28AM[0m [32mINF[0m [1mscanned ~4355228 bytes (4.36 MB) in 420ms[0m
[90m6:28AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ On kara-lair (host with ~/.config/terminal-jail/rules.d/00-builtins.yaml present from the documented install path), bare .venv/bin/python -m pytest -q passes with 0 failed (previously 12 failed / 295 passed / 13 skipped from user-rules override): Host file ~/.config/terminal-jail/rules.d/00-builtins.yaml exists and is byte-identical to the shipped plugin/terminal_jail/rules/00-builtins.yaml (diff returned IDENTICAL). Ran `.venv/bin/python -m pytest -q` -> exit_code=0, output tail: '308 passed, 13 skipped in 7.95s' (0 failed).
  ✓ plugin/test_packaging.py mirror test compares rule PATTERNS (or RuleLoader behavior parity), not just ids/counts — reverting any YAML pattern to its pre-fix weaker form fails the test: plugin/test_packaging.py:137 test_shipped_rules_yaml_patterns_match_engine_builtins loads rules via RuleLoader(system_dir=..., user_dir='/nonexistent') and compares engine_rule.match['pattern'] vs yaml_rule.match['pattern'] per rule id (lines 178-190). Mutation test: weakened the auto-script YAML pattern to its pre-fix form -> 'FAILED plugin/test_packaging.py::test_shipped_rules_yaml_patterns_match_engine_builtins ... 1 failed, 6 passed in 0.20s' with engine= vs yaml= pattern diff at test_packaging.py:188. File restored afterwards (diff vs backup = RESTORED_OK).
  ✓ scripts/yaml-mirror-parity-probe.py covers pattern equality across all shipped rules and exits non-zero on pattern drift: scripts/yaml-mirror-parity-probe.py check_patterns() iterates all ENGINE_RULES (30) comparing engine vs loaded YAML pattern strings; main() returns 0 if ok else 1. Clean run: `.venv/bin/python scripts/yaml-mirror-parity-probe.py` -> '[pattern] 30 shipped rules compared -> OK', 'ALL PROBES PASS', EXIT=0. Mutation run (weakened auto-script pattern) -> PROBE_EXIT=1, '[pattern] auto-script: DRIFT', '[pattern] 30 shipped rules compared -> MISMATCH', 'PROBE FAILURES: shipped YAML mirror is not parity-clean'.
  ✓ plugin/terminal_jail/rules/00-builtins.yaml header comment count matches the real rule/blocklist id counts: Header lines 6-7 state 'the same 30 rules hardcoded in the Python engine (12 blocklist / 8 sandbox / 10 allow)'. Verified real counts: YAML rules by action = 12 block / 8 sandbox / 10 allow / 30 total; engine BUILTIN_BLOCKLIST=12, BUILTIN_SANDBOX=8, BUILTIN_ALLOWLIST=10, total=30. Counts match exactly (also consistent with docs/quickstart.md:230).
All four criteria pass: full suite is green (308 passed, 13 skipped, 0 failed) on the host with the installed YAML mirror, and both the packaging mirror test and the parity probe were proven to fail/exit non-zero when a YAML pattern is reverted to its weaker pre-fix form, with the header counts matching the real 12/8/10 engine counts.

Overall: PASS ✓
