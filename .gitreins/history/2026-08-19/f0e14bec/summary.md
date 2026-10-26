# Verdict: TJ-DF-014

**Task:** P3 --user jail inherits host identity env (TJ-DF-014)
**Evaluated:** 2026-08-19T23:02:09.209070
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m6:00PM[0m [32mINF[0m [1mscanned ~9701380 bytes (9.70 MB) in 942ms[0m
[90m6:00PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ standalone/terminal-jail: when --user is active (USE_USER_NS=1) the wrapper exports scrubbed identity env before exec — running ./standalone/terminal-jail --user env shows USER=nobody, LOGNAME=nobody, HOME=/nonexistent: standalone/terminal-jail:296 `export USER=nobody LOGNAME=nobody HOME=/nonexistent` inside `if [ "$USE_USER_NS" -eq 1 ]` block (line 288), before the exec unshare calls. Runtime verified: `./standalone/terminal-jail --user env` grep shows USER=nobody, LOGNAME=nobody, HOME=/nonexistent.
  ✓ Bare mode (no --user) leaves caller identity env untouched — USER/LOGNAME/HOME pass through unchanged: The else branch (USE_USER_NS=0, terminal-jail:298-299) performs no export of USER/LOGNAME/HOME, so caller identity passes through. Runtime bare mode fails on this host (mount-proc requires CAP_SYS_ADMIN) = documented degradation; test_bare_mode_keeps_identity_env handles this via the _host_denied_namespaces guard.
  ✓ plugin/test_standalone_cli.py gains tests asserting the scrub (--user env shows scrubbed values; bare env keeps caller values), following the existing _host_denied_namespaces host-capability guard pattern: plugin/test_standalone_cli.py:237 test_user_jail_scrubs_identity_env asserts USER=nobody/LOGNAME=nobody/HOME=/nonexistent; :253 test_bare_mode_keeps_identity_env asserts USER=tester/HOME=/home/tester pass through. Both use the _host_denied_namespaces guard pattern. Verified: `pytest -k identity_env` = 2 passed.
  ✓ Full suite green: .venv/bin/python -m pytest -q passes with 4 skipped (no new skips); uvx ruff check plugin/ clean; gitreins guard 4/4 PASS: `.venv/bin/python -m pytest -q` = 303 passed, 4 skipped (all 4 pre-existing: test_interruptor_integration:427, test_seccomp:417/438/458 — no new skips). `uvx ruff check plugin/` = All checks passed. LSP diagnostics clean (0 findings), no hardcoded secrets in changed files. Guard 4/4 (secrets/lint/tests/static_analysis) PASS.
  ✓ README.md documents the --user identity-env scrub in the --user section: README.md:27-28 in the --user section: "# --user also scrubs inherited identity env (USER=nobody, LOGNAME=nobody, HOME=/nonexistent) so jailed tools can't read/write the caller's home."
All 5 criteria verified: the --user jail scrubs identity env (USER=nobody/LOGNAME=nobody/HOME=/nonexistent) before exec, bare mode passes env through, tests follow the _host_denied_namespaces guard pattern and pass, full suite green (303 passed/4 skipped, ruff clean, guard 4/4), and README documents the scrub.

## Summary

Judge Result: TJ-DF-014

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m6:00PM[0m [32mINF[0m [1mscanned ~9701380 bytes (9.70 MB) in 942ms[0m
[90m6:00PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ standalone/terminal-jail: when --user is active (USE_USER_NS=1) the wrapper exports scrubbed identity env before exec — running ./standalone/terminal-jail --user env shows USER=nobody, LOGNAME=nobody, HOME=/nonexistent: standalone/terminal-jail:296 `export USER=nobody LOGNAME=nobody HOME=/nonexistent` inside `if [ "$USE_USER_NS" -eq 1 ]` block (line 288), before the exec unshare calls. Runtime verified: `./standalone/terminal-jail --user env` grep shows USER=nobody, LOGNAME=nobody, HOME=/nonexistent.
  ✓ Bare mode (no --user) leaves caller identity env untouched — USER/LOGNAME/HOME pass through unchanged: The else branch (USE_USER_NS=0, terminal-jail:298-299) performs no export of USER/LOGNAME/HOME, so caller identity passes through. Runtime bare mode fails on this host (mount-proc requires CAP_SYS_ADMIN) = documented degradation; test_bare_mode_keeps_identity_env handles this via the _host_denied_namespaces guard.
  ✓ plugin/test_standalone_cli.py gains tests asserting the scrub (--user env shows scrubbed values; bare env keeps caller values), following the existing _host_denied_namespaces host-capability guard pattern: plugin/test_standalone_cli.py:237 test_user_jail_scrubs_identity_env asserts USER=nobody/LOGNAME=nobody/HOME=/nonexistent; :253 test_bare_mode_keeps_identity_env asserts USER=tester/HOME=/home/tester pass through. Both use the _host_denied_namespaces guard pattern. Verified: `pytest -k identity_env` = 2 passed.
  ✓ Full suite green: .venv/bin/python -m pytest -q passes with 4 skipped (no new skips); uvx ruff check plugin/ clean; gitreins guard 4/4 PASS: `.venv/bin/python -m pytest -q` = 303 passed, 4 skipped (all 4 pre-existing: test_interruptor_integration:427, test_seccomp:417/438/458 — no new skips). `uvx ruff check plugin/` = All checks passed. LSP diagnostics clean (0 findings), no hardcoded secrets in changed files. Guard 4/4 (secrets/lint/tests/static_analysis) PASS.
  ✓ README.md documents the --user identity-env scrub in the --user section: README.md:27-28 in the --user section: "# --user also scrubs inherited identity env (USER=nobody, LOGNAME=nobody, HOME=/nonexistent) so jailed tools can't read/write the caller's home."
All 5 criteria verified: the --user jail scrubs identity env (USER=nobody/LOGNAME=nobody/HOME=/nonexistent) before exec, bare mode passes env through, tests follow the _host_denied_namespaces guard pattern and pass, full suite green (303 passed/4 skipped, ruff clean, guard 4/4), and README documents the scrub.

Overall: PASS ✓
