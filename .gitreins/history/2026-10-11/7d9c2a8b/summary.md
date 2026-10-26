# Verdict: QA-TERMINAL-JAIL-17

**Task:** Landlock allowlist must support home-based payload interpreters
**Evaluated:** 2026-10-11T12:35:05.892188
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE

Cap exceeded: Iteration cap (300) reached (300.1 used). Increase max_iterations or split criteria.

## Summary

Judge Result: QA-TERMINAL-JAIL-17

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE

Cap exceeded: Iteration cap (300) reached (300.1 used). Increase max_iterations or split criteria.

Overall: FAIL ✗
