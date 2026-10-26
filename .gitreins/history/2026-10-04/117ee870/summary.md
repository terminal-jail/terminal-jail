# Verdict: DOC-8

**Task:** Per-host capability matrix with measurable probes
**Evaluated:** 2026-10-04T05:48:54.147252
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ docs/capability-matrix.md exists, linked from README, probes named, numbers agree with composed-deployment doc, pinned by doc tests: docs/capability-matrix.md exists (143 lines, 6 layer rows x 4 launch-shape columns). README.md:279 links it ('then read **[docs/capability-matrix.md](docs/capability-matrix.md)**') and README carries the '### What containment do I actually get on MY host?' section naming both probes. Probes named and real: `python3 scripts/pidns-capability-probe.py` and `python3 scripts/fs-isolation-probe.py` (both exist, executable); run live they emit exactly the quoted verdicts — pidns probe → 'FULL' (exit 0), fs probe → 'DEGRADED: mapped launch failed ... setgroups failed: Operation not permitted' (exit 0). Numbers agree with docs/composed-deployment.md §3: capability-matrix carries **5** (bwrap), **1084** (unshare --user host view), **4** (container) and composed-deployment.md §3 carries the identical 'entry count **5**/**1084**/**4**'; the 2026-10-03 re-measurement 1175 vs 1173 is also present. Pinned by doc tests: `tests/test_capability_matrix_doc.py` (12 tests incl. test_snapshot_numbers_agree_with_the_shared_matrix, test_readme_links_the_capability_matrix) plus `tests/test_composed_doc.py` (7 tests) — ran `.venv/bin/python -m pytest tests/test_capability_matrix_doc.py tests/test_composed_doc.py -v` → '19 passed in 0.03s', exit_code 0. [resolution 0.41; docs/capability-matrix.md]
docs/capability-matrix.md exists, is linked from README, names both real probes, its measured numbers match docs/composed-deployment.md §3, and all 19 doc-pinning tests pass.

## Summary

Judge Result: DOC-8

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ docs/capability-matrix.md exists, linked from README, probes named, numbers agree with composed-deployment doc, pinned by doc tests: docs/capability-matrix.md exists (143 lines, 6 layer rows x 4 launch-shape columns). README.md:279 links it ('then read **[docs/capability-matrix.md](docs/capability-matrix.md)**') and README carries the '### What containment do I actually get on MY host?' section naming both probes. Probes named and real: `python3 scripts/pidns-capability-probe.py` and `python3 scripts/fs-isolation-probe.py` (both exist, executable); run live they emit exactly the quoted verdicts — pidns probe → 'FULL' (exit 0), fs probe → 'DEGRADED: mapped launch failed ... setgroups failed: Operation not permitted' (exit 0). Numbers agree with docs/composed-deployment.md §3: capability-matrix carries **5** (bwrap), **1084** (unshare --user host view), **4** (container) and composed-deployment.md §3 carries the identical 'entry count **5**/**1084**/**4**'; the 2026-10-03 re-measurement 1175 vs 1173 is also present. Pinned by doc tests: `tests/test_capability_matrix_doc.py` (12 tests incl. test_snapshot_numbers_agree_with_the_shared_matrix, test_readme_links_the_capability_matrix) plus `tests/test_composed_doc.py` (7 tests) — ran `.venv/bin/python -m pytest tests/test_capability_matrix_doc.py tests/test_composed_doc.py -v` → '19 passed in 0.03s', exit_code 0. [resolution 0.41; docs/capability-matrix.md]
docs/capability-matrix.md exists, is linked from README, names both real probes, its measured numbers match docs/composed-deployment.md §3, and all 19 doc-pinning tests pass.

Overall: PASS ✓
