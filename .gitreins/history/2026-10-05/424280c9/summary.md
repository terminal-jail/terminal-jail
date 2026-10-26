# Verdict: RELTOOL-1791152794779715762

**Task:** Release tooling: tag-triggered release workflow (artifact channel gate 1/RELEASE-TJ-008)
**Evaluated:** 2026-10-05T02:36:42.667557
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ On tag push v*: workflow builds sdist+wheel (python -m build), generates artifacts with sha256sums, creates a GitHub Release with categorized notes via gh; does NOT auto-bump pyproject; includes a workflow lint/act-style validation or a documented dry-run proof; CI remains green on the pushed SHA.: All legs verified. (a) tag trigger: .github/workflows/release.yml:20-21 `on: push: tags: ["v*"]`. (b) build: release.yml:110-111 `run: python -m build` (sdist+wheel) on Python 3.11. (c) checksums: release.yml:113-118 `sha256sum -- *.tar.gz *.whl > SHA256SUMS; sha256sum -c SHA256SUMS`. (d) gh Release: release.yml:124-131 `gh release create "${RELEASE_TAG}" dist/* --verify-tag --title ... --generate-notes --notes-start-tag ...`, followed by a post-create asset-list verification step (release.yml:133-148) that exits 1 on mismatch. (e) categorized notes: .github/release.yml (commit 4f43984) defines changelog.categories (Features/Bug fixes/Security/Documentation/Tests and CI/Other changes), which GitHub auto-consumes for --generate-notes. (f) no auto-bump: release.yml:88-106 is a read-only version==tag check; no write to pyproject.toml anywhere in the workflow; pyproject.toml:7 still `version = "1.2.0"`; test_release_workflow_never_bumps_version_or_creates_tags asserts absence of `git tag`/`git push`/`sed -i`/`> pyproject.toml`. (g) validation/dry-run proof: tests/test_release_workflow.py (15 PyYAML structural tests over release.yml+ci.yml) plus docs/releasing.md:88-107 'Documented dry-run proof' section and read-only scripts/release-cut-check.sh. (h) CI green on pushed SHA: `gh run list --commit 4f43984894f57be4152a24bd418bfe61690bcd4b --json name,status,conclusion,headSha,event` -> {"conclusion":"success","event":"push","headSha":"4f43984...","name":"CI","status":"completed"}. FRESH TEST EVIDENCE: `.venv/bin/python -m pytest tests/test_release_workflow.py -v` -> '15 passed in 6.14s' (exit 0); `.venv/bin/python -m pytest tests/ -q` -> '108 passed, 3 skipped in 22.84s' (exit 0); `./scripts/release-cut-check.sh v1.3.0` -> exit 1 with named failures (dirty tree, version mismatch) and 'OK: CI green on HEAD 4f43984'.
The tag-triggered release workflow builds sdist+wheel with python -m build, emits SHA256SUMS, publishes a categorized-notes GitHub Release via gh, never bumps pyproject, ships structural/dry-run validation, and CI is green on the pushed SHA 4f43984.

## Summary

Judge Result: RELTOOL-1791152794779715762

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ On tag push v*: workflow builds sdist+wheel (python -m build), generates artifacts with sha256sums, creates a GitHub Release with categorized notes via gh; does NOT auto-bump pyproject; includes a workflow lint/act-style validation or a documented dry-run proof; CI remains green on the pushed SHA.: All legs verified. (a) tag trigger: .github/workflows/release.yml:20-21 `on: push: tags: ["v*"]`. (b) build: release.yml:110-111 `run: python -m build` (sdist+wheel) on Python 3.11. (c) checksums: release.yml:113-118 `sha256sum -- *.tar.gz *.whl > SHA256SUMS; sha256sum -c SHA256SUMS`. (d) gh Release: release.yml:124-131 `gh release create "${RELEASE_TAG}" dist/* --verify-tag --title ... --generate-notes --notes-start-tag ...`, followed by a post-create asset-list verification step (release.yml:133-148) that exits 1 on mismatch. (e) categorized notes: .github/release.yml (commit 4f43984) defines changelog.categories (Features/Bug fixes/Security/Documentation/Tests and CI/Other changes), which GitHub auto-consumes for --generate-notes. (f) no auto-bump: release.yml:88-106 is a read-only version==tag check; no write to pyproject.toml anywhere in the workflow; pyproject.toml:7 still `version = "1.2.0"`; test_release_workflow_never_bumps_version_or_creates_tags asserts absence of `git tag`/`git push`/`sed -i`/`> pyproject.toml`. (g) validation/dry-run proof: tests/test_release_workflow.py (15 PyYAML structural tests over release.yml+ci.yml) plus docs/releasing.md:88-107 'Documented dry-run proof' section and read-only scripts/release-cut-check.sh. (h) CI green on pushed SHA: `gh run list --commit 4f43984894f57be4152a24bd418bfe61690bcd4b --json name,status,conclusion,headSha,event` -> {"conclusion":"success","event":"push","headSha":"4f43984...","name":"CI","status":"completed"}. FRESH TEST EVIDENCE: `.venv/bin/python -m pytest tests/test_release_workflow.py -v` -> '15 passed in 6.14s' (exit 0); `.venv/bin/python -m pytest tests/ -q` -> '108 passed, 3 skipped in 22.84s' (exit 0); `./scripts/release-cut-check.sh v1.3.0` -> exit 1 with named failures (dirty tree, version mismatch) and 'OK: CI green on HEAD 4f43984'.
The tag-triggered release workflow builds sdist+wheel with python -m build, emits SHA256SUMS, publishes a categorized-notes GitHub Release via gh, never bumps pyproject, ships structural/dry-run validation, and CI is green on the pushed SHA 4f43984.

Overall: PASS ✓
