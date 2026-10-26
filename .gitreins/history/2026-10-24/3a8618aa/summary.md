# Verdict: INT-CI-3

**Task:** Fix test assertions for TERMINAL_JAIL_VERBOSE_WARN single-line default
**Evaluated:** 2026-10-24T11:54:10.433241
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE
  ✗ plugin/test_backend_selection.py::test_auto_uses_bwrap_for_user_when_mapping_unavailable passes AND plugin/test_userns.py::TestDegradedFallback::test_degraded_host_warns_and_keeps_working passes AND CI green on main: Both named tests pass: `.venv/bin/python -m pytest plugin/test_backend_selection.py::test_auto_uses_bwrap_for_user_when_mapping_unavailable plugin/test_userns.py::TestDegradedFallback::test_degraded_host_warns_and_keeps_working -q` -> "2 passed in 0.99s", exit 0. Assertions at test_backend_selection.py:368-375 and test_userns.py:490-497 both expect the single-line "filesystem isolation degraded (AppArmor); set TERMINAL_JAIL_VERBOSE_WARN=1 for details". Still need: CI green on main.
Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: INT-CI-3

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE
  ✗ plugin/test_backend_selection.py::test_auto_uses_bwrap_for_user_when_mapping_unavailable passes AND plugin/test_userns.py::TestDegradedFallback::test_degraded_host_warns_and_keeps_working passes AND CI green on main: Both named tests pass: `.venv/bin/python -m pytest plugin/test_backend_selection.py::test_auto_uses_bwrap_for_user_when_mapping_unavailable plugin/test_userns.py::TestDegradedFallback::test_degraded_host_warns_and_keeps_working -q` -> "2 passed in 0.99s", exit 0. Assertions at test_backend_selection.py:368-375 and test_userns.py:490-497 both expect the single-line "filesystem isolation degraded (AppArmor); set TERMINAL_JAIL_VERBOSE_WARN=1 for details". Still need: CI green on main.
Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
