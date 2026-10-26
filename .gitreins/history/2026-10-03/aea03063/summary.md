# Verdict: TJ-GAP-088

**Task:** Enforceable private-/proc demand + proc_view attribution
**Evaluated:** 2026-10-03T21:59:24.319871
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ Flag/env fails closed when backend cannot deliver private procfs; verdict states proc_view; parity probe added; docs corrected; full suite green: All five sub-parts verified. (1) FAILS CLOSED: standalone/terminal-jail:795-797 refuses (exit 2, 'command not run') when TJ_PRIVATE_PROC_REQUIRED=1 and TJ_BACKEND!=bwrap; :1002-1004 covers the firewall-rewrite ns-failure path; :1037-1039 covers the unshare launch-failure path; :341-349 rejects unknown TERMINAL_JAIL_PRIVATE_PROC values before any namespace work; :283-285 parses --private-proc. Live: `TERMINAL_JAIL_PRIVATE_PROC=required TERMINAL_JAIL_JAIL_BACKEND=unshare ./standalone/terminal-jail --no-interruptor --user echo hi` -> exit=2, stderr 'TERMINAL_JAIL_PRIVATE_PROC=required but the resolved backend 'unshare' cannot provide a private /proc; command not run'; `TERMINAL_JAIL_PRIVATE_PROC=bogus` -> exit=2; stub-PATH composed+demand -> exit=2. (2) PROC_VIEW VERDICT: :1098/:1112 print proc_view=private (bwrap), :1102/:1116 print proc_view=host (unshare), :943/:945/:1073 print proc_view=platform-owned / proc_view=none (composed). Live: unshare run printed 'proc_view=host (unshare backend: the host /proc view is exposed...)'; bwrap run printed 'proc_view=private (bwrap backend: fresh procfs via --proc /proc)'; composed forced with no outer layer printed 'proc_view=none'. (3) PARITY PROBE: scripts/backend-parity-battery.py adds cell 8 `_private_proc_demand_cell` (:454) and cell 9 `_proc_view_attribution_cell` (:530), plus /proc/1 identity in cells 1-2 (:180). Battery run output: '8 private-proc demand enforced (fail closed) ... rc=2, stdout='', marker=ABSENT ... FAIL-CLOSED-PROVEN' and '9 proc_view attribution per launch ... bwrap: proc_view=private; unshare: proc_view=host ... SAME'; 'zero unexplained divergences'. plugin/test_private_proc_demand.py:641-671 pins both cells host-independently. (4) DOCS CORRECTED: README.md:243 (demand callout), :311 (env-var table row), :646 (method note that an auto-backend run is NOT evidence about the unshare path); specs/cli.md:235 (per-run attribution paragraph) plus the exit-code table row for unknown TERMINAL_JAIL_PRIVATE_PROC and the demand refusal; docs/backend-parity.md gains the TJ-GAP-088 method note, the demand/attribution section under known limit (a), and the standing-probe cross-reference. (5) FULL SUITE GREEN: `.venv/bin/python -m pytest -x --tb=short -q -p no:cacheprovider` -> '1628 passed, 10 skipped in 135.47s (0:02:15)', exit_code 0. New file alone: '20 passed in 4.90s'. No regression in the sibling composed work: scripts/composed-mode-battery.py -> '3/3 PASS, 0 UNAVAILABLE'.
The private-/proc demand fails closed across every non-bwrap path, every launch attributes proc_view, parity battery cells 8-9 plus 20 new pytest cases pin it, docs are corrected, and the full suite is green (1628 passed, 10 skipped, exit 0).

## Summary

Judge Result: TJ-GAP-088

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ Flag/env fails closed when backend cannot deliver private procfs; verdict states proc_view; parity probe added; docs corrected; full suite green: All five sub-parts verified. (1) FAILS CLOSED: standalone/terminal-jail:795-797 refuses (exit 2, 'command not run') when TJ_PRIVATE_PROC_REQUIRED=1 and TJ_BACKEND!=bwrap; :1002-1004 covers the firewall-rewrite ns-failure path; :1037-1039 covers the unshare launch-failure path; :341-349 rejects unknown TERMINAL_JAIL_PRIVATE_PROC values before any namespace work; :283-285 parses --private-proc. Live: `TERMINAL_JAIL_PRIVATE_PROC=required TERMINAL_JAIL_JAIL_BACKEND=unshare ./standalone/terminal-jail --no-interruptor --user echo hi` -> exit=2, stderr 'TERMINAL_JAIL_PRIVATE_PROC=required but the resolved backend 'unshare' cannot provide a private /proc; command not run'; `TERMINAL_JAIL_PRIVATE_PROC=bogus` -> exit=2; stub-PATH composed+demand -> exit=2. (2) PROC_VIEW VERDICT: :1098/:1112 print proc_view=private (bwrap), :1102/:1116 print proc_view=host (unshare), :943/:945/:1073 print proc_view=platform-owned / proc_view=none (composed). Live: unshare run printed 'proc_view=host (unshare backend: the host /proc view is exposed...)'; bwrap run printed 'proc_view=private (bwrap backend: fresh procfs via --proc /proc)'; composed forced with no outer layer printed 'proc_view=none'. (3) PARITY PROBE: scripts/backend-parity-battery.py adds cell 8 `_private_proc_demand_cell` (:454) and cell 9 `_proc_view_attribution_cell` (:530), plus /proc/1 identity in cells 1-2 (:180). Battery run output: '8 private-proc demand enforced (fail closed) ... rc=2, stdout='', marker=ABSENT ... FAIL-CLOSED-PROVEN' and '9 proc_view attribution per launch ... bwrap: proc_view=private; unshare: proc_view=host ... SAME'; 'zero unexplained divergences'. plugin/test_private_proc_demand.py:641-671 pins both cells host-independently. (4) DOCS CORRECTED: README.md:243 (demand callout), :311 (env-var table row), :646 (method note that an auto-backend run is NOT evidence about the unshare path); specs/cli.md:235 (per-run attribution paragraph) plus the exit-code table row for unknown TERMINAL_JAIL_PRIVATE_PROC and the demand refusal; docs/backend-parity.md gains the TJ-GAP-088 method note, the demand/attribution section under known limit (a), and the standing-probe cross-reference. (5) FULL SUITE GREEN: `.venv/bin/python -m pytest -x --tb=short -q -p no:cacheprovider` -> '1628 passed, 10 skipped in 135.47s (0:02:15)', exit_code 0. New file alone: '20 passed in 4.90s'. No regression in the sibling composed work: scripts/composed-mode-battery.py -> '3/3 PASS, 0 UNAVAILABLE'.
The private-/proc demand fails closed across every non-bwrap path, every launch attributes proc_view, parity battery cells 8-9 plus 20 new pytest cases pin it, docs are corrected, and the full suite is green (1628 passed, 10 skipped, exit 0).

Overall: PASS ✓
