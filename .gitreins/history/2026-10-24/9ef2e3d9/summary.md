# Verdict: REVIEW-TJ-013

**Task:** Single-line default for fs-isolation degraded warning
**Evaluated:** 2026-10-24T01:37:17.386604
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_backend_selection.py::test_auto_uses_bwrap_for_user_when_mapping_unavailable [firs
- ✗ **tier2**
  - INCOMPLETE
  ✓ 1. ./standalone/terminal-jail true 2>&1 | wc -l < 10.: Ran `./standalone/terminal-jail true 2>&1 | wc -l` in /home/kara/terminal-jail => output `2`, which is < 10. The two lines are the verdict JSON line and `terminal-jail: proc_view=private (bwrap backend: fresh procfs via --proc /proc)`. [resolution 0.17; plugin/test_standalone_cli.py]
  ✗ 2. TERMINAL_JAIL_VERBOSE_WARN=1 ./standalone/terminal-jail true 2>&1 | wc -l >= 10.: Ran `TERMINAL_JAIL_VERBOSE_WARN=1 ./standalone/terminal-jail true 2>&1 | wc -l` => output `2`, NOT >= 10. The verbose branch at standalone/terminal-jail:658-672 is never reached in bare mode on this host because the fs-isolation warning is not emitted at all (bwrap backend is used, so `_tj_fs_isolation_warning` at line 790 is not called). Only when `--user` is passed does the degraded path fire: `TERMINAL_JAIL_VERBOSE_WARN=1 ./standalone/terminal-jail --user true 2>&1 | wc -l` => 13. The criterion's literal command therefore fails.
  ✓ 3. grep -c TERMINAL_JAIL_VERBOSE_WARN standalone/terminal-jail >= 1.: `grep -c TERMINAL_JAIL_VERBOSE_WARN standalone/terminal-jail` => `4` (>= 1). Occurrences at lines 340 (default assignment), 341 (export), 658 (verbose branch test), 673 (default one-line message).
  ✓ 4. pytest plugin/test_standalone_cli.py passes.: Ran `.venv/bin/python -m pytest plugin/test_standalone_cli.py -q` from repo root /home/kara/terminal-jail => `23 passed in 9.82s`, exit_code 0. The relevant test `test_fs_isolation_warning_verbosity` (plugin/test_standalone_cli.py:217-234) passes, but only because it invokes the CLI with `--user` (which does trigger the degraded path) and it contains a `pytest.skip("HOST-NOT-DEGRADED-FSISO...")` guard at line 229.
  ✓ 5. ruff check exits 0.: Ran `.venv/bin/python -m ruff check` => `All checks passed!`, exit_code 0.
The verbose-warning code and tests exist and pass, but criterion 2 fails: the criterion's literal command without `--user` emits only 2 lines in verbose mode (needs >= 10), since the degraded fs-isolation warning never fires in bare mode on this host.

## Summary

Judge Result: REVIEW-TJ-013

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_backend_selection.py::test_auto_uses_bwrap_for_user_when_mapping_unavailable [firs

Stage tier2: FAIL
  INCOMPLETE
  ✓ 1. ./standalone/terminal-jail true 2>&1 | wc -l < 10.: Ran `./standalone/terminal-jail true 2>&1 | wc -l` in /home/kara/terminal-jail => output `2`, which is < 10. The two lines are the verdict JSON line and `terminal-jail: proc_view=private (bwrap backend: fresh procfs via --proc /proc)`. [resolution 0.17; plugin/test_standalone_cli.py]
  ✗ 2. TERMINAL_JAIL_VERBOSE_WARN=1 ./standalone/terminal-jail true 2>&1 | wc -l >= 10.: Ran `TERMINAL_JAIL_VERBOSE_WARN=1 ./standalone/terminal-jail true 2>&1 | wc -l` => output `2`, NOT >= 10. The verbose branch at standalone/terminal-jail:658-672 is never reached in bare mode on this host because the fs-isolation warning is not emitted at all (bwrap backend is used, so `_tj_fs_isolation_warning` at line 790 is not called). Only when `--user` is passed does the degraded path fire: `TERMINAL_JAIL_VERBOSE_WARN=1 ./standalone/terminal-jail --user true 2>&1 | wc -l` => 13. The criterion's literal command therefore fails.
  ✓ 3. grep -c TERMINAL_JAIL_VERBOSE_WARN standalone/terminal-jail >= 1.: `grep -c TERMINAL_JAIL_VERBOSE_WARN standalone/terminal-jail` => `4` (>= 1). Occurrences at lines 340 (default assignment), 341 (export), 658 (verbose branch test), 673 (default one-line message).
  ✓ 4. pytest plugin/test_standalone_cli.py passes.: Ran `.venv/bin/python -m pytest plugin/test_standalone_cli.py -q` from repo root /home/kara/terminal-jail => `23 passed in 9.82s`, exit_code 0. The relevant test `test_fs_isolation_warning_verbosity` (plugin/test_standalone_cli.py:217-234) passes, but only because it invokes the CLI with `--user` (which does trigger the degraded path) and it contains a `pytest.skip("HOST-NOT-DEGRADED-FSISO...")` guard at line 229.
  ✓ 5. ruff check exits 0.: Ran `.venv/bin/python -m ruff check` => `All checks passed!`, exit_code 0.
The verbose-warning code and tests exist and pass, but criterion 2 fails: the criterion's literal command without `--user` emits only 2 lines in verbose mode (needs >= 10), since the degraded fs-isolation warning never fires in bare mode on this host.

Overall: FAIL ✗
