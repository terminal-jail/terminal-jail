# Verdict: QA-TJ20-CIGUARD

**Task:** Fix env-dependent test failures (QA-TERMINAL-JAIL-20)
**Evaluated:** 2026-10-14T12:50:05.576821
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ tests/test_composed_mode.py byte-identical refusal test is deterministic across host classes (tier warnings pinned off or normalized, with a comment); plugin/test_install.py rc=0 assertion is environment-guarded with a grep-able skip marker and a proven skip branch; full repo pytest suite passes; uvx ruff check clean; CHANGELOG entry under [Unreleased]: All sub-requirements verified. (1) tests/test_composed_mode.py:156-186 test_explicit_unshare_pin_refusal_byte_identical pins TERMINAL_JAIL_LANDLOCK=0 and TERMINAL_JAIL_LANDLOCK_NET=0 in extra_env with a 15-line explanatory docstring; the seam is real — landlock.py:1118 _degrade() and landlock_net.py:603 _degrade() both `return ""` when the knob is explicitly falsy. Ran `.venv/bin/python -m pytest tests/test_composed_mode.py -q` => '14 passed, 3 skipped in 15.80s'. (2) plugin/test_install.py:928-934 defines grep-able HOST_DENIED_USERNS_SKIP marker 'HOST-DENIED-USERNS: ...'; line 1015-1016 guards the rc=0 assertion with `if not _mapped_launch_creatable(): pytest.skip(...)`; the skip branch is PROVEN by TestMappedLaunchGuardSelfCheck::test_skip_arm_fires_when_probe_reports_denial which monkeypatches the probe to deny, runs the real test body, and asserts pytest.raises(pytest.skip.Exception) containing 'HOST-DENIED-USERNS' — ran it: '2 passed in 1.17s RC=0'. Ran `.venv/bin/python -m pytest plugin/test_install.py -q` => '90 passed in 41.22s RC=0'. (3) Full repo suite `.venv/bin/python -m pytest -q` => '1956 passed, 11 skipped in 165.63s RC=0'. (4) `uvx ruff check .` => 'All checks passed!' exit 0. (5) CHANGELOG.md line 23 has the '**Tests (QA-TERMINAL-JAIL-20):**' entry under '## [Unreleased]' (line 1, before '## [1.3.0]' at line 57) with reproduction evidence (CI run 38540785800). [resolution 0.10; tests/test_composed_mode.py, plugin/test_install.py]
All five sub-requirements of the single criterion are satisfied: the byte-identical refusal test pins both Landlock tiers off with a comment, the rc=0 assertion is guarded by a grep-able HOST-DENIED-USERNS marker with a proven skip branch, the full suite passes (1956 passed/11 skipped), ruff is clean, and the CHANGELOG entry sits under [Unreleased].

## Summary

Judge Result: QA-TJ20-CIGUARD

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ tests/test_composed_mode.py byte-identical refusal test is deterministic across host classes (tier warnings pinned off or normalized, with a comment); plugin/test_install.py rc=0 assertion is environment-guarded with a grep-able skip marker and a proven skip branch; full repo pytest suite passes; uvx ruff check clean; CHANGELOG entry under [Unreleased]: All sub-requirements verified. (1) tests/test_composed_mode.py:156-186 test_explicit_unshare_pin_refusal_byte_identical pins TERMINAL_JAIL_LANDLOCK=0 and TERMINAL_JAIL_LANDLOCK_NET=0 in extra_env with a 15-line explanatory docstring; the seam is real — landlock.py:1118 _degrade() and landlock_net.py:603 _degrade() both `return ""` when the knob is explicitly falsy. Ran `.venv/bin/python -m pytest tests/test_composed_mode.py -q` => '14 passed, 3 skipped in 15.80s'. (2) plugin/test_install.py:928-934 defines grep-able HOST_DENIED_USERNS_SKIP marker 'HOST-DENIED-USERNS: ...'; line 1015-1016 guards the rc=0 assertion with `if not _mapped_launch_creatable(): pytest.skip(...)`; the skip branch is PROVEN by TestMappedLaunchGuardSelfCheck::test_skip_arm_fires_when_probe_reports_denial which monkeypatches the probe to deny, runs the real test body, and asserts pytest.raises(pytest.skip.Exception) containing 'HOST-DENIED-USERNS' — ran it: '2 passed in 1.17s RC=0'. Ran `.venv/bin/python -m pytest plugin/test_install.py -q` => '90 passed in 41.22s RC=0'. (3) Full repo suite `.venv/bin/python -m pytest -q` => '1956 passed, 11 skipped in 165.63s RC=0'. (4) `uvx ruff check .` => 'All checks passed!' exit 0. (5) CHANGELOG.md line 23 has the '**Tests (QA-TERMINAL-JAIL-20):**' entry under '## [Unreleased]' (line 1, before '## [1.3.0]' at line 57) with reproduction evidence (CI run 38540785800). [resolution 0.10; tests/test_composed_mode.py, plugin/test_install.py]
All five sub-requirements of the single criterion are satisfied: the byte-identical refusal test pins both Landlock tiers off with a comment, the rc=0 assertion is guarded by a grep-able HOST-DENIED-USERNS marker with a proven skip branch, the full suite passes (1956 passed/11 skipped), ruff is clean, and the CHANGELOG entry sits under [Unreleased].

Overall: PASS ✓
