# Verdict: DF-TERMINAL-JAIL-21

**Task:** install.sh --rule-pack aborts entire install without PyYAML
**Evaluated:** 2026-09-19T17:57:40.836512
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ Simulated no-PyYAML host: install.sh --rule-pack db leaves the wrapper installed with the pack skipped, stderr names PyYAML plus remedy, exit 2: Live reproduction: shadowed `yaml.py` (raises ImportError) on PATH, HOME=/tmp/tj21, `sh install.sh --rule-pack db` -> EXIT=2; /tmp/tj21/home/.local/bin/terminal-jail exists (26683 bytes) and 00-builtins.yaml installed; no terminal-jail-pack-db.yaml written; stderr: "terminal-jail installer: skipped: pack 'db' — PyYAML is required to parse YAML rule packs and was not found; install the distro package (Debian/Ubuntu: apt install python3-yaml, Fedora/RHEL: dnf install python3-yaml) or run pip install pyyaml, then re-run this installer" plus "SUMMARY — at least one requested rule pack was skipped; base install completed". Code: install.sh:355-365 (PyYAML preflight -> skip_rule_pack, return 0), install.sh:561-570 (end-of-run summary + exit 2).
  ✓ PyYAML-present host installs the db pack to the resolved rules dir with exit 0 unchanged: Live run with real PyYAML, HOME=/tmp/tj21b: `sh install.sh --rule-pack db` -> EXIT=0, stderr empty, stdout "installed rule pack 'db' to /tmp/tj21b/home/.config/terminal-jail/rules.d/terminal-jail-pack-db.yaml"; `cmp` against plugin/terminal_jail/rules/packs/db.yaml -> IDENTICAL; 00-builtins.yaml also present in the same resolved rules dir (install.sh:396-397, resolve_user_rules_dir at install.sh:270-290).
  ✓ README, quickstart and specs/cli.md document the PyYAML requirement and the skip-not-abort contract: README.md:484-497 — "A refusal is a loud skip, not an abort (DF-TERMINAL-JAIL-21) ... exits `2`" and "parsing a YAML pack additionally requires **PyYAML** (Debian/Ubuntu: `apt install python3-yaml`, Fedora/RHEL: `dnf install python3-yaml`, or `pip install pyyaml`) ... it never aborts the base install". docs/quickstart.md:47-54 — "needs `python3` with **PyYAML** ... is a **skip, not a failure**: the wrapper and default rules still install ... exits `2`". specs/cli.md:382 (flag table: "loud SKIP ... base install always completes, and the installer exits `2`") and specs/cli.md:422-432 (preflight probe `import yaml`, both remedies, JSON fallback, "skip, never abort").
  ✓ pytest plugin/test_install.py plugin/test_rule_packs.py green including the new no-PyYAML regression cells: `.venv/bin/python -m pytest plugin/test_install.py plugin/test_rule_packs.py -q --tb=short -p no:cacheprovider` -> exit_code 0, "71 passed in 4.07s". New regression cells collected and passing: test_install_with_no_pyyaml_skips_yaml_pack_but_installs_the_base (plugin/test_install.py:1478-1507), test_install_with_no_pyyaml_still_installs_a_plain_json_pack (:1514-1543), test_install_with_no_python3_skips_the_pack_but_installs_the_base (:1546-1572), test_install_malformed_pack_with_pyyaml_present_refuses_but_installs_base (:1576-1594); targeted run `-k "no_pyyaml or no_python3 or malformed"` -> "6 passed, 65 deselected". LSP diagnostics: 0 findings.
All four criteria verified with live installer runs (no-PyYAML host exits 2 with wrapper installed and pack skipped; PyYAML host exits 0 with the db pack byte-identical in the resolved rules dir), documentation in README/quickstart/specs/cli.md, and 71/71 pytest green including the new no-PyYAML regression cells.

## Summary

Judge Result: DF-TERMINAL-JAIL-21

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ Simulated no-PyYAML host: install.sh --rule-pack db leaves the wrapper installed with the pack skipped, stderr names PyYAML plus remedy, exit 2: Live reproduction: shadowed `yaml.py` (raises ImportError) on PATH, HOME=/tmp/tj21, `sh install.sh --rule-pack db` -> EXIT=2; /tmp/tj21/home/.local/bin/terminal-jail exists (26683 bytes) and 00-builtins.yaml installed; no terminal-jail-pack-db.yaml written; stderr: "terminal-jail installer: skipped: pack 'db' — PyYAML is required to parse YAML rule packs and was not found; install the distro package (Debian/Ubuntu: apt install python3-yaml, Fedora/RHEL: dnf install python3-yaml) or run pip install pyyaml, then re-run this installer" plus "SUMMARY — at least one requested rule pack was skipped; base install completed". Code: install.sh:355-365 (PyYAML preflight -> skip_rule_pack, return 0), install.sh:561-570 (end-of-run summary + exit 2).
  ✓ PyYAML-present host installs the db pack to the resolved rules dir with exit 0 unchanged: Live run with real PyYAML, HOME=/tmp/tj21b: `sh install.sh --rule-pack db` -> EXIT=0, stderr empty, stdout "installed rule pack 'db' to /tmp/tj21b/home/.config/terminal-jail/rules.d/terminal-jail-pack-db.yaml"; `cmp` against plugin/terminal_jail/rules/packs/db.yaml -> IDENTICAL; 00-builtins.yaml also present in the same resolved rules dir (install.sh:396-397, resolve_user_rules_dir at install.sh:270-290).
  ✓ README, quickstart and specs/cli.md document the PyYAML requirement and the skip-not-abort contract: README.md:484-497 — "A refusal is a loud skip, not an abort (DF-TERMINAL-JAIL-21) ... exits `2`" and "parsing a YAML pack additionally requires **PyYAML** (Debian/Ubuntu: `apt install python3-yaml`, Fedora/RHEL: `dnf install python3-yaml`, or `pip install pyyaml`) ... it never aborts the base install". docs/quickstart.md:47-54 — "needs `python3` with **PyYAML** ... is a **skip, not a failure**: the wrapper and default rules still install ... exits `2`". specs/cli.md:382 (flag table: "loud SKIP ... base install always completes, and the installer exits `2`") and specs/cli.md:422-432 (preflight probe `import yaml`, both remedies, JSON fallback, "skip, never abort").
  ✓ pytest plugin/test_install.py plugin/test_rule_packs.py green including the new no-PyYAML regression cells: `.venv/bin/python -m pytest plugin/test_install.py plugin/test_rule_packs.py -q --tb=short -p no:cacheprovider` -> exit_code 0, "71 passed in 4.07s". New regression cells collected and passing: test_install_with_no_pyyaml_skips_yaml_pack_but_installs_the_base (plugin/test_install.py:1478-1507), test_install_with_no_pyyaml_still_installs_a_plain_json_pack (:1514-1543), test_install_with_no_python3_skips_the_pack_but_installs_the_base (:1546-1572), test_install_malformed_pack_with_pyyaml_present_refuses_but_installs_base (:1576-1594); targeted run `-k "no_pyyaml or no_python3 or malformed"` -> "6 passed, 65 deselected". LSP diagnostics: 0 findings.
All four criteria verified with live installer runs (no-PyYAML host exits 2 with wrapper installed and pack skipped; PyYAML host exits 0 with the db pack byte-identical in the resolved rules dir), documentation in README/quickstart/specs/cli.md, and 71/71 pytest green including the new no-PyYAML regression cells.

Overall: PASS ✓
