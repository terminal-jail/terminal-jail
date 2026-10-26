# Verdict: JSONL-NORM-003

**Task:** Board lint rejects pending P0/P1 rows without evidence body or creator
**Evaluated:** 2026-10-12T06:23:36.309463
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ board_id_guard.py exits 1 on a pending P0/P1 row with empty description+detail or null created_by, naming id/line/fields; P2/P3 warn-only; tests added; live board run shows expected rejections: scripts/board_id_guard.py _scan_evidence() gates only status=='pending' rows with priority in EVIDENCE_PRIORITY_REJECT=('P0','P1') into report.evidence_violations (P2/P3 -> evidence_warnings); BoardReport.ok excludes evidence_violations and main() returns EXIT_INVALID(1) when not ok. Diagnostics format 'line {line_no}: {row_id}: {field} {detail}' names id/line/field. Live run: `.venv/bin/python scripts/board_id_guard.py` -> EXIT=1 with 'evidence violations (2): line 2: E2E-001 ... line 8: NEVER-DONE ...' (both confirmed pending P1, created_by=None, description/detail=None) and 'evidence warnings (5)' for pending P2/P3 rows (lines 113/145/155/164/255) on stderr. Tests: `.venv/bin/python -m pytest tests/test_board_schema_guard.py -x --tb=short` -> 19 passed in 2.43s, including test_evidence_rejects_pending_p1_without_body_or_creator (returncode==1, names id/line/fields), test_evidence_pending_p2_gap_warns_on_stderr_but_exits_zero (returncode==0, stderr warnings), test_evidence_strict_flag_rejects_pending_p2_gaps, and grandfathering tests. LSP diagnostics: 0. [resolution 0.42; board_id_guard.py]
board_id_guard.py correctly rejects pending P0/P1 rows lacking evidence body/creator with exit 1 naming id/line/fields, warns-only on P2/P3, has passing tests, and the live board run shows the expected rejections.

## Summary

Judge Result: JSONL-NORM-003

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ board_id_guard.py exits 1 on a pending P0/P1 row with empty description+detail or null created_by, naming id/line/fields; P2/P3 warn-only; tests added; live board run shows expected rejections: scripts/board_id_guard.py _scan_evidence() gates only status=='pending' rows with priority in EVIDENCE_PRIORITY_REJECT=('P0','P1') into report.evidence_violations (P2/P3 -> evidence_warnings); BoardReport.ok excludes evidence_violations and main() returns EXIT_INVALID(1) when not ok. Diagnostics format 'line {line_no}: {row_id}: {field} {detail}' names id/line/field. Live run: `.venv/bin/python scripts/board_id_guard.py` -> EXIT=1 with 'evidence violations (2): line 2: E2E-001 ... line 8: NEVER-DONE ...' (both confirmed pending P1, created_by=None, description/detail=None) and 'evidence warnings (5)' for pending P2/P3 rows (lines 113/145/155/164/255) on stderr. Tests: `.venv/bin/python -m pytest tests/test_board_schema_guard.py -x --tb=short` -> 19 passed in 2.43s, including test_evidence_rejects_pending_p1_without_body_or_creator (returncode==1, names id/line/fields), test_evidence_pending_p2_gap_warns_on_stderr_but_exits_zero (returncode==0, stderr warnings), test_evidence_strict_flag_rejects_pending_p2_gaps, and grandfathering tests. LSP diagnostics: 0. [resolution 0.42; board_id_guard.py]
board_id_guard.py correctly rejects pending P0/P1 rows lacking evidence body/creator with exit 1 naming id/line/fields, warns-only on P2/P3, has passing tests, and the live board run shows the expected rejections.

Overall: PASS ✓
