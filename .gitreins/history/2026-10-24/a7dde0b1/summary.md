# Verdict: QA-TERMINAL-JAIL-BATTERY-1

**Task:** Landlock clean-machine fixture portability
**Evaluated:** 2026-10-24T21:31:48.735588
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE

Cap exceeded: Iteration cap (300) reached (300 used). Increase max_iterations or split criteria.

## Summary

Judge Result: QA-TERMINAL-JAIL-BATTERY-1

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE

Cap exceeded: Iteration cap (300) reached (300 used). Increase max_iterations or split criteria.

Overall: FAIL ✗
