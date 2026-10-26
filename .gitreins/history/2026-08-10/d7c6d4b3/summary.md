# Verdict: tj-df-008

**Task:** Document that TERMINAL_JAIL_SECCOMP requires --seccomp flag (TJ-DF-008)
**Evaluated:** 2026-08-10T20:48:17.430011
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m3:46PM[0m [32mINF[0m [1mscanned ~7365229 bytes (7.37 MB) in 650ms[0m
[90m3:46PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ README TERMINAL_JAIL_SECCOMP row explicitly states the --seccomp flag is also required: README.md line 154: 'TERMINAL_JAIL_SECCOMP ... only honored when the CLI is also invoked with --seccomp; the env var alone does not activate the filter.'
  ✓ standalone/terminal-jail wrapper script unchanged (git diff HEAD~1 -- standalone/ empty): git diff HEAD~1 -- standalone/ returns 0 lines (empty output); standalone/terminal-jail last modified in prior commit 9af0b7e.
  ✓ Full suite green (pytest -q: 274 passed, 4 skipped) and gitreins guard 4/4: pytest -q -> '274 passed, 4 skipped in 5.01s'; gitreins guard -> 'Tier 1 Guards: PASS' with all 4 guards green (secrets, lint, tests, static_analysis).
All three criteria for TJ-DF-008 are satisfied: README documents the --seccomp requirement, standalone/ wrapper is unchanged, and the full suite plus gitreins guard pass.

## Summary

Judge Result: tj-df-008

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m3:46PM[0m [32mINF[0m [1mscanned ~7365229 bytes (7.37 MB) in 650ms[0m
[90m3:46PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ README TERMINAL_JAIL_SECCOMP row explicitly states the --seccomp flag is also required: README.md line 154: 'TERMINAL_JAIL_SECCOMP ... only honored when the CLI is also invoked with --seccomp; the env var alone does not activate the filter.'
  ✓ standalone/terminal-jail wrapper script unchanged (git diff HEAD~1 -- standalone/ empty): git diff HEAD~1 -- standalone/ returns 0 lines (empty output); standalone/terminal-jail last modified in prior commit 9af0b7e.
  ✓ Full suite green (pytest -q: 274 passed, 4 skipped) and gitreins guard 4/4: pytest -q -> '274 passed, 4 skipped in 5.01s'; gitreins guard -> 'Tier 1 Guards: PASS' with all 4 guards green (secrets, lint, tests, static_analysis).
All three criteria for TJ-DF-008 are satisfied: README documents the --seccomp requirement, standalone/ wrapper is unchanged, and the full suite plus gitreins guard pass.

Overall: PASS ✓
