# Verdict: tj-gap-032

**Task:** Sync shipped 00-builtins.yaml mirror with engine BUILTIN_* constants (TJ-GAP-032)
**Evaluated:** 2026-08-14T12:11:20.368834
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:10AM[0m [32mINF[0m [1mscanned ~8814227 bytes (8.81 MB) in 739ms[0m
[90m7:10AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ grep -c 'id:' plugin/terminal_jail/rules/00-builtins.yaml outputs 29 (11 blocklist): run_command grep -c 'id:' returned 29; header confirms 11 blocklist / 8 sandbox / 10 allow
  ✓ plugin/terminal_jail/rules/00-builtins.yaml header no longer says 27 rules: grep '27 rules' returns exit 1 (no match); header now reads 'These reflect the same 29 rules hardcoded in the Python engine'
  ✓ plugin/test_packaging.py contains a test asserting YAML rule IDs == engine builtin IDs (test_shipped_rules_yaml_mirrors_engine_builtin_ids): test_shipped_rules_yaml_mirrors_engine_builtin_ids defined at plugin/test_packaging.py:85, added in commit 9c3a5d1; asserts yaml_ids == engine_ids and per-layer counts vs BUILTIN_BLOCKLIST/SANDBOX/ALLOWLIST
  ✓ .venv/bin/python -m pytest -q passes (286 passed, 4 skipped): pytest run from plugin dir output: '286 passed, 4 skipped in 4.82s'
  ✓ gitreins guard passes 4/4: gitreins guard output: 'Tier 1 Guards: PASS' with secrets clean, lint ok, tests, static_analysis all green
  ✓ Commit addresses TJ-GAP-032 and includes Co-authored-by trailer: Commit 9c3a5d1 'fix: sync shipped 00-builtins.yaml mirror with engine BUILTIN_* constants (TJ-GAP-032)' includes 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' trailer
All 6 criteria verified: YAML mirror synced to 29 rules (11 blocklist), header updated, mirror-sync test added, pytest 286/4 green, gitreins guard 4/4, and commit 9c3a5d1 addresses TJ-GAP-032 with Co-authored-by trailer.

## Summary

Judge Result: tj-gap-032

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m7:10AM[0m [32mINF[0m [1mscanned ~8814227 bytes (8.81 MB) in 739ms[0m
[90m7:10AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ grep -c 'id:' plugin/terminal_jail/rules/00-builtins.yaml outputs 29 (11 blocklist): run_command grep -c 'id:' returned 29; header confirms 11 blocklist / 8 sandbox / 10 allow
  ✓ plugin/terminal_jail/rules/00-builtins.yaml header no longer says 27 rules: grep '27 rules' returns exit 1 (no match); header now reads 'These reflect the same 29 rules hardcoded in the Python engine'
  ✓ plugin/test_packaging.py contains a test asserting YAML rule IDs == engine builtin IDs (test_shipped_rules_yaml_mirrors_engine_builtin_ids): test_shipped_rules_yaml_mirrors_engine_builtin_ids defined at plugin/test_packaging.py:85, added in commit 9c3a5d1; asserts yaml_ids == engine_ids and per-layer counts vs BUILTIN_BLOCKLIST/SANDBOX/ALLOWLIST
  ✓ .venv/bin/python -m pytest -q passes (286 passed, 4 skipped): pytest run from plugin dir output: '286 passed, 4 skipped in 4.82s'
  ✓ gitreins guard passes 4/4: gitreins guard output: 'Tier 1 Guards: PASS' with secrets clean, lint ok, tests, static_analysis all green
  ✓ Commit addresses TJ-GAP-032 and includes Co-authored-by trailer: Commit 9c3a5d1 'fix: sync shipped 00-builtins.yaml mirror with engine BUILTIN_* constants (TJ-GAP-032)' includes 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' trailer
All 6 criteria verified: YAML mirror synced to 29 rules (11 blocklist), header updated, mirror-sync test added, pytest 286/4 green, gitreins guard 4/4, and commit 9c3a5d1 addresses TJ-GAP-032 with Co-authored-by trailer.

Overall: PASS ✓
