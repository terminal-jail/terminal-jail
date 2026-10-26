# Verdict: TJ-DF-029

**Task:** Add host-baseline negative control to systemd-directive-probe RestrictNamespaces judge
**Evaluated:** 2026-10-04T13:18:16.529244
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE
  ✗ Host control runs unshare outside transient unit; verdict ENFORCED only when host rc==0 and unit rc!=0; UNKNOWN when host denies unprivileged userns; tests cover both branches; no regression to other directives: Criterion 1 (host control outside unit; ENFORCED only host rc==0 & unit rc!=0; UNKNOWN on host deny; tests both branches; no regression):

(a) Host control outside transient unit: scripts/systemd-directive-probe.py `_host_unshare_baseline()` (lines ~250-290) runs `subprocess.run([unshare, "--user", "--pid", "true"], ...)` directly on host — no systemd-run, no --wait/--collect/--unit switches. Confirmed by test_built_argv_never_touches_gateway_or_etc_or_control_verbs which asserts the non-systemd-run argv carries no unit switches.

(b) ENFORCED only when host rc==0 AND unit rc!=0: `_judge_restrict_namespaces` — baseline_rc None -> UNKNOWN; baseline_rc != 0 -> UNKNOWN ("host denies unprivileged user namespaces"); observed != "0" -> ENFORCED; else NOT_ENFORCED. Correct gating.

(c) UNKNOWN when host denies: evidence string "host denies unprivileged user namespaces (host-baseline unshare rc=...)". Test test_rns_host_denies_is_unknown_despite_inunit_denial asserts verdict UNKNOWN + "host denies" + "host-baseline".

(d) Tests cover both branches: test_rns_host_denies_is_unknown_despite_inunit_denial (host deny -> UNKNOWN), test_rns_host_allows_and_unit_denies_is_enforced (host allow + unit deny -> ENFORCED), test_rns_host_allows_and_unit_allows_is_not_enforced (NOT_ENFORCED), test_rns_host_baseline_timeout_is_unknown, test_host_baseline_missing_executable_is_unknown, test_host_baseline_executable_error_is_unknown.

(e) Test run: `.venv/bin/python -m pytest plugin/test_systemd_directive_probe.py -q --tb=short` -> "17 passed in 10.96s" (exit 0). Non-live subset: "16 passed, 1 deselected in 10.90s".

(f) No regression: git show 108bc78 diff touches ONLY _judge_restrict_namespaces + new _host_unshare_baseline + docstring; no other judge modified. LSP diagnostics: 0 findings.

Full-suite run in progress (/tmp/full_suite.log) — pending.

Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: TJ-DF-029

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE
  ✗ Host control runs unshare outside transient unit; verdict ENFORCED only when host rc==0 and unit rc!=0; UNKNOWN when host denies unprivileged userns; tests cover both branches; no regression to other directives: Criterion 1 (host control outside unit; ENFORCED only host rc==0 & unit rc!=0; UNKNOWN on host deny; tests both branches; no regression):

(a) Host control outside transient unit: scripts/systemd-directive-probe.py `_host_unshare_baseline()` (lines ~250-290) runs `subprocess.run([unshare, "--user", "--pid", "true"], ...)` directly on host — no systemd-run, no --wait/--collect/--unit switches. Confirmed by test_built_argv_never_touches_gateway_or_etc_or_control_verbs which asserts the non-systemd-run argv carries no unit switches.

(b) ENFORCED only when host rc==0 AND unit rc!=0: `_judge_restrict_namespaces` — baseline_rc None -> UNKNOWN; baseline_rc != 0 -> UNKNOWN ("host denies unprivileged user namespaces"); observed != "0" -> ENFORCED; else NOT_ENFORCED. Correct gating.

(c) UNKNOWN when host denies: evidence string "host denies unprivileged user namespaces (host-baseline unshare rc=...)". Test test_rns_host_denies_is_unknown_despite_inunit_denial asserts verdict UNKNOWN + "host denies" + "host-baseline".

(d) Tests cover both branches: test_rns_host_denies_is_unknown_despite_inunit_denial (host deny -> UNKNOWN), test_rns_host_allows_and_unit_denies_is_enforced (host allow + unit deny -> ENFORCED), test_rns_host_allows_and_unit_allows_is_not_enforced (NOT_ENFORCED), test_rns_host_baseline_timeout_is_unknown, test_host_baseline_missing_executable_is_unknown, test_host_baseline_executable_error_is_unknown.

(e) Test run: `.venv/bin/python -m pytest plugin/test_systemd_directive_probe.py -q --tb=short` -> "17 passed in 10.96s" (exit 0). Non-live subset: "16 passed, 1 deselected in 10.90s".

(f) No regression: git show 108bc78 diff touches ONLY _judge_restrict_namespaces + new _host_unshare_baseline + docstring; no other judge modified. LSP diagnostics: 0 findings.

Full-suite run in progress (/tmp/full_suite.log) — pending.

Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
