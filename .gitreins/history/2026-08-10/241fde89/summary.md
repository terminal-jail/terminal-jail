# Verdict: tj-df-006

**Task:** Fix pip editable install to expose terminal_jail as top-level package (TJ-DF-006)
**Evaluated:** 2026-08-10T18:29:47.073607
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m1:28PM[0m [32mINF[0m [1mscanned ~7358992 bytes (7.36 MB) in 914ms[0m
[90m1:28PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ Fresh venv: python3 -m venv /tmp/x && /tmp/x/bin/pip install -q -e /home/kara/terminal-jail && /tmp/x/bin/python -c 'import terminal_jail' succeeds: pip install -q -e exit 0; /tmp/x/bin/python -c 'import terminal_jail' → OK at /home/kara/terminal-jail/plugin/terminal_jail/__init__.py (pyproject.toml where=['plugin'], include=['terminal_jail*'])
  ✓ /tmp/x/bin/python -c 'import terminal_jail.seccomp' and 'import terminal_jail.interruptor_bridge' succeed from the installed env: Both imports succeeded from /tmp/x installed env (seccomp.py and interruptor_bridge.py exist under plugin/terminal_jail/)
  ✓ Fast CI-runnable smoke test asserts the packaging contract (tomllib config check) and fails if config is reverted: plugin/test_packaging.py parses pyproject.toml via tomllib, asserts packages.find.where==['plugin'] and include contains 'terminal_jail*'; 4 passed in 0.02s; verified FAILS (AssertionError where=['.']) when config reverted to where=['.']/include=['plugin*']
  ✓ Full suite green (pytest -q: 274 passed, 4 skipped) and gitreins guard 4/4: pytest -q → 274 passed, 4 skipped in 6.08s; all 4 guards pass: secrets clean, ruff lint pass, tests pass, LSP static_analysis 0 diagnostics
pip editable install now exposes terminal_jail as top-level package; all 4 criteria verified via fresh-venv install, imports, tomllib smoke test (fails on revert), and full suite 274 passed/4 skipped with 4/4 guards green.

## Summary

Judge Result: tj-df-006

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m1:28PM[0m [32mINF[0m [1mscanned ~7358992 bytes (7.36 MB) in 914ms[0m
[90m1:28PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ Fresh venv: python3 -m venv /tmp/x && /tmp/x/bin/pip install -q -e /home/kara/terminal-jail && /tmp/x/bin/python -c 'import terminal_jail' succeeds: pip install -q -e exit 0; /tmp/x/bin/python -c 'import terminal_jail' → OK at /home/kara/terminal-jail/plugin/terminal_jail/__init__.py (pyproject.toml where=['plugin'], include=['terminal_jail*'])
  ✓ /tmp/x/bin/python -c 'import terminal_jail.seccomp' and 'import terminal_jail.interruptor_bridge' succeed from the installed env: Both imports succeeded from /tmp/x installed env (seccomp.py and interruptor_bridge.py exist under plugin/terminal_jail/)
  ✓ Fast CI-runnable smoke test asserts the packaging contract (tomllib config check) and fails if config is reverted: plugin/test_packaging.py parses pyproject.toml via tomllib, asserts packages.find.where==['plugin'] and include contains 'terminal_jail*'; 4 passed in 0.02s; verified FAILS (AssertionError where=['.']) when config reverted to where=['.']/include=['plugin*']
  ✓ Full suite green (pytest -q: 274 passed, 4 skipped) and gitreins guard 4/4: pytest -q → 274 passed, 4 skipped in 6.08s; all 4 guards pass: secrets clean, ruff lint pass, tests pass, LSP static_analysis 0 diagnostics
pip editable install now exposes terminal_jail as top-level package; all 4 criteria verified via fresh-venv install, imports, tomllib smoke test (fails on revert), and full suite 274 passed/4 skipped with 4/4 guards green.

Overall: PASS ✓
