# Verdict: TJ-DF-044

**Task:** Ship landlock-net-loader.py via install.sh and surface the bridge's landlock-net degrade warning
**Evaluated:** 2026-10-13T20:38:37.011625
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (tests/test_release_workflow.py::test_check_script_green_path_on_prepared_scratch_clone [first 
- ✗ **tier2**
  - INCOMPLETE
  ✓ install.sh copies standalone/landlock-net-loader.py into the installed LIB_DIR (same block that copies seccomp-loader.py and landlock-loader.py, install.sh ~1219-1227): PASS: install.sh lines 1229-1233 (post-diff) contain the new block copying standalone/landlock-net-loader.py into $LIB_DIR, immediately after the landlock-loader.py block (1219-1223) and seccomp-loader.py block (1214-1218). Verified via sed -n 1200,1250p install.sh and git show 41cde86.
  ✗ the installed layout ~/.local/lib/terminal-jail/ contains landlock-net-loader.py after a fresh ./install.sh run: Not verified — evaluation terminated before this criterion was checked
  ✗ the wrapper no longer discards the bridge's stderr wholesale: a landlock-net degrade warning emitted by the bridge on stderr reaches the operator's terminal, while the bridge's stdout JSON contract consumed by _interruptor_evaluate stays intact: Not verified — evaluation terminated before this criterion was checked
  ✗ with TERMINAL_JAIL_LANDLOCK_NET=1 and the loader missing, the probe payload's connect() behavior either enforces or the operator sees the loud degrade warning — never silent: Not verified — evaluation terminated before this criterion was checked
  ✗ regression tests cover the install.sh copy list (packaging/install test scope) and pass: .venv/bin/python -m pytest plugin -q: Not verified — evaluation terminated before this criterion was checked
  ✓ uvx ruff check . exits 0: PASS: `uvx ruff check .` -> "All checks passed!" RUFF_EXIT=0
Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: TJ-DF-044

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (tests/test_release_workflow.py::test_check_script_green_path_on_prepared_scratch_clone [first 

Stage tier2: FAIL
  INCOMPLETE
  ✓ install.sh copies standalone/landlock-net-loader.py into the installed LIB_DIR (same block that copies seccomp-loader.py and landlock-loader.py, install.sh ~1219-1227): PASS: install.sh lines 1229-1233 (post-diff) contain the new block copying standalone/landlock-net-loader.py into $LIB_DIR, immediately after the landlock-loader.py block (1219-1223) and seccomp-loader.py block (1214-1218). Verified via sed -n 1200,1250p install.sh and git show 41cde86.
  ✗ the installed layout ~/.local/lib/terminal-jail/ contains landlock-net-loader.py after a fresh ./install.sh run: Not verified — evaluation terminated before this criterion was checked
  ✗ the wrapper no longer discards the bridge's stderr wholesale: a landlock-net degrade warning emitted by the bridge on stderr reaches the operator's terminal, while the bridge's stdout JSON contract consumed by _interruptor_evaluate stays intact: Not verified — evaluation terminated before this criterion was checked
  ✗ with TERMINAL_JAIL_LANDLOCK_NET=1 and the loader missing, the probe payload's connect() behavior either enforces or the operator sees the loud degrade warning — never silent: Not verified — evaluation terminated before this criterion was checked
  ✗ regression tests cover the install.sh copy list (packaging/install test scope) and pass: .venv/bin/python -m pytest plugin -q: Not verified — evaluation terminated before this criterion was checked
  ✓ uvx ruff check . exits 0: PASS: `uvx ruff check .` -> "All checks passed!" RUFF_EXIT=0
Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
