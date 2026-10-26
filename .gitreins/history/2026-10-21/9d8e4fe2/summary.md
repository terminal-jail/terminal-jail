# Verdict: INT-CI-011

**Task:** Fix CI test failures: broaden error message assertions for cross-environment compatibility
**Evaluated:** 2026-10-21T16:40:19.265859
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✗ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ CI Python 3.11/3.12/3.13 lanes fail on two assertions that hardcode environment-specific error messages ('cannot read', 'not found') instead of accepting the union of all valid degradation messages (also 'not reachable'). Fix: use the same multi-needle pattern from test_modify_path_unreadable_loader_degrades_before_composition in the two failing tests.: Commit 1ce4200 broadens exactly the two CI-failing assertions to the multi-needle any() pattern. (1) plugin/test_tjdf046_egress_allow_path.py:502-527 (test_unreadable_loader_degrades_loudly): `assert "cannot read" in result.stderr` replaced by `assert any(needle in result.stderr for needle in ("cannot read", "not readable", "not reachable", "cannot be inspected", "lacks o+x"))` — the identical needle set used by test_modify_path_unreadable_loader_degrades_before_composition at lines 488-499. (2) plugin/test_tjdf047_plain_allow_degrade.py:225-248 (test_missing_loader_degrades_on_the_plain_allow_launch): `assert "not found" in result.stderr` replaced by `assert any(needle in result.stderr for needle in ("not found", "not reachable", "not readable", "missing"))`. These are precisely the two tests the board names as the CI failures (.coding-hermes/board/tasks.jsonl:291 foreman_note, run 39574929653: 'test_unreadable_loader_degrades_loudly (asserts cannot read in stderr)' and 'test_missing_loader_degrades_on_the_plain_allow_launch (asserts not found in stderr)', with actual CI stderr 'landlock-net-loader.py is not reachable by the launch payload' — now accepted by both patterns). The 'not reachable' wording is real: plugin/terminal_jail/interruptor/landlock_net.py:765 and landlock.py:1312 emit it. Test evidence: `.venv/bin/python -m pytest plugin/test_tjdf046_egress_allow_path.py plugin/test_tjdf047_plain_allow_degrade.py -x --tb=short -q` -> exit_code 0, '38 passed, 1 skipped in 10.47s'; focused run of the two changed tests -> exit_code 0, '2 passed in 0.46s'.
Both CI-failing assertions were converted to the same multi-needle any() pattern used by test_modify_path_unreadable_loader_degrades_before_composition, accepting 'not reachable' and the other valid degradation messages, and the affected suites pass locally (38 passed, 1 skipped).

## Summary

Judge Result: INT-CI-011

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✗ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ CI Python 3.11/3.12/3.13 lanes fail on two assertions that hardcode environment-specific error messages ('cannot read', 'not found') instead of accepting the union of all valid degradation messages (also 'not reachable'). Fix: use the same multi-needle pattern from test_modify_path_unreadable_loader_degrades_before_composition in the two failing tests.: Commit 1ce4200 broadens exactly the two CI-failing assertions to the multi-needle any() pattern. (1) plugin/test_tjdf046_egress_allow_path.py:502-527 (test_unreadable_loader_degrades_loudly): `assert "cannot read" in result.stderr` replaced by `assert any(needle in result.stderr for needle in ("cannot read", "not readable", "not reachable", "cannot be inspected", "lacks o+x"))` — the identical needle set used by test_modify_path_unreadable_loader_degrades_before_composition at lines 488-499. (2) plugin/test_tjdf047_plain_allow_degrade.py:225-248 (test_missing_loader_degrades_on_the_plain_allow_launch): `assert "not found" in result.stderr` replaced by `assert any(needle in result.stderr for needle in ("not found", "not reachable", "not readable", "missing"))`. These are precisely the two tests the board names as the CI failures (.coding-hermes/board/tasks.jsonl:291 foreman_note, run 39574929653: 'test_unreadable_loader_degrades_loudly (asserts cannot read in stderr)' and 'test_missing_loader_degrades_on_the_plain_allow_launch (asserts not found in stderr)', with actual CI stderr 'landlock-net-loader.py is not reachable by the launch payload' — now accepted by both patterns). The 'not reachable' wording is real: plugin/terminal_jail/interruptor/landlock_net.py:765 and landlock.py:1312 emit it. Test evidence: `.venv/bin/python -m pytest plugin/test_tjdf046_egress_allow_path.py plugin/test_tjdf047_plain_allow_degrade.py -x --tb=short -q` -> exit_code 0, '38 passed, 1 skipped in 10.47s'; focused run of the two changed tests -> exit_code 0, '2 passed in 0.46s'.
Both CI-failing assertions were converted to the same multi-needle any() pattern used by test_modify_path_unreadable_loader_degrades_before_composition, accepting 'not reachable' and the other valid degradation messages, and the affected suites pass locally (38 passed, 1 skipped).

Overall: FAIL ✗
