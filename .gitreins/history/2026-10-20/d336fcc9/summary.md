# Verdict: TJ-DF-051

**Task:** Fix composed-mode egress double report
**Evaluated:** 2026-10-20T23:02:18.490853
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✗ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE
  ✗ On a composed launch with TERMINAL_JAIL_LANDLOCK_NET=1 and a 0750 ancestor, the stderr contract must never contain both the Landlock network not-applied warning and the kernel egress tier APPLIED line; invalid allowlist input must emit exactly one named-cause degradation line; add a regression test for the composed/0750 shape and preserve the existing egress behavior.: No source or test change was made — the only diff is the board row in .gitreins/tasks.yaml (TJ-DF-051 marked complete) plus .coding-hermes/board/tasks.jsonl. The defect mechanism is unchanged: landlock_net.py:727-731 _compute_sandbox_prefix still calls _degrade("...not reachable ... 0700/0750 home") from the engine (nobody-uid assumption) while standalone/terminal-jail:1109 _tj_egress_tier_decide --here runs in owner context, attaches, and landlock-net-loader.py:125 prints kernel_denial_notice — so both the not-applied warning and the APPLIED line can still appear. The invalid-allowlist double report also persists: engine probe child landlock_net.py:659-663 returns "FAIL invalid allowlist token 'x'" -> _degrade prints a wrapper-style line, and loader apply_net_tier (landlock_net.py:561-565) returns the cause -> landlock-net-loader.py:114-121 prints a second line with a different cause (two lines, two causes). No regression test for the composed/0750 shape exists (grep for TJ-DF-051 finds only tasks.yaml, docs/dogfood report, and skills doc; no test file). Targeted run of existing tests (test_tjdf046_egress_allow_path.py + test_landlock_net.py) gives 65 passed, 1 skipped, but those tests do not cover the composed/0750 contract, so the criterion is unmet.
The task was only marked complete on the board; no code or regression test was added and both the composed/0750 double-report and the invalid-allowlist double-line defects remain in the source.

## Summary

Judge Result: TJ-DF-051

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✗ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE
  ✗ On a composed launch with TERMINAL_JAIL_LANDLOCK_NET=1 and a 0750 ancestor, the stderr contract must never contain both the Landlock network not-applied warning and the kernel egress tier APPLIED line; invalid allowlist input must emit exactly one named-cause degradation line; add a regression test for the composed/0750 shape and preserve the existing egress behavior.: No source or test change was made — the only diff is the board row in .gitreins/tasks.yaml (TJ-DF-051 marked complete) plus .coding-hermes/board/tasks.jsonl. The defect mechanism is unchanged: landlock_net.py:727-731 _compute_sandbox_prefix still calls _degrade("...not reachable ... 0700/0750 home") from the engine (nobody-uid assumption) while standalone/terminal-jail:1109 _tj_egress_tier_decide --here runs in owner context, attaches, and landlock-net-loader.py:125 prints kernel_denial_notice — so both the not-applied warning and the APPLIED line can still appear. The invalid-allowlist double report also persists: engine probe child landlock_net.py:659-663 returns "FAIL invalid allowlist token 'x'" -> _degrade prints a wrapper-style line, and loader apply_net_tier (landlock_net.py:561-565) returns the cause -> landlock-net-loader.py:114-121 prints a second line with a different cause (two lines, two causes). No regression test for the composed/0750 shape exists (grep for TJ-DF-051 finds only tasks.yaml, docs/dogfood report, and skills doc; no test file). Targeted run of existing tests (test_tjdf046_egress_allow_path.py + test_landlock_net.py) gives 65 passed, 1 skipped, but those tests do not cover the composed/0750 contract, so the criterion is unmet.
The task was only marked complete on the board; no code or regression test was added and both the composed/0750 double-report and the invalid-allowlist double-line defects remain in the source.

Overall: FAIL ✗
