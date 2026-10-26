# Verdict: INT-CI-007

**Task:** Fix CI matrix failure: test env helpers inherit CI=true from GitHub Actions, causing --no-path auto-skip of PATH setup
**Evaluated:** 2026-10-16T20:22:19.671239
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ 1. The fix (ccd6097) clears CI and SUDO_USER in _install_env, _env, and _home_env test helpers, matching _baseline_env_without_ci_sudo.: git show ccd6097 adds "CI": "" and "SUDO_USER": "" to all three helpers: _install_env at plugin/test_install.py:1871-1875, _env at plugin/test_uninstall.py:33-36, _home_env at plugin/test_uninstall.py:49-52. _baseline_env_without_ci_sudo at plugin/test_install.py:2737-2749 does env=_install_env(tmp_path); env["CI"]=""; env["SUDO_USER"]="" — identical semantics (empty == unset). Pre-fix grep of ccd6097^:plugin/test_install.py confirms no "CI" key existed in _install_env.
  ✓ 2. 10 previously-failing tests now pass: test_default_install_keeps_classic_path_behavior, test_custom_install_dir_appends_despite_stale_default_block, test_tmp_prefix_skips_path_block, test_ci_env_skips_path_block, test_sudo_user_skips_path_block, test_custom_install_dir_path_entry_points_at_actual_dir, test_custom_install_dir_path_entry_is_idempotent, test_uninstall_still_removes_marked_block, test_uninstall_leaves_zero_terminal_jail_files, test_uninstall_custom_scope_removes_every_target, test_uninstall_then_reinstall_round_trip.: Ran the exact CI condition: `CI=true SUDO_USER=root .venv/bin/python -m pytest -p no:cacheprovider --tb=short -q <11 node ids>` => exit_code 0, output `...........  [100%]` / `11 passed in 7.88s`. All 11 tests exist: test_install.py:2602,2632,2652,2677,2802,2847,2877,2920 and test_uninstall.py:109,196,273 (test_uninstall_still_removes_marked_block lives in test_install.py:2920).
  ✓ 3. Guard full: PASS 4/4 (secrets clean, lint ok, tests full pass, static_analysis skipped).: .gitreins/logs/guard-20261016T193959.046456Z.log (run_utc 2026-10-16T19:39:59Z, after ccd6097 at 19:33:12Z): `test_mode: full`, `test_targets: all (whole tree)`, `overall: PASS (DEGRADED — skipped checks)`, `guards: 4 (0 failed, 1 skipped)`. [PASS] secrets (gitleaks: clean); [PASS] lint exit_code=0 (ruff: clean, 90 tracked files); [PASS] tests exit_code=0 (`1992 passed, 11 skipped in 209.09s`); [SKIP] static_analysis (skip_reason: no packaging marker).
  ✓ 4. Push verified: origin/main parity 0 ahead.: `git fetch origin` then `git rev-list --left-right --count origin/main...HEAD` => `0	0` (0 ahead, 0 behind). origin/main and HEAD both resolve to 34b2bf0; `git merge-base --is-ancestor ccd6097 origin/main` => YES.
All four criteria verified: ccd6097 clears CI/SUDO_USER in the three test env helpers matching _baseline_env_without_ci_sudo, all 11 named tests pass under CI=true/SUDO_USER=root, the full guard run is PASS 4/4, and origin/main parity is 0 ahead.

## Summary

Judge Result: INT-CI-007

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ 1. The fix (ccd6097) clears CI and SUDO_USER in _install_env, _env, and _home_env test helpers, matching _baseline_env_without_ci_sudo.: git show ccd6097 adds "CI": "" and "SUDO_USER": "" to all three helpers: _install_env at plugin/test_install.py:1871-1875, _env at plugin/test_uninstall.py:33-36, _home_env at plugin/test_uninstall.py:49-52. _baseline_env_without_ci_sudo at plugin/test_install.py:2737-2749 does env=_install_env(tmp_path); env["CI"]=""; env["SUDO_USER"]="" — identical semantics (empty == unset). Pre-fix grep of ccd6097^:plugin/test_install.py confirms no "CI" key existed in _install_env.
  ✓ 2. 10 previously-failing tests now pass: test_default_install_keeps_classic_path_behavior, test_custom_install_dir_appends_despite_stale_default_block, test_tmp_prefix_skips_path_block, test_ci_env_skips_path_block, test_sudo_user_skips_path_block, test_custom_install_dir_path_entry_points_at_actual_dir, test_custom_install_dir_path_entry_is_idempotent, test_uninstall_still_removes_marked_block, test_uninstall_leaves_zero_terminal_jail_files, test_uninstall_custom_scope_removes_every_target, test_uninstall_then_reinstall_round_trip.: Ran the exact CI condition: `CI=true SUDO_USER=root .venv/bin/python -m pytest -p no:cacheprovider --tb=short -q <11 node ids>` => exit_code 0, output `...........  [100%]` / `11 passed in 7.88s`. All 11 tests exist: test_install.py:2602,2632,2652,2677,2802,2847,2877,2920 and test_uninstall.py:109,196,273 (test_uninstall_still_removes_marked_block lives in test_install.py:2920).
  ✓ 3. Guard full: PASS 4/4 (secrets clean, lint ok, tests full pass, static_analysis skipped).: .gitreins/logs/guard-20261016T193959.046456Z.log (run_utc 2026-10-16T19:39:59Z, after ccd6097 at 19:33:12Z): `test_mode: full`, `test_targets: all (whole tree)`, `overall: PASS (DEGRADED — skipped checks)`, `guards: 4 (0 failed, 1 skipped)`. [PASS] secrets (gitleaks: clean); [PASS] lint exit_code=0 (ruff: clean, 90 tracked files); [PASS] tests exit_code=0 (`1992 passed, 11 skipped in 209.09s`); [SKIP] static_analysis (skip_reason: no packaging marker).
  ✓ 4. Push verified: origin/main parity 0 ahead.: `git fetch origin` then `git rev-list --left-right --count origin/main...HEAD` => `0	0` (0 ahead, 0 behind). origin/main and HEAD both resolve to 34b2bf0; `git merge-base --is-ancestor ccd6097 origin/main` => YES.
All four criteria verified: ccd6097 clears CI/SUDO_USER in the three test env helpers matching _baseline_env_without_ci_sudo, all 11 named tests pass under CI=true/SUDO_USER=root, the full guard run is PASS 4/4, and origin/main parity is 0 ahead.

Overall: PASS ✓
