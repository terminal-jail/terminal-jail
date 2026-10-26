# Verdict: TJ-GAP-057

**Task:** CI RED: pin ruff to one version and make lint deterministic
**Evaluated:** 2026-09-16T19:34:03.767956
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m2:32PM[0m [32mINF[0m [1mscanned ~3415051 bytes (3.42 MB) in 385ms[0m
[90m2:32PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ The repo names exactly one ruff version: .github/workflows/ci.yml installs a pinned ruff==0.16.8 (no bare 'pip install ruff') and pyproject.toml [dependency-groups] dev pins the same version: .github/workflows/ci.yml:51 `run: pip install 'ruff==0.16.8'` (pinned, no bare install); pyproject.toml:34 `dev = ["pytest>=8", "ruff==0.16.8"]`. grep for 'ruff' across .github/, pyproject.toml, uv.lock shows only these version declarations — no other ruff version is named in CI or packaging config.
  ✓ pyproject.toml declares an explicit [tool.ruff] config (target-version + explicit [tool.ruff.lint].select) so a future ruff release can no longer change the default rule set and red the gate without a commit: pyproject.toml:51-56: `[tool.ruff]` with `target-version = "py311"` and `line-length = 88`, plus `[tool.ruff.lint]` with explicit `select = ["E4", "E7", "E9", "F", "I"]`. The rule set is now pinned in-repo rather than inherited from ruff defaults.
  ✓ plugin/test_escape_waves.py satisfies I001 under BOTH ruff 0.15.22 and ruff 0.16.8: 'ruff check plugin/' and 'uvx ruff check plugin/' both exit 0: `ruff --version` -> ruff 0.15.22; `ruff check plugin/` -> 'All checks passed!' EXIT=0. `uvx ruff --version` -> ruff 0.16.8; `uvx ruff check plugin/` -> 'All checks passed!' EXIT=0. Targeted `--select I001` under both versions also EXIT=0. plugin/test_escape_waves.py:16-17 imports are correctly sorted (`import pytest` then `from terminal_jail.interruptor import ...`).
  ✓ The full test suite still passes on the changed tree: Ran the configured test command from .gitreins/config.yaml (`pytest -x --tb=short`): PYTEST_EXIT=0, output tail '401 passed, 14 skipped in 17.38s' (415 collected, 0 failures).
All four criteria verified: ruff pinned to 0.16.8 in both ci.yml and pyproject.toml dev group, explicit [tool.ruff]/[tool.ruff.lint] config present, plugin/ lints clean under both ruff 0.15.22 and 0.16.8, and the full suite passes (401 passed, 14 skipped, exit 0).

## Summary

Judge Result: TJ-GAP-057

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m2:32PM[0m [32mINF[0m [1mscanned ~3415051 bytes (3.42 MB) in 385ms[0m
[90m2:32PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ The repo names exactly one ruff version: .github/workflows/ci.yml installs a pinned ruff==0.16.8 (no bare 'pip install ruff') and pyproject.toml [dependency-groups] dev pins the same version: .github/workflows/ci.yml:51 `run: pip install 'ruff==0.16.8'` (pinned, no bare install); pyproject.toml:34 `dev = ["pytest>=8", "ruff==0.16.8"]`. grep for 'ruff' across .github/, pyproject.toml, uv.lock shows only these version declarations — no other ruff version is named in CI or packaging config.
  ✓ pyproject.toml declares an explicit [tool.ruff] config (target-version + explicit [tool.ruff.lint].select) so a future ruff release can no longer change the default rule set and red the gate without a commit: pyproject.toml:51-56: `[tool.ruff]` with `target-version = "py311"` and `line-length = 88`, plus `[tool.ruff.lint]` with explicit `select = ["E4", "E7", "E9", "F", "I"]`. The rule set is now pinned in-repo rather than inherited from ruff defaults.
  ✓ plugin/test_escape_waves.py satisfies I001 under BOTH ruff 0.15.22 and ruff 0.16.8: 'ruff check plugin/' and 'uvx ruff check plugin/' both exit 0: `ruff --version` -> ruff 0.15.22; `ruff check plugin/` -> 'All checks passed!' EXIT=0. `uvx ruff --version` -> ruff 0.16.8; `uvx ruff check plugin/` -> 'All checks passed!' EXIT=0. Targeted `--select I001` under both versions also EXIT=0. plugin/test_escape_waves.py:16-17 imports are correctly sorted (`import pytest` then `from terminal_jail.interruptor import ...`).
  ✓ The full test suite still passes on the changed tree: Ran the configured test command from .gitreins/config.yaml (`pytest -x --tb=short`): PYTEST_EXIT=0, output tail '401 passed, 14 skipped in 17.38s' (415 collected, 0 failures).
All four criteria verified: ruff pinned to 0.16.8 in both ci.yml and pyproject.toml dev group, explicit [tool.ruff]/[tool.ruff.lint] config present, plugin/ lints clean under both ruff 0.15.22 and 0.16.8, and the full suite passes (401 passed, 14 skipped, exit 0).

Overall: PASS ✓
