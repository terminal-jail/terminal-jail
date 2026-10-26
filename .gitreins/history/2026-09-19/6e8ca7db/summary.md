# Verdict: DF-TERMINAL-JAIL-18

**Task:** Host-classification probes are jail-aware
**Evaluated:** 2026-09-19T21:05:20.361399
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ scripts/pidns-capability-probe.py and scripts/fs-isolation-probe.py run through the terminal-jail CLI no longer report misleading UNKNOWN on a classifiable host: they either classify correctly under the jail or explicitly detect the jail and report the direct-run equivalent with a clear caveat; always exit 0 contract kept; direct-run classifications unchanged: Jail detection implemented in both probes: scripts/pidns-capability-probe.py:66-84 (_inside_terminal_jail via _JAIL_ENV_MARKERS TERMINAL_JAIL_FS_ISOLATION/TERMINAL_JAIL_SECCOMP + multi-value NSpid from /proc/self/status), :87-107 (_jail_aware_verdict), :110-115 (_classify short-circuits before any subprocess); scripts/fs-isolation-probe.py:66-84 (same detection), :87-131 (_jail_aware_verdict reports wrapper-observed TERMINAL_JAIL_FS_ISOLATION mapped/degraded/absent with explicit caveat 'NOT a host classification by this probe'), :243-249 (_classify short-circuits before fixture creation). LIVE through CLI: `./standalone/terminal-jail .venv/bin/python scripts/pidns-capability-probe.py` -> 'JAIL-AWARE: ... multi-value NSpid in /proc/self/status: 1165199 1 ...' rc=0; fs probe -> 'JAIL-AWARE: ... NOT a host classification by this probe ...' rc=0; --user shape -> JAIL-AWARE with 'jail env markers present: TERMINAL_JAIL_FS_ISOLATION' and fs reports 'TERMINAL_JAIL_FS_ISOLATION=degraded' rc=0; --seccomp shape -> JAIL-AWARE rc=0. PRE-FIX REPRO from git show 41e39c6^ confirms the bug was real: old pidns through CLI -> 'UNKNOWN: probe timed out after 15s' rc=0; old fs through CLI -> "UNKNOWN: probe error: [Errno 22] Invalid argument: '/tmp/tj-fsiso-.../secret600'" rc=0. DIRECT-RUN UNCHANGED: old pidns direct = 'FULL' rc=0, new pidns direct = 'FULL' rc=0; old fs direct = "DEGRADED: mapped launch failed (rc=1, stderr='unshare: setgroups failed: Operation not permitted'); causes: uid-mapping denied ..." rc=0, new fs direct byte-identical; direct /proc/self/status NSpid is single-valued (1373483) so no false positive. EXIT-0 CONTRACT: rc=0 in every shape (direct, auto-sandbox, --user, --seccomp, HOME unset). TESTS: `.venv/bin/python -m pytest plugin/test_host_probes.py -q` -> '22 passed in 0.71s'; `-m integration` -> '3 passed, 19 deselected'; full suite `.venv/bin/python -m pytest -q` -> '919 passed, 5 skipped in 27.11s' EXIT=0; ruff check on both probes + test file -> 'All checks passed!'; LSP diagnostics 0 findings.
Both host-classification probes now detect their own jail context and emit an honest JAIL-AWARE verdict with direct-run guidance (exit 0) instead of the pre-fix misleading UNKNOWN, while direct-run classifications remain byte-identical and the full suite is green (919 passed, 5 skipped).

## Summary

Judge Result: DF-TERMINAL-JAIL-18

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ scripts/pidns-capability-probe.py and scripts/fs-isolation-probe.py run through the terminal-jail CLI no longer report misleading UNKNOWN on a classifiable host: they either classify correctly under the jail or explicitly detect the jail and report the direct-run equivalent with a clear caveat; always exit 0 contract kept; direct-run classifications unchanged: Jail detection implemented in both probes: scripts/pidns-capability-probe.py:66-84 (_inside_terminal_jail via _JAIL_ENV_MARKERS TERMINAL_JAIL_FS_ISOLATION/TERMINAL_JAIL_SECCOMP + multi-value NSpid from /proc/self/status), :87-107 (_jail_aware_verdict), :110-115 (_classify short-circuits before any subprocess); scripts/fs-isolation-probe.py:66-84 (same detection), :87-131 (_jail_aware_verdict reports wrapper-observed TERMINAL_JAIL_FS_ISOLATION mapped/degraded/absent with explicit caveat 'NOT a host classification by this probe'), :243-249 (_classify short-circuits before fixture creation). LIVE through CLI: `./standalone/terminal-jail .venv/bin/python scripts/pidns-capability-probe.py` -> 'JAIL-AWARE: ... multi-value NSpid in /proc/self/status: 1165199 1 ...' rc=0; fs probe -> 'JAIL-AWARE: ... NOT a host classification by this probe ...' rc=0; --user shape -> JAIL-AWARE with 'jail env markers present: TERMINAL_JAIL_FS_ISOLATION' and fs reports 'TERMINAL_JAIL_FS_ISOLATION=degraded' rc=0; --seccomp shape -> JAIL-AWARE rc=0. PRE-FIX REPRO from git show 41e39c6^ confirms the bug was real: old pidns through CLI -> 'UNKNOWN: probe timed out after 15s' rc=0; old fs through CLI -> "UNKNOWN: probe error: [Errno 22] Invalid argument: '/tmp/tj-fsiso-.../secret600'" rc=0. DIRECT-RUN UNCHANGED: old pidns direct = 'FULL' rc=0, new pidns direct = 'FULL' rc=0; old fs direct = "DEGRADED: mapped launch failed (rc=1, stderr='unshare: setgroups failed: Operation not permitted'); causes: uid-mapping denied ..." rc=0, new fs direct byte-identical; direct /proc/self/status NSpid is single-valued (1373483) so no false positive. EXIT-0 CONTRACT: rc=0 in every shape (direct, auto-sandbox, --user, --seccomp, HOME unset). TESTS: `.venv/bin/python -m pytest plugin/test_host_probes.py -q` -> '22 passed in 0.71s'; `-m integration` -> '3 passed, 19 deselected'; full suite `.venv/bin/python -m pytest -q` -> '919 passed, 5 skipped in 27.11s' EXIT=0; ruff check on both probes + test file -> 'All checks passed!'; LSP diagnostics 0 findings.
Both host-classification probes now detect their own jail context and emit an honest JAIL-AWARE verdict with direct-run guidance (exit 0) instead of the pre-fix misleading UNKNOWN, while direct-run classifications remain byte-identical and the full suite is green (919 passed, 5 skipped).

Overall: PASS ✓
