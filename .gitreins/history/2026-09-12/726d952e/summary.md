# Verdict: E2E-001-GAP-07

**Task:** Warm-start benchmark regression: rules loader re-parses 11KB builtins YAML with pure-Python safe_load on every intercept
**Evaluated:** 2026-09-12T11:49:10.785474
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m6:47AM[0m [32mINF[0m [1mscanned ~4025238 bytes (4.03 MB) in 301ms[0m
[90m6:47AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ plugin/terminal_jail/interruptor/rules.py prefers yaml.CSafeLoader when available with safe_load fallback: rules.py:186-189: `if hasattr(yaml, "CSafeLoader"): data = yaml.load(content, Loader=yaml.CSafeLoader) else: data = yaml.safe_load(content)`. Verified CSafeLoader present (yaml 6.0.3) and fallback path works: after `del yaml.CSafeLoader`, RuleLoader.load_all() still loaded 30 rules.
  ✓ warm-start benchmark (scripts/benchmark-interruptor.py) passes < 5ms with the full shipped builtins file in the user rules dir: Ran `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=<tmp with 00-builtins.yaml (11243 bytes)> python3 scripts/benchmark-interruptor.py --json`: warm_start_ms=1.022, warm_start_pass=true, all_pass=true. Confirmed regression is real: pure yaml.safe_load=9.42ms vs CSafeLoader=0.89ms on the same file.
  ✓ full suite passes (309+ passed, 13 skipped) and YAML/engine parity probe stays 30/30: `.venv/bin/python -m pytest -q` -> `310 passed, 13 skipped in 5.98s` (exit 0). `scripts/yaml-mirror-parity-probe.py` -> `[totals] block=12/12 sandbox=8/8 allow=10/10 total=30/30 -> OK` and `ALL PROBES PASS` (exit 0).
All three criteria verified: CSafeLoader preference with working safe_load fallback, warm-start benchmark at 1.022ms (<5ms) with the full builtins file in the user rules dir, and 310 passed/13 skipped plus 30/30 parity probe.

## Summary

Judge Result: E2E-001-GAP-07

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m6:47AM[0m [32mINF[0m [1mscanned ~4025238 bytes (4.03 MB) in 301ms[0m
[90m6:47AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ plugin/terminal_jail/interruptor/rules.py prefers yaml.CSafeLoader when available with safe_load fallback: rules.py:186-189: `if hasattr(yaml, "CSafeLoader"): data = yaml.load(content, Loader=yaml.CSafeLoader) else: data = yaml.safe_load(content)`. Verified CSafeLoader present (yaml 6.0.3) and fallback path works: after `del yaml.CSafeLoader`, RuleLoader.load_all() still loaded 30 rules.
  ✓ warm-start benchmark (scripts/benchmark-interruptor.py) passes < 5ms with the full shipped builtins file in the user rules dir: Ran `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=<tmp with 00-builtins.yaml (11243 bytes)> python3 scripts/benchmark-interruptor.py --json`: warm_start_ms=1.022, warm_start_pass=true, all_pass=true. Confirmed regression is real: pure yaml.safe_load=9.42ms vs CSafeLoader=0.89ms on the same file.
  ✓ full suite passes (309+ passed, 13 skipped) and YAML/engine parity probe stays 30/30: `.venv/bin/python -m pytest -q` -> `310 passed, 13 skipped in 5.98s` (exit 0). `scripts/yaml-mirror-parity-probe.py` -> `[totals] block=12/12 sandbox=8/8 allow=10/10 total=30/30 -> OK` and `ALL PROBES PASS` (exit 0).
All three criteria verified: CSafeLoader preference with working safe_load fallback, warm-start benchmark at 1.022ms (<5ms) with the full builtins file in the user rules dir, and 310 passed/13 skipped plus 30/30 parity probe.

Overall: PASS ✓
