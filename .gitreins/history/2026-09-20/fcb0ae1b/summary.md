# Verdict: TJ-GAP-068

**Task:** AGENTS.md guard invocation falsely FAILs the tests lane (gitreins venv pytest shadows the repo interpreter)
**Evaluated:** 2026-09-20T17:38:08.272963
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ AGENTS.md's GitReins section documents plain gitreins guard via the pipx shim with NO PATH prefix naming the gitreins-poc venv, and explicitly warns that putting that venv on PATH makes the tests lane falsely FAIL (its Python 3.10 pytest shadows the repo interpreter and dies on import tomllib on Python 3.11+): AGENTS.md:27-43 'GitReins Quality Harness' section shows the bare invocation ```bash\ngitreins guard\n``` with no PATH prefix. AGENTS.md:31-35 states: '`gitreins` resolves through the pipx shim (`~/.local/bin/gitreins`). Do NOT put `$HOME/gitreins-poc/.venv/bin` on PATH for this: that venv is Python 3.10, and its `pytest` shadows the repo interpreter — the tests lane then dies at collection on `import tomllib` (3.11+) and falsely FAILs on a clean tree (observed 2026-09-19, guard log guard-20260919T005837).' Confirmed the shim exists: /home/kara/.local/bin/gitreins -> /home/kara/.local/share/pipx/venvs/gitreins/bin/gitreins.
  ✓ The section documents that the tests lane is interpreter-pinned via .gitreins/config.yaml test_command (.venv/bin/python -m pytest -x --tb=short), independent of PATH ordering: AGENTS.md:36-38 states: 'The tests lane is interpreter-pinned in `.gitreins/config.yaml` (`test_command: .venv/bin/python -m pytest -x --tb=short`), so it is independent of PATH ordering.' Cross-checked .gitreins/config.yaml guards block: `test_command: .venv/bin/python -m pytest -x --tb=short` with the PINNED INTERPRETER (tick #289) comment explaining the 3.10/tomllib shadowing.
  ✓ A bare gitreins guard --full in the repo root runs green (all four lanes) under the fixed invocation: Ran bare `gitreins guard --full` from /home/kara/terminal-jail (no PATH prefix). Fresh guard log .gitreins/logs/guard-20260920T173524.338353Z.log (run_utc 2026-09-20T17:35:24Z) reports: `overall: PASS`, `guards: 4 (0 failed, 0 skipped)`, `test_mode: full`. All four lanes green: `[PASS] secrets passed=true`, `[PASS] lint passed=true exit_code=0` (ruff clean, 51 tracked files), `[PASS] tests (full) passed=true exit_code=0` — '1214 passed, 7 skipped in 34.18s' under 'platform linux -- Python 3.11.15, pytest-9.1.1' (repo interpreter, not the 3.10 gitreins venv), `[PASS] static_analysis passed=true`. Note: guard output is written to .gitreins/logs/guard-*.log, not stdout.
AGENTS.md documents the bare pipx-shim `gitreins guard` invocation with an explicit warning against the gitreins-poc 3.10 venv on PATH, documents the interpreter-pinned test_command, and a fresh bare `gitreins guard --full` run in the repo root is green across all four lanes (1214 passed under Python 3.11.15).

## Summary

Judge Result: TJ-GAP-068

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ AGENTS.md's GitReins section documents plain gitreins guard via the pipx shim with NO PATH prefix naming the gitreins-poc venv, and explicitly warns that putting that venv on PATH makes the tests lane falsely FAIL (its Python 3.10 pytest shadows the repo interpreter and dies on import tomllib on Python 3.11+): AGENTS.md:27-43 'GitReins Quality Harness' section shows the bare invocation ```bash\ngitreins guard\n``` with no PATH prefix. AGENTS.md:31-35 states: '`gitreins` resolves through the pipx shim (`~/.local/bin/gitreins`). Do NOT put `$HOME/gitreins-poc/.venv/bin` on PATH for this: that venv is Python 3.10, and its `pytest` shadows the repo interpreter — the tests lane then dies at collection on `import tomllib` (3.11+) and falsely FAILs on a clean tree (observed 2026-09-19, guard log guard-20260919T005837).' Confirmed the shim exists: /home/kara/.local/bin/gitreins -> /home/kara/.local/share/pipx/venvs/gitreins/bin/gitreins.
  ✓ The section documents that the tests lane is interpreter-pinned via .gitreins/config.yaml test_command (.venv/bin/python -m pytest -x --tb=short), independent of PATH ordering: AGENTS.md:36-38 states: 'The tests lane is interpreter-pinned in `.gitreins/config.yaml` (`test_command: .venv/bin/python -m pytest -x --tb=short`), so it is independent of PATH ordering.' Cross-checked .gitreins/config.yaml guards block: `test_command: .venv/bin/python -m pytest -x --tb=short` with the PINNED INTERPRETER (tick #289) comment explaining the 3.10/tomllib shadowing.
  ✓ A bare gitreins guard --full in the repo root runs green (all four lanes) under the fixed invocation: Ran bare `gitreins guard --full` from /home/kara/terminal-jail (no PATH prefix). Fresh guard log .gitreins/logs/guard-20260920T173524.338353Z.log (run_utc 2026-09-20T17:35:24Z) reports: `overall: PASS`, `guards: 4 (0 failed, 0 skipped)`, `test_mode: full`. All four lanes green: `[PASS] secrets passed=true`, `[PASS] lint passed=true exit_code=0` (ruff clean, 51 tracked files), `[PASS] tests (full) passed=true exit_code=0` — '1214 passed, 7 skipped in 34.18s' under 'platform linux -- Python 3.11.15, pytest-9.1.1' (repo interpreter, not the 3.10 gitreins venv), `[PASS] static_analysis passed=true`. Note: guard output is written to .gitreins/logs/guard-*.log, not stdout.
AGENTS.md documents the bare pipx-shim `gitreins guard` invocation with an explicit warning against the gitreins-poc 3.10 venv on PATH, documents the interpreter-pinned test_command, and a fresh bare `gitreins guard --full` run in the repo root is green across all four lanes (1214 passed under Python 3.11.15).

Overall: PASS ✓
