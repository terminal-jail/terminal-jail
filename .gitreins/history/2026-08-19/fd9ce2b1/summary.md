# Verdict: TJ-DF-011

**Task:** P0 chmod recursive world-writable bypass
**Evaluated:** 2026-08-19T22:35:55.362979
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m5:34PM[0m [32mINF[0m [1mscanned ~9433190 bytes (9.43 MB) in 833ms[0m
[90m5:34PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ Bridge blocks all 5 variants: chmod -R 777 /, chmod --recursive 777 /, chmod a+rwx /, chmod 7777 /, chmod -R 777 /etc under rule builtin-chmod-777-root: Verified via bridge JSON stdin protocol: all 5 variants return action=block rule=builtin-chmod-777-root. Pattern at blocklist.py:139. Direct intercept() also confirms.
  ✓ 00-builtins.yaml chmod pattern stays byte-identical to blocklist.py: Programmatic comparison: PY pattern == YAML pattern == '\bchmod\s+(?=[^|;&]*(?<!\S)(?:7777|777|a\+rwx)\b)(?=[^|;&]*(?<!\S)(?:-[a-z]*r[a-z]*|--recursive)\b)?[^|;&]*\s+/' -> BYTE-IDENTICAL: True. blocklist.py:139 vs 00-builtins.yaml:106.
  ✓ Regression tests cover the 5 variants plus allow controls: test_interruptor.py:66-70 covers all 5 variants in test_blocked; lines 124-127 cover allow controls (chmod 755 /, chmod -R 644 /etc, chmod 777 ./relative) in test_safe_commands; line 761 covers quoted recursive form. Full suite: 301 passed, 4 skipped (pytest -x --tb=short).
All 3 criteria verified: bridge blocks all 5 chmod world-writable variants under builtin-chmod-777-root, the YAML pattern is byte-identical to blocklist.py, and regression tests cover the variants plus allow controls with a passing suite.

## Summary

Judge Result: TJ-DF-011

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m5:34PM[0m [32mINF[0m [1mscanned ~9433190 bytes (9.43 MB) in 833ms[0m
[90m5:34PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ Bridge blocks all 5 variants: chmod -R 777 /, chmod --recursive 777 /, chmod a+rwx /, chmod 7777 /, chmod -R 777 /etc under rule builtin-chmod-777-root: Verified via bridge JSON stdin protocol: all 5 variants return action=block rule=builtin-chmod-777-root. Pattern at blocklist.py:139. Direct intercept() also confirms.
  ✓ 00-builtins.yaml chmod pattern stays byte-identical to blocklist.py: Programmatic comparison: PY pattern == YAML pattern == '\bchmod\s+(?=[^|;&]*(?<!\S)(?:7777|777|a\+rwx)\b)(?=[^|;&]*(?<!\S)(?:-[a-z]*r[a-z]*|--recursive)\b)?[^|;&]*\s+/' -> BYTE-IDENTICAL: True. blocklist.py:139 vs 00-builtins.yaml:106.
  ✓ Regression tests cover the 5 variants plus allow controls: test_interruptor.py:66-70 covers all 5 variants in test_blocked; lines 124-127 cover allow controls (chmod 755 /, chmod -R 644 /etc, chmod 777 ./relative) in test_safe_commands; line 761 covers quoted recursive form. Full suite: 301 passed, 4 skipped (pytest -x --tb=short).
All 3 criteria verified: bridge blocks all 5 chmod world-writable variants under builtin-chmod-777-root, the YAML pattern is byte-identical to blocklist.py, and regression tests cover the variants plus allow controls with a passing suite.

Overall: PASS ✓
