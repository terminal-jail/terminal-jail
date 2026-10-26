# Verdict: TJ-GAP-065

**Task:** install.sh PATH hint follows actual TERMINAL_JAIL_INSTALL_DIR
**Evaluated:** 2026-09-20T15:03:34.526293
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ custom-prefix install no longer appends hardcoded HOME/.local/bin PATH while claiming configured; default install unchanged; scratch-HOME proof + automated test: install.sh:663-675 (commit 66a68bc) adds a custom-prefix branch that appends `export PATH="${TERMINAL_JAIL_INSTALL_DIR}:$PATH"` via printf (variable expanded at write time) and only prints 'added PATH entry to <file>' after a real write; the hardcoded `$HOME/.local/bin` heredoc is now confined to the default branch (install.sh:643-660), which is byte-identical to the pre-fix behavior. Scratch-HOME proof (manual, real run): `HOME=/tmp/tj065/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj065/bin sh install.sh` -> rc got `export PATH="/tmp/tj065/bin:$PATH"`, binary at /tmp/tj065/bin/terminal-jail, and /tmp/tj065/home/.local/bin/terminal-jail does NOT exist; re-run adds no duplicate (1 marker). Default install proof: `HOME=/tmp/tj065d/home TERMINAL_JAIL_INSTALL_DIR= sh install.sh` -> classic `export PATH="$HOME/.local/bin:$PATH"` in ~/.profile, binary at ~/.local/bin/terminal-jail, rerun prints 0 'added PATH entry' and keeps 1 marker. Already-on-PATH case prints the honest 'is already on PATH' and writes nothing. Automated tests: plugin/test_install.py:1564-1700 (test_custom_install_dir_path_entry_points_at_actual_dir, test_custom_install_dir_path_entry_is_idempotent, test_custom_install_dir_appends_despite_stale_default_block, test_default_install_keeps_classic_path_behavior) -> `.venv/bin/python -m pytest plugin/test_install.py -k 'custom_install_dir or default_install_keeps'` = '4 passed, 50 deselected'. Full suite per .gitreins/config.yaml test_command `.venv/bin/python -m pytest -x --tb=short` -> exit_code 0, '1102 passed, 7 skipped in 28.89s'.
Custom-prefix installs now append a PATH line naming the actual TERMINAL_JAIL_INSTALL_DIR (never the hardcoded $HOME/.local/bin) and only claim success after writing, default installs are unchanged and idempotent, and both scratch-HOME manual runs and 4 new automated tests plus the full 1102-test suite pass.

## Summary

Judge Result: TJ-GAP-065

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ custom-prefix install no longer appends hardcoded HOME/.local/bin PATH while claiming configured; default install unchanged; scratch-HOME proof + automated test: install.sh:663-675 (commit 66a68bc) adds a custom-prefix branch that appends `export PATH="${TERMINAL_JAIL_INSTALL_DIR}:$PATH"` via printf (variable expanded at write time) and only prints 'added PATH entry to <file>' after a real write; the hardcoded `$HOME/.local/bin` heredoc is now confined to the default branch (install.sh:643-660), which is byte-identical to the pre-fix behavior. Scratch-HOME proof (manual, real run): `HOME=/tmp/tj065/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj065/bin sh install.sh` -> rc got `export PATH="/tmp/tj065/bin:$PATH"`, binary at /tmp/tj065/bin/terminal-jail, and /tmp/tj065/home/.local/bin/terminal-jail does NOT exist; re-run adds no duplicate (1 marker). Default install proof: `HOME=/tmp/tj065d/home TERMINAL_JAIL_INSTALL_DIR= sh install.sh` -> classic `export PATH="$HOME/.local/bin:$PATH"` in ~/.profile, binary at ~/.local/bin/terminal-jail, rerun prints 0 'added PATH entry' and keeps 1 marker. Already-on-PATH case prints the honest 'is already on PATH' and writes nothing. Automated tests: plugin/test_install.py:1564-1700 (test_custom_install_dir_path_entry_points_at_actual_dir, test_custom_install_dir_path_entry_is_idempotent, test_custom_install_dir_appends_despite_stale_default_block, test_default_install_keeps_classic_path_behavior) -> `.venv/bin/python -m pytest plugin/test_install.py -k 'custom_install_dir or default_install_keeps'` = '4 passed, 50 deselected'. Full suite per .gitreins/config.yaml test_command `.venv/bin/python -m pytest -x --tb=short` -> exit_code 0, '1102 passed, 7 skipped in 28.89s'.
Custom-prefix installs now append a PATH line naming the actual TERMINAL_JAIL_INSTALL_DIR (never the hardcoded $HOME/.local/bin) and only claim success after writing, default installs are unchanged and idempotent, and both scratch-HOME manual runs and 4 new automated tests plus the full 1102-test suite pass.

Overall: PASS ✓
