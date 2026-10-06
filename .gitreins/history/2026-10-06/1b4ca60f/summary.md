# Verdict: TJ-REVIEW-009

**Task:** bwrap signal-reach boundary documented + battery probe
**Evaluated:** 2026-10-06T20:58:35.949593
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ docs/backend-parity.md contains a 'Signal reach boundary' section quoting the measured bwrap command and its CAN-SIGNAL-PID1 output plus the ESRCH host-pid contrast, cross-referencing TJ-GAP-088: docs/backend-parity.md:229 has heading '## Signal reach boundary (bwrap private /proc) — REVIEW-TJ-009'. Lines 249-251 quote the measured command verbatim (`bwrap --proc /proc --dev /dev --unshare-pid --ro-bind /usr /usr ... bash -c 'kill -0 1 && echo CAN-SIGNAL-PID1; ps -p 1 -o comm='`) with output `CAN-SIGNAL-PID1` / `bwrap`. Lines 280-281 give the ESRCH host-pid contrast: `kill -0 <host-pid> -> bash: kill: (184986) - No such process (ESRCH)` and `kill -TERM <host-pid>-> same ESRCH; the host process SURVIVED`. TJ-GAP-088 cross-referenced at lines 8, 122, and 300 ('Nothing here changes TJ-GAP-088's unshare proc leak'). Pinned by tests/test_signal_reach_doc.py (SECTION_HEADING + _PINNED_DOC_STRINGS incl. 'CAN-SIGNAL-PID1', 'ESRCH', 'TJ-GAP-088'). [resolution 0.23; docs/backend-parity.md]
  ✓ scripts/backend-parity-battery.py registers a signal-reach probe cell that reports the measured boundary and skips with a named reason when bwrap is missing; battery ends with zero unexplained divergences: scripts/backend-parity-battery.py:617 defines `_signal_reach_cell()` (cell name '10 signal reach — bwrap private /proc (REVIEW-TJ-009)'), registered in collect_cells at line 843. Missing-bwrap path at line 643: `return _unmeasured(name, "bwrap", expected, "bwrap not found on PATH")` -> verdict KNOWN-LIMIT, notes 'UNMEASURED on this host: bwrap not found on PATH' (verified by monkeypatching shutil.which -> output exactly that). Live run on this host: `timeout 300 .venv/bin/python scripts/backend-parity-battery.py` -> cell 10 verdict SAME, measured 'kill -0 1: CAN-SIGNAL-PID1; /proc/1 comm: bwrap; host pid 1703629: ESRCH-HOSTPID, TERM TERM-FAILED; ns jail=pid:[4026536327] host=pid:[4026531836] shared=False', and the run ends with 'zero unexplained divergences: every cell is SAME, KNOWN-LIMIT (documented) or FAIL-CLOSED-PROVEN.' (print_table lines 871-884). [resolution 0.23; scripts/backend-parity-battery.py]
  ✓ doc-pin tests pass and full unit scope is green on the merged tree with ruff clean: Doc-pin suite: `cd /home/kara/terminal-jail && .venv/bin/python -m pytest tests/test_signal_reach_doc.py -q --tb=short` -> '5 passed in 0.01s' (exit 0). Full unit scope: `.venv/bin/python -m pytest -q --tb=short` -> '1692 passed, 10 skipped in 107.06s (0:01:47)' (exit 0). Ruff: `.venv/bin/python -m ruff check .` -> 'All checks passed!' (exit 0).
All three criteria verified: the signal-reach boundary section is documented with the measured bwrap command, CAN-SIGNAL-PID1 output and ESRCH host-pid contrast cross-referencing TJ-GAP-088; battery cell 10 reports the measured boundary, skips with the named reason 'bwrap not found on PATH', and the live battery ends with zero unexplained divergences; doc-pin tests (5 passed), full suite (1692 passed, 10 skipped) and ruff are all green.

## Summary

Judge Result: TJ-REVIEW-009

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ docs/backend-parity.md contains a 'Signal reach boundary' section quoting the measured bwrap command and its CAN-SIGNAL-PID1 output plus the ESRCH host-pid contrast, cross-referencing TJ-GAP-088: docs/backend-parity.md:229 has heading '## Signal reach boundary (bwrap private /proc) — REVIEW-TJ-009'. Lines 249-251 quote the measured command verbatim (`bwrap --proc /proc --dev /dev --unshare-pid --ro-bind /usr /usr ... bash -c 'kill -0 1 && echo CAN-SIGNAL-PID1; ps -p 1 -o comm='`) with output `CAN-SIGNAL-PID1` / `bwrap`. Lines 280-281 give the ESRCH host-pid contrast: `kill -0 <host-pid> -> bash: kill: (184986) - No such process (ESRCH)` and `kill -TERM <host-pid>-> same ESRCH; the host process SURVIVED`. TJ-GAP-088 cross-referenced at lines 8, 122, and 300 ('Nothing here changes TJ-GAP-088's unshare proc leak'). Pinned by tests/test_signal_reach_doc.py (SECTION_HEADING + _PINNED_DOC_STRINGS incl. 'CAN-SIGNAL-PID1', 'ESRCH', 'TJ-GAP-088'). [resolution 0.23; docs/backend-parity.md]
  ✓ scripts/backend-parity-battery.py registers a signal-reach probe cell that reports the measured boundary and skips with a named reason when bwrap is missing; battery ends with zero unexplained divergences: scripts/backend-parity-battery.py:617 defines `_signal_reach_cell()` (cell name '10 signal reach — bwrap private /proc (REVIEW-TJ-009)'), registered in collect_cells at line 843. Missing-bwrap path at line 643: `return _unmeasured(name, "bwrap", expected, "bwrap not found on PATH")` -> verdict KNOWN-LIMIT, notes 'UNMEASURED on this host: bwrap not found on PATH' (verified by monkeypatching shutil.which -> output exactly that). Live run on this host: `timeout 300 .venv/bin/python scripts/backend-parity-battery.py` -> cell 10 verdict SAME, measured 'kill -0 1: CAN-SIGNAL-PID1; /proc/1 comm: bwrap; host pid 1703629: ESRCH-HOSTPID, TERM TERM-FAILED; ns jail=pid:[4026536327] host=pid:[4026531836] shared=False', and the run ends with 'zero unexplained divergences: every cell is SAME, KNOWN-LIMIT (documented) or FAIL-CLOSED-PROVEN.' (print_table lines 871-884). [resolution 0.23; scripts/backend-parity-battery.py]
  ✓ doc-pin tests pass and full unit scope is green on the merged tree with ruff clean: Doc-pin suite: `cd /home/kara/terminal-jail && .venv/bin/python -m pytest tests/test_signal_reach_doc.py -q --tb=short` -> '5 passed in 0.01s' (exit 0). Full unit scope: `.venv/bin/python -m pytest -q --tb=short` -> '1692 passed, 10 skipped in 107.06s (0:01:47)' (exit 0). Ruff: `.venv/bin/python -m ruff check .` -> 'All checks passed!' (exit 0).
All three criteria verified: the signal-reach boundary section is documented with the measured bwrap command, CAN-SIGNAL-PID1 output and ESRCH host-pid contrast cross-referencing TJ-GAP-088; battery cell 10 reports the measured boundary, skips with the named reason 'bwrap not found on PATH', and the live battery ends with zero unexplained divergences; doc-pin tests (5 passed), full suite (1692 passed, 10 skipped) and ruff are all green.

Overall: PASS ✓
