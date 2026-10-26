# Verdict: TJ-GAP-069

**Task:** rules-drift-probe reports silent same-id mirror downgrades
**Evaluated:** 2026-09-20T15:08:17.104975
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ classifier probe prints DRIFT rows (id, engine vs host action, files); --fail-on-drift exits non-zero; unit tests for drift + clean; docs updated: scripts/rules-drift-probe.py:139-146 emits `DRIFT: <id>: engine action=<a> installed action=<b> (<direction>)` plus both file paths (shipped mirror + installed copy). Live run with a downgraded tmp user dir printed 'DRIFT: builtin-kill-all: engine action=block installed action=sandbox (weaker)' + shipped mirror path + installed copy path + 'RESULT: drift=1'. Exit codes live: bare run on drift rc=0; `--fail-on-drift` on drift rc=1; `--fail-on-drift` clean/absent dirs rc=0 with 'OK: no installed override ... RESULT: drift=0'. Tests: plugin/test_rules_drift_probe.py (17 cases) covers drift (row content, bare rc 0, --fail-on-drift rc 1, stronger-direction) and clean (absent/empty dirs, full-parity mirror drift=0, --fail-on-drift rc 0) plus not-drift scopes; `.venv/bin/python -m pytest plugin/test_rules_drift_probe.py -q -p no:cacheprovider` -> '17 passed in 0.87s', EXIT=0; full suite `.venv/bin/python -m pytest -x --tb=short` -> '1102 passed, 7 skipped in 44.86s' (no failures). LSP diagnostics: 0. Docs: README.md:288-291, specs/cli.md:400-401, docs/quickstart.md:66-67, CHANGELOG.md:3-23.
The rules-drift-probe prints DRIFT rows with id/engine-vs-installed actions/both file paths, --fail-on-drift exits 1 on drift and 0 when clean, 17 hermetic drift+clean unit tests pass (full suite 1102 passed), and README/specs/quickstart/CHANGELOG are updated.

## Summary

Judge Result: TJ-GAP-069

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ classifier probe prints DRIFT rows (id, engine vs host action, files); --fail-on-drift exits non-zero; unit tests for drift + clean; docs updated: scripts/rules-drift-probe.py:139-146 emits `DRIFT: <id>: engine action=<a> installed action=<b> (<direction>)` plus both file paths (shipped mirror + installed copy). Live run with a downgraded tmp user dir printed 'DRIFT: builtin-kill-all: engine action=block installed action=sandbox (weaker)' + shipped mirror path + installed copy path + 'RESULT: drift=1'. Exit codes live: bare run on drift rc=0; `--fail-on-drift` on drift rc=1; `--fail-on-drift` clean/absent dirs rc=0 with 'OK: no installed override ... RESULT: drift=0'. Tests: plugin/test_rules_drift_probe.py (17 cases) covers drift (row content, bare rc 0, --fail-on-drift rc 1, stronger-direction) and clean (absent/empty dirs, full-parity mirror drift=0, --fail-on-drift rc 0) plus not-drift scopes; `.venv/bin/python -m pytest plugin/test_rules_drift_probe.py -q -p no:cacheprovider` -> '17 passed in 0.87s', EXIT=0; full suite `.venv/bin/python -m pytest -x --tb=short` -> '1102 passed, 7 skipped in 44.86s' (no failures). LSP diagnostics: 0. Docs: README.md:288-291, specs/cli.md:400-401, docs/quickstart.md:66-67, CHANGELOG.md:3-23.
The rules-drift-probe prints DRIFT rows with id/engine-vs-installed actions/both file paths, --fail-on-drift exits 1 on drift and 0 when clean, 17 hermetic drift+clean unit tests pass (full suite 1102 passed), and README/specs/quickstart/CHANGELOG are updated.

Overall: PASS ✓
