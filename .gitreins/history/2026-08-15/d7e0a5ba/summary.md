# Verdict: TJ-GAP-034

**Task:** P2 — README Graceful Degradation exit-code contract violated
**Evaluated:** 2026-08-15T10:08:09.161848
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m5:07AM[0m [32mINF[0m [1mscanned ~9629681 bytes (9.63 MB) in 927ms[0m
[90m5:07AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ grep -q 'namespace creation failed' standalone/terminal-jail: standalone/terminal-jail:296 — 'echo "terminal-jail: namespace creation failed (unshare exit ${probe_rc}); command not run" >&2' in the namespace preflight block
  ✓ grep -q 'test_bare_wrapper_unshare_failure_exits_2' plugin/test_install.py: plugin/test_install.py:614 — 'def test_bare_wrapper_unshare_failure_exits_2(...)' defined
  ✓ grep -q 'exits with code 2' README.md: README.md:206 — '- **CLI**: exits with code 2 and a message if unshare not found, not on Linux, or namespace creation fails.'
All three grep-based criteria for TJ-GAP-034 are satisfied with concrete file:line evidence.

## Summary

Judge Result: TJ-GAP-034

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m5:07AM[0m [32mINF[0m [1mscanned ~9629681 bytes (9.63 MB) in 927ms[0m
[90m5:07AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ grep -q 'namespace creation failed' standalone/terminal-jail: standalone/terminal-jail:296 — 'echo "terminal-jail: namespace creation failed (unshare exit ${probe_rc}); command not run" >&2' in the namespace preflight block
  ✓ grep -q 'test_bare_wrapper_unshare_failure_exits_2' plugin/test_install.py: plugin/test_install.py:614 — 'def test_bare_wrapper_unshare_failure_exits_2(...)' defined
  ✓ grep -q 'exits with code 2' README.md: README.md:206 — '- **CLI**: exits with code 2 and a message if unshare not found, not on Linux, or namespace creation fails.'
All three grep-based criteria for TJ-GAP-034 are satisfied with concrete file:line evidence.

Overall: PASS ✓
