# Verdict: TJ-GAP-038

**Task:** --help seccomp text contradicts README
**Evaluated:** 2026-08-19T05:44:39.817589
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m12:43AM[0m [32mINF[0m [1mscanned ~9672177 bytes (9.67 MB) in 1.13s[0m
[90m12:43AM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ ./standalone/terminal-jail --help seccomp text no longer claims TERMINAL_JAIL_SECCOMP env var controls activation: standalone/terminal-jail:55-59 --help --seccomp text reads 'Filter is active only when this flag is passed; the TERMINAL_JAIL_SECCOMP env var is an internal handoff to the seccomp loader and does not activate the filter.' Verified via `./standalone/terminal-jail --help` output. No longer claims env var controls activation.
  ✗ --help seccomp text agrees verbatim with README env-var table row: Help text (standalone/terminal-jail:55-59) is NOT verbatim with README line 154. README: 'only honored when the CLI is also invoked with `--seccomp`; the env var alone does not activate the filter.' Help: 'Filter is active only when this flag is passed; the TERMINAL_JAIL_SECCOMP env var is an internal handoff to the seccomp loader and does not activate the filter.' Semantically similar but wording differs (help adds 'internal handoff to the seccomp loader', omits README's 'only honored when the CLI is also invoked with --seccomp'). Criterion requires verbatim agreement.
Criterion 1 passes (help no longer claims env var activates filter), but criterion 2 fails because the --help seccomp text does not agree verbatim with the README env-var table row.

## Summary

Judge Result: TJ-GAP-038

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m12:43AM[0m [32mINF[0m [1mscanned ~9672177 bytes (9.67 MB) in 1.13s[0m
[90m12:43AM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ ./standalone/terminal-jail --help seccomp text no longer claims TERMINAL_JAIL_SECCOMP env var controls activation: standalone/terminal-jail:55-59 --help --seccomp text reads 'Filter is active only when this flag is passed; the TERMINAL_JAIL_SECCOMP env var is an internal handoff to the seccomp loader and does not activate the filter.' Verified via `./standalone/terminal-jail --help` output. No longer claims env var controls activation.
  ✗ --help seccomp text agrees verbatim with README env-var table row: Help text (standalone/terminal-jail:55-59) is NOT verbatim with README line 154. README: 'only honored when the CLI is also invoked with `--seccomp`; the env var alone does not activate the filter.' Help: 'Filter is active only when this flag is passed; the TERMINAL_JAIL_SECCOMP env var is an internal handoff to the seccomp loader and does not activate the filter.' Semantically similar but wording differs (help adds 'internal handoff to the seccomp loader', omits README's 'only honored when the CLI is also invoked with --seccomp'). Criterion requires verbatim agreement.
Criterion 1 passes (help no longer claims env var activates filter), but criterion 2 fails because the --help seccomp text does not agree verbatim with the README env-var table row.

Overall: PASS ✓
