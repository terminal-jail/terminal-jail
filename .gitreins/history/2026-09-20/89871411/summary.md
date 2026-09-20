# Verdict: DF-TERMINAL-JAIL-25

**Task:** Same-id warn downgrade loses the rule's block_message
**Evaluated:** 2026-09-20T20:19:21.859540
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✗ **tier2**
  - INCOMPLETE

Cap exceeded: Time cap (1h) exceeded (1h elapsed). Increase max_time or simplify criteria.

## Summary

Judge Result: DF-TERMINAL-JAIL-25

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: FAIL
  INCOMPLETE

Cap exceeded: Time cap (1h) exceeded (1h elapsed). Increase max_time or simplify criteria.

Overall: FAIL ✗
