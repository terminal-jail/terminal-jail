# Verdict: tj-gap-032

**Task:** Sync shipped 00-builtins.yaml mirror with engine BUILTIN_* constants (TJ-GAP-032)
**Evaluated:** 2026-08-14T12:10:21.747889
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:09AM[0m [32mINF[0m [1mscanned ~8814227 bytes (8.81 MB) in 696ms[0m
[90m7:09AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ grep -c 'id:' plugin/terminal_jail/rules/00-builtins.yaml outputs 29 (11 blocklist): grep -c 'id:' plugin/terminal_jail/rules/00-builtins.yaml outputs 29
  ✓ plugin/terminal_jail/rules/00-builtins.yaml header no longer says 27 rules: Header says 'These reflect the same 29 rules hardcoded in the Python engine (11 blocklist / 8 sandbox / 10 allow)'; grep for '27' returns empty
  ✓ plugin/test_packaging.py contains a test asserting YAML rule IDs == engine builtin IDs (test_shipped_rules_yaml_mirrors_engine_builtin_ids): plugin/test_packaging.py:85 defines test_shipped_rules_yaml_mirrors_engine_builtin_ids asserting yaml_ids == engine_ids and per-layer counts (11/8/10) against BUILTIN_BLOCKLIST/SANDBOX/ALLOWLIST
  ✓ .venv/bin/python -m pytest -q passes (286 passed, 4 skipped): Actual output: '286 passed, 4 skipped in 4.81s'
  ✓ gitreins guard passes 4/4: gitreins guard => 'Tier 1 Guards: PASS' with secrets, lint, tests, static_analysis all checkmarked
  ✓ Commit addresses TJ-GAP-032 and includes Co-authored-by trailer: Commit 9c3a5d1 title 'fix: sync shipped 00-builtins.yaml mirror with engine BUILTIN_* constants (TJ-GAP-032)'; body includes 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' (grep -c = 1)
All 6 criteria verified: YAML mirror has 29 ids, header updated, sync test added, pytest 286/4 green, gitreins guard 4/4, and commit references TJ-GAP-032 with Co-authored-by trailer.

## Summary

Judge Result: tj-gap-032

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:09AM[0m [32mINF[0m [1mscanned ~8814227 bytes (8.81 MB) in 696ms[0m
[90m7:09AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ grep -c 'id:' plugin/terminal_jail/rules/00-builtins.yaml outputs 29 (11 blocklist): grep -c 'id:' plugin/terminal_jail/rules/00-builtins.yaml outputs 29
  ✓ plugin/terminal_jail/rules/00-builtins.yaml header no longer says 27 rules: Header says 'These reflect the same 29 rules hardcoded in the Python engine (11 blocklist / 8 sandbox / 10 allow)'; grep for '27' returns empty
  ✓ plugin/test_packaging.py contains a test asserting YAML rule IDs == engine builtin IDs (test_shipped_rules_yaml_mirrors_engine_builtin_ids): plugin/test_packaging.py:85 defines test_shipped_rules_yaml_mirrors_engine_builtin_ids asserting yaml_ids == engine_ids and per-layer counts (11/8/10) against BUILTIN_BLOCKLIST/SANDBOX/ALLOWLIST
  ✓ .venv/bin/python -m pytest -q passes (286 passed, 4 skipped): Actual output: '286 passed, 4 skipped in 4.81s'
  ✓ gitreins guard passes 4/4: gitreins guard => 'Tier 1 Guards: PASS' with secrets, lint, tests, static_analysis all checkmarked
  ✓ Commit addresses TJ-GAP-032 and includes Co-authored-by trailer: Commit 9c3a5d1 title 'fix: sync shipped 00-builtins.yaml mirror with engine BUILTIN_* constants (TJ-GAP-032)'; body includes 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' (grep -c = 1)
All 6 criteria verified: YAML mirror has 29 ids, header updated, sync test added, pytest 286/4 green, gitreins guard 4/4, and commit references TJ-GAP-032 with Co-authored-by trailer.

Overall: PASS ✓
