# Verdict: TJ-GAP-070

**Task:** Fail closed on engine-evaluation errors in interruptor bridge + wrapper verdict hardening
**Evaluated:** 2026-09-22T14:58:46.842712
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ Poison-priority rules fixture makes standalone/terminal-jail exit 126 with a block box in enforce mode; bridge emits action=block with [bridge-error] reason on intercept() exception; non-JSON/empty bridge stdout blocks in enforce mode; [bridge-error] reason treated as block in enforce, loud warn in warn mode; load-time schema pass refuses bad field types with stderr note; all existing suites stay green; clean-rules control unchanged; regression tests added: All sub-requirements verified. (1) Poison fixture POISON_PRIORITY_YAML (plugin/test_bridge_fail_closed.py:70-78, `priority: not-a-number`) drives: bridge verdict block (test_poison_priority_bridge_verdict_blocks:522), intercept() raises RuleSchemaError (test_poison_priority_intercept_raises:549), loader refuses loudly (test_poison_priority_file_refused_loudly:503). (2) Bridge fail-closed: plugin/terminal_jail/interruptor_bridge.py:73-90 `except Exception` -> `_emit_fail_closed` emitting action=block, rule_id="[bridge-error]", reason "[bridge-error] {detail} — fail-closed: blocking command (enforce mode)"; test_engine_exception_emits_block_verdict:118 asserts exactly this. (3) Wrapper: standalone/terminal-jail:310-357 normalizes empty stdout to sentinel and routes unusable verdicts to exit 126 (enforce) / WARN (warn); :375-390 treats `[bridge-error]*` reason as block in enforce, WARN+allow in warn; :396-409 prints block box and `exit 126`. Tests test_empty_bridge_stdout_blocks_in_enforce:363, test_garbage_bridge_stdout_blocks_in_enforce:314, test_whitespace_bridge_stdout_blocks_in_enforce:419, test_bridge_error_reason_blocks_in_enforce:262, test_bridge_error_reason_warns_and_runs_in_warn_mode:285. (4) Loader schema pass: plugin/terminal_jail/interruptor/rules.py:124-410 RuleSchemaError + validate_rule_document + one-line stderr note naming the file (test asserts err.count('\n')==1 and 'bad.yaml' in err); bool-priority and non-dict-entry refusals at :624/:637. (5) Clean-rules controls unchanged: test_clean_rules_still_load:589, test_valid_user_rule_file_still_loads:598, test_normal_allow_verdict_unchanged:438, test_normal_block_verdict_unchanged:471, test_parse_failure_still_skips_with_warning_not_abort:560. (6) Tests green: `.venv/bin/python -m pytest -q --tb=short` -> `1395 passed, 7 skipped in 35.14s` (exit 0); plugin/test_bridge_fail_closed.py -> `25 passed in 0.98s` (exit 0).


## Summary

Judge Result: TJ-GAP-070

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ Poison-priority rules fixture makes standalone/terminal-jail exit 126 with a block box in enforce mode; bridge emits action=block with [bridge-error] reason on intercept() exception; non-JSON/empty bridge stdout blocks in enforce mode; [bridge-error] reason treated as block in enforce, loud warn in warn mode; load-time schema pass refuses bad field types with stderr note; all existing suites stay green; clean-rules control unchanged; regression tests added: All sub-requirements verified. (1) Poison fixture POISON_PRIORITY_YAML (plugin/test_bridge_fail_closed.py:70-78, `priority: not-a-number`) drives: bridge verdict block (test_poison_priority_bridge_verdict_blocks:522), intercept() raises RuleSchemaError (test_poison_priority_intercept_raises:549), loader refuses loudly (test_poison_priority_file_refused_loudly:503). (2) Bridge fail-closed: plugin/terminal_jail/interruptor_bridge.py:73-90 `except Exception` -> `_emit_fail_closed` emitting action=block, rule_id="[bridge-error]", reason "[bridge-error] {detail} — fail-closed: blocking command (enforce mode)"; test_engine_exception_emits_block_verdict:118 asserts exactly this. (3) Wrapper: standalone/terminal-jail:310-357 normalizes empty stdout to sentinel and routes unusable verdicts to exit 126 (enforce) / WARN (warn); :375-390 treats `[bridge-error]*` reason as block in enforce, WARN+allow in warn; :396-409 prints block box and `exit 126`. Tests test_empty_bridge_stdout_blocks_in_enforce:363, test_garbage_bridge_stdout_blocks_in_enforce:314, test_whitespace_bridge_stdout_blocks_in_enforce:419, test_bridge_error_reason_blocks_in_enforce:262, test_bridge_error_reason_warns_and_runs_in_warn_mode:285. (4) Loader schema pass: plugin/terminal_jail/interruptor/rules.py:124-410 RuleSchemaError + validate_rule_document + one-line stderr note naming the file (test asserts err.count('\n')==1 and 'bad.yaml' in err); bool-priority and non-dict-entry refusals at :624/:637. (5) Clean-rules controls unchanged: test_clean_rules_still_load:589, test_valid_user_rule_file_still_loads:598, test_normal_allow_verdict_unchanged:438, test_normal_block_verdict_unchanged:471, test_parse_failure_still_skips_with_warning_not_abort:560. (6) Tests green: `.venv/bin/python -m pytest -q --tb=short` -> `1395 passed, 7 skipped in 35.14s` (exit 0); plugin/test_bridge_fail_closed.py -> `25 passed in 0.98s` (exit 0).


Overall: PASS ✓
