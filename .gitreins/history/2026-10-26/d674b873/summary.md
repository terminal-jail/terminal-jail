# Verdict: QA-TERMINAL-JAIL-21

**Task:** Fix private-proc demand battery divergence
**Evaluated:** 2026-10-26T00:04:42.829842
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE
  ✗ The private-proc demand battery changes must pass plugin/test_private_proc_demand.py, the full suite, ruff check and format, and preserve honest KNOWN-LIMIT behavior for composed hosts; the landed commit must be pushed and origin parity must be zero.: Test/lint/KNOWN-LIMIT halves PASS, but the push/parity half FAILS. Evidence: (a) plugin/test_private_proc_demand.py — HEAD a96a355: `20 passed in 5.08s`; fix branch b9abd50: `22 passed in 6.04s`. (b) Full suite — HEAD: `2055 passed, 15 skipped in 183.54s`; branch b9abd50: `2057 passed, 15 skipped in 186.53s` (exit 0 both). (c) ruff — `.venv/bin/python -m ruff check .` -> CHECK_RC=0 'All checks passed!'; `ruff format --check .` -> FMT_RC=0 '154 files already formatted' (both trees). (d) KNOWN-LIMIT honesty preserved: b9abd50 adds scripts/backend-parity-battery.py `_proc_view_pair_ok` accepting `proc_view=platform-owned` on composed hosts while still rejecting `proc_view=none`/missing/rc!=0, cell 5b refusal -> KNOWN-LIMIT/UNMEASURED, cells 1-2 UNMEASURED must be KNOWN-LIMIT; pinned by new tests `test_battery_cell9_verdict_accepts_composed_host_attribution` and `test_battery_live_slice_refusal_is_known_limit_not_divergence`; live runs: backend-parity-battery rc=0 'zero unexplained divergences' with DIFFERS=[] (cell 8 FAIL-CLOSED-PROVEN, cell 9 SAME, cell 2 KNOWN-LIMIT), composed-mode-battery '3/3 PASS, 0 UNAVAILABLE'. (e) PUSH/PARITY FAILS: the landed fix commit b9abd50 ('fix(battery): parity battery accepts composed-host truths... Addresses QA-TERMINAL-JAIL-21') is NOT an ancestor of HEAD (`git merge-base --is-ancestor b9abd50 HEAD` -> NOT-ANCESTOR) and NOT in origin/main (`--is-ancestor b9abd50 origin/main` -> NOT-IN-ORIGIN). It exists only on branch wt/QA-TERMINAL-JAIL-21 (local + origin/wt/QA-TERMINAL-JAIL-21); `git rev-list --left-right --count origin/main...origin/wt/QA-TERMINAL-JAIL-21` = `1 1` (branch 1 ahead, 1 behind). HEAD...origin/main = `0 0` only because the work never landed on main — the working tree at HEAD still contains the OLD battery code (grep `_proc_view_pair_ok` in HEAD scripts/backend-parity-battery.py = 0 matches) and the OLD test file (grep `test_battery_cell9_verdict_accepts_composed_host_attribution` = 0 matches), while the branch worktree has both (2 and 1 matches). The task's own diff is only the .gitreins/tasks.yaml board row marking the task complete — no code change is on main. So the landed commit is not pushed to main and origin parity for the landed work is not zero.
The battery fix passes its test file, the full suite, ruff check/format and keeps honest KNOWN-LIMIT composed-host behavior, but the fix commit b9abd50 was never merged/pushed to main (it lives only on wt/QA-TERMINAL-JAIL-21, 1 ahead / 1 behind origin/main), so the push-and-zero-parity requirement fails.

## Summary

Judge Result: QA-TERMINAL-JAIL-21

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE
  ✗ The private-proc demand battery changes must pass plugin/test_private_proc_demand.py, the full suite, ruff check and format, and preserve honest KNOWN-LIMIT behavior for composed hosts; the landed commit must be pushed and origin parity must be zero.: Test/lint/KNOWN-LIMIT halves PASS, but the push/parity half FAILS. Evidence: (a) plugin/test_private_proc_demand.py — HEAD a96a355: `20 passed in 5.08s`; fix branch b9abd50: `22 passed in 6.04s`. (b) Full suite — HEAD: `2055 passed, 15 skipped in 183.54s`; branch b9abd50: `2057 passed, 15 skipped in 186.53s` (exit 0 both). (c) ruff — `.venv/bin/python -m ruff check .` -> CHECK_RC=0 'All checks passed!'; `ruff format --check .` -> FMT_RC=0 '154 files already formatted' (both trees). (d) KNOWN-LIMIT honesty preserved: b9abd50 adds scripts/backend-parity-battery.py `_proc_view_pair_ok` accepting `proc_view=platform-owned` on composed hosts while still rejecting `proc_view=none`/missing/rc!=0, cell 5b refusal -> KNOWN-LIMIT/UNMEASURED, cells 1-2 UNMEASURED must be KNOWN-LIMIT; pinned by new tests `test_battery_cell9_verdict_accepts_composed_host_attribution` and `test_battery_live_slice_refusal_is_known_limit_not_divergence`; live runs: backend-parity-battery rc=0 'zero unexplained divergences' with DIFFERS=[] (cell 8 FAIL-CLOSED-PROVEN, cell 9 SAME, cell 2 KNOWN-LIMIT), composed-mode-battery '3/3 PASS, 0 UNAVAILABLE'. (e) PUSH/PARITY FAILS: the landed fix commit b9abd50 ('fix(battery): parity battery accepts composed-host truths... Addresses QA-TERMINAL-JAIL-21') is NOT an ancestor of HEAD (`git merge-base --is-ancestor b9abd50 HEAD` -> NOT-ANCESTOR) and NOT in origin/main (`--is-ancestor b9abd50 origin/main` -> NOT-IN-ORIGIN). It exists only on branch wt/QA-TERMINAL-JAIL-21 (local + origin/wt/QA-TERMINAL-JAIL-21); `git rev-list --left-right --count origin/main...origin/wt/QA-TERMINAL-JAIL-21` = `1 1` (branch 1 ahead, 1 behind). HEAD...origin/main = `0 0` only because the work never landed on main — the working tree at HEAD still contains the OLD battery code (grep `_proc_view_pair_ok` in HEAD scripts/backend-parity-battery.py = 0 matches) and the OLD test file (grep `test_battery_cell9_verdict_accepts_composed_host_attribution` = 0 matches), while the branch worktree has both (2 and 1 matches). The task's own diff is only the .gitreins/tasks.yaml board row marking the task complete — no code change is on main. So the landed commit is not pushed to main and origin parity for the landed work is not zero.
The battery fix passes its test file, the full suite, ruff check/format and keeps honest KNOWN-LIMIT composed-host behavior, but the fix commit b9abd50 was never merged/pushed to main (it lives only on wt/QA-TERMINAL-JAIL-21, 1 ahead / 1 behind origin/main), so the push-and-zero-parity requirement fails.

Overall: FAIL ✗
