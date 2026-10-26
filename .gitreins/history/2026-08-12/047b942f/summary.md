# Verdict: e2e-001-gap-06

**Task:** Fix builtin-kill-all bypass: block every kill syntax targeting pid -1 (E2E-001-GAP-06)
**Evaluated:** 2026-08-12T02:25:06.660745
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m9:24PM[0m [32mINF[0m [1mscanned ~6899589 bytes (6.90 MB) in 509ms[0m
[90m9:24PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ intercept('kill -- -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call (action=block, rule_id=builtin-kill-all) and test_interruptor.py:43
  ✓ intercept('kill -9 -- -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:42
  ✓ intercept('kill -TERM -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:44
  ✓ intercept('kill -s TERM -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:45
  ✓ intercept('kill -n 9 -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:46
  ✓ intercept('kill 123 -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:47
  ✓ intercept('kill -9 123 -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:48
  ✓ intercept('kill -1 123') does not block (benign SIGHUP to single pid): Verified via direct intercept() call (action=allow) and test_interruptor.py:107
  ✓ intercept('kill -9 123') does not block: Verified via direct intercept() call (action=allow) and test_interruptor.py:109
  ✓ plugin/terminal_jail/rules/00-builtins.yaml builtin-kill-all pattern equals the Python blocklist.py pattern for the same rule: Verified via yaml.safe_load comparison — both patterns identical: '(?<![A-Za-z0-9])kill\s+(?:-s\s+\S+\s+|-n\s+\S+\s+|--\s+|-(?!l)\S+\s+|\d+\s+)+(?<!-s\s)(?<!-n\s)(?<!\S)-1(?:\s|;|\||&|\)|`|$)'
  ✓ .venv/bin/python -m pytest -q passes with at least 280 passed: 285 passed, 4 skipped in 4.29s (>= 280)
All 11 criteria verified: the builtin-kill-all pattern blocks all 7 mass-kill pid -1 syntaxes, allows benign single-pid kills, YAML/Python patterns match exactly, and the full suite passes 285 tests.

## Summary

Judge Result: e2e-001-gap-06

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m9:24PM[0m [32mINF[0m [1mscanned ~6899589 bytes (6.90 MB) in 509ms[0m
[90m9:24PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ intercept('kill -- -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call (action=block, rule_id=builtin-kill-all) and test_interruptor.py:43
  ✓ intercept('kill -9 -- -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:42
  ✓ intercept('kill -TERM -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:44
  ✓ intercept('kill -s TERM -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:45
  ✓ intercept('kill -n 9 -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:46
  ✓ intercept('kill 123 -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:47
  ✓ intercept('kill -9 123 -1') returns action=block with rule_id=builtin-kill-all: Verified via direct intercept() call and test_interruptor.py:48
  ✓ intercept('kill -1 123') does not block (benign SIGHUP to single pid): Verified via direct intercept() call (action=allow) and test_interruptor.py:107
  ✓ intercept('kill -9 123') does not block: Verified via direct intercept() call (action=allow) and test_interruptor.py:109
  ✓ plugin/terminal_jail/rules/00-builtins.yaml builtin-kill-all pattern equals the Python blocklist.py pattern for the same rule: Verified via yaml.safe_load comparison — both patterns identical: '(?<![A-Za-z0-9])kill\s+(?:-s\s+\S+\s+|-n\s+\S+\s+|--\s+|-(?!l)\S+\s+|\d+\s+)+(?<!-s\s)(?<!-n\s)(?<!\S)-1(?:\s|;|\||&|\)|`|$)'
  ✓ .venv/bin/python -m pytest -q passes with at least 280 passed: 285 passed, 4 skipped in 4.29s (>= 280)
All 11 criteria verified: the builtin-kill-all pattern blocks all 7 mass-kill pid -1 syntaxes, allows benign single-pid kills, YAML/Python patterns match exactly, and the full suite passes 285 tests.

Overall: PASS ✓
