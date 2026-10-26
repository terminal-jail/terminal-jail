# Verdict: TJ-GAP-090

**Task:** Onboarding: zero-to-contained in five minutes on a FRESH machine
**Evaluated:** 2026-10-08T02:26:43.445712
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_tjdf042_warn_docs_pin.py::test_docs_pin_warn_mode_downgrade_provenance [first fail
- ✗ **tier2**
  - INCOMPLETE

Evaluator error: LLM call failed: 402 Client Error: Payment Required for url: https://api.deepseek.com/v1/chat/completions (provider=openai model=deepseek-v4-flash url=https://api.deepseek.com/v1/chat/completions key=<GITREINS_LLM_API_KEY>)

## Summary

Judge Result: TJ-GAP-090

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_tjdf042_warn_docs_pin.py::test_docs_pin_warn_mode_downgrade_provenance [first fail

Stage tier2: FAIL
  INCOMPLETE

Evaluator error: LLM call failed: 402 Client Error: Payment Required for url: https://api.deepseek.com/v1/chat/completions (provider=openai model=deepseek-v4-flash url=https://api.deepseek.com/v1/chat/completions key=<GITREINS_LLM_API_KEY>)

Overall: FAIL ✗
