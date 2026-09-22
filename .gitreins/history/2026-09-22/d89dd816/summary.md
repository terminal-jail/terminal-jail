# Verdict: INT-CI-001

**Task:** Fix host-degradation CI failures in wrapper verdict-hardening tests
**Evaluated:** 2026-09-22T14:39:47.288485
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✗ **tier2**
  - INCOMPLETE

Cap exceeded: Input token budget (8.0M) exceeded (8.1M used). Increase max_input_tokens or reduce message context.

## Summary

Judge Result: INT-CI-001

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: FAIL
  INCOMPLETE

Cap exceeded: Input token budget (8.0M) exceeded (8.1M used). Increase max_input_tokens or reduce message context.

Overall: FAIL ✗
