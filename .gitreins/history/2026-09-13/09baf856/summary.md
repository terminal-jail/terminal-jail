# Verdict: QA-TERMINAL-JAIL-7

**Task:** Make seccomp negative control container-portable
**Evaluated:** 2026-09-13T18:20:13.638460
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m1:19PM[0m [32mINF[0m [1mscanned ~4573069 bytes (4.57 MB) in 420ms[0m
[90m1:19PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ The no-try_apply negative control passes on a bare host with Seccomp=0 and inside a stock Docker container with inherited Seccomp=2, while still requiring NoNewPrivs=0.: plugin/test_seccomp.py:294 sets ok_expr to "nn == '0' and sc in ('0', '2')" and :344-350 asserts either 'applied=None NoNewPrivs=0 Seccomp=0' or '...Seccomp=2'. Verified empirically: bare host /proc/self/status shows Seccomp=0/NoNewPrivs=0 and test passes; docker run python:3.11-slim shows Seccomp=2/Seccomp_filters=1 inherited and negative control PASSED; docker run python:3.13-slim likewise Seccomp=2 and PASSED. Old assertion would have failed in container (probe printed 'applied=None NoNewPrivs=0 Seccomp=2', OLD assertion would pass: False), confirming the fix is real and necessary.
  ✓ The positive control remains strict: try_apply reports applied=True, NoNewPrivs=1, and Seccomp=2.: plugin/test_seccomp.py:292 keeps ok_expr = "result.applied and nn == '1' and sc == '2'" and :322 asserts "applied=True NoNewPrivs=1 Seccomp=2" in stdout. test_filter_install_sets_no_new_privs_and_seccomp PASSED on host and in both Docker containers (41 passed, 3 skipped each).
  ✓ The change is test-only, documents inherited container-runtime filters accurately, and introduces no production behavior change.: Commit 00b1a09 touches only plugin/test_seccomp.py (1 file, +23/-6); `git diff 6b4d197 00b1a09 -- plugin/terminal_jail/seccomp.py` is empty, so no production change. Docstring at plugin/test_seccomp.py:276-281 accurately states bare host reports Seccomp=0 while container runtimes install their own filter so /proc/self/status reports Seccomp=2 before terminal-jail acts — confirmed by host (Seccomp=0) vs Docker (Seccomp=2, Seccomp_filters=1).
  ✓ The focused seccomp tests, full pytest suite, and ruff check pass; the focused negative control is verified in stock Python 3.11 and 3.13 Docker containers.: Focused: `.venv/bin/python -m pytest plugin/test_seccomp.py -v` -> '41 passed, 3 skipped in 0.38s'. Full suite: `.venv/bin/python -m pytest -x --tb=short` -> '334 passed, 13 skipped in 7.39s'. Ruff: `ruff check .` -> 'All checks passed!' (exit 0). Docker python:3.11-slim (Seccomp=2) -> '41 passed, 3 skipped'; Docker python:3.13-slim (Seccomp=2) -> '41 passed, 3 skipped'.
All four criteria pass: the negative control now accepts the inherited Seccomp=2 container baseline while still requiring NoNewPrivs=0, the positive control stays strict, the change is test-only with accurate docs, and focused/full pytest plus ruff pass on host and in stock Python 3.11/3.13 Docker containers.

## Summary

Judge Result: QA-TERMINAL-JAIL-7

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m1:19PM[0m [32mINF[0m [1mscanned ~4573069 bytes (4.57 MB) in 420ms[0m
[90m1:19PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ The no-try_apply negative control passes on a bare host with Seccomp=0 and inside a stock Docker container with inherited Seccomp=2, while still requiring NoNewPrivs=0.: plugin/test_seccomp.py:294 sets ok_expr to "nn == '0' and sc in ('0', '2')" and :344-350 asserts either 'applied=None NoNewPrivs=0 Seccomp=0' or '...Seccomp=2'. Verified empirically: bare host /proc/self/status shows Seccomp=0/NoNewPrivs=0 and test passes; docker run python:3.11-slim shows Seccomp=2/Seccomp_filters=1 inherited and negative control PASSED; docker run python:3.13-slim likewise Seccomp=2 and PASSED. Old assertion would have failed in container (probe printed 'applied=None NoNewPrivs=0 Seccomp=2', OLD assertion would pass: False), confirming the fix is real and necessary.
  ✓ The positive control remains strict: try_apply reports applied=True, NoNewPrivs=1, and Seccomp=2.: plugin/test_seccomp.py:292 keeps ok_expr = "result.applied and nn == '1' and sc == '2'" and :322 asserts "applied=True NoNewPrivs=1 Seccomp=2" in stdout. test_filter_install_sets_no_new_privs_and_seccomp PASSED on host and in both Docker containers (41 passed, 3 skipped each).
  ✓ The change is test-only, documents inherited container-runtime filters accurately, and introduces no production behavior change.: Commit 00b1a09 touches only plugin/test_seccomp.py (1 file, +23/-6); `git diff 6b4d197 00b1a09 -- plugin/terminal_jail/seccomp.py` is empty, so no production change. Docstring at plugin/test_seccomp.py:276-281 accurately states bare host reports Seccomp=0 while container runtimes install their own filter so /proc/self/status reports Seccomp=2 before terminal-jail acts — confirmed by host (Seccomp=0) vs Docker (Seccomp=2, Seccomp_filters=1).
  ✓ The focused seccomp tests, full pytest suite, and ruff check pass; the focused negative control is verified in stock Python 3.11 and 3.13 Docker containers.: Focused: `.venv/bin/python -m pytest plugin/test_seccomp.py -v` -> '41 passed, 3 skipped in 0.38s'. Full suite: `.venv/bin/python -m pytest -x --tb=short` -> '334 passed, 13 skipped in 7.39s'. Ruff: `ruff check .` -> 'All checks passed!' (exit 0). Docker python:3.11-slim (Seccomp=2) -> '41 passed, 3 skipped'; Docker python:3.13-slim (Seccomp=2) -> '41 passed, 3 skipped'.
All four criteria pass: the negative control now accepts the inherited Seccomp=2 container baseline while still requiring NoNewPrivs=0, the positive control stays strict, the change is test-only with accurate docs, and focused/full pytest plus ruff pass on host and in stock Python 3.11/3.13 Docker containers.

Overall: PASS ✓
