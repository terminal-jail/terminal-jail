# Verdict: INT-CI-011

**Task:** Fix duplicate Landlock egress degrade warning on unreadable loader
**Evaluated:** 2026-10-21T07:46:08.215958
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✗ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ The committed fix must make plugin/test_tjdf046_egress_allow_path.py::TestLaunchShape::test_modify_path_unreadable_loader_degrades_before_composition observe exactly one Landlock network degrade warning while the payload runs, preserve a named unreadable-loader cause, avoid composing the unreadable loader, and include repository-local ch:trace evidence for row INT-CI-011. Verify the focused regression and the configured full unit suite.: Fix committed as d2fdf89 (HEAD 36454de differs only in board data). Mechanism: standalone/terminal-jail:449-453 creates a launch-private TERMINAL_JAIL_LANDLOCK_NET_MARK via mktemp when TJ_LANDLOCK_NET_ON=1; plugin/terminal_jail/interruptor/landlock_net.py:620-651 (_note_engine_degradation, called from _degrade) appends the cause best-effort; standalone/terminal-jail:1069-1106 (_tj_egress_engine_degradation_mark / _tj_egress_tier_decide) suppresses the wrapper's second warning when the mark is non-empty; mark removed at standalone/terminal-jail:1327-1328. Test asserts stderr.count('WARNING: Landlock network (egress) tier not applied') == 1 (plugin/test_tjdf046_egress_allow_path.py:487-490), a named cause from either layer (lines 492-503), 'SHAPE-OK' in stdout (line 486), and str(hidden) not in argv (lines 504-505). ch:trace row=INT-CI-011 present at plugin/test_tjdf046_egress_allow_path.py:463 (spec/doc/evidence/witness fields). Focused run: `.venv/bin/python -m pytest plugin/test_tjdf046_egress_allow_path.py::TestLaunchShape::test_modify_path_unreadable_loader_degrades_before_composition -x --tb=short -q` -> exit_code 0, '1 passed in 0.26s'. Whole file: '22 passed, 1 skipped in 6.58s'. Configured full suite (`.venv/bin/python -m pytest -x --tb=short -q` from .gitreins/config.yaml guards.test_command) -> exit_code 0, '2158 passed, 62 skipped, 3 warnings in 124.14s (0:02:04)'. Independent live probe reproducing the test body printed exactly one warning line: 'terminal-jail: WARNING: Landlock network (egress) tier not applied (the payload cannot read /var/tmp/.../landlock-net-loader.py in the launch that would run it)...' with COUNT 1 and stdout 'SHAPE-OK'. [resolution 0.11; plugin/test_tjdf046_egress_allow_path.py]
The committed fix (d2fdf89) deduplicates the egress degrade via a launch-private mark file; the focused regression passes (1 passed), the full configured suite is green (2158 passed, 62 skipped), and a live probe confirms exactly one named warning with the payload running and the unreadable loader absent from argv.

## Summary

Judge Result: INT-CI-011

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✗ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ The committed fix must make plugin/test_tjdf046_egress_allow_path.py::TestLaunchShape::test_modify_path_unreadable_loader_degrades_before_composition observe exactly one Landlock network degrade warning while the payload runs, preserve a named unreadable-loader cause, avoid composing the unreadable loader, and include repository-local ch:trace evidence for row INT-CI-011. Verify the focused regression and the configured full unit suite.: Fix committed as d2fdf89 (HEAD 36454de differs only in board data). Mechanism: standalone/terminal-jail:449-453 creates a launch-private TERMINAL_JAIL_LANDLOCK_NET_MARK via mktemp when TJ_LANDLOCK_NET_ON=1; plugin/terminal_jail/interruptor/landlock_net.py:620-651 (_note_engine_degradation, called from _degrade) appends the cause best-effort; standalone/terminal-jail:1069-1106 (_tj_egress_engine_degradation_mark / _tj_egress_tier_decide) suppresses the wrapper's second warning when the mark is non-empty; mark removed at standalone/terminal-jail:1327-1328. Test asserts stderr.count('WARNING: Landlock network (egress) tier not applied') == 1 (plugin/test_tjdf046_egress_allow_path.py:487-490), a named cause from either layer (lines 492-503), 'SHAPE-OK' in stdout (line 486), and str(hidden) not in argv (lines 504-505). ch:trace row=INT-CI-011 present at plugin/test_tjdf046_egress_allow_path.py:463 (spec/doc/evidence/witness fields). Focused run: `.venv/bin/python -m pytest plugin/test_tjdf046_egress_allow_path.py::TestLaunchShape::test_modify_path_unreadable_loader_degrades_before_composition -x --tb=short -q` -> exit_code 0, '1 passed in 0.26s'. Whole file: '22 passed, 1 skipped in 6.58s'. Configured full suite (`.venv/bin/python -m pytest -x --tb=short -q` from .gitreins/config.yaml guards.test_command) -> exit_code 0, '2158 passed, 62 skipped, 3 warnings in 124.14s (0:02:04)'. Independent live probe reproducing the test body printed exactly one warning line: 'terminal-jail: WARNING: Landlock network (egress) tier not applied (the payload cannot read /var/tmp/.../landlock-net-loader.py in the launch that would run it)...' with COUNT 1 and stdout 'SHAPE-OK'. [resolution 0.11; plugin/test_tjdf046_egress_allow_path.py]
The committed fix (d2fdf89) deduplicates the egress degrade via a launch-private mark file; the focused regression passes (1 passed), the full configured suite is green (2158 passed, 62 skipped), and a live probe confirms exactly one named warning with the payload running and the unreadable loader absent from argv.

Overall: FAIL ✗
