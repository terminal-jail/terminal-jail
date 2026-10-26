# Verdict: TJ-DF-003

**Task:** P1 seccomp filter unprivileged install (PR_SET_NO_NEW_PRIVS)
**Evaluated:** 2026-08-10T12:52:42.219201
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:51AM[0m [32mINF[0m [1mscanned ~7857674 bytes (7.86 MB) in 941ms[0m
[90m7:51AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ apply_filter() calls prctl(PR_SET_NO_NEW_PRIVS, 1) before prctl(PR_SET_SECCOMP): plugin/terminal_jail/seccomp.py:432 calls prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) before prctl(_PR_SET_SECCOMP, ...) at line 442; constant _PR_SET_NO_NEW_PRIVS=38 defined at line 122
  ✓ unprivileged install verified live: TERMINAL_JAIL_SECCOMP=1 loader probe reports applied=True, /proc/self/status NoNewPrivs=1 Seccomp=2, no running-without-seccomp warning: Live probe with TERMINAL_JAIL_SECCOMP=1 output 'applied=True NoNewPrivs=1 Seccomp=2' with no warning; regression test test_filter_install_sets_no_new_privs_and_seccomp passed asserting same values
  ✓ regression tests in plugin/test_seccomp.py (positive latch probe + negative control) and full suite passes 256/6: TestNoNewPrivsBeforeFilter has positive test_filter_install_sets_no_new_privs_and_seccomp and negative test_negative_control_no_filter_without_try_apply, both PASSED; full suite: '256 passed, 6 skipped'
  ✓ no_new_privs failure raises SeccompPermissionError; existing EPERM/EACCES mapping for filter install unchanged: seccomp.py:436 raises SeccompPermissionError on prctl(PR_SET_NO_NEW_PRIVS) failure; lines 451-452 retain existing errno.EPERM/EACCES -> SeccompPermissionError mapping for PR_SET_SECCOMP
  ✓ scope limited to plugin/terminal_jail/seccomp.py and plugin/test_seccomp.py: git show b4c885e --name-only returns exactly plugin/terminal_jail/seccomp.py and plugin/test_seccomp.py; only other working-tree changes are task metadata (.gitreins/tasks.yaml, board events)
All 5 criteria verified: PR_SET_NO_NEW_PRIVS set before PR_SET_SECCOMP, live probe confirms applied=True/NoNewPrivs=1/Seccomp=2 with no warning, regression tests + full suite pass 256/6, SeccompPermissionError raised on no_new_privs failure with EPERM/EACCES mapping intact, and scope limited to the two specified files.

## Summary

Judge Result: TJ-DF-003

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:51AM[0m [32mINF[0m [1mscanned ~7857674 bytes (7.86 MB) in 941ms[0m
[90m7:51AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ apply_filter() calls prctl(PR_SET_NO_NEW_PRIVS, 1) before prctl(PR_SET_SECCOMP): plugin/terminal_jail/seccomp.py:432 calls prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) before prctl(_PR_SET_SECCOMP, ...) at line 442; constant _PR_SET_NO_NEW_PRIVS=38 defined at line 122
  ✓ unprivileged install verified live: TERMINAL_JAIL_SECCOMP=1 loader probe reports applied=True, /proc/self/status NoNewPrivs=1 Seccomp=2, no running-without-seccomp warning: Live probe with TERMINAL_JAIL_SECCOMP=1 output 'applied=True NoNewPrivs=1 Seccomp=2' with no warning; regression test test_filter_install_sets_no_new_privs_and_seccomp passed asserting same values
  ✓ regression tests in plugin/test_seccomp.py (positive latch probe + negative control) and full suite passes 256/6: TestNoNewPrivsBeforeFilter has positive test_filter_install_sets_no_new_privs_and_seccomp and negative test_negative_control_no_filter_without_try_apply, both PASSED; full suite: '256 passed, 6 skipped'
  ✓ no_new_privs failure raises SeccompPermissionError; existing EPERM/EACCES mapping for filter install unchanged: seccomp.py:436 raises SeccompPermissionError on prctl(PR_SET_NO_NEW_PRIVS) failure; lines 451-452 retain existing errno.EPERM/EACCES -> SeccompPermissionError mapping for PR_SET_SECCOMP
  ✓ scope limited to plugin/terminal_jail/seccomp.py and plugin/test_seccomp.py: git show b4c885e --name-only returns exactly plugin/terminal_jail/seccomp.py and plugin/test_seccomp.py; only other working-tree changes are task metadata (.gitreins/tasks.yaml, board events)
All 5 criteria verified: PR_SET_NO_NEW_PRIVS set before PR_SET_SECCOMP, live probe confirms applied=True/NoNewPrivs=1/Seccomp=2 with no warning, regression tests + full suite pass 256/6, SeccompPermissionError raised on no_new_privs failure with EPERM/EACCES mapping intact, and scope limited to the two specified files.

Overall: PASS ✓
