# Verdict: tj-gap-023

**Task:** install.sh release path gated behind explicit opt-in (TJ-GAP-023)
**Evaluated:** 2026-08-10T00:49:12.160634
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:47PM[0m [32mINF[0m [1mscanned ~7817231 bytes (7.82 MB) in 1.35s[0m
[90m7:47PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✗ **tier2**
  - INCOMPLETE
  ✓ install.sh refuses release mode without TERMINAL_JAIL_USE_RELEASE=1: absolute-path invocation (curl | sh equivalent) exits 1 with a message pointing at ./install.sh from a checkout: install.sh gate (lines ~55-65) exits 1 with 'Supported install: run ./install.sh from a repository checkout' when LOCAL_WRAPPER empty and flag != 1; test_release_mode_requires_opt_in (plugin/test_install.py:375) verifies absolute-path invocation exits 1 with 'release mode is not enabled'
  ✓ TERMINAL_JAIL_USE_RELEASE=1 restores release-mode behavior (download + sha256 verify + atomic install): install.sh else branch does download() + check_sha256() + atomic mv to install dir; release-mode tests (test_successful_install, test_checksum_fail, etc.) set TERMINAL_JAIL_USE_RELEASE=1 and pass (16 install tests pass)
  ✗ README.md and docs/quickstart.md document the opt-in flag and no longer imply bare TERMINAL_JAIL_BASE_URL enables release mode: README.md (lines 160-165) documents TERMINAL_JAIL_USE_RELEASE=1 opt-in, but docs/quickstart.md does NOT document the flag — grep for USE_RELEASE/BASE_URL in quickstart returns nothing (only line 37 'From source (recommended until release assets are published)'). Criterion requires BOTH files to document the flag.
  ✓ plugin/test_install.py covers the gate (release without flag fails) and all release-mode tests pass with the flag set: test_release_mode_requires_opt_in (plugin/test_install.py:375) covers the gate; all release-mode tests set TERMINAL_JAIL_USE_RELEASE=1 and pass; plugin/test_install.py: 16 passed
  ✓ Full suite green: .venv/bin/python -m pytest -q passes, ruff clean, gitreins guard 4/4 PASS: .venv/bin/python -m pytest -q => 239 passed, 6 skipped; ruff check plugin/ standalone/ => All checks passed; gitreins guard => Tier 1 Guards PASS (secrets, lint, tests, static_analysis) 4/4
  ✓ Commit includes Co-authored-by trailer and addresses TJ-GAP-023: Commit 9af0b7e 'fix: installed binary fails closed without bridge; release mode opt-in (TJ-GAP-021, TJ-GAP-023)' includes 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' and addresses TJ-GAP-023
All criteria pass except criterion 3: README.md documents the TERMINAL_JAIL_USE_RELEASE opt-in flag but docs/quickstart.md does not document it, so the task is incomplete.

## Summary

Judge Result: tj-gap-023

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:47PM[0m [32mINF[0m [1mscanned ~7817231 bytes (7.82 MB) in 1.35s[0m
[90m7:47PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: FAIL
  INCOMPLETE
  ✓ install.sh refuses release mode without TERMINAL_JAIL_USE_RELEASE=1: absolute-path invocation (curl | sh equivalent) exits 1 with a message pointing at ./install.sh from a checkout: install.sh gate (lines ~55-65) exits 1 with 'Supported install: run ./install.sh from a repository checkout' when LOCAL_WRAPPER empty and flag != 1; test_release_mode_requires_opt_in (plugin/test_install.py:375) verifies absolute-path invocation exits 1 with 'release mode is not enabled'
  ✓ TERMINAL_JAIL_USE_RELEASE=1 restores release-mode behavior (download + sha256 verify + atomic install): install.sh else branch does download() + check_sha256() + atomic mv to install dir; release-mode tests (test_successful_install, test_checksum_fail, etc.) set TERMINAL_JAIL_USE_RELEASE=1 and pass (16 install tests pass)
  ✗ README.md and docs/quickstart.md document the opt-in flag and no longer imply bare TERMINAL_JAIL_BASE_URL enables release mode: README.md (lines 160-165) documents TERMINAL_JAIL_USE_RELEASE=1 opt-in, but docs/quickstart.md does NOT document the flag — grep for USE_RELEASE/BASE_URL in quickstart returns nothing (only line 37 'From source (recommended until release assets are published)'). Criterion requires BOTH files to document the flag.
  ✓ plugin/test_install.py covers the gate (release without flag fails) and all release-mode tests pass with the flag set: test_release_mode_requires_opt_in (plugin/test_install.py:375) covers the gate; all release-mode tests set TERMINAL_JAIL_USE_RELEASE=1 and pass; plugin/test_install.py: 16 passed
  ✓ Full suite green: .venv/bin/python -m pytest -q passes, ruff clean, gitreins guard 4/4 PASS: .venv/bin/python -m pytest -q => 239 passed, 6 skipped; ruff check plugin/ standalone/ => All checks passed; gitreins guard => Tier 1 Guards PASS (secrets, lint, tests, static_analysis) 4/4
  ✓ Commit includes Co-authored-by trailer and addresses TJ-GAP-023: Commit 9af0b7e 'fix: installed binary fails closed without bridge; release mode opt-in (TJ-GAP-021, TJ-GAP-023)' includes 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' and addresses TJ-GAP-023
All criteria pass except criterion 3: README.md documents the TERMINAL_JAIL_USE_RELEASE opt-in flag but docs/quickstart.md does not document it, so the task is incomplete.

Overall: FAIL ✗
