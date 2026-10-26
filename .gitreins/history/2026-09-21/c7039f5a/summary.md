# Verdict: TJ-GAP-056

**Task:** Backend parity battery: bwrap vs unshare containment evidence (private /proc, orphan teardown, escape replay, DEGRADED fail-closed)
**Evaluated:** 2026-09-21T07:05:19.642834
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ scripts/backend-parity-battery.py exists, runs on kara-lair, exits 0 as a classifier, and emits a per-cell parity table covering private-/proc PID visibility, --die-with-parent orphan teardown, the escape-wave replay under TERMINAL_JAIL_JAIL_BACKEND=bwrap, and the DEGRADED-host fail-closed contract; docs/backend-parity.md carries the measured table with this host's real numbers plus an explicit known-limits section; both backends fail closed with exit 2 and the command not run when the namespace probe fails, asserted by a test in plugin/test_backend_parity.py (host-conditional cells skip with a grep-able HOST-DEGRADED marker); specs/cli.md backend section points at the shipped battery instead of the TJ-GAP-056 placeholder; suite green with no new failures beyond the pre-change baseline and uvx ruff check clean: Battery: `.venv/bin/python scripts/backend-parity-battery.py` on karaHermes-mde-7840hs exited 0 and printed the per-cell table — cell 1 private /proc bwrap SAME (4 vs host 1378), cell 2 private /proc unshare KNOWN-LIMIT (1382 vs 1378), cell 3 orphan teardown bwrap SAME (payload gone in 20 ms), cell 4 orphan unshare SAME, cell 5 escape-wave replay under TERMINAL_JAIL_JAIL_BACKEND=bwrap SAME (rc=0, tail '221 passed in 1.21s'), cell 5b live argv/exit slice, cell 6 fail-closed bwrap+unshare FAIL-CLOSED-PROVEN, cell 7 host classification. docs/backend-parity.md:1-152 carries the verbatim measured table with this host's real numbers (kernel 7.0.0-30-generic, bwrap 0.11.1, 4 vs ~1340) plus an explicit '## Known limits' section (a)-(d). plugin/test_backend_parity.py: 9 passed in 5.32s — test_fail_closed_bwrap_probe_fails_leaves_marker_absent and test_fail_closed_unshare_probe_fails_leaves_marker_absent assert returncode==2, 'command not run' in stderr, stdout=='', and marker absent; HOST-DEGRADED-BWRAP/HOST-DEGRADED-PIDNS skip markers at lines 274,291,365,376. Manual reproduction: bwrap stub -> EXIT=2, marker NO; unshare stub -> EXIT=2, marker NO. specs/cli.md:256 diff shows the placeholder 'a bwrap-specific containment battery is TJ-GAP-056' replaced with a pointer to scripts/backend-parity-battery.py + docs/backend-parity.md. Full suite: `.venv/bin/python -m pytest -q -p no:cacheprovider` -> '1357 passed, 7 skipped in 37.49s' (green, no failures). `uvx ruff check` -> 'All checks passed!' EXIT=0 (also clean on the two changed files).
All required artifacts ship and verify: the battery runs and exits 0 with the full parity table, docs carry the measured numbers plus known limits, both backends fail closed (exit 2, command not run) under test, specs/cli.md points at the battery, and the suite (1357 passed, 7 skipped) plus ruff are green.

## Summary

Judge Result: TJ-GAP-056

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ scripts/backend-parity-battery.py exists, runs on kara-lair, exits 0 as a classifier, and emits a per-cell parity table covering private-/proc PID visibility, --die-with-parent orphan teardown, the escape-wave replay under TERMINAL_JAIL_JAIL_BACKEND=bwrap, and the DEGRADED-host fail-closed contract; docs/backend-parity.md carries the measured table with this host's real numbers plus an explicit known-limits section; both backends fail closed with exit 2 and the command not run when the namespace probe fails, asserted by a test in plugin/test_backend_parity.py (host-conditional cells skip with a grep-able HOST-DEGRADED marker); specs/cli.md backend section points at the shipped battery instead of the TJ-GAP-056 placeholder; suite green with no new failures beyond the pre-change baseline and uvx ruff check clean: Battery: `.venv/bin/python scripts/backend-parity-battery.py` on karaHermes-mde-7840hs exited 0 and printed the per-cell table — cell 1 private /proc bwrap SAME (4 vs host 1378), cell 2 private /proc unshare KNOWN-LIMIT (1382 vs 1378), cell 3 orphan teardown bwrap SAME (payload gone in 20 ms), cell 4 orphan unshare SAME, cell 5 escape-wave replay under TERMINAL_JAIL_JAIL_BACKEND=bwrap SAME (rc=0, tail '221 passed in 1.21s'), cell 5b live argv/exit slice, cell 6 fail-closed bwrap+unshare FAIL-CLOSED-PROVEN, cell 7 host classification. docs/backend-parity.md:1-152 carries the verbatim measured table with this host's real numbers (kernel 7.0.0-30-generic, bwrap 0.11.1, 4 vs ~1340) plus an explicit '## Known limits' section (a)-(d). plugin/test_backend_parity.py: 9 passed in 5.32s — test_fail_closed_bwrap_probe_fails_leaves_marker_absent and test_fail_closed_unshare_probe_fails_leaves_marker_absent assert returncode==2, 'command not run' in stderr, stdout=='', and marker absent; HOST-DEGRADED-BWRAP/HOST-DEGRADED-PIDNS skip markers at lines 274,291,365,376. Manual reproduction: bwrap stub -> EXIT=2, marker NO; unshare stub -> EXIT=2, marker NO. specs/cli.md:256 diff shows the placeholder 'a bwrap-specific containment battery is TJ-GAP-056' replaced with a pointer to scripts/backend-parity-battery.py + docs/backend-parity.md. Full suite: `.venv/bin/python -m pytest -q -p no:cacheprovider` -> '1357 passed, 7 skipped in 37.49s' (green, no failures). `uvx ruff check` -> 'All checks passed!' EXIT=0 (also clean on the two changed files).
All required artifacts ship and verify: the battery runs and exits 0 with the full parity table, docs carry the measured numbers plus known limits, both backends fail closed (exit 2, command not run) under test, specs/cli.md points at the battery, and the suite (1357 passed, 7 skipped) plus ruff are green.

Overall: PASS ✓
