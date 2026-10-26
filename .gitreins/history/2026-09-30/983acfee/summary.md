# Verdict: TJ-DF-033

**Task:** Wire metrics counters to plugin hooks
**Evaluated:** 2026-09-30T06:28:19.097237
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out
- ✓ **tier2**
  - COMPLETE
  ✓ The Metrics dataclass in plugin/terminal_jail/plugin.py has 9 counters that are never incremented outside tests. Add increment calls at the hook sites that already fire: pre_tool_call/post_tool_call in plugin/__init__.py must increment commands_wrapped/commands_wrapped_user_ns/commands_passed_disabled/commands_passed_no_unshare based on the mode and namespace outcome; jail_crashes increments when a sandboxed command exits non-zero; byte_budget_rejections increments when the byte budget check rejects; wrap_time_ns_total and wrap_count increment around the unshare wrap; perf_regression_alert_count increments when a perf alert fires. Add a test in plugin/test_metrics_counters.py that runs a real intercept() call and asserts the counter incremented. Run .venv/bin/python -m pytest plugin/test_metrics_counters.py -v and confirm it passes. Run scripts/metrics-export.py --json and confirm at least one counter is non-zero after a real command.: All 9 counters wired to real production sites. plugin/terminal_jail/plugin.py:225-240 (_record_wrap) bumps wrap_count, wrap_time_ns_total, commands_wrapped[_user_ns], byte_budget_rejections; :209 (_check_slow_wrap) bumps perf_regression_alert_count; called from plugin/terminal_jail/interruptor/__init__.py:88-100 on Action.MODIFY (the real unshare wrap). plugin/__init__.py:66 bumps commands_passed_no_unshare, :69 bumps commands_passed_disabled (pre_tool_call arms), :93 bumps jail_crashes (post-exec transform_terminal_output hook, the post-execution hook that actually fires — no post_tool_call hook exists in this codebase). interruptor/__init__.py:64 bumps commands_passed_disabled for disabled mode. TEST EVIDENCE: `.venv/bin/python -m pytest plugin/test_metrics_counters.py -v` -> '28 passed in 0.24s' exit_code 0; combined run with test_interruptor.py+test_plugin.py -> '559 passed in 4.20s' exit_code 0. plugin/test_metrics_counters.py (369 lines) runs real intercept() calls (e.g. test_real_wrap_increments_wrapped_and_time asserts commands_wrapped==1, wrap_count==1, wrap_time_ns_total>0). EXPORT EVIDENCE: same-process intercept('pytest -q') then runpy scripts/metrics-export.py --json -> commands_wrapped=1, wrap_count=1, wrap_time_ns_total=12289013 (non-zero); counters are process-local by design (documented plugin.py:20-24), so a separate-process export is necessarily zero. Manual checks: byte_budget_rejections=1 on over-budget wrap, commands_passed_disabled=1 on disabled mode, jail_crashes=1 on wrapped non-zero exit. LSP diagnostics: 0 findings. [resolution 0.18; plugin/terminal_jail/plugin.py, plugin/__init__.py, plugin/test_metrics_counters.py, scripts/metrics-export.py]


## Summary

Judge Result: TJ-DF-033

Stage tier1: FAIL
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out

Stage tier2: PASS
  COMPLETE
  ✓ The Metrics dataclass in plugin/terminal_jail/plugin.py has 9 counters that are never incremented outside tests. Add increment calls at the hook sites that already fire: pre_tool_call/post_tool_call in plugin/__init__.py must increment commands_wrapped/commands_wrapped_user_ns/commands_passed_disabled/commands_passed_no_unshare based on the mode and namespace outcome; jail_crashes increments when a sandboxed command exits non-zero; byte_budget_rejections increments when the byte budget check rejects; wrap_time_ns_total and wrap_count increment around the unshare wrap; perf_regression_alert_count increments when a perf alert fires. Add a test in plugin/test_metrics_counters.py that runs a real intercept() call and asserts the counter incremented. Run .venv/bin/python -m pytest plugin/test_metrics_counters.py -v and confirm it passes. Run scripts/metrics-export.py --json and confirm at least one counter is non-zero after a real command.: All 9 counters wired to real production sites. plugin/terminal_jail/plugin.py:225-240 (_record_wrap) bumps wrap_count, wrap_time_ns_total, commands_wrapped[_user_ns], byte_budget_rejections; :209 (_check_slow_wrap) bumps perf_regression_alert_count; called from plugin/terminal_jail/interruptor/__init__.py:88-100 on Action.MODIFY (the real unshare wrap). plugin/__init__.py:66 bumps commands_passed_no_unshare, :69 bumps commands_passed_disabled (pre_tool_call arms), :93 bumps jail_crashes (post-exec transform_terminal_output hook, the post-execution hook that actually fires — no post_tool_call hook exists in this codebase). interruptor/__init__.py:64 bumps commands_passed_disabled for disabled mode. TEST EVIDENCE: `.venv/bin/python -m pytest plugin/test_metrics_counters.py -v` -> '28 passed in 0.24s' exit_code 0; combined run with test_interruptor.py+test_plugin.py -> '559 passed in 4.20s' exit_code 0. plugin/test_metrics_counters.py (369 lines) runs real intercept() calls (e.g. test_real_wrap_increments_wrapped_and_time asserts commands_wrapped==1, wrap_count==1, wrap_time_ns_total>0). EXPORT EVIDENCE: same-process intercept('pytest -q') then runpy scripts/metrics-export.py --json -> commands_wrapped=1, wrap_count=1, wrap_time_ns_total=12289013 (non-zero); counters are process-local by design (documented plugin.py:20-24), so a separate-process export is necessarily zero. Manual checks: byte_budget_rejections=1 on over-budget wrap, commands_passed_disabled=1 on disabled mode, jail_crashes=1 on wrapped non-zero exit. LSP diagnostics: 0 findings. [resolution 0.18; plugin/terminal_jail/plugin.py, plugin/__init__.py, plugin/test_metrics_counters.py, scripts/metrics-export.py]


Overall: FAIL ✗
