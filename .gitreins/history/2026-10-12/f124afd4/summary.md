# Verdict: QA-TERMINAL-JAIL-18

**Task:** Update test expectations for Landlock tier payload shape
**Evaluated:** 2026-10-12T02:48:48.973643
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ 15+ test_interruptor/test_host_probes tests pin pre-tier Landlock payload shape; suite red where standalone/landlock-loader.py is reachable. Fix: update test expectations to match current landlock-loader -- <cmd> payload shape. PASS: pytest plugin/test_interruptor.py plugin/test_host_probes.py all pass where landlock-loader is reachable.: Loader IS reachable in this checkout: `landlock.sandbox_prefix()` returns 'python3 /home/kara/terminal-jail/standalone/landlock-loader.py -- ' (parent /home/kara is drwxr-x--x = o+x), so tests run in the required condition. RED-BEFORE: running the pre-fix files (git show 208287f^) against the current engine gives 13 failed/504 passed in plugin/test_interruptor.py (TestSandboxPipelineReconstruction x8, TestSandboxReconstructionRefusal x3, TestUserRules::test_user_modify_rule_wraps_in_unshare) and 2 failed/20 passed in plugin/test_host_probes.py (TestJailedProbesThroughCli pidns/fs probes, exit 126 Permission denied) = 15 failures, matching the '15+' claim; failure text shows expected "'danger-tool --wipe'" vs got "'python3 /home/kara/terminal-jail/standalone/landlock-loader.py -- danger-tool --wipe'". GREEN-AFTER (commit 208287f adds mask_landlock_tails() + _PAYLOAD_LANDLOCK_TAIL_RE and applies the mask to every pinned expectation, plus new TestLandlockTierShapes and TestTierComposedProbeThroughCli): `.venv/bin/python -m pytest plugin/test_interruptor.py plugin/test_host_probes.py -q` -> '545 passed in 4.68s' (exit 0); `-m integration` -> '4 passed, 541 deselected' including TestTierComposedProbeThroughCli::test_probes_survive_the_composed_tier_launch PASSED; `-k LandlockTierShapes` -> 3 passed. Full suite via config test_command -> '1945 passed, 10 skipped in 195.81s', zero failures. LSP diagnostics: 0 findings. Files were restored to HEAD after the red-before experiment (git status plugin/ clean). [resolution 0.23; standalone/landlock-loader.py, plugin/test_interruptor.py, plugin/test_host_probes.py]


## Summary

Judge Result: QA-TERMINAL-JAIL-18

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ 15+ test_interruptor/test_host_probes tests pin pre-tier Landlock payload shape; suite red where standalone/landlock-loader.py is reachable. Fix: update test expectations to match current landlock-loader -- <cmd> payload shape. PASS: pytest plugin/test_interruptor.py plugin/test_host_probes.py all pass where landlock-loader is reachable.: Loader IS reachable in this checkout: `landlock.sandbox_prefix()` returns 'python3 /home/kara/terminal-jail/standalone/landlock-loader.py -- ' (parent /home/kara is drwxr-x--x = o+x), so tests run in the required condition. RED-BEFORE: running the pre-fix files (git show 208287f^) against the current engine gives 13 failed/504 passed in plugin/test_interruptor.py (TestSandboxPipelineReconstruction x8, TestSandboxReconstructionRefusal x3, TestUserRules::test_user_modify_rule_wraps_in_unshare) and 2 failed/20 passed in plugin/test_host_probes.py (TestJailedProbesThroughCli pidns/fs probes, exit 126 Permission denied) = 15 failures, matching the '15+' claim; failure text shows expected "'danger-tool --wipe'" vs got "'python3 /home/kara/terminal-jail/standalone/landlock-loader.py -- danger-tool --wipe'". GREEN-AFTER (commit 208287f adds mask_landlock_tails() + _PAYLOAD_LANDLOCK_TAIL_RE and applies the mask to every pinned expectation, plus new TestLandlockTierShapes and TestTierComposedProbeThroughCli): `.venv/bin/python -m pytest plugin/test_interruptor.py plugin/test_host_probes.py -q` -> '545 passed in 4.68s' (exit 0); `-m integration` -> '4 passed, 541 deselected' including TestTierComposedProbeThroughCli::test_probes_survive_the_composed_tier_launch PASSED; `-k LandlockTierShapes` -> 3 passed. Full suite via config test_command -> '1945 passed, 10 skipped in 195.81s', zero failures. LSP diagnostics: 0 findings. Files were restored to HEAD after the red-before experiment (git status plugin/ clean). [resolution 0.23; standalone/landlock-loader.py, plugin/test_interruptor.py, plugin/test_host_probes.py]


Overall: PASS ✓
