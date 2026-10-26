# Verdict: TJ-GAP-042

**Task:** Battery PID-NS layer FULL vs DEGRADED labeling + honest bare-mode tests
**Evaluated:** 2026-08-26T18:00:22.460319
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: 
    ○
    │╲
    │ ○
    ○ ░
    ░    gitleaks

[90m12:59PM[0m [32mINF[0m [1mscanned ~8977599 
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ python3 scripts/pidns-capability-probe.py exits 0 and prints DEGRADED on this host (FULL when bare mode works, UNKNOWN otherwise): Ran `python3 scripts/pidns-capability-probe.py` → output 'DEGRADED', exit 0. Script classifies FULL (rc==0), DEGRADED (rc==2 + degradation markers), UNKNOWN otherwise.
  ✓ plugin/test_standalone_cli.py has test_bare_mode_pid_namespace_containment asserting the PID ns inode inside bare-mode jail differs from the host when capable, and skipping with HOST-DEGRADED-PIDNS marker when the host refuses namespace creation: test_bare_mode_pid_namespace_containment at plugin/test_standalone_cli.py:342 asserts `inside != str(outside)` (PID ns inode differs) when capable, and pytest.skip('HOST-DEGRADED-PIDNS: host refused PID namespace creation...') at line 357 when host refuses.
  ✓ Bare-mode host-conditional tests skip with HOST-DEGRADED-PIDNS marker instead of silently passing when host refuses namespace creation (9 markers in a standalone_cli run on this host): `.venv/bin/python -m pytest plugin/test_standalone_cli.py -q -rs` produced exactly 9 HOST-DEGRADED-PIDNS skips (lines 182,198,214,227,238,266,282,335,357); 10 passed, 9 skipped.
  ✓ README.md headline no longer implies automatic --user fallback and Graceful Degradation documents FULL vs DEGRADED battery labeling: README.md headline (lines 1-28) says 'use the --user fallback instead' as explicit user action, no automatic fallback. Graceful Degradation (lines 203-210) states 'There is no automatic fallback' and documents FULL/DEGRADED labeling via scripts/pidns-capability-probe.py.
  ✓ .venv/bin/python -m pytest -q passes with zero failures on this host and standalone/terminal-jail bare mode still exits 2 with the degradation message (fail-closed contract preserved): `.venv/bin/python -m pytest -q` → 307 passed, 13 skipped, 0 failures. `./standalone/terminal-jail true` exits 2 with 'namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user'.
All 5 criteria verified: probe prints DEGRADED with exit 0, containment test asserts inode difference and skips with HOST-DEGRADED-PIDNS, exactly 9 markers in standalone_cli run, README documents no automatic fallback + FULL/DEGRADED labeling, and full pytest passes with fail-closed exit-2 preserved.

## Summary

Judge Result: TJ-GAP-042

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: 
    ○
    │╲
    │ ○
    ○ ░
    ░    gitleaks

[90m12:59PM[0m [32mINF[0m [1mscanned ~8977599 
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ python3 scripts/pidns-capability-probe.py exits 0 and prints DEGRADED on this host (FULL when bare mode works, UNKNOWN otherwise): Ran `python3 scripts/pidns-capability-probe.py` → output 'DEGRADED', exit 0. Script classifies FULL (rc==0), DEGRADED (rc==2 + degradation markers), UNKNOWN otherwise.
  ✓ plugin/test_standalone_cli.py has test_bare_mode_pid_namespace_containment asserting the PID ns inode inside bare-mode jail differs from the host when capable, and skipping with HOST-DEGRADED-PIDNS marker when the host refuses namespace creation: test_bare_mode_pid_namespace_containment at plugin/test_standalone_cli.py:342 asserts `inside != str(outside)` (PID ns inode differs) when capable, and pytest.skip('HOST-DEGRADED-PIDNS: host refused PID namespace creation...') at line 357 when host refuses.
  ✓ Bare-mode host-conditional tests skip with HOST-DEGRADED-PIDNS marker instead of silently passing when host refuses namespace creation (9 markers in a standalone_cli run on this host): `.venv/bin/python -m pytest plugin/test_standalone_cli.py -q -rs` produced exactly 9 HOST-DEGRADED-PIDNS skips (lines 182,198,214,227,238,266,282,335,357); 10 passed, 9 skipped.
  ✓ README.md headline no longer implies automatic --user fallback and Graceful Degradation documents FULL vs DEGRADED battery labeling: README.md headline (lines 1-28) says 'use the --user fallback instead' as explicit user action, no automatic fallback. Graceful Degradation (lines 203-210) states 'There is no automatic fallback' and documents FULL/DEGRADED labeling via scripts/pidns-capability-probe.py.
  ✓ .venv/bin/python -m pytest -q passes with zero failures on this host and standalone/terminal-jail bare mode still exits 2 with the degradation message (fail-closed contract preserved): `.venv/bin/python -m pytest -q` → 307 passed, 13 skipped, 0 failures. `./standalone/terminal-jail true` exits 2 with 'namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user'.
All 5 criteria verified: probe prints DEGRADED with exit 0, containment test asserts inode difference and skips with HOST-DEGRADED-PIDNS, exactly 9 markers in standalone_cli run, README documents no automatic fallback + FULL/DEGRADED labeling, and full pytest passes with fail-closed exit-2 preserved.

Overall: PASS ✓
