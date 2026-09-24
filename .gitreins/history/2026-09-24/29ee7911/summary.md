# Verdict: TJ-DF-022

**Task:** install.sh --hermes-plugin update path for the deployed Hermes plugin
**Evaluated:** 2026-09-24T21:37:23.695504
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh --hermes-plugin installs/refreshes the plugin tree to a target dir with stale files replaced; exit 0 on success, non-zero with clear error when the repo plugin tree is missing; refresh documented in README.md and docs/quickstart.md; regression tests in plugin/test_install.py cover fresh install, stale-target refresh, and missing-tree failure; tests pass and ruff clean: install.sh:427-493 implements the mode: target resolution (positional arg / --hermes-plugin-dir= / TERMINAL_JAIL_HERMES_PLUGIN_DIR / $HOME/.hermes/plugins/terminal-jail), missing-tree guard install.sh:452-456 -> exit 2 with 'needs a repository checkout ... nothing was written', stale removal via `find "$TARGET" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +` (install.sh:481) then `cp -R "$plugin_source_dir"/plugin/. "$TARGET/"` (install.sh:487), exit 0 (install.sh:493). LIVE: stale target (spin_policy.py + version 0.2.0) -> exit 0, 'refreshed Hermes plugin tree ... (stale files removed)', 'deployed Hermes plugin v1.2.0', stale file gone, plugin.yaml now 1.2.0. LIVE missing tree (checkout with only install.sh) -> exit 2, '--hermes-plugin needs a repository checkout (no plugin/plugin.yaml + plugin/terminal_jail next to ...); nothing was written', pre-existing keep-me.txt untouched. Docs: README.md:243-248 (install + refresh paragraph 'empties the deployed package and re-copies the current tree, so stale v0.2-era files cannot survive the update'); docs/quickstart.md:420-430 and docs/quickstart.md:500 refresh paragraph. Tests: plugin/test_install.py:2228 fresh deploy, :2261 stale refresh, :2287 idempotent/complete, :2308 --hermes-plugin-dir override, :2321 missing-tree failure, :2345 no release opt-in, :2371 flag mixing, :2388 default target under $HOME. Command evidence: `.venv/bin/python -m pytest plugin/test_install.py -x --tb=short -q` -> '66 passed in 14.41s'; `-k hermes_plugin` -> '8 passed, 58 deselected'; full suite `.venv/bin/python -m pytest -q --tb=short` -> '1444 passed, 7 skipped in 53.06s'; `.venv/bin/python -m ruff check .` -> 'All checks passed!' (exit 0). [resolution 0.06; install.sh, README.md, docs/quickstart.md, plugin/test_install.py]
install.sh --hermes-plugin deploys/refreshes the plugin tree with stale-file removal, exits 0 on success and 2 with a clear error on a missing repo tree, is documented in README.md and docs/quickstart.md, and its regression tests pass (66 passed; full suite 1444 passed/7 skipped) with ruff clean.

## Summary

Judge Result: TJ-DF-022

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ install.sh --hermes-plugin installs/refreshes the plugin tree to a target dir with stale files replaced; exit 0 on success, non-zero with clear error when the repo plugin tree is missing; refresh documented in README.md and docs/quickstart.md; regression tests in plugin/test_install.py cover fresh install, stale-target refresh, and missing-tree failure; tests pass and ruff clean: install.sh:427-493 implements the mode: target resolution (positional arg / --hermes-plugin-dir= / TERMINAL_JAIL_HERMES_PLUGIN_DIR / $HOME/.hermes/plugins/terminal-jail), missing-tree guard install.sh:452-456 -> exit 2 with 'needs a repository checkout ... nothing was written', stale removal via `find "$TARGET" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +` (install.sh:481) then `cp -R "$plugin_source_dir"/plugin/. "$TARGET/"` (install.sh:487), exit 0 (install.sh:493). LIVE: stale target (spin_policy.py + version 0.2.0) -> exit 0, 'refreshed Hermes plugin tree ... (stale files removed)', 'deployed Hermes plugin v1.2.0', stale file gone, plugin.yaml now 1.2.0. LIVE missing tree (checkout with only install.sh) -> exit 2, '--hermes-plugin needs a repository checkout (no plugin/plugin.yaml + plugin/terminal_jail next to ...); nothing was written', pre-existing keep-me.txt untouched. Docs: README.md:243-248 (install + refresh paragraph 'empties the deployed package and re-copies the current tree, so stale v0.2-era files cannot survive the update'); docs/quickstart.md:420-430 and docs/quickstart.md:500 refresh paragraph. Tests: plugin/test_install.py:2228 fresh deploy, :2261 stale refresh, :2287 idempotent/complete, :2308 --hermes-plugin-dir override, :2321 missing-tree failure, :2345 no release opt-in, :2371 flag mixing, :2388 default target under $HOME. Command evidence: `.venv/bin/python -m pytest plugin/test_install.py -x --tb=short -q` -> '66 passed in 14.41s'; `-k hermes_plugin` -> '8 passed, 58 deselected'; full suite `.venv/bin/python -m pytest -q --tb=short` -> '1444 passed, 7 skipped in 53.06s'; `.venv/bin/python -m ruff check .` -> 'All checks passed!' (exit 0). [resolution 0.06; install.sh, README.md, docs/quickstart.md, plugin/test_install.py]
install.sh --hermes-plugin deploys/refreshes the plugin tree with stale-file removal, exits 0 on success and 2 with a clear error on a missing repo tree, is documented in README.md and docs/quickstart.md, and its regression tests pass (66 passed; full suite 1444 passed/7 skipped) with ruff clean.

Overall: PASS ✓
