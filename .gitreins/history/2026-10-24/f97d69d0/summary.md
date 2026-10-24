# Verdict: TJ-DF-055

**Task:** README resident daemon wrapper signal guidance
**Evaluated:** 2026-10-24T10:28:15.852180
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ README.md resident section (lines 346-412) explicitly instructs operators to signal the Python daemon process, not the wrapping shell; verify the criterion with the exact grep from the task row. This task is documentation-only; do not change wrapper behavior.: README.md:394-397 (inside the resident section headed at README.md:347 '### Choosing a bridge transport: one-shot vs resident (TJ-GAP-084)', well within lines 346-412) reads: '**Resident signal target.** If the daemon is launched through `bash -lic` or another wrapping shell, that shell may not forward `SIGINT`/`SIGTERM` to its child. Signal the Python daemon process, not the wrapping shell; the daemon can then exit cleanly and remove its socket.' Exact grep `grep -n "Signal the" README.md` -> `395:wrapping shell, that shell may not forward `SIGINT`/`SIGTERM` to its child. Signal the` (exit 0), and `grep -n "Resident signal target" README.md` -> `394:`. Documentation-only confirmed: commit af869b2 'docs(readme): TJ-DF-055 — explain resident daemon signal target' changed only README.md (+5 lines, 1 file changed), and `git diff HEAD --stat -- standalone/ plugin/ scripts/` is empty (no wrapper behavior change). Tests run fresh: `.venv/bin/python -m pytest tests/test_signal_reach_doc.py tests/test_quickstart_doc.py -q` -> '13 passed in 0.03s' exit 0; full suite `.venv/bin/python -m pytest -q --tb=line -p no:cacheprovider` -> '2055 passed, 15 skipped in 187.68s (0:03:07)' exit 0. [resolution 0.26; README.md]
README.md:394-397 explicitly tells operators to signal the Python daemon process rather than the wrapping shell, inside the resident section (346-412), with only README.md changed and the full suite green (2055 passed, 15 skipped).

## Summary

Judge Result: TJ-DF-055

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ README.md resident section (lines 346-412) explicitly instructs operators to signal the Python daemon process, not the wrapping shell; verify the criterion with the exact grep from the task row. This task is documentation-only; do not change wrapper behavior.: README.md:394-397 (inside the resident section headed at README.md:347 '### Choosing a bridge transport: one-shot vs resident (TJ-GAP-084)', well within lines 346-412) reads: '**Resident signal target.** If the daemon is launched through `bash -lic` or another wrapping shell, that shell may not forward `SIGINT`/`SIGTERM` to its child. Signal the Python daemon process, not the wrapping shell; the daemon can then exit cleanly and remove its socket.' Exact grep `grep -n "Signal the" README.md` -> `395:wrapping shell, that shell may not forward `SIGINT`/`SIGTERM` to its child. Signal the` (exit 0), and `grep -n "Resident signal target" README.md` -> `394:`. Documentation-only confirmed: commit af869b2 'docs(readme): TJ-DF-055 — explain resident daemon signal target' changed only README.md (+5 lines, 1 file changed), and `git diff HEAD --stat -- standalone/ plugin/ scripts/` is empty (no wrapper behavior change). Tests run fresh: `.venv/bin/python -m pytest tests/test_signal_reach_doc.py tests/test_quickstart_doc.py -q` -> '13 passed in 0.03s' exit 0; full suite `.venv/bin/python -m pytest -q --tb=line -p no:cacheprovider` -> '2055 passed, 15 skipped in 187.68s (0:03:07)' exit 0. [resolution 0.26; README.md]
README.md:394-397 explicitly tells operators to signal the Python daemon process rather than the wrapping shell, inside the resident section (346-412), with only README.md changed and the full suite green (2055 passed, 15 skipped).

Overall: PASS ✓
