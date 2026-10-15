# Verdict: REVIEW-TJ-011

**Task:** Version drift: wrapper self-reports 1.2.0 vs pyproject 1.3.0, plugin.yaml 1.2.0, README 1.2.0-shipped
**Evaluated:** 2026-10-15T14:55:12.623566
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (tests/test_composed_mode.py::TestCompositionBattery::test_live_three_cell_run [first failing i
- ✗ **tier2**
  - INCOMPLETE
  ✗ On HEAD 6e058d8 four artifacts disagreed on shipped version (row REVIEW-TJ-011). Fix required: single version authority = pyproject.toml; wrapper derives at install time; TERMINAL_JAIL_VERSION override preserved; drift-guard test added; no unintended bumps to 1.3.0 shipped narrative (release hold RELEASE-TJ-008 stays). Worker commit 353f176 on wt/REVIEW-TJ-011: standalone/terminal-jail reads pyproject version in checkout, install.sh sed-bakes VERSION_DEFAULT into installed wrapper; plugin.yaml 1.3.0 + tests/test_version.py (3 tests incl override); full worktree suite 1981 passed 11 skipped; foreman re-verified --version=1.3.0, override=9.9.9, no ':-1.2.0' hardcode remains, README narrative untouched.: REVIEW-TJ-011 verification progress:

1. Single version authority = pyproject.toml: PASS
   - pyproject.toml:7 version = "1.3.0"
   - standalone/terminal-jail:97-107 reads ${SCRIPT_DIR}/../pyproject.toml at runtime in checkout
   - install.sh:1152-1171 reads $SCRIPT_DIR/pyproject.toml, sed-bakes into installed wrapper

2. Wrapper derives at install time: PASS
   - install.sh:1177 sed "s/^VERSION_DEFAULT=\"\"$/VERSION_DEFAULT=\"$LOCAL_VERSION\"/"
   - E2E verified: ./install.sh -> "installing v1.3.0", installed wrapper /tmp/tjtest/bin/terminal-jail --version => "terminal-jail 1.3.0", baked line VERSION_DEFAULT="1.3.0"

3. TERMINAL_JAIL_VERSION override preserved: PASS
   - standalone/terminal-jail:109 VERSION="${TERMINAL_JAIL_VERSION:-${VERSION_DEFAULT}}"
   - TERMINAL_JAIL_VERSION=9.9.9 ./standalone/terminal-jail --version => "terminal-jail 9.9.9"
   - baked wrapper override also => 9.9.9

4. Drift-guard test added: PASS
   - tests/test_version.py (3 tests): test_standalone_reports_pyproject_version, test_standalone_version_override_still_works, test_plugin_manifest_version_matches_pyproject
   - .venv/bin/python -m pytest tests/test_version.py -v => 3 passed in 0.07s

5. No unintended bumps to 1.3.0 shipped narrative / README untouched: PASS
   - README.md NOT in git diff 6e058d8..HEAD --name-only
   - README.md:19 still "v1.2.0 is shipped; the v1.3.0 candidate is held per release row RELEASE-TJ-008"

6. plugin.yaml 1.3.0: PASS - plugin/plugin.yaml:2 version: "1.3.0"

7. No ':-1.2.0' hardcode in wrapper: PASS
   - HEAD 6e058d8 standalone/terminal-jail:80 was VERSION="${TERMINAL_JAIL_VERSION:-1.2.0}"
   - HEAD now :109 VERSION="${TERMINAL_JAIL_VERSION:-${VERSION_DEFAULT}}"
   - NOTE: install.sh:13 still has TERMINAL_JAIL_VERSION="${TERMINAL_JAIL_VERSION:-1.2.0}" (release-download default, separate concern)

8. Full suite: RUNNING in background (/tmp/fullsuite.log) - awaiting result

Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: REVIEW-TJ-011

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (tests/test_composed_mode.py::TestCompositionBattery::test_live_three_cell_run [first failing i

Stage tier2: FAIL
  INCOMPLETE
  ✗ On HEAD 6e058d8 four artifacts disagreed on shipped version (row REVIEW-TJ-011). Fix required: single version authority = pyproject.toml; wrapper derives at install time; TERMINAL_JAIL_VERSION override preserved; drift-guard test added; no unintended bumps to 1.3.0 shipped narrative (release hold RELEASE-TJ-008 stays). Worker commit 353f176 on wt/REVIEW-TJ-011: standalone/terminal-jail reads pyproject version in checkout, install.sh sed-bakes VERSION_DEFAULT into installed wrapper; plugin.yaml 1.3.0 + tests/test_version.py (3 tests incl override); full worktree suite 1981 passed 11 skipped; foreman re-verified --version=1.3.0, override=9.9.9, no ':-1.2.0' hardcode remains, README narrative untouched.: REVIEW-TJ-011 verification progress:

1. Single version authority = pyproject.toml: PASS
   - pyproject.toml:7 version = "1.3.0"
   - standalone/terminal-jail:97-107 reads ${SCRIPT_DIR}/../pyproject.toml at runtime in checkout
   - install.sh:1152-1171 reads $SCRIPT_DIR/pyproject.toml, sed-bakes into installed wrapper

2. Wrapper derives at install time: PASS
   - install.sh:1177 sed "s/^VERSION_DEFAULT=\"\"$/VERSION_DEFAULT=\"$LOCAL_VERSION\"/"
   - E2E verified: ./install.sh -> "installing v1.3.0", installed wrapper /tmp/tjtest/bin/terminal-jail --version => "terminal-jail 1.3.0", baked line VERSION_DEFAULT="1.3.0"

3. TERMINAL_JAIL_VERSION override preserved: PASS
   - standalone/terminal-jail:109 VERSION="${TERMINAL_JAIL_VERSION:-${VERSION_DEFAULT}}"
   - TERMINAL_JAIL_VERSION=9.9.9 ./standalone/terminal-jail --version => "terminal-jail 9.9.9"
   - baked wrapper override also => 9.9.9

4. Drift-guard test added: PASS
   - tests/test_version.py (3 tests): test_standalone_reports_pyproject_version, test_standalone_version_override_still_works, test_plugin_manifest_version_matches_pyproject
   - .venv/bin/python -m pytest tests/test_version.py -v => 3 passed in 0.07s

5. No unintended bumps to 1.3.0 shipped narrative / README untouched: PASS
   - README.md NOT in git diff 6e058d8..HEAD --name-only
   - README.md:19 still "v1.2.0 is shipped; the v1.3.0 candidate is held per release row RELEASE-TJ-008"

6. plugin.yaml 1.3.0: PASS - plugin/plugin.yaml:2 version: "1.3.0"

7. No ':-1.2.0' hardcode in wrapper: PASS
   - HEAD 6e058d8 standalone/terminal-jail:80 was VERSION="${TERMINAL_JAIL_VERSION:-1.2.0}"
   - HEAD now :109 VERSION="${TERMINAL_JAIL_VERSION:-${VERSION_DEFAULT}}"
   - NOTE: install.sh:13 still has TERMINAL_JAIL_VERSION="${TERMINAL_JAIL_VERSION:-1.2.0}" (release-download default, separate concern)

8. Full suite: RUNNING in background (/tmp/fullsuite.log) - awaiting result

Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
