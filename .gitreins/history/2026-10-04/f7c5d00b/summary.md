# Verdict: INT-CI-2

**Task:** Coverage tooling: pytest-cov in dev group, CI coverage job with measured floor
**Evaluated:** 2026-10-04T05:20:56.398911
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE

Cap exceeded: Time cap (1h) exceeded (1h elapsed). Increase max_time or simplify criteria.

## Summary

Judge Result: INT-CI-2

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE

Cap exceeded: Time cap (1h) exceeded (1h elapsed). Increase max_time or simplify criteria.

Overall: FAIL ✗
