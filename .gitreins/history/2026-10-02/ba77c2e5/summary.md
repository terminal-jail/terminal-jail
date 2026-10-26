# Verdict: INT-CI-2

**Task:** Coverage tooling: pytest-cov in dev group + CI-reported measured baseline
**Evaluated:** 2026-10-02T09:24:01.750677
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out
- ✗ **tier2**
  - INCOMPLETE
  ✓ pyproject.toml [dependency-groups].dev includes pytest-cov: pyproject.toml line 33: [dependency-groups] dev = ["pytest>=8", "pytest-cov>=6", "ruff==0.16.8"]. Confirmed installed: `.venv/bin/python -c "import pytest_cov"` -> pytest-cov 7.1.0. [resolution 0.11; pyproject.toml]
  ✓ uv sync --dev --python 3.11 then .venv/bin/python -m pytest plugin -q --cov=terminal_jail --cov-report=term-missing completes and prints a coverage total for plugin/terminal_jail: Ran `uv sync --dev --python 3.11` (exit 0, 'Resolved 12 packages in 9ms') then `.venv/bin/python -m pytest plugin -q --cov=terminal_jail --cov-report=term-missing`. Completed with exit 0 and printed the per-file table plus 'TOTAL 1255 316 75%' and '1510 passed, 7 skipped in 370.89s (0:06:10)'. Coverage total for plugin/terminal_jail is printed.
  ✓ The measured coverage number and the exact command are recorded in the repo (README development section): README.md '## Development' (line 719) -> '### Coverage' (line 727) records the exact command `uv sync --dev --python 3.11 && uv run pytest plugin -q --cov=terminal_jail --cov-report=term-missing` (line 730) and the measured baseline 'TOTAL 75% (1255 statements, 316 missed; 1510 passed, 7 skipped in ~148s)' (line 733). My independent run reproduced 75% / 1255 stmts / 316 missed / 1510 passed / 7 skipped.
  ✗ ci.yml test job installs pytest-cov and runs the coverage step, publishing the total in the job log as an artifact: ci.yml test job DOES install pytest-cov (line 30 `pip install pytest-cov`) and DOES run the coverage step (line 38 `pytest plugin/ tests/ -v --tb=short -m "not integration" --cov=terminal_jail --cov-report=term --cov-fail-under=74`), which prints the total to the job log. However the 'as an artifact' half is entirely missing: `grep -rn "upload-artifact|artifact" .github/` returns zero matches (exit 1), and there is no `actions/upload-artifact` step, no `--cov-report=xml`/coverage.xml, no `--junitxml`, and no `$GITHUB_STEP_SUMMARY` write anywhere in .github/ or scripts/. The coverage total is never published as a downloadable artifact.
  ✓ the coverage floor (--cov-fail-under) is set at or below the measured baseline, with the honest caveats (exclusions) stated where the number is published: ci.yml line 38 sets `--cov-fail-under=74`, below both measured baselines (75% host venv 3.11 and 74.82% CI scope), documented at README.md line 733. Caveats are stated at the point of publication (README lines 735-739): 'Excluded from measurement' (the tests themselves plus host/platform-gated skips — PID-namespace, seccomp requiring CAP_SYS_ADMIN, SIGHUP reload), host-dependence of the percentage, 'Not a proxy for assertion quality', and the two 0% entry surfaces (__init__.py, plugin.py).
Criteria 1, 2, 3, and 5 are fully met (pytest-cov in dev group, coverage command reproduces TOTAL 75%, README records command+baseline, floor 74 with honest caveats), but criterion 4 fails because ci.yml never uploads the coverage total as an artifact (no actions/upload-artifact step anywhere).

## Summary

Judge Result: INT-CI-2

Stage tier1: FAIL
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out

Stage tier2: FAIL
  INCOMPLETE
  ✓ pyproject.toml [dependency-groups].dev includes pytest-cov: pyproject.toml line 33: [dependency-groups] dev = ["pytest>=8", "pytest-cov>=6", "ruff==0.16.8"]. Confirmed installed: `.venv/bin/python -c "import pytest_cov"` -> pytest-cov 7.1.0. [resolution 0.11; pyproject.toml]
  ✓ uv sync --dev --python 3.11 then .venv/bin/python -m pytest plugin -q --cov=terminal_jail --cov-report=term-missing completes and prints a coverage total for plugin/terminal_jail: Ran `uv sync --dev --python 3.11` (exit 0, 'Resolved 12 packages in 9ms') then `.venv/bin/python -m pytest plugin -q --cov=terminal_jail --cov-report=term-missing`. Completed with exit 0 and printed the per-file table plus 'TOTAL 1255 316 75%' and '1510 passed, 7 skipped in 370.89s (0:06:10)'. Coverage total for plugin/terminal_jail is printed.
  ✓ The measured coverage number and the exact command are recorded in the repo (README development section): README.md '## Development' (line 719) -> '### Coverage' (line 727) records the exact command `uv sync --dev --python 3.11 && uv run pytest plugin -q --cov=terminal_jail --cov-report=term-missing` (line 730) and the measured baseline 'TOTAL 75% (1255 statements, 316 missed; 1510 passed, 7 skipped in ~148s)' (line 733). My independent run reproduced 75% / 1255 stmts / 316 missed / 1510 passed / 7 skipped.
  ✗ ci.yml test job installs pytest-cov and runs the coverage step, publishing the total in the job log as an artifact: ci.yml test job DOES install pytest-cov (line 30 `pip install pytest-cov`) and DOES run the coverage step (line 38 `pytest plugin/ tests/ -v --tb=short -m "not integration" --cov=terminal_jail --cov-report=term --cov-fail-under=74`), which prints the total to the job log. However the 'as an artifact' half is entirely missing: `grep -rn "upload-artifact|artifact" .github/` returns zero matches (exit 1), and there is no `actions/upload-artifact` step, no `--cov-report=xml`/coverage.xml, no `--junitxml`, and no `$GITHUB_STEP_SUMMARY` write anywhere in .github/ or scripts/. The coverage total is never published as a downloadable artifact.
  ✓ the coverage floor (--cov-fail-under) is set at or below the measured baseline, with the honest caveats (exclusions) stated where the number is published: ci.yml line 38 sets `--cov-fail-under=74`, below both measured baselines (75% host venv 3.11 and 74.82% CI scope), documented at README.md line 733. Caveats are stated at the point of publication (README lines 735-739): 'Excluded from measurement' (the tests themselves plus host/platform-gated skips — PID-namespace, seccomp requiring CAP_SYS_ADMIN, SIGHUP reload), host-dependence of the percentage, 'Not a proxy for assertion quality', and the two 0% entry surfaces (__init__.py, plugin.py).
Criteria 1, 2, 3, and 5 are fully met (pytest-cov in dev group, coverage command reproduces TOTAL 75%, README records command+baseline, floor 74 with honest caveats), but criterion 4 fails because ci.yml never uploads the coverage total as an artifact (no actions/upload-artifact step anywhere).

Overall: FAIL ✗
