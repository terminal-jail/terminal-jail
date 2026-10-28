# Verdict: DOC-24

**Task:** Document TERMINAL_JAIL_HERMES_PLUGIN_DIR for Hermes plugin deployment
**Evaluated:** 2026-10-28T02:32:23.995925
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ Add TERMINAL_JAIL_HERMES_PLUGIN_DIR to the maintained plugin-install reference with its default, target precedence, and a safe example; rerun bash install.sh --help and grep the reader-facing docs to verify both surfaces.: Commit cf904da adds the variable to the maintained plugin-install reference (README.md '### Plugin (Hermes)' section) with all three required elements: (1) SAFE EXAMPLE at README.md:449 — `TERMINAL_JAIL_HERMES_PLUGIN_DIR=/custom/dir ./install.sh --hermes-plugin   # env override (no explicit target)` (concrete path, no placeholder tokens); (2) TARGET PRECEDENCE at README.md:452-455 — 'first non-empty of: the `--hermes-plugin <dir>` / `--hermes-plugin-dir=<dir>` argument, the `TERMINAL_JAIL_HERMES_PLUGIN_DIR` environment variable, then the default', which matches the code chain at install.sh:668-676 exactly (HERMES_PLUGIN_ARG -> TERMINAL_JAIL_HERMES_PLUGIN_DIR -> $HOME/.hermes/plugins/terminal-jail); (3) DEFAULT at README.md:455 — '`~/.hermes/plugins/terminal-jail` (derived from `$HOME`)', also stated at docs/quickstart.md:667-668. Both surfaces verified: `bash install.sh --help` returned EXIT=0 and its help text documents the var with default at install.sh:322 and install.sh:98; grep of reader-facing docs confirms README.md:449,454 and docs/quickstart.md:666. Tests run fresh: full suite `.venv/bin/python -m pytest -q` -> '2057 passed, 15 skipped in 176.11s' (zero failures); tests/test_quickstart_doc.py -> '8 passed', EXIT=0. Minor nit only: the 13-row '| Variable | Default | Purpose |' table at README.md:460-472 does not list the var (it is documented in the install block and precedence prose instead), which the criterion does not require. [resolution 0.19; install.sh]
TERMINAL_JAIL_HERMES_PLUGIN_DIR is documented in the README plugin-install reference with its default, exact target precedence matching install.sh:668-676, and a safe copy-pasteable example, with both surfaces verified (install.sh --help exit 0, docs grep) and the full suite green at 2057 passed.

## Summary

Judge Result: DOC-24

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ Add TERMINAL_JAIL_HERMES_PLUGIN_DIR to the maintained plugin-install reference with its default, target precedence, and a safe example; rerun bash install.sh --help and grep the reader-facing docs to verify both surfaces.: Commit cf904da adds the variable to the maintained plugin-install reference (README.md '### Plugin (Hermes)' section) with all three required elements: (1) SAFE EXAMPLE at README.md:449 — `TERMINAL_JAIL_HERMES_PLUGIN_DIR=/custom/dir ./install.sh --hermes-plugin   # env override (no explicit target)` (concrete path, no placeholder tokens); (2) TARGET PRECEDENCE at README.md:452-455 — 'first non-empty of: the `--hermes-plugin <dir>` / `--hermes-plugin-dir=<dir>` argument, the `TERMINAL_JAIL_HERMES_PLUGIN_DIR` environment variable, then the default', which matches the code chain at install.sh:668-676 exactly (HERMES_PLUGIN_ARG -> TERMINAL_JAIL_HERMES_PLUGIN_DIR -> $HOME/.hermes/plugins/terminal-jail); (3) DEFAULT at README.md:455 — '`~/.hermes/plugins/terminal-jail` (derived from `$HOME`)', also stated at docs/quickstart.md:667-668. Both surfaces verified: `bash install.sh --help` returned EXIT=0 and its help text documents the var with default at install.sh:322 and install.sh:98; grep of reader-facing docs confirms README.md:449,454 and docs/quickstart.md:666. Tests run fresh: full suite `.venv/bin/python -m pytest -q` -> '2057 passed, 15 skipped in 176.11s' (zero failures); tests/test_quickstart_doc.py -> '8 passed', EXIT=0. Minor nit only: the 13-row '| Variable | Default | Purpose |' table at README.md:460-472 does not list the var (it is documented in the install block and precedence prose instead), which the criterion does not require. [resolution 0.19; install.sh]
TERMINAL_JAIL_HERMES_PLUGIN_DIR is documented in the README plugin-install reference with its default, exact target precedence matching install.sh:668-676, and a safe copy-pasteable example, with both surfaces verified (install.sh --help exit 0, docs grep) and the full suite green at 2057 passed.

Overall: PASS ✓
