# Verdict: TJ-DF-034

**Task:** Add --rule-pack-file path to install.sh
**Evaluated:** 2026-09-30T06:17:41.038585
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh --rule-pack <name> only accepts packs shipped in plugin/terminal_jail/rules/packs/. Add a new flag --rule-pack-file <path> that: (1) validates the pack with rule-pack-tool.py validate <path>, (2) byte-copies it to the resolved rules dir (same destination as --rule-pack), (3) adds a symmetric --uninstall-rule-pack-file <path> that removes the installed copy. Document both flags in README.md under the rule-pack section. Add a test in scripts/test_install.sh (or extend the existing install test) that creates a temp pack file, installs it with --rule-pack-file, verifies it landed in the rules dir, then uninstalls it. Run the test and confirm it passes.: install.sh: --rule-pack-file parsed (add_rule_pack_file, ~line 230) and installed by install_rule_pack_file (~line 940) which runs `python3 "$pack_tool" validate "$pack_file" --pack-name "$pack_name" --rules-dir "$RESOLVED_RULES_DIR"` then `cp -- "$pack_file" "$pack_dest"` where pack_dest=${RESOLVED_RULES_DIR}/terminal-jail-pack-<name>.yaml (identical destination to --rule-pack). Symmetric --uninstall-rule-pack-file (uninstall_rule_pack_file, ~line 1000) removes that copy and exits 1 when nothing is installed. README.md lines 120-131 document both flags under the rule-pack section ('Externally-authored pack files (--rule-pack-file)'). Test plugin/test_install.py:1643 test_rule_pack_file_install_then_uninstall_round_trip creates a temp pack, installs with --rule-pack-file, asserts the byte-identical copy landed in the rules dir, then uninstalls. Ran `.venv/bin/python -m pytest plugin/test_install.py -k "rule_pack_file or rule_pack" -v` => exit 0, '17 passed, 55 deselected'; full file `.venv/bin/python -m pytest plugin/test_install.py -q` => '72 passed in 27.98s'. Independent manual e2e: validator printed "rule-pack-tool: pack 'my-pack' valid", `cmp` => BYTE-IDENTICAL, uninstall removed only the pack (00-builtins.yaml survived). LSP diagnostics: 0 findings. [resolution 0.06; install.sh, rule-pack-tool.py, README.md, scripts/test_install.sh]
All sub-requirements of TJ-DF-034 are implemented and verified: --rule-pack-file validates via rule-pack-tool.py, byte-copies to the same resolved rules dir, --uninstall-rule-pack-file removes the copy, both flags are documented in README.md, and the round-trip test passes (17/17 rule-pack tests, 72/72 install tests).

## Summary

Judge Result: TJ-DF-034

Stage tier1: FAIL
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out

Stage tier2: PASS
  COMPLETE
  ✓ install.sh --rule-pack <name> only accepts packs shipped in plugin/terminal_jail/rules/packs/. Add a new flag --rule-pack-file <path> that: (1) validates the pack with rule-pack-tool.py validate <path>, (2) byte-copies it to the resolved rules dir (same destination as --rule-pack), (3) adds a symmetric --uninstall-rule-pack-file <path> that removes the installed copy. Document both flags in README.md under the rule-pack section. Add a test in scripts/test_install.sh (or extend the existing install test) that creates a temp pack file, installs it with --rule-pack-file, verifies it landed in the rules dir, then uninstalls it. Run the test and confirm it passes.: install.sh: --rule-pack-file parsed (add_rule_pack_file, ~line 230) and installed by install_rule_pack_file (~line 940) which runs `python3 "$pack_tool" validate "$pack_file" --pack-name "$pack_name" --rules-dir "$RESOLVED_RULES_DIR"` then `cp -- "$pack_file" "$pack_dest"` where pack_dest=${RESOLVED_RULES_DIR}/terminal-jail-pack-<name>.yaml (identical destination to --rule-pack). Symmetric --uninstall-rule-pack-file (uninstall_rule_pack_file, ~line 1000) removes that copy and exits 1 when nothing is installed. README.md lines 120-131 document both flags under the rule-pack section ('Externally-authored pack files (--rule-pack-file)'). Test plugin/test_install.py:1643 test_rule_pack_file_install_then_uninstall_round_trip creates a temp pack, installs with --rule-pack-file, asserts the byte-identical copy landed in the rules dir, then uninstalls. Ran `.venv/bin/python -m pytest plugin/test_install.py -k "rule_pack_file or rule_pack" -v` => exit 0, '17 passed, 55 deselected'; full file `.venv/bin/python -m pytest plugin/test_install.py -q` => '72 passed in 27.98s'. Independent manual e2e: validator printed "rule-pack-tool: pack 'my-pack' valid", `cmp` => BYTE-IDENTICAL, uninstall removed only the pack (00-builtins.yaml survived). LSP diagnostics: 0 findings. [resolution 0.06; install.sh, rule-pack-tool.py, README.md, scripts/test_install.sh]
All sub-requirements of TJ-DF-034 are implemented and verified: --rule-pack-file validates via rule-pack-tool.py, byte-copies to the same resolved rules dir, --uninstall-rule-pack-file removes the copy, both flags are documented in README.md, and the round-trip test passes (17/17 rule-pack tests, 72/72 install tests).

Overall: FAIL ✗
