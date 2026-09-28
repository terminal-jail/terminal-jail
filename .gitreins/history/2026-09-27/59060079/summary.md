# Verdict: TJ-DF-037

**Task:** Kernel-matrix teardown verification
**Evaluated:** 2026-09-27T22:39:34.143531
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ Implement a deterministic committed harness that runs both unshare and bwrap orphan-teardown cells, reports kernel/backend/verdict/survival/exit code, documents the measured limitation honestly, and adds regression coverage or manual-gate instructions without fabricating unavailable kernels.: scripts/kernel-matrix-teardown.py (592 lines, tracked in git, commit e39ba82) runs both cells: main() iterates BACKENDS=('bwrap','unshare') calling run_backend_cell(). Live run `.venv/bin/python scripts/kernel-matrix-teardown.py --json` (exit 0) emitted two rows with kernel='7.0.0-31-generic', backend bwrap+unshare, verdict PASS, survival_seconds ~0.0202, exit_code -9, captured, evidence; human mode prints kernel/backend/verdict/survival/exit/captured table. Deterministic: bounded LAUNCH_WAIT=10s/TEARDOWN_BUDGET=15s, sorted rows, offline --selftest. Honest limitation: docs/backend-parity.md:140-200 'Kernel-matrix teardown status (TJ-DF-037)' states dev host is one kernel not a proof, Debian 13.7/6.12.107 unshare FAIL stays UNVERIFIED external cell (raw output not attached), third kernel UNMEASURED, 'Matrix verdict: NOT GREEN'; live summary confirms matrix_green=false with 1 complete kernel (need >=3). No fabrication: harness executes only on its own host, --import parses external evidence without remote execution, validate_row rejects malformed rows and UNAVAILABLE/UNMEASURED can never become PASS. Regression coverage: tests/test_kernel_matrix_teardown.py (458 lines, tracked) — `.venv/bin/python -m pytest tests/test_kernel_matrix_teardown.py -v` → '47 passed in 1.32s' (exit 0), including live subprocess tests and selftest non-vacuity; --selftest printed 'SELFTEST PASS: valid control accepted; 18 malformed arms rejected; UNAVAILABLE-with-numbers rejected' (exit 0). Manual-gate instructions at docs/backend-parity.md:159-190 give exact live-cell and external capture/import commands.


## Summary

Judge Result: TJ-DF-037

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ Implement a deterministic committed harness that runs both unshare and bwrap orphan-teardown cells, reports kernel/backend/verdict/survival/exit code, documents the measured limitation honestly, and adds regression coverage or manual-gate instructions without fabricating unavailable kernels.: scripts/kernel-matrix-teardown.py (592 lines, tracked in git, commit e39ba82) runs both cells: main() iterates BACKENDS=('bwrap','unshare') calling run_backend_cell(). Live run `.venv/bin/python scripts/kernel-matrix-teardown.py --json` (exit 0) emitted two rows with kernel='7.0.0-31-generic', backend bwrap+unshare, verdict PASS, survival_seconds ~0.0202, exit_code -9, captured, evidence; human mode prints kernel/backend/verdict/survival/exit/captured table. Deterministic: bounded LAUNCH_WAIT=10s/TEARDOWN_BUDGET=15s, sorted rows, offline --selftest. Honest limitation: docs/backend-parity.md:140-200 'Kernel-matrix teardown status (TJ-DF-037)' states dev host is one kernel not a proof, Debian 13.7/6.12.107 unshare FAIL stays UNVERIFIED external cell (raw output not attached), third kernel UNMEASURED, 'Matrix verdict: NOT GREEN'; live summary confirms matrix_green=false with 1 complete kernel (need >=3). No fabrication: harness executes only on its own host, --import parses external evidence without remote execution, validate_row rejects malformed rows and UNAVAILABLE/UNMEASURED can never become PASS. Regression coverage: tests/test_kernel_matrix_teardown.py (458 lines, tracked) — `.venv/bin/python -m pytest tests/test_kernel_matrix_teardown.py -v` → '47 passed in 1.32s' (exit 0), including live subprocess tests and selftest non-vacuity; --selftest printed 'SELFTEST PASS: valid control accepted; 18 malformed arms rejected; UNAVAILABLE-with-numbers rejected' (exit 0). Manual-gate instructions at docs/backend-parity.md:159-190 give exact live-cell and external capture/import commands.


Overall: PASS ✓
