# Verdict: TJ-DF-043

**Task:** Resolve unshare orphan-teardown containment failure (kernel 6.12) or narrow+enforce the backend contract
**Evaluated:** 2026-10-03T01:20:18.416614
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✗ **tier2**
  - INCOMPLETE
  ✗ 1) Root cause named with kernel citation or minimal reproducer for 6.12 unshare teardown failure. 2) EITHER teardown holds across kernel matrix cells with recorded survival times OR guarantee narrowed+enforced: auto refuses backends whose teardown contract cannot hold, documented in README + --help + docs/backend-parity.md. 3) Regression pinned in matrix harness/CI. 4) No weakening of firewall or other containment layers.: Criterion 1 (root cause named w/ kernel citation or minimal reproducer):
- Commit 7018c08 names root cause: util-linux arms --kill-child PR_SET_PDEATHSIG BEFORE -S/-G setgid/setuid; kernel clears pdeath_signal on cred change.
- Citations: man 2 prctl PR_SET_PDEATHSIG; kernel/cred.c commit_creds() task->pdeath_signal=0; kernel/exit.c forget_original_parent; kernel/signal.c kill_ok_by_cred.
- Reproducer: LD_PRELOAD syscall-order shim showed prctl(PDEATHSIG)->setgroups(0)->setgid(65534)->setuid(65534)->exec; measured orphan >5s 2/2 reps on Debian 13.7/kernel 6.12.107 (bunker-las-03).
- Documented in docs/backend-parity.md known-limit (e) line 134; README; CHANGELOG; test docstrings.
=> PASS
Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: TJ-DF-043

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: FAIL
  INCOMPLETE
  ✗ 1) Root cause named with kernel citation or minimal reproducer for 6.12 unshare teardown failure. 2) EITHER teardown holds across kernel matrix cells with recorded survival times OR guarantee narrowed+enforced: auto refuses backends whose teardown contract cannot hold, documented in README + --help + docs/backend-parity.md. 3) Regression pinned in matrix harness/CI. 4) No weakening of firewall or other containment layers.: Criterion 1 (root cause named w/ kernel citation or minimal reproducer):
- Commit 7018c08 names root cause: util-linux arms --kill-child PR_SET_PDEATHSIG BEFORE -S/-G setgid/setuid; kernel clears pdeath_signal on cred change.
- Citations: man 2 prctl PR_SET_PDEATHSIG; kernel/cred.c commit_creds() task->pdeath_signal=0; kernel/exit.c forget_original_parent; kernel/signal.c kill_ok_by_cred.
- Reproducer: LD_PRELOAD syscall-order shim showed prctl(PDEATHSIG)->setgroups(0)->setgid(65534)->setuid(65534)->exec; measured orphan >5s 2/2 reps on Debian 13.7/kernel 6.12.107 (bunker-las-03).
- Documented in docs/backend-parity.md known-limit (e) line 134; README; CHANGELOG; test docstrings.
=> PASS
Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
