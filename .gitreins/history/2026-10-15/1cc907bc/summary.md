# Verdict: INT-CI-006

**Task:** Composed-mode live three-cell run flaky: docker live cell FAILs under pytest then passes with zero code change
**Evaluated:** 2026-10-15T21:08:02.522646
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ the battery's explicit-backend-no-downgrade arm stderr contract passes deterministically on this host: tests/test_composed_mode.py::test_live_three_cell_run passes twice consecutively; composed-mode-battery.py spawns CLI arms with a hermetic env base (_cli_env strips GIT_/PYTEST_/COVERAGE_/BUILD_ namespaces) and the byte-identical arm pins the Landlock tiers like its sibling test; tests/test_composed_mode.py::test_cli_run_child_env_is_hermetic pins the env hygiene; full tests/test_composed_mode.py 15 passed 3 skipped (pre-existing container-conditional skips); uvx ruff check . clean: All sub-claims verified with fresh command output. (1) test_live_three_cell_run passes twice consecutively: run 1 `pytest tests/test_composed_mode.py::TestCompositionBattery::test_live_three_cell_run -p no:cacheprovider` -> '1 passed in 16.14s'; run 2 same command -> '1 passed in 17.87s'. Docker IS on PATH (/home/kara/bin/docker) so the live three-cell run actually executed rather than skipping. (2) Hermetic env base: scripts/composed-mode-battery.py:93 `_CLI_ENV_DROP_PREFIXES = ("GIT_", "PYTEST_", "COVERAGE_", "BUILD_")`; :96-108 `_cli_env()` copies os.environ and deletes every key with those prefixes while retaining PATH/HOME/TERMINAL_JAIL_*; :117 `_cli_run` calls `env = _cli_env()`, layers env_extra, and passes `env=env` to subprocess.run. (3) Byte-identical arm pins Landlock tiers like its sibling: battery :257-258 sets TERMINAL_JAIL_LANDLOCK="0" and TERMINAL_JAIL_LANDLOCK_NET="0" (plus :259 TERMINAL_JAIL_VERDICT_LOG="0") in the explicit-backend-no-downgrade arm, mirroring tests/test_composed_mode.py:167-172 test_explicit_unshare_pin_refusal_byte_identical; the arm asserts rc==2 and stderr == the exact refusal string (battery :266-278). (4) tests/test_composed_mode.py:377-436 test_cli_run_child_env_is_hermetic PASSED in 0.02s, asserting no GIT_/PYTEST_/COVERAGE_/BUILD_ leak, PATH/HOME/TERMINAL_JAIL_COMPOSED preserved, and that _cli_run wires the hermetic base + env_extra to the child. (5) Full file: `pytest tests/test_composed_mode.py -v -p no:cacheprovider` -> '15 passed, 3 skipped in 17.53s' (the 3 skips are the container-conditional TestInsideContainer class, skipif not /.dockerenv). (6) `uvx ruff check .` -> 'All checks passed!' EXIT=0. [resolution 0.30; tests/test_composed_mode.py, composed-mode-battery.py]
All INT-CI-006 sub-claims verified by fresh execution: live three-cell run passed twice consecutively, hermetic _cli_env/_cli_run wiring and Landlock tier pins are present, the env-hygiene test passes, the full file reports 15 passed/3 skipped, and ruff is clean.

## Summary

Judge Result: INT-CI-006

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ the battery's explicit-backend-no-downgrade arm stderr contract passes deterministically on this host: tests/test_composed_mode.py::test_live_three_cell_run passes twice consecutively; composed-mode-battery.py spawns CLI arms with a hermetic env base (_cli_env strips GIT_/PYTEST_/COVERAGE_/BUILD_ namespaces) and the byte-identical arm pins the Landlock tiers like its sibling test; tests/test_composed_mode.py::test_cli_run_child_env_is_hermetic pins the env hygiene; full tests/test_composed_mode.py 15 passed 3 skipped (pre-existing container-conditional skips); uvx ruff check . clean: All sub-claims verified with fresh command output. (1) test_live_three_cell_run passes twice consecutively: run 1 `pytest tests/test_composed_mode.py::TestCompositionBattery::test_live_three_cell_run -p no:cacheprovider` -> '1 passed in 16.14s'; run 2 same command -> '1 passed in 17.87s'. Docker IS on PATH (/home/kara/bin/docker) so the live three-cell run actually executed rather than skipping. (2) Hermetic env base: scripts/composed-mode-battery.py:93 `_CLI_ENV_DROP_PREFIXES = ("GIT_", "PYTEST_", "COVERAGE_", "BUILD_")`; :96-108 `_cli_env()` copies os.environ and deletes every key with those prefixes while retaining PATH/HOME/TERMINAL_JAIL_*; :117 `_cli_run` calls `env = _cli_env()`, layers env_extra, and passes `env=env` to subprocess.run. (3) Byte-identical arm pins Landlock tiers like its sibling: battery :257-258 sets TERMINAL_JAIL_LANDLOCK="0" and TERMINAL_JAIL_LANDLOCK_NET="0" (plus :259 TERMINAL_JAIL_VERDICT_LOG="0") in the explicit-backend-no-downgrade arm, mirroring tests/test_composed_mode.py:167-172 test_explicit_unshare_pin_refusal_byte_identical; the arm asserts rc==2 and stderr == the exact refusal string (battery :266-278). (4) tests/test_composed_mode.py:377-436 test_cli_run_child_env_is_hermetic PASSED in 0.02s, asserting no GIT_/PYTEST_/COVERAGE_/BUILD_ leak, PATH/HOME/TERMINAL_JAIL_COMPOSED preserved, and that _cli_run wires the hermetic base + env_extra to the child. (5) Full file: `pytest tests/test_composed_mode.py -v -p no:cacheprovider` -> '15 passed, 3 skipped in 17.53s' (the 3 skips are the container-conditional TestInsideContainer class, skipif not /.dockerenv). (6) `uvx ruff check .` -> 'All checks passed!' EXIT=0. [resolution 0.30; tests/test_composed_mode.py, composed-mode-battery.py]
All INT-CI-006 sub-claims verified by fresh execution: live three-cell run passed twice consecutively, hermetic _cli_env/_cli_run wiring and Landlock tier pins are present, the env-hygiene test passes, the full file reports 15 passed/3 skipped, and ruff is clean.

Overall: PASS ✓
