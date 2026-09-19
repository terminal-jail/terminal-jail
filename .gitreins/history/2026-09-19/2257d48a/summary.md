# Verdict: DF-TERMINAL-JAIL-22

**Task:** Prefix install rule-pack target is inert
**Evaluated:** 2026-09-19T19:24:29.650407
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ A custom-prefix install must place requested packs in a directory the engine actually loads or emit an explicit non-success warning; tests and docs must prove the resolved path, suite and lint green.: install.sh:323-326 adds an engine-env resolver case (custom prefix + exported TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR -> RESOLVED_RULES_DIR = that exact dir), and the engine reads that var verbatim (plugin/terminal_jail/interruptor/config.py:50-52). install.sh:381-385 makes the remaining prefix-local scope SKIP each requested pack before the validator runs with an explicit non-success stderr reason naming the inert target and 3 remediations, then return 0 (nothing written); install.sh:492-493 extends the prefix WARNING to name the engine-env channel and the pack skip. Independent live proof: engine-env run -> EXIT=0, pack byte-copied to /tmp/df22/engine-rules.d/terminal-jail-pack-db.yaml, prefix config never created, and intercept('psql ... DROP DATABASE prod_app') -> block/pack-db-drop-database while 'SELECT 1' -> allow (load proof, not file presence); prefix run -> EXIT=2 with 'skipped: pack db ... prefix-local config the engine does NOT load ... Nothing was written for this pack. Remediation, pick one: (1) TERMINAL_JAIL_RULES_DIR=... (2) TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=... (3) default install dir' + 'base install completed', rules.d holding only 00-builtins.yaml; default install unchanged (EXIT=0, pack installed to ~/.config/terminal-jail/rules.d). Tests: plugin/test_install.py:1676,1708,1735,1750,1786 pin the prefix skip (exit 2, remediation named, no pack file, base install completes; two packs skip independently), --unrule-pack scope-agnostic removal, and both engine-loaded channels with intercept() BLOCK verdicts; RED-proven by running the two new tests against 808ff39's install.sh -> '2 failed', then restoring install.sh (git diff empty) -> 49 passed. Gates (actual output): `.venv/bin/python -m pytest -q --tb=short` -> '889 passed, 5 skipped in 46.19s'; `uvx ruff check` -> 'All checks passed!' EXIT=0; scripts/yaml-mirror-parity-probe.py -> 'ALL PROBES PASS'; read_lsp_diagnostics -> count 0. Docs: README.md:446,472,485; docs/quickstart.md:416; specs/cli.md:392,451,456; CHANGELOG.md:11,20 document the engine-env channel, the prefix pack skip, and the remediation.
Custom-prefix installs now either land packs in an engine-loaded directory (explicit TERMINAL_JAIL_RULES_DIR or engine-env TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR, verified by live intercept() BLOCK) or skip loudly with exit 2 and full remediation, with tests, docs, 889-passing suite, clean ruff, and clean LSP.

## Summary

Judge Result: DF-TERMINAL-JAIL-22

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ A custom-prefix install must place requested packs in a directory the engine actually loads or emit an explicit non-success warning; tests and docs must prove the resolved path, suite and lint green.: install.sh:323-326 adds an engine-env resolver case (custom prefix + exported TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR -> RESOLVED_RULES_DIR = that exact dir), and the engine reads that var verbatim (plugin/terminal_jail/interruptor/config.py:50-52). install.sh:381-385 makes the remaining prefix-local scope SKIP each requested pack before the validator runs with an explicit non-success stderr reason naming the inert target and 3 remediations, then return 0 (nothing written); install.sh:492-493 extends the prefix WARNING to name the engine-env channel and the pack skip. Independent live proof: engine-env run -> EXIT=0, pack byte-copied to /tmp/df22/engine-rules.d/terminal-jail-pack-db.yaml, prefix config never created, and intercept('psql ... DROP DATABASE prod_app') -> block/pack-db-drop-database while 'SELECT 1' -> allow (load proof, not file presence); prefix run -> EXIT=2 with 'skipped: pack db ... prefix-local config the engine does NOT load ... Nothing was written for this pack. Remediation, pick one: (1) TERMINAL_JAIL_RULES_DIR=... (2) TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=... (3) default install dir' + 'base install completed', rules.d holding only 00-builtins.yaml; default install unchanged (EXIT=0, pack installed to ~/.config/terminal-jail/rules.d). Tests: plugin/test_install.py:1676,1708,1735,1750,1786 pin the prefix skip (exit 2, remediation named, no pack file, base install completes; two packs skip independently), --unrule-pack scope-agnostic removal, and both engine-loaded channels with intercept() BLOCK verdicts; RED-proven by running the two new tests against 808ff39's install.sh -> '2 failed', then restoring install.sh (git diff empty) -> 49 passed. Gates (actual output): `.venv/bin/python -m pytest -q --tb=short` -> '889 passed, 5 skipped in 46.19s'; `uvx ruff check` -> 'All checks passed!' EXIT=0; scripts/yaml-mirror-parity-probe.py -> 'ALL PROBES PASS'; read_lsp_diagnostics -> count 0. Docs: README.md:446,472,485; docs/quickstart.md:416; specs/cli.md:392,451,456; CHANGELOG.md:11,20 document the engine-env channel, the prefix pack skip, and the remediation.
Custom-prefix installs now either land packs in an engine-loaded directory (explicit TERMINAL_JAIL_RULES_DIR or engine-env TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR, verified by live intercept() BLOCK) or skip loudly with exit 2 and full remediation, with tests, docs, 889-passing suite, clean ruff, and clean LSP.

Overall: PASS ✓
