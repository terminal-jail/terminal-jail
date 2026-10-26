# Verdict: INT-CI-007

**Task:** Fix CI matrix failure: test env helpers inherit CI=true from GitHub Actions, causing --no-path auto-skip of PATH setup
**Evaluated:** 2026-10-16T21:56:28.657682
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ 1. The fix (ccd6097) clears CI and SUDO_USER in _install_env, _env, and _home_env test helpers, matching _baseline_env_without_ci_sudo.
2. 10 previously-failing tests now pass: test_default_install_keeps_classic_path_behavior, test_custom_install_dir_appends_despite_stale_default_block, test_tmp_prefix_skips_path_block, test_ci_env_skips_path_block, test_sudo_user_skips_path_block, test_custom_install_dir_path_entry_points_at_actual_dir, test_custom_install_dir_path_entry_is_idempotent, test_uninstall_still_removes_marked_block, test_uninstall_leaves_zero_terminal_jail_files, test_uninstall_custom_scope_removes_every_target, test_uninstall_then_reinstall_round_trip.
3. Guard full: PASS 4/4 (secrets clean, lint ok, tests full pass, static_analysis skipped).
4. Push verified: origin/main parity 0 ahead.: PASS: ccd6097 adds "CI": "" and "SUDO_USER": "" to _install_env (plugin/test_install.py:1871-1875), _env (plugin/test_uninstall.py:33-37), _home_env (plugin/test_uninstall.py:49-53). _baseline_env_without_ci_sudo (plugin/test_install.py:2726-2733) does env=_install_env(tmp_path); env["CI"]=""; env["SUDO_USER"]="" — now redundant but consistent. install.sh:1356-1363 confirms SUDO_USER/CI trigger path_block_skip_reason.
Partial verdict — all verified criteria passed

## Summary

Judge Result: INT-CI-007

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ 1. The fix (ccd6097) clears CI and SUDO_USER in _install_env, _env, and _home_env test helpers, matching _baseline_env_without_ci_sudo.
2. 10 previously-failing tests now pass: test_default_install_keeps_classic_path_behavior, test_custom_install_dir_appends_despite_stale_default_block, test_tmp_prefix_skips_path_block, test_ci_env_skips_path_block, test_sudo_user_skips_path_block, test_custom_install_dir_path_entry_points_at_actual_dir, test_custom_install_dir_path_entry_is_idempotent, test_uninstall_still_removes_marked_block, test_uninstall_leaves_zero_terminal_jail_files, test_uninstall_custom_scope_removes_every_target, test_uninstall_then_reinstall_round_trip.
3. Guard full: PASS 4/4 (secrets clean, lint ok, tests full pass, static_analysis skipped).
4. Push verified: origin/main parity 0 ahead.: PASS: ccd6097 adds "CI": "" and "SUDO_USER": "" to _install_env (plugin/test_install.py:1871-1875), _env (plugin/test_uninstall.py:33-37), _home_env (plugin/test_uninstall.py:49-53). _baseline_env_without_ci_sudo (plugin/test_install.py:2726-2733) does env=_install_env(tmp_path); env["CI"]=""; env["SUDO_USER"]="" — now redundant but consistent. install.sh:1356-1363 confirms SUDO_USER/CI trigger path_block_skip_reason.
Partial verdict — all verified criteria passed

Overall: PASS ✓
