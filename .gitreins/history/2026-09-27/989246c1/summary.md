# Verdict: DOC-2

**Task:** Fix CONTRIBUTING documentation drift
**Evaluated:** 2026-09-27T13:25:02.684049
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ CONTRIBUTING setup uses a runnable dependency workflow; test counts match pytest --collect-only; the project tree has no phantom plugin/test_integration.py; and line-length guidance matches pyproject.toml.: All four sub-claims verified. (1) Runnable workflow: CONTRIBUTING.md:8-11 documents `uv sync --dev`; `uv sync --dev --dry-run` exit=0 ('Resolved 9 packages', 'Found up-to-date lockfile at: uv.lock', 'Would make no changes'); uv.lock exists. pyproject.toml:31 has `[dependency-groups] dev=["pytest>=8","ruff==0.16.8"]` with optional-dependencies=None, so the old `pip install -e ".[dev]"` genuinely fails and CONTRIBUTING.md:15 now says so; pip fallback `python3 -m pip install -e . pytest "ruff==0.16.8"` verified via `pip install --dry-run` exit=0 ('Would install ruff-0.16.8 terminal-jail-1.2.0'); dead `--cov` example removed (grep pytest-cov/--cov in CONTRIBUTING.md = no match); `.venv/bin/ruff check plugin/` => 'All checks passed!'. (2) Test counts: `python3 -m pytest plugin/ --collect-only -q` => '1444 tests collected'; per-file test_plugin 16, test_install 66, test_standalone_cli 21, test_metrics_export 21 all match CONTRIBUTING.md:59-64; running those 4 modules => '124 passed' (=16+66+21+21); '21 further test modules' is correct (25 plugin/test_*.py minus the 4 named). (3) No phantom file: `ls plugin/test_integration.py` => 'No such file or directory', `find . -name test_integration.py` => none, and `grep test_integration CONTRIBUTING.md` => no match (entry replaced with real layout). (4) Line length: pyproject.toml:53 `line-length = 88` matches CONTRIBUTING.md:46 'Line length: 88 characters (set as `line-length` in `pyproject.toml`)'. Integration marker list in CONTRIBUTING.md matches `grep -l pytest.mark.integration` exactly (test_env_scrub, test_userns, test_backend_parity, test_backend_selection, test_host_probes). [resolution 0.09; plugin/test_integration.py]
CONTRIBUTING.md now documents a verified-runnable uv/pip dependency workflow, per-file test counts matching pytest --collect-only (16/66/21/21, 1444 total), no phantom plugin/test_integration.py, and line-length 88 matching pyproject.toml.

## Summary

Judge Result: DOC-2

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ CONTRIBUTING setup uses a runnable dependency workflow; test counts match pytest --collect-only; the project tree has no phantom plugin/test_integration.py; and line-length guidance matches pyproject.toml.: All four sub-claims verified. (1) Runnable workflow: CONTRIBUTING.md:8-11 documents `uv sync --dev`; `uv sync --dev --dry-run` exit=0 ('Resolved 9 packages', 'Found up-to-date lockfile at: uv.lock', 'Would make no changes'); uv.lock exists. pyproject.toml:31 has `[dependency-groups] dev=["pytest>=8","ruff==0.16.8"]` with optional-dependencies=None, so the old `pip install -e ".[dev]"` genuinely fails and CONTRIBUTING.md:15 now says so; pip fallback `python3 -m pip install -e . pytest "ruff==0.16.8"` verified via `pip install --dry-run` exit=0 ('Would install ruff-0.16.8 terminal-jail-1.2.0'); dead `--cov` example removed (grep pytest-cov/--cov in CONTRIBUTING.md = no match); `.venv/bin/ruff check plugin/` => 'All checks passed!'. (2) Test counts: `python3 -m pytest plugin/ --collect-only -q` => '1444 tests collected'; per-file test_plugin 16, test_install 66, test_standalone_cli 21, test_metrics_export 21 all match CONTRIBUTING.md:59-64; running those 4 modules => '124 passed' (=16+66+21+21); '21 further test modules' is correct (25 plugin/test_*.py minus the 4 named). (3) No phantom file: `ls plugin/test_integration.py` => 'No such file or directory', `find . -name test_integration.py` => none, and `grep test_integration CONTRIBUTING.md` => no match (entry replaced with real layout). (4) Line length: pyproject.toml:53 `line-length = 88` matches CONTRIBUTING.md:46 'Line length: 88 characters (set as `line-length` in `pyproject.toml`)'. Integration marker list in CONTRIBUTING.md matches `grep -l pytest.mark.integration` exactly (test_env_scrub, test_userns, test_backend_parity, test_backend_selection, test_host_probes). [resolution 0.09; plugin/test_integration.py]
CONTRIBUTING.md now documents a verified-runnable uv/pip dependency workflow, per-file test counts matching pytest --collect-only (16/66/21/21, 1444 total), no phantom plugin/test_integration.py, and line-length 88 matching pyproject.toml.

Overall: PASS ✓
