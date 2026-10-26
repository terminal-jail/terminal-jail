# Verdict: QA-TERMINAL-JAIL-10

**Task:** builtin-id-collision refusal test tolerates sandbox-fallback WARNING
**Evaluated:** 2026-09-20T15:00:51.080613
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ test_builtin_id_collision_is_refused asserts the refusal line and rc without failing when the mapping-less-PID-namespace WARNING precedes it; full suite green: plugin/test_rule_packs.py:294 test_builtin_id_collision_is_refused calls _assert_refused(result, "collide with engine builtin ids"); _assert_refused (lines 262-292) asserts result.returncode == 2, requires exactly one line starting with REFUSAL_PREFIX ("rule-pack-tool: refused:", line 53), asserts the needle is in that line, and tolerates only DOCUMENTED_SANDBOX_BANNERS = ("terminal-jail: WARNING: no filesystem isolation",) (lines 47-49) each at most once — any other stderr line is a hard failure, so the mapping-less-PID-namespace WARNING preceding the refusal no longer breaks the test. No residual brittle assertion: `grep -rn "len(stderr_lines)" plugin/` -> none. Contract self-tests TestAssertRefusedContract (lines 494-560) include test_refusal_plus_df15_warning_passes (line 522) covering the WARNING-then-refusal 2-line shape plus negative controls. Fresh test runs: `.venv/bin/python -m pytest plugin/test_rule_packs.py -q` -> exit 0, "35 passed in 1.12s"; full suite `.venv/bin/python -m pytest -q` -> exit 0, "1102 passed, 7 skipped in 28.10s"; targeted run of test_builtin_id_collision_is_refused + all 8 TestAssertRefusedContract tests -> "9 passed in 0.31s".
The refusal test now asserts rc=2 and the refusal line by presence while tolerating the documented sandbox-fallback WARNING, and the full suite is green (1102 passed, 7 skipped).

## Summary

Judge Result: QA-TERMINAL-JAIL-10

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ test_builtin_id_collision_is_refused asserts the refusal line and rc without failing when the mapping-less-PID-namespace WARNING precedes it; full suite green: plugin/test_rule_packs.py:294 test_builtin_id_collision_is_refused calls _assert_refused(result, "collide with engine builtin ids"); _assert_refused (lines 262-292) asserts result.returncode == 2, requires exactly one line starting with REFUSAL_PREFIX ("rule-pack-tool: refused:", line 53), asserts the needle is in that line, and tolerates only DOCUMENTED_SANDBOX_BANNERS = ("terminal-jail: WARNING: no filesystem isolation",) (lines 47-49) each at most once — any other stderr line is a hard failure, so the mapping-less-PID-namespace WARNING preceding the refusal no longer breaks the test. No residual brittle assertion: `grep -rn "len(stderr_lines)" plugin/` -> none. Contract self-tests TestAssertRefusedContract (lines 494-560) include test_refusal_plus_df15_warning_passes (line 522) covering the WARNING-then-refusal 2-line shape plus negative controls. Fresh test runs: `.venv/bin/python -m pytest plugin/test_rule_packs.py -q` -> exit 0, "35 passed in 1.12s"; full suite `.venv/bin/python -m pytest -q` -> exit 0, "1102 passed, 7 skipped in 28.10s"; targeted run of test_builtin_id_collision_is_refused + all 8 TestAssertRefusedContract tests -> "9 passed in 0.31s".
The refusal test now asserts rc=2 and the refusal line by presence while tolerating the documented sandbox-fallback WARNING, and the full suite is green (1102 passed, 7 skipped).

Overall: PASS ✓
