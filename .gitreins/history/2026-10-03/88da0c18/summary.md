# Verdict: DOC-9

**Task:** Composed deployment docs + shared per-layer guarantee matrix
**Evaluated:** 2026-10-03T20:39:45.856022
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (tests/test_composed_mode.py::test_composed_off_refusal_names_cause_and_options [first failing 
- ✓ **tier2**
  - COMPLETE
  ✓ Repo gains a 'Composed deployment' doc stating the three configurations (tool alone / platform alone / both) with a runnable composed quickstart naming the inner-namespace requirement, the measured per-layer guarantee matrix (layer | enforcer | evidence | what the other layer does not give) appears with identical numbers and cross-links to the bunker counterpart rows, and the matrix numbers are pinned by a check: docs/composed-deployment.md (242 lines, committed 813d5c6) satisfies every element: §1 'The three configurations' table lists Tool alone / Platform alone / BOTH composed (lines 20-26); §2 'Composed quickstart' gives runnable docker commands (lines 73,91,132,146,153) plus the inner-namespace requirement table (lines 41-55); §3 'Shared per-layer guarantee matrix' has the exact header 'Layer | Who enforces | Measured evidence | What the other layer does NOT give you' (line 178) with three LAYER rows carrying the numbers 4/5/1084, /proc/1 identities, CapEff, exit 126, rule_id builtin-rm-rf-root; cross-links to bunker counterpart rows GAP-179 (line 228) and DOC-043 (line 231) with 'identical per-layer guarantee matrix (the same numbers as §3)' and 'one source of truth' (lines 232-233). Pinning check: tests/test_composed_doc.py — ran `.venv/bin/python -m pytest tests/test_composed_doc.py -v` => '7 passed in 0.01s' (exit 0), asserting the pinned strings, three layer rows, frozen numbers, and README link (README.md:667). Note: 4 failures in tests/test_composed_mode.py stem from uncommitted TJ-GAP-088 WIP (standalone/terminal-jail modified in working tree, task status in_progress), not from DOC-9's committed deliverable.
The 'Composed deployment' doc exists with all three configurations, a runnable quickstart naming the inner-namespace requirement, the measured per-layer matrix with identical numbers and bunker cross-links, and its numbers are pinned by tests/test_composed_doc.py (7 passed).

## Summary

Judge Result: DOC-9

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (tests/test_composed_mode.py::test_composed_off_refusal_names_cause_and_options [first failing 

Stage tier2: PASS
  COMPLETE
  ✓ Repo gains a 'Composed deployment' doc stating the three configurations (tool alone / platform alone / both) with a runnable composed quickstart naming the inner-namespace requirement, the measured per-layer guarantee matrix (layer | enforcer | evidence | what the other layer does not give) appears with identical numbers and cross-links to the bunker counterpart rows, and the matrix numbers are pinned by a check: docs/composed-deployment.md (242 lines, committed 813d5c6) satisfies every element: §1 'The three configurations' table lists Tool alone / Platform alone / BOTH composed (lines 20-26); §2 'Composed quickstart' gives runnable docker commands (lines 73,91,132,146,153) plus the inner-namespace requirement table (lines 41-55); §3 'Shared per-layer guarantee matrix' has the exact header 'Layer | Who enforces | Measured evidence | What the other layer does NOT give you' (line 178) with three LAYER rows carrying the numbers 4/5/1084, /proc/1 identities, CapEff, exit 126, rule_id builtin-rm-rf-root; cross-links to bunker counterpart rows GAP-179 (line 228) and DOC-043 (line 231) with 'identical per-layer guarantee matrix (the same numbers as §3)' and 'one source of truth' (lines 232-233). Pinning check: tests/test_composed_doc.py — ran `.venv/bin/python -m pytest tests/test_composed_doc.py -v` => '7 passed in 0.01s' (exit 0), asserting the pinned strings, three layer rows, frozen numbers, and README link (README.md:667). Note: 4 failures in tests/test_composed_mode.py stem from uncommitted TJ-GAP-088 WIP (standalone/terminal-jail modified in working tree, task status in_progress), not from DOC-9's committed deliverable.
The 'Composed deployment' doc exists with all three configurations, a runnable quickstart naming the inner-namespace requirement, the measured per-layer matrix with identical numbers and bunker cross-links, and its numbers are pinned by tests/test_composed_doc.py (7 passed).

Overall: FAIL ✗
