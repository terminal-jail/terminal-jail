# Verdict: e2e-001-gap-06

**Task:** Fix builtin-kill-all bypass: block every kill syntax targeting pid -1 (E2E-001-GAP-06)
**Evaluated:** 2026-08-12T02:24:08.400854
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m9:23PM[0m [32mINF[0m [1mscanned ~6899589 bytes (6.90 MB) in 481ms[0m
[90m9:23PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ intercept('kill -- -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -- -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -9 -- -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -9 -- -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -TERM -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -TERM -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -s TERM -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -s TERM -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -n 9 -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -n 9 -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill 123 -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill 123 -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -9 123 -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -9 123 -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -1 123') does not block (benign SIGHUP to single pid): Direct test: intercept('kill -1 123') -> action=allow rule_id=None (no block)
  ✓ intercept('kill -9 123') does not block: Direct test: intercept('kill -9 123') -> action=allow rule_id=None (no block)
  ✓ plugin/terminal_jail/rules/00-builtins.yaml builtin-kill-all pattern equals the Python blocklist.py pattern for the same rule: yaml.safe_load parity check: py_pattern == yaml_pattern EQUAL: True for builtin-kill-all
  ✓ .venv/bin/python -m pytest -q passes with at least 280 passed: .venv/bin/python -m pytest -q -> 285 passed, 4 skipped (>=280)
All 11 criteria verified: the new kill-syntax pattern blocks all 7 mass-kill pid -1 vectors, leaves benign single-pid kills allowed, matches between blocklist.py and 00-builtins.yaml, and the full suite passes 285 tests.

## Summary

Judge Result: e2e-001-gap-06

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m9:23PM[0m [32mINF[0m [1mscanned ~6899589 bytes (6.90 MB) in 481ms[0m
[90m9:23PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ intercept('kill -- -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -- -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -9 -- -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -9 -- -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -TERM -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -TERM -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -s TERM -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -s TERM -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -n 9 -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -n 9 -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill 123 -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill 123 -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -9 123 -1') returns action=block with rule_id=builtin-kill-all: Direct test: intercept('kill -9 123 -1') -> action=block rule_id=builtin-kill-all
  ✓ intercept('kill -1 123') does not block (benign SIGHUP to single pid): Direct test: intercept('kill -1 123') -> action=allow rule_id=None (no block)
  ✓ intercept('kill -9 123') does not block: Direct test: intercept('kill -9 123') -> action=allow rule_id=None (no block)
  ✓ plugin/terminal_jail/rules/00-builtins.yaml builtin-kill-all pattern equals the Python blocklist.py pattern for the same rule: yaml.safe_load parity check: py_pattern == yaml_pattern EQUAL: True for builtin-kill-all
  ✓ .venv/bin/python -m pytest -q passes with at least 280 passed: .venv/bin/python -m pytest -q -> 285 passed, 4 skipped (>=280)
All 11 criteria verified: the new kill-syntax pattern blocks all 7 mass-kill pid -1 vectors, leaves benign single-pid kills allowed, matches between blocklist.py and 00-builtins.yaml, and the full suite passes 285 tests.

Overall: PASS ✓
