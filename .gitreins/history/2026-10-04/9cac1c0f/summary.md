# Verdict: RELTOOL-1791152794779715762

**Task:** Release tooling: tag-triggered release workflow (artifact channel gate 1/RELEASE-TJ-008)
**Evaluated:** 2026-10-04T23:47:40.374899
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE
  ✗ On tag push v*: workflow builds sdist+wheel (python -m build), generates artifacts with sha256sums, creates a GitHub Release with categorized notes via gh; does NOT auto-bump pyproject; includes a workflow lint/act-style validation or a documented dry-run proof; CI remains green on the pushed SHA.: Most sub-requirements are present in .github/workflows/release.yml: push trigger tags ['v*'] (lines 20-21), `python -m build` (line 114), `sha256sum -- *.tar.gz *.whl > SHA256SUMS` + `sha256sum -c` (lines 119-120), `gh release create ... --generate-notes` (lines 127-130), read-only version check that never bumps pyproject (lines 88-105), plus docs/releasing.md runbook and scripts/release-cut-check.sh dry-run validation (15/15 tests pass locally: `.venv/bin/python -m pytest tests/test_release_workflow.py` -> 15 passed). HOWEVER the final clause 'CI remains green on the pushed SHA' is VIOLATED. HEAD is the release commit b6c12c77bd87e108536bf28b1556089be9f46272; `gh run list --commit b6c12c77bd87e108536bf28b1556089be9f46272` returns conclusion=failure (run 37243382640, the latest run on main). Jobs Python 3.11, 3.12 and 3.13 all FAILED. Root cause is a defect in the delivered test itself: tests/test_release_workflow.py::test_check_script_fails_clearly_on_nonexistent_tag asserts `git rev-parse -q --verify refs/tags/v1.2.0` returns 0, but actions/checkout@v4 does not fetch tags, so the tag is absent in CI -> 'AssertionError: v1.2.0 expected to exist for this test' / 'assert 1 == 0'; CI log tail: '1 failed, 1586 passed, 18 skipped, 70 deselected in 88.25s' then '##[error]Process completed with exit code 1'. The test only passes in the local clone because v1.2.0 exists there. No later commit fixed it (git log -1 == b6c12c7).


## Summary

Judge Result: RELTOOL-1791152794779715762

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE
  ✗ On tag push v*: workflow builds sdist+wheel (python -m build), generates artifacts with sha256sums, creates a GitHub Release with categorized notes via gh; does NOT auto-bump pyproject; includes a workflow lint/act-style validation or a documented dry-run proof; CI remains green on the pushed SHA.: Most sub-requirements are present in .github/workflows/release.yml: push trigger tags ['v*'] (lines 20-21), `python -m build` (line 114), `sha256sum -- *.tar.gz *.whl > SHA256SUMS` + `sha256sum -c` (lines 119-120), `gh release create ... --generate-notes` (lines 127-130), read-only version check that never bumps pyproject (lines 88-105), plus docs/releasing.md runbook and scripts/release-cut-check.sh dry-run validation (15/15 tests pass locally: `.venv/bin/python -m pytest tests/test_release_workflow.py` -> 15 passed). HOWEVER the final clause 'CI remains green on the pushed SHA' is VIOLATED. HEAD is the release commit b6c12c77bd87e108536bf28b1556089be9f46272; `gh run list --commit b6c12c77bd87e108536bf28b1556089be9f46272` returns conclusion=failure (run 37243382640, the latest run on main). Jobs Python 3.11, 3.12 and 3.13 all FAILED. Root cause is a defect in the delivered test itself: tests/test_release_workflow.py::test_check_script_fails_clearly_on_nonexistent_tag asserts `git rev-parse -q --verify refs/tags/v1.2.0` returns 0, but actions/checkout@v4 does not fetch tags, so the tag is absent in CI -> 'AssertionError: v1.2.0 expected to exist for this test' / 'assert 1 == 0'; CI log tail: '1 failed, 1586 passed, 18 skipped, 70 deselected in 88.25s' then '##[error]Process completed with exit code 1'. The test only passes in the local clone because v1.2.0 exists there. No later commit fixed it (git log -1 == b6c12c7).


Overall: FAIL ✗
