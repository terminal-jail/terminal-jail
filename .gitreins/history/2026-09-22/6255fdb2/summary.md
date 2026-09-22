# Verdict: TJ-GAP-072

**Task:** Installer upgrade prunes stale installed files and caps rules .bak retention
**Evaluated:** 2026-09-22T18:16:07.206606
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh records an install manifest of every file it wrote under LIB_DIR and refreshes that manifest on every re-install: install.sh:725-766: manifest="$plugin_tree/.install-manifest"; new_manifest captured from checkout via `find . -type f | sort`; written unconditionally each run via `printf '%s\n' "$new_manifest" > "${manifest}.tmp"; mv -f "${manifest}.tmp" "$manifest"` (atomic refresh). Manual repro: first install wrote 82-line manifest; after deleting seccomp.py from checkout and re-running, manifest refreshed to 81 lines with seccomp.py absent. Test test_upgrade_prunes_module_deleted_from_checkout PASSED (asserts .install-manifest exists and contains interruptor_bridge.py/seccomp.py).
  ✓ after a module file is deleted from plugin/terminal_jail in the checkout, re-running install.sh removes that stale file from the installed lib tree, proven by a regression test that installs, deletes, re-installs and asserts absence: install.sh:750-760 prunes files in previous_manifest that are absent from new_manifest (guarded against .install-manifest/absolute/.. paths). Regression test plugin/test_install.py:2045 test_upgrade_prunes_module_deleted_from_checkout installs, unlinks checkout/plugin/terminal_jail/seccomp.py, reinstalls, asserts `not victim.exists()` and the stdout prune line, plus user-extra file survives. Ran: `pytest plugin/test_install.py -k upgrade_prunes_module_deleted_from_checkout` -> PASSED. Manual repro printed 'pruned stale installed file: .../seccomp.py' and file was gone.
  ✓ rules backup retention is capped: after repeated installs with differing user rules only the newest 5 .bak-* backups remain, proven by a regression test: install.sh:809-813: `LC_ALL=C ls -1 "$RESOLVED_RULES_DIR"/00-builtins.yaml.bak-* | sort -r | tail -n +6 | while read ...; do rm -f ...` keeps newest 5. Regression test plugin/test_install.py:2099 test_rules_bak_retention_capped does 7 installs over differing rules and asserts len(backups)==5, newest holds edit 6, oldest holds edit 2, exactly 2 prune lines. Ran: `pytest plugin/test_install.py -k rules_bak_retention_capped` -> PASSED. Manual repro: 7 installs -> exactly 5 .bak-* files, 2 'pruned old rules backup' lines.
  ✓ existing behavior preserved: default-dir install, custom-prefix install and --uninstall still pass their existing tests, and the uninstall census still leaves user-authored rules in place: Full suite: `.venv/bin/python -m pytest -q` -> '1397 passed, 7 skipped in 44.66s' (exit 0). Named tests PASSED: test_default_install_dir_keeps_live_rules_target, test_prefix_install_does_not_touch_home_rules, test_default_install_keeps_classic_path_behavior, test_custom_install_dir_path_entry_points_at_actual_dir, test_uninstall_preserves_user_authored_rule_and_lists_it, test_uninstall_leaves_zero_terminal_jail_files. Uninstall census install.sh:557-566 explicitly prints 'left in place (user-authored): <path>' for non-installer files and never deletes them.
All four criteria verified: install manifest written/refreshed, stale-file pruning and 5-backup retention cap both proven by passing regression tests and independent manual reproduction, and the full suite (1397 passed, 7 skipped) confirms existing install/uninstall behavior is preserved.

## Summary

Judge Result: TJ-GAP-072

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ install.sh records an install manifest of every file it wrote under LIB_DIR and refreshes that manifest on every re-install: install.sh:725-766: manifest="$plugin_tree/.install-manifest"; new_manifest captured from checkout via `find . -type f | sort`; written unconditionally each run via `printf '%s\n' "$new_manifest" > "${manifest}.tmp"; mv -f "${manifest}.tmp" "$manifest"` (atomic refresh). Manual repro: first install wrote 82-line manifest; after deleting seccomp.py from checkout and re-running, manifest refreshed to 81 lines with seccomp.py absent. Test test_upgrade_prunes_module_deleted_from_checkout PASSED (asserts .install-manifest exists and contains interruptor_bridge.py/seccomp.py).
  ✓ after a module file is deleted from plugin/terminal_jail in the checkout, re-running install.sh removes that stale file from the installed lib tree, proven by a regression test that installs, deletes, re-installs and asserts absence: install.sh:750-760 prunes files in previous_manifest that are absent from new_manifest (guarded against .install-manifest/absolute/.. paths). Regression test plugin/test_install.py:2045 test_upgrade_prunes_module_deleted_from_checkout installs, unlinks checkout/plugin/terminal_jail/seccomp.py, reinstalls, asserts `not victim.exists()` and the stdout prune line, plus user-extra file survives. Ran: `pytest plugin/test_install.py -k upgrade_prunes_module_deleted_from_checkout` -> PASSED. Manual repro printed 'pruned stale installed file: .../seccomp.py' and file was gone.
  ✓ rules backup retention is capped: after repeated installs with differing user rules only the newest 5 .bak-* backups remain, proven by a regression test: install.sh:809-813: `LC_ALL=C ls -1 "$RESOLVED_RULES_DIR"/00-builtins.yaml.bak-* | sort -r | tail -n +6 | while read ...; do rm -f ...` keeps newest 5. Regression test plugin/test_install.py:2099 test_rules_bak_retention_capped does 7 installs over differing rules and asserts len(backups)==5, newest holds edit 6, oldest holds edit 2, exactly 2 prune lines. Ran: `pytest plugin/test_install.py -k rules_bak_retention_capped` -> PASSED. Manual repro: 7 installs -> exactly 5 .bak-* files, 2 'pruned old rules backup' lines.
  ✓ existing behavior preserved: default-dir install, custom-prefix install and --uninstall still pass their existing tests, and the uninstall census still leaves user-authored rules in place: Full suite: `.venv/bin/python -m pytest -q` -> '1397 passed, 7 skipped in 44.66s' (exit 0). Named tests PASSED: test_default_install_dir_keeps_live_rules_target, test_prefix_install_does_not_touch_home_rules, test_default_install_keeps_classic_path_behavior, test_custom_install_dir_path_entry_points_at_actual_dir, test_uninstall_preserves_user_authored_rule_and_lists_it, test_uninstall_leaves_zero_terminal_jail_files. Uninstall census install.sh:557-566 explicitly prints 'left in place (user-authored): <path>' for non-installer files and never deletes them.
All four criteria verified: install manifest written/refreshed, stale-file pruning and 5-backup retention cap both proven by passing regression tests and independent manual reproduction, and the full suite (1397 passed, 7 skipped) confirms existing install/uninstall behavior is preserved.

Overall: PASS ✓
