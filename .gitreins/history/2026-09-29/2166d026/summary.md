# Verdict: TJ-DF-038

**Task:** Preflight misdiagnoses missing uname as non-Linux
**Evaluated:** 2026-09-29T10:15:42.082999
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ preflight names missing tool, /proc/version fallback, fail-closed exit 2, regression tests green: standalone/terminal-jail:452-467 (commit cd31f7b): L452 captures `uname -s`; L453-463 when empty falls back to /proc/sys/kernel/ostype then /proc/version ('Linux version') and otherwise prints 'terminal-jail: uname not found on PATH; cannot verify platform (install coreutils)' and exits 2 (names the missing tool); L465-467 non-Linux prints 'this CLI requires Linux PID namespaces' and exits 2 (fail-closed). Live: PATH without uname -> 'unshare is required (install util-linux)' rc=2 (no false non-Linux claim); stub uname=Darwin -> 'requires Linux PID namespaces' rc=2. Regression test plugin/test_standalone_cli.py:169-207 test_missing_uname_on_linux_host covers both arms. Fresh runs: `plugin/test_standalone_cli.py` 22 passed in 3.76s; `test_missing_uname_on_linux_host` 1 passed in 0.59s; `test_standalone_cli.py test_install.py test_modify_preflight.py` 94 passed in 20.20s (exit 0).
Preflight now names a missing uname, falls back to /proc/version, fails closed with exit 2, and the added regression test plus the standalone-CLI/install/modify-preflight suites are green.

## Summary

Judge Result: TJ-DF-038

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ preflight names missing tool, /proc/version fallback, fail-closed exit 2, regression tests green: standalone/terminal-jail:452-467 (commit cd31f7b): L452 captures `uname -s`; L453-463 when empty falls back to /proc/sys/kernel/ostype then /proc/version ('Linux version') and otherwise prints 'terminal-jail: uname not found on PATH; cannot verify platform (install coreutils)' and exits 2 (names the missing tool); L465-467 non-Linux prints 'this CLI requires Linux PID namespaces' and exits 2 (fail-closed). Live: PATH without uname -> 'unshare is required (install util-linux)' rc=2 (no false non-Linux claim); stub uname=Darwin -> 'requires Linux PID namespaces' rc=2. Regression test plugin/test_standalone_cli.py:169-207 test_missing_uname_on_linux_host covers both arms. Fresh runs: `plugin/test_standalone_cli.py` 22 passed in 3.76s; `test_missing_uname_on_linux_host` 1 passed in 0.59s; `test_standalone_cli.py test_install.py test_modify_preflight.py` 94 passed in 20.20s (exit 0).
Preflight now names a missing uname, falls back to /proc/version, fails closed with exit 2, and the added regression test plus the standalone-CLI/install/modify-preflight suites are green.

Overall: PASS ✓
