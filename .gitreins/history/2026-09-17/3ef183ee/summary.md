# Verdict: DF-TERMINAL-JAIL-8

**Task:** install.sh must scope the shipped-rules install to the selected install prefix
**Evaluated:** 2026-09-17T02:00:23.348538
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m8:58PM[0m [32mINF[0m [1mscanned ~3442185 bytes (3.44 MB) in 295ms[0m
[90m8:58PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh resolves the rules target as: explicit TERMINAL_JAIL_RULES_DIR when set, else HOME/.config/terminal-jail/rules.d only when the install dir is the default HOME/.local/bin, else the install prefix config dir: install.sh:178-187 implements exactly this three-way resolution: `if [ -n "$TERMINAL_JAIL_RULES_DIR" ]` -> used verbatim (rules_scope=explicit); `elif [ "$TERMINAL_JAIL_INSTALL_DIR" = "$HOME/.local/bin" ]` -> $HOME/.config/terminal-jail/rules.d; `else rules_prefix="$(CDPATH= cd -- "${TERMINAL_JAIL_INSTALL_DIR}/.." && pwd ...)"` -> ${rules_prefix}/config/terminal-jail/rules.d (parent resolved identically to LIB_DIR at line 150).
  ✓ a scratch install with a customized HOME config file leaves that file byte-identical and creates no backup beside it: Ran `HOME=/tmp/tj8/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj8/bin sh install.sh` with a seeded customized HOME/.config/terminal-jail/rules.d/00-builtins.yaml. `md5sum -c` -> 'OK' (byte-identical); live dir listing contained only 00-builtins.yaml (no .bak-*); rules landed at /tmp/tj8/config/terminal-jail/rules.d/00-builtins.yaml. Covered by plugin/test_install.py:535 test_prefix_install_does_not_touch_home_rules.
  ✓ an explicit TERMINAL_JAIL_RULES_DIR is honored for a scratch install: Ran `HOME=/tmp/tj8b/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj8b/bin TERMINAL_JAIL_RULES_DIR=/tmp/tj8b/custom-rules sh install.sh` -> output 'installed default rules to /tmp/tj8b/custom-rules/00-builtins.yaml' (16638 bytes present); no 'non-default install prefix' warning; HOME/.config does not exist. Covered by plugin/test_install.py:592 test_explicit_rules_dir_wins_over_install_scope.
  ✓ the default install dir still writes HOME/.config/terminal-jail/rules.d/00-builtins.yaml: Ran `HOME=/tmp/tj8c/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj8c/home/.local/bin sh install.sh` -> 'installed default rules to /tmp/tj8c/home/.config/terminal-jail/rules.d/00-builtins.yaml' (16638 bytes). Covered by plugin/test_install.py:631 test_default_install_dir_keeps_live_rules_target.
  ✓ backup-on-difference semantics for a customized target file are preserved: Default-dir install over a customized live file printed 'WARNING — existing user rules differed; backed up to .../00-builtins.yaml.bak-20260917T015949Z before installing defaults'; the .bak file contained the original '# customized by user\nrules: []\n'. Also verified in prefix scope (/tmp/tj8e/config/terminal-jail/rules.d/00-builtins.yaml.bak-20260917T015951Z). Logic at install.sh:196-201 (cmp -s guard + cp backup).
  ✓ a single warning line names the resolved prefix-scoped rules dir and the engine real search paths: Prefix install emitted exactly one WARNING line: 'terminal-jail installer: WARNING — non-default install prefix; installing default rules to /tmp/tj8/config/terminal-jail/rules.d. The engine loads /etc/terminal-jail/rules.d and ~/.config/terminal-jail/rules.d only; set TERMINAL_JAIL_RULES_DIR explicitly to target the live rules directory.' (install.sh:188-190). Names the resolved prefix dir and both engine search paths.
  ✓ specs/cli.md, README.md and docs/quickstart.md document TERMINAL_JAIL_RULES_DIR and the scope rule: specs/cli.md:297 (table row for TERMINAL_JAIL_RULES_DIR) and :300 (explicit 'Scope rule (DF-TERMINAL-JAIL-8)' paragraph); README.md:240-246 ('Rules follow the install scope' + TERMINAL_JAIL_RULES_DIR 'always wins'); docs/quickstart.md:296-299 (default vs prefix target + TERMINAL_JAIL_RULES_DIR override). All three document the variable and the scope rule.
  ✓ plugin test suite green and uvx ruff check reports no findings: `.venv/bin/pytest -q` -> '404 passed, 14 skipped in 9.27s' (exit 0); plugin/test_install.py alone -> '24 passed'. `uvx ruff check` -> 'All checks passed!' (exit 0). LSP diagnostics: 0 findings. Additionally confirmed the new regression tests genuinely fail against the pre-fix install.sh (2 failed: test_prefix_install_does_not_touch_home_rules, test_explicit_rules_dir_wins_over_install_scope) and pass against the fixed version.
All 8 criteria pass: install.sh implements the three-way prefix-scoped rules resolution with preserved backup semantics and a single honest warning, docs are updated, and the full plugin suite (404 passed) plus ruff are green.

## Summary

Judge Result: DF-TERMINAL-JAIL-8

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m8:58PM[0m [32mINF[0m [1mscanned ~3442185 bytes (3.44 MB) in 295ms[0m
[90m8:58PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ install.sh resolves the rules target as: explicit TERMINAL_JAIL_RULES_DIR when set, else HOME/.config/terminal-jail/rules.d only when the install dir is the default HOME/.local/bin, else the install prefix config dir: install.sh:178-187 implements exactly this three-way resolution: `if [ -n "$TERMINAL_JAIL_RULES_DIR" ]` -> used verbatim (rules_scope=explicit); `elif [ "$TERMINAL_JAIL_INSTALL_DIR" = "$HOME/.local/bin" ]` -> $HOME/.config/terminal-jail/rules.d; `else rules_prefix="$(CDPATH= cd -- "${TERMINAL_JAIL_INSTALL_DIR}/.." && pwd ...)"` -> ${rules_prefix}/config/terminal-jail/rules.d (parent resolved identically to LIB_DIR at line 150).
  ✓ a scratch install with a customized HOME config file leaves that file byte-identical and creates no backup beside it: Ran `HOME=/tmp/tj8/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj8/bin sh install.sh` with a seeded customized HOME/.config/terminal-jail/rules.d/00-builtins.yaml. `md5sum -c` -> 'OK' (byte-identical); live dir listing contained only 00-builtins.yaml (no .bak-*); rules landed at /tmp/tj8/config/terminal-jail/rules.d/00-builtins.yaml. Covered by plugin/test_install.py:535 test_prefix_install_does_not_touch_home_rules.
  ✓ an explicit TERMINAL_JAIL_RULES_DIR is honored for a scratch install: Ran `HOME=/tmp/tj8b/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj8b/bin TERMINAL_JAIL_RULES_DIR=/tmp/tj8b/custom-rules sh install.sh` -> output 'installed default rules to /tmp/tj8b/custom-rules/00-builtins.yaml' (16638 bytes present); no 'non-default install prefix' warning; HOME/.config does not exist. Covered by plugin/test_install.py:592 test_explicit_rules_dir_wins_over_install_scope.
  ✓ the default install dir still writes HOME/.config/terminal-jail/rules.d/00-builtins.yaml: Ran `HOME=/tmp/tj8c/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj8c/home/.local/bin sh install.sh` -> 'installed default rules to /tmp/tj8c/home/.config/terminal-jail/rules.d/00-builtins.yaml' (16638 bytes). Covered by plugin/test_install.py:631 test_default_install_dir_keeps_live_rules_target.
  ✓ backup-on-difference semantics for a customized target file are preserved: Default-dir install over a customized live file printed 'WARNING — existing user rules differed; backed up to .../00-builtins.yaml.bak-20260917T015949Z before installing defaults'; the .bak file contained the original '# customized by user\nrules: []\n'. Also verified in prefix scope (/tmp/tj8e/config/terminal-jail/rules.d/00-builtins.yaml.bak-20260917T015951Z). Logic at install.sh:196-201 (cmp -s guard + cp backup).
  ✓ a single warning line names the resolved prefix-scoped rules dir and the engine real search paths: Prefix install emitted exactly one WARNING line: 'terminal-jail installer: WARNING — non-default install prefix; installing default rules to /tmp/tj8/config/terminal-jail/rules.d. The engine loads /etc/terminal-jail/rules.d and ~/.config/terminal-jail/rules.d only; set TERMINAL_JAIL_RULES_DIR explicitly to target the live rules directory.' (install.sh:188-190). Names the resolved prefix dir and both engine search paths.
  ✓ specs/cli.md, README.md and docs/quickstart.md document TERMINAL_JAIL_RULES_DIR and the scope rule: specs/cli.md:297 (table row for TERMINAL_JAIL_RULES_DIR) and :300 (explicit 'Scope rule (DF-TERMINAL-JAIL-8)' paragraph); README.md:240-246 ('Rules follow the install scope' + TERMINAL_JAIL_RULES_DIR 'always wins'); docs/quickstart.md:296-299 (default vs prefix target + TERMINAL_JAIL_RULES_DIR override). All three document the variable and the scope rule.
  ✓ plugin test suite green and uvx ruff check reports no findings: `.venv/bin/pytest -q` -> '404 passed, 14 skipped in 9.27s' (exit 0); plugin/test_install.py alone -> '24 passed'. `uvx ruff check` -> 'All checks passed!' (exit 0). LSP diagnostics: 0 findings. Additionally confirmed the new regression tests genuinely fail against the pre-fix install.sh (2 failed: test_prefix_install_does_not_touch_home_rules, test_explicit_rules_dir_wins_over_install_scope) and pass against the fixed version.
All 8 criteria pass: install.sh implements the three-way prefix-scoped rules resolution with preserved backup semantics and a single honest warning, docs are updated, and the full plugin suite (404 passed) plus ruff are green.

Overall: PASS ✓
