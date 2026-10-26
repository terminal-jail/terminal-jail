# Verdict: tj-gap-023

**Task:** install.sh release path gated behind explicit opt-in (TJ-GAP-023)
**Evaluated:** 2026-08-10T00:50:57.140202
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:49PM[0m [32mINF[0m [1mscanned ~7817231 bytes (7.82 MB) in 894ms[0m
[90m7:49PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh refuses release mode without TERMINAL_JAIL_USE_RELEASE=1: absolute-path invocation (curl | sh equivalent) exits 1 with a message pointing at ./install.sh from a checkout: install.sh gate (lines ~55-65) exits 1 with 'Supported install: run ./install.sh from a repository checkout' when LOCAL_WRAPPER empty and flag != 1; test_release_mode_requires_opt_in (plugin/test_install.py:375) uses absolute-path invocation and asserts rc=1 + 'release mode is not enabled'
  ✓ TERMINAL_JAIL_USE_RELEASE=1 restores release-mode behavior (download + sha256 verify + atomic install): install.sh else branch does download() + check_sha256() + atomic mv; test_successful_install sets TERMINAL_JAIL_USE_RELEASE=1 and asserts 'checksum OK' + 'installed to' + binary exists/executable; test_checksum_fail verifies checksum verification FAILED
  ✓ README.md and docs/quickstart.md document the opt-in flag and no longer imply bare TERMINAL_JAIL_BASE_URL enables release mode: README.md lines 160-165 document TERMINAL_JAIL_USE_RELEASE=1 opt-in (changed in commit 5971f7f from bare BASE_URL); docs/quickstart.md lines 43-46 document the flag (added in commit 775edba); both no longer imply bare BASE_URL enables release mode
  ✓ plugin/test_install.py covers the gate (release without flag fails) and all release-mode tests pass with the flag set: test_release_mode_requires_opt_in (plugin/test_install.py:375) covers the gate; all release-mode tests (test_successful_install, test_checksum_fail, test_bad_shebang_rejected, test_creates_install_dir, test_tmp_files_cleaned_after_install, test_no_downloader, test_no_checksum_tool) set TERMINAL_JAIL_USE_RELEASE=1; plugin/test_install.py: 16 passed
  ✓ Full suite green: .venv/bin/python -m pytest -q passes, ruff clean, gitreins guard 4/4 PASS: .venv/bin/python -m pytest -q => 239 passed, 6 skipped; ruff check plugin/ standalone/ => All checks passed; gitreins guard => Tier 1 Guards PASS (secrets, lint, tests, static_analysis) 4/4
  ✓ Commit includes Co-authored-by trailer and addresses TJ-GAP-023: Commit 9af0b7e 'fix: installed binary fails closed without bridge; release mode opt-in (TJ-GAP-021, TJ-GAP-023)' includes 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' and addresses TJ-GAP-023; commit 775edba also includes the Co-authored-by trailer
All 6 criteria for TJ-GAP-023 are satisfied: install.sh gates release mode behind TERMINAL_JAIL_USE_RELEASE=1, docs document the opt-in, tests cover the gate and release mode, full suite is green with gitreins guard 4/4 PASS, and commits include the Co-authored-by trailer.

## Summary

Judge Result: tj-gap-023

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:49PM[0m [32mINF[0m [1mscanned ~7817231 bytes (7.82 MB) in 894ms[0m
[90m7:49PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ install.sh refuses release mode without TERMINAL_JAIL_USE_RELEASE=1: absolute-path invocation (curl | sh equivalent) exits 1 with a message pointing at ./install.sh from a checkout: install.sh gate (lines ~55-65) exits 1 with 'Supported install: run ./install.sh from a repository checkout' when LOCAL_WRAPPER empty and flag != 1; test_release_mode_requires_opt_in (plugin/test_install.py:375) uses absolute-path invocation and asserts rc=1 + 'release mode is not enabled'
  ✓ TERMINAL_JAIL_USE_RELEASE=1 restores release-mode behavior (download + sha256 verify + atomic install): install.sh else branch does download() + check_sha256() + atomic mv; test_successful_install sets TERMINAL_JAIL_USE_RELEASE=1 and asserts 'checksum OK' + 'installed to' + binary exists/executable; test_checksum_fail verifies checksum verification FAILED
  ✓ README.md and docs/quickstart.md document the opt-in flag and no longer imply bare TERMINAL_JAIL_BASE_URL enables release mode: README.md lines 160-165 document TERMINAL_JAIL_USE_RELEASE=1 opt-in (changed in commit 5971f7f from bare BASE_URL); docs/quickstart.md lines 43-46 document the flag (added in commit 775edba); both no longer imply bare BASE_URL enables release mode
  ✓ plugin/test_install.py covers the gate (release without flag fails) and all release-mode tests pass with the flag set: test_release_mode_requires_opt_in (plugin/test_install.py:375) covers the gate; all release-mode tests (test_successful_install, test_checksum_fail, test_bad_shebang_rejected, test_creates_install_dir, test_tmp_files_cleaned_after_install, test_no_downloader, test_no_checksum_tool) set TERMINAL_JAIL_USE_RELEASE=1; plugin/test_install.py: 16 passed
  ✓ Full suite green: .venv/bin/python -m pytest -q passes, ruff clean, gitreins guard 4/4 PASS: .venv/bin/python -m pytest -q => 239 passed, 6 skipped; ruff check plugin/ standalone/ => All checks passed; gitreins guard => Tier 1 Guards PASS (secrets, lint, tests, static_analysis) 4/4
  ✓ Commit includes Co-authored-by trailer and addresses TJ-GAP-023: Commit 9af0b7e 'fix: installed binary fails closed without bridge; release mode opt-in (TJ-GAP-021, TJ-GAP-023)' includes 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' and addresses TJ-GAP-023; commit 775edba also includes the Co-authored-by trailer
All 6 criteria for TJ-GAP-023 are satisfied: install.sh gates release mode behind TERMINAL_JAIL_USE_RELEASE=1, docs document the opt-in, tests cover the gate and release mode, full suite is green with gitreins guard 4/4 PASS, and commits include the Co-authored-by trailer.

Overall: PASS ✓
