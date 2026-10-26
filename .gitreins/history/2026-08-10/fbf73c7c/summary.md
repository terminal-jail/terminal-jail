# Verdict: tj-df-005

**Task:** Fix README/quickstart/specs built-in rules documentation (TJ-DF-005)
**Evaluated:** 2026-08-10T18:31:34.976878
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m1:29PM[0m [32mINF[0m [1mscanned ~7358992 bytes (7.36 MB) in 861ms[0m
[90m1:29PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ Every rule listed in README Built-in Rules section exists in the engine (blocklist.py/sandbox.py/allowlist.py) with the stated action: README lists 11 blocklist rules (builtin-kill-all...builtin-sudo) all present in blocklist.py with action=block/priority=1000; 8 sandbox rules (auto-pytest...auto-script) all in sandbox.py with action=sandbox; 10 allow rules (allow-echo...allow-cd) all in allowlist.py with action=allow. Rule IDs and actions match engine exactly.
  ✓ Engine rule counts documented as 11 blocklist + 8 sandbox + 10 allow (grep -c rule_id= per module): grep -c rule_id= returns 11 (blocklist.py), 8 (sandbox.py), 10 (allowlist.py). README documents '11 critical blocklist, 8 auto-sandbox, 10 always-allow' and '29 total'.
  ✓ README/docs/quickstart.md/specs/integration.md contain zero stale '27 built-in rules' or '27 total' claims: grep for '27 built-in|27 total|27 rules' in README.md, docs/quickstart.md, specs/integration.md all return no matches (exit 1). All updated to 29.
  ✓ chmod 000 / and sudo/su/mount/apt-as-sandbox fictions removed from README tables: README Auto-Sandbox section now lists the correct 8 rules (auto-pytest/npm-test/go-test/make/pip/cargo/gcc/script); builtin-chmod-777-root explicitly states 'chmod 000 /' is NOT blocked. Old README fictions (chmod 000 /, sudo/su/mount/apt as sandbox) removed. Full suite green: 274 passed, 4 skipped.
All 4 criteria verified: README/quickstart/specs now document the correct 29 built-in rules (11 blocklist + 8 sandbox + 10 allow) matching the engine, with no stale '27' claims and all chmod-000/sudo/su/mount/apt fictions removed.

## Summary

Judge Result: tj-df-005

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m1:29PM[0m [32mINF[0m [1mscanned ~7358992 bytes (7.36 MB) in 861ms[0m
[90m1:29PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ Every rule listed in README Built-in Rules section exists in the engine (blocklist.py/sandbox.py/allowlist.py) with the stated action: README lists 11 blocklist rules (builtin-kill-all...builtin-sudo) all present in blocklist.py with action=block/priority=1000; 8 sandbox rules (auto-pytest...auto-script) all in sandbox.py with action=sandbox; 10 allow rules (allow-echo...allow-cd) all in allowlist.py with action=allow. Rule IDs and actions match engine exactly.
  ✓ Engine rule counts documented as 11 blocklist + 8 sandbox + 10 allow (grep -c rule_id= per module): grep -c rule_id= returns 11 (blocklist.py), 8 (sandbox.py), 10 (allowlist.py). README documents '11 critical blocklist, 8 auto-sandbox, 10 always-allow' and '29 total'.
  ✓ README/docs/quickstart.md/specs/integration.md contain zero stale '27 built-in rules' or '27 total' claims: grep for '27 built-in|27 total|27 rules' in README.md, docs/quickstart.md, specs/integration.md all return no matches (exit 1). All updated to 29.
  ✓ chmod 000 / and sudo/su/mount/apt-as-sandbox fictions removed from README tables: README Auto-Sandbox section now lists the correct 8 rules (auto-pytest/npm-test/go-test/make/pip/cargo/gcc/script); builtin-chmod-777-root explicitly states 'chmod 000 /' is NOT blocked. Old README fictions (chmod 000 /, sudo/su/mount/apt as sandbox) removed. Full suite green: 274 passed, 4 skipped.
All 4 criteria verified: README/quickstart/specs now document the correct 29 built-in rules (11 blocklist + 8 sandbox + 10 allow) matching the engine, with no stale '27' claims and all chmod-000/sudo/su/mount/apt fictions removed.

Overall: PASS ✓
