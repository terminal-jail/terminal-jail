# Verdict: TJ-DF-020

**Task:** seccomp glibc-routed variant syscalls
**Evaluated:** 2026-09-23T12:21:45.421810
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ clock_adjtime NR 305 is in the x86_64 deny list, BPF fall-through skips repaired so all deny NRs take effect, and a libc-wrapper regression test asserts EPERM for adjtimex under the filter: All three sub-requirements verified. (1) NR 305 in x86_64 deny list: plugin/terminal_jail/seccomp.py _DENY_EXTRA['x86_64'] contains `305,  # clock_adjtime — glibc routes adjtimex() here (TJ-DF-020)`; runtime check `305 in deny_set_for_arch('x86_64')` -> True. (2) BPF fall-through repaired: git diff HEAD~1 shows `jf = 1 if remaining else 0` replaced by `jf=0` in _build_filter (plugin/terminal_jail/seccomp.py:331-345). Independent BPF interpreter simulation of the built program: all 18 deny NRs return SECCOMP_RET_ERRNO|EPERM, getpid(39)->ALLOW, wrong-arch->KILL. Red-proof by re-installing the old buggy jf=1 logic: bypassed NRs = [159,164,167,174,176,246,249,305,320] (305 bypassed) — confirming the fix makes all deny NRs take effect. (3) libc-wrapper regression test: plugin/test_seccomp.py:547 TestGlibcVariantNrs::test_libc_adjtimex_returns_eperm_under_filter installs the filter via try_apply() in a subprocess and calls libc.adjtimex(), asserting 'errno=1'. Live reproduction of the exact probe: rc=0, stdout='errno=1'. Test run: `.venv/bin/python -m pytest plugin/test_seccomp.py -q` -> 47 passed, 3 skipped (skips are PT-004a/b/c requiring CAP_SYS_ADMIN, unrelated); GlibcVariantNrs subset -> 6 passed. No LSP diagnostics.
NR 305 added to the x86_64 deny list, the BPF jf fall-through skip repaired (red-proofed: buggy version bypassed 305 and 8 other NRs), and the libc-wrapper adjtimex EPERM regression test passes live.

## Summary

Judge Result: TJ-DF-020

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ clock_adjtime NR 305 is in the x86_64 deny list, BPF fall-through skips repaired so all deny NRs take effect, and a libc-wrapper regression test asserts EPERM for adjtimex under the filter: All three sub-requirements verified. (1) NR 305 in x86_64 deny list: plugin/terminal_jail/seccomp.py _DENY_EXTRA['x86_64'] contains `305,  # clock_adjtime — glibc routes adjtimex() here (TJ-DF-020)`; runtime check `305 in deny_set_for_arch('x86_64')` -> True. (2) BPF fall-through repaired: git diff HEAD~1 shows `jf = 1 if remaining else 0` replaced by `jf=0` in _build_filter (plugin/terminal_jail/seccomp.py:331-345). Independent BPF interpreter simulation of the built program: all 18 deny NRs return SECCOMP_RET_ERRNO|EPERM, getpid(39)->ALLOW, wrong-arch->KILL. Red-proof by re-installing the old buggy jf=1 logic: bypassed NRs = [159,164,167,174,176,246,249,305,320] (305 bypassed) — confirming the fix makes all deny NRs take effect. (3) libc-wrapper regression test: plugin/test_seccomp.py:547 TestGlibcVariantNrs::test_libc_adjtimex_returns_eperm_under_filter installs the filter via try_apply() in a subprocess and calls libc.adjtimex(), asserting 'errno=1'. Live reproduction of the exact probe: rc=0, stdout='errno=1'. Test run: `.venv/bin/python -m pytest plugin/test_seccomp.py -q` -> 47 passed, 3 skipped (skips are PT-004a/b/c requiring CAP_SYS_ADMIN, unrelated); GlibcVariantNrs subset -> 6 passed. No LSP diagnostics.
NR 305 added to the x86_64 deny list, the BPF jf fall-through skip repaired (red-proofed: buggy version bypassed 305 and 8 other NRs), and the libc-wrapper adjtimex EPERM regression test passes live.

Overall: PASS ✓
