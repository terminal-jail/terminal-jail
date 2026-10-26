# Verdict: TJ-GAP-059

**Task:** GTFOBins-sweep harness: machine-readable catalog to per-function-class verdict matrix
**Evaluated:** 2026-09-20T13:23:54.716475
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE

(auto-parsed from non-JSON response — JSON parse failed: Expecting ':' delimiter: line 3 column 2417 (char 2463)) All criteria verified with concrete evidence.

{"verdict":"COMPLETE","items":[{"criterion":"scripts/gtfobins-sweep.py runs --help and a seed-catalog sweep exits 0, printing a per-function-class verdict matrix and a coverage summary line","status":"PASS","detail":"`.venv/bin/python scripts/gtfobins-s

## Summary

Judge Result: TJ-GAP-059

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE

(auto-parsed from non-JSON response — JSON parse failed: Expecting ':' delimiter: line 3 column 2417 (char 2463)) All criteria verified with concrete evidence.

{"verdict":"COMPLETE","items":[{"criterion":"scripts/gtfobins-sweep.py runs --help and a seed-catalog sweep exits 0, printing a per-function-class verdict matrix and a coverage summary line","status":"PASS","detail":"`.venv/bin/python scripts/gtfobins-s

Overall: PASS ✓
