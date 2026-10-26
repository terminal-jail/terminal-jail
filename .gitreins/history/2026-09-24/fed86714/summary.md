# Verdict: TJ-DF-025

**Task:** install.sh --list-rule-packs must exit 0 when a shipped pack cannot be parsed (PyYAML-less host)
**Evaluated:** 2026-09-24T19:12:46.246385
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ on a host without PyYAML, install.sh --list-rule-packs exits 0 and lists the unreadable pack with a one-line skip reason; an explicit request for a specific unreadable pack still refuses non-zero; a --list-rule-packs && install.sh chain completes a full install; specs/cli.md wording matches the shipped behavior; the full plugin suite stays green: Live PyYAML-shadowed host (PATH shim whose yaml.py raises ImportError): `sh install.sh --list-rule-packs` -> EXIT=0 with exactly one stderr line `db: unreadable (cannot parse (PackParseError: PyYAML is not installed, so only plain-JSON rule documents can be read (Expecting value: line 1 column 1 (char 0))))` (scripts/rule-pack-tool.py cmd_list:416-441 catches PackParseError, prints `<name>: unreadable (<reason>)` and `continue`s, returns 0). Explicit request on the same host: `sh install.sh --rule-pack db` -> EXIT=2, `PyYAML is required to parse YAML rule packs and was not found` (install.sh:649-651), rules dir contains only 00-builtins.yaml (nothing written for the pack). Chain: `sh -c 'sh install.sh --list-rule-packs && sh install.sh'` -> EXIT=0, wrapper at bin2/terminal-jail and live2/00-builtins.yaml (full install completed). specs/cli.md:390 states the listing prints `<name> TAB <path> TAB <rule count>` and that an unparseable pack is reported as `<name>: unreadable (<reason>)` on stderr with exit 0 while an explicit `--rule-pack <name>` keeps the DF-21 refusal contract — matches shipped behavior (README.md:124 agrees). Tests: `plugin/test_install.py -k list_rule_packs` 3 passed; `plugin/test_rule_packs.py -k ListSkipNotRefuse` 4 passed; `plugin/test_install.py -k 'pyyaml or no_python3'` 5 passed; full plugin suite `.venv/bin/python -m pytest plugin/ -q` -> `1411 passed, 7 skipped in 71.95s` (exit 0). [resolution 0.21; install.sh, specs/cli.md]
install.sh --list-rule-packs now exits 0 with a one-line `db: unreadable (…PyYAML…)` skip on a PyYAML-less host, explicit --rule-pack db still exits 2, the && chain completes a full install, specs/cli.md matches, and the full plugin suite is green (1411 passed, 7 skipped).

## Summary

Judge Result: TJ-DF-025

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ on a host without PyYAML, install.sh --list-rule-packs exits 0 and lists the unreadable pack with a one-line skip reason; an explicit request for a specific unreadable pack still refuses non-zero; a --list-rule-packs && install.sh chain completes a full install; specs/cli.md wording matches the shipped behavior; the full plugin suite stays green: Live PyYAML-shadowed host (PATH shim whose yaml.py raises ImportError): `sh install.sh --list-rule-packs` -> EXIT=0 with exactly one stderr line `db: unreadable (cannot parse (PackParseError: PyYAML is not installed, so only plain-JSON rule documents can be read (Expecting value: line 1 column 1 (char 0))))` (scripts/rule-pack-tool.py cmd_list:416-441 catches PackParseError, prints `<name>: unreadable (<reason>)` and `continue`s, returns 0). Explicit request on the same host: `sh install.sh --rule-pack db` -> EXIT=2, `PyYAML is required to parse YAML rule packs and was not found` (install.sh:649-651), rules dir contains only 00-builtins.yaml (nothing written for the pack). Chain: `sh -c 'sh install.sh --list-rule-packs && sh install.sh'` -> EXIT=0, wrapper at bin2/terminal-jail and live2/00-builtins.yaml (full install completed). specs/cli.md:390 states the listing prints `<name> TAB <path> TAB <rule count>` and that an unparseable pack is reported as `<name>: unreadable (<reason>)` on stderr with exit 0 while an explicit `--rule-pack <name>` keeps the DF-21 refusal contract — matches shipped behavior (README.md:124 agrees). Tests: `plugin/test_install.py -k list_rule_packs` 3 passed; `plugin/test_rule_packs.py -k ListSkipNotRefuse` 4 passed; `plugin/test_install.py -k 'pyyaml or no_python3'` 5 passed; full plugin suite `.venv/bin/python -m pytest plugin/ -q` -> `1411 passed, 7 skipped in 71.95s` (exit 0). [resolution 0.21; install.sh, specs/cli.md]
install.sh --list-rule-packs now exits 0 with a one-line `db: unreadable (…PyYAML…)` skip on a PyYAML-less host, explicit --rule-pack db still exits 2, the && chain completes a full install, specs/cli.md matches, and the full plugin suite is green (1411 passed, 7 skipped).

Overall: PASS ✓
