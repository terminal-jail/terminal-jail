# Verdict: REVIEW-TJ-014

**Task:** install.sh PATH append pollution
**Evaluated:** 2026-10-16T12:19:53.293532
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh gains --no-path flag AND skips the PATH block when install dir is under /tmp or when CI/SUDO_USER is set; existing --uninstall path removes the marked block; test covers all three skip conditions; README documents the flag: --no-path flag: install.sh:265 (help text), 381-388 (arg parse; --no-path=* refused with exit 2), 1354-1355 (skip reason '--no-path flag'). Auto-skips in the ordered if/elif chain: SUDO_USER at install.sh:1357, CI (non-empty and != 0/false/no/off) at 1359-1364, /tmp prefix via `case "$TERMINAL_JAIL_INSTALL_DIR" in /tmp/*)` at 1365-1366; the whole PATH block (1372-1430) is wrapped in the else branch so it is skipped entirely. --uninstall removes the marked block: install.sh:855-880 greps '# terminal-jail' + the exact path line and awk-deletes the marker-scoped block. Tests: plugin/test_install.py:2739 (--no-path), 2781 (/tmp prefix), 2822 (CI=true, plus CI=0 falsy control), 2852 (SUDO_USER), 2873 (precedence), 2896 (uninstall still removes marked block). README.md:70 documents --no-path and all three auto-skip conditions. TEST EVIDENCE: `cd /home/kara/terminal-jail && .venv/bin/python -m pytest plugin/test_install.py -k "no_path or tmp_prefix or ci_env or sudo_user or skip_precedence or uninstall_still_removes" -p no:cacheprovider --tb=short -q` -> exit_code 0, output '........ [100%]  8 passed, 90 deselected in 8.57s'. [resolution 0.04; install.sh]
install.sh implements --no-path plus /tmp, CI, and SUDO_USER auto-skips, --uninstall removes the marked block, README documents the flag, and all 8 targeted tests pass (exit 0).

## Summary

Judge Result: REVIEW-TJ-014

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ install.sh gains --no-path flag AND skips the PATH block when install dir is under /tmp or when CI/SUDO_USER is set; existing --uninstall path removes the marked block; test covers all three skip conditions; README documents the flag: --no-path flag: install.sh:265 (help text), 381-388 (arg parse; --no-path=* refused with exit 2), 1354-1355 (skip reason '--no-path flag'). Auto-skips in the ordered if/elif chain: SUDO_USER at install.sh:1357, CI (non-empty and != 0/false/no/off) at 1359-1364, /tmp prefix via `case "$TERMINAL_JAIL_INSTALL_DIR" in /tmp/*)` at 1365-1366; the whole PATH block (1372-1430) is wrapped in the else branch so it is skipped entirely. --uninstall removes the marked block: install.sh:855-880 greps '# terminal-jail' + the exact path line and awk-deletes the marker-scoped block. Tests: plugin/test_install.py:2739 (--no-path), 2781 (/tmp prefix), 2822 (CI=true, plus CI=0 falsy control), 2852 (SUDO_USER), 2873 (precedence), 2896 (uninstall still removes marked block). README.md:70 documents --no-path and all three auto-skip conditions. TEST EVIDENCE: `cd /home/kara/terminal-jail && .venv/bin/python -m pytest plugin/test_install.py -k "no_path or tmp_prefix or ci_env or sudo_user or skip_precedence or uninstall_still_removes" -p no:cacheprovider --tb=short -q` -> exit_code 0, output '........ [100%]  8 passed, 90 deselected in 8.57s'. [resolution 0.04; install.sh]
install.sh implements --no-path plus /tmp, CI, and SUDO_USER auto-skips, --uninstall removes the marked block, README documents the flag, and all 8 targeted tests pass (exit 0).

Overall: PASS ✓
