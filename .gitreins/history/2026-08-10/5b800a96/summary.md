# Verdict: tj-df-005

**Task:** Fix README/quickstart/specs built-in rules documentation (TJ-DF-005)
**Evaluated:** 2026-08-10T18:33:15.499668
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m1:31PM[0m [32mINF[0m [1mscanned ~7358992 bytes (7.36 MB) in 824ms[0m
[90m1:31PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ Every rule listed in README Built-in Rules section exists in the engine (blocklist.py/sandbox.py/allowlist.py) with the stated action: All 29 README rules verified in engine: blocklist.py has builtin-kill-all/killpg-pid1/fork-bomb/rm-rf-root/dd-root/mkfs/fdisk/chmod-777-root/echo-to-system/curl-pipe-shell/sudo all action=block (lines 13-146); sandbox.py has auto-pytest/npm-test/go-test/make/pip/cargo/gcc/script all action=sandbox (lines 13-93); allowlist.py has allow-echo/ls/pwd/cat-safe/grep/find-safe/git-read/python-version/which/cd all action=allow (lines 12-87). Descriptions match README patterns.
  ✓ Engine rule counts documented as 11 blocklist + 8 sandbox + 10 allow (grep -c rule_id= per module): grep -c rule_id= confirms blocklist=11, sandbox=8, allowlist=10. README line 73 documents '11 critical blocklist, 8 auto-sandbox, 10 always-allow'; quickstart line 171 documents '29 built-in rules in the engine (11 blocklist + 8 auto-sandbox + 10 allow)'; integration.md lines 7/20/99 document '29 built-in rules'.
  ✓ README/docs/quickstart.md/specs/integration.md contain zero stale '27 built-in rules' or '27 total' claims: grep for '27 built-in|27 total|27 rules|27 Built-in' across all three files returned exit 1 (no matches). All remaining '27' occurrences are kernel version 7.0.0-27 (README:217, quickstart:130), not rule counts.
  ✓ chmod 000 / and sudo/su/mount/apt-as-sandbox fictions removed from README tables: README auto-sandbox list (lines 88-96) now shows pytest/npm/go/make/pip/cargo/gcc/script — no sudo/su/mount/apt/passwd fictions. chmod 000 / explicitly clarified as NOT blocked (line 84; builtin-chmod-777-root targets chmod 777). builtin-sudo is a legitimate blocklist rule (line 87). quickstart/integration mount/apt references are legitimate technical/install content, not sandbox fictions.
All four documentation-fix criteria verified: README/quickstart/specs now correctly document 29 built-in rules (11 blocklist + 8 sandbox + 10 allow) matching the engine, with zero stale '27' claims and all sandbox/chmod fictions removed.

## Summary

Judge Result: tj-df-005

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m1:31PM[0m [32mINF[0m [1mscanned ~7358992 bytes (7.36 MB) in 824ms[0m
[90m1:31PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ Every rule listed in README Built-in Rules section exists in the engine (blocklist.py/sandbox.py/allowlist.py) with the stated action: All 29 README rules verified in engine: blocklist.py has builtin-kill-all/killpg-pid1/fork-bomb/rm-rf-root/dd-root/mkfs/fdisk/chmod-777-root/echo-to-system/curl-pipe-shell/sudo all action=block (lines 13-146); sandbox.py has auto-pytest/npm-test/go-test/make/pip/cargo/gcc/script all action=sandbox (lines 13-93); allowlist.py has allow-echo/ls/pwd/cat-safe/grep/find-safe/git-read/python-version/which/cd all action=allow (lines 12-87). Descriptions match README patterns.
  ✓ Engine rule counts documented as 11 blocklist + 8 sandbox + 10 allow (grep -c rule_id= per module): grep -c rule_id= confirms blocklist=11, sandbox=8, allowlist=10. README line 73 documents '11 critical blocklist, 8 auto-sandbox, 10 always-allow'; quickstart line 171 documents '29 built-in rules in the engine (11 blocklist + 8 auto-sandbox + 10 allow)'; integration.md lines 7/20/99 document '29 built-in rules'.
  ✓ README/docs/quickstart.md/specs/integration.md contain zero stale '27 built-in rules' or '27 total' claims: grep for '27 built-in|27 total|27 rules|27 Built-in' across all three files returned exit 1 (no matches). All remaining '27' occurrences are kernel version 7.0.0-27 (README:217, quickstart:130), not rule counts.
  ✓ chmod 000 / and sudo/su/mount/apt-as-sandbox fictions removed from README tables: README auto-sandbox list (lines 88-96) now shows pytest/npm/go/make/pip/cargo/gcc/script — no sudo/su/mount/apt/passwd fictions. chmod 000 / explicitly clarified as NOT blocked (line 84; builtin-chmod-777-root targets chmod 777). builtin-sudo is a legitimate blocklist rule (line 87). quickstart/integration mount/apt references are legitimate technical/install content, not sandbox fictions.
All four documentation-fix criteria verified: README/quickstart/specs now correctly document 29 built-in rules (11 blocklist + 8 sandbox + 10 allow) matching the engine, with zero stale '27' claims and all sandbox/chmod fictions removed.

Overall: PASS ✓
