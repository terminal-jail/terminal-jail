# Verdict: TJ-DF-029

**Task:** Add host-baseline negative control to systemd-directive-probe RestrictNamespaces judge
**Evaluated:** 2026-10-04T14:27:23.315441
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE
  ✗ Host control runs unshare outside transient unit; verdict ENFORCED only when host rc==0 and unit rc!=0; UNKNOWN when host denies unprivileged userns; tests cover both branches; no regression to other directives: Criterion 1 (host control outside unit; ENFORCED only host rc==0 & unit rc!=0; UNKNOWN when host denies; tests both branches; no regression):
- _host_unshare_baseline (scripts/systemd-directive-probe.py:264-296) runs [unshare,"--user","--pid","true"] via subprocess.run directly, no unit switches, bounded timeout 10s. Returns (None,reason) on missing/exec-error/timeout.
- _judge_restrict_namespaces (lines 303-331): baseline_rc None -> UNKNOWN; baseline_rc!=0 -> UNKNOWN "host denies unprivileged user namespaces"; observed!=0 -> ENFORCED (only when host rc==0); else NOT_ENFORCED.
- Tests: plugin/test_systemd_directive_probe.py test_rns_host_denies_is_unknown_despite_inunit_denial (UNKNOWN branch), test_rns_host_allows_and_unit_denies_is_enforced (ENFORCED branch), test_rns_host_allows_and_unit_allows_is_not_enforced, test_rns_host_baseline_timeout_is_unknown, test_host_baseline_missing_executable_is_unknown, test_host_baseline_executable_error_is_unknown.
- Targeted run: 17 passed in 10.98s (incl live host test).
- Commit 108bc78 diff touches only _host_unshare_baseline + _judge_restrict_namespaces; grep for def _judge/_JUDGES/_PAYLOADS in diff = no matches -> no other directive judges changed.
- Full suite: RUNNING (pending).

Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: TJ-DF-029

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE
  ✗ Host control runs unshare outside transient unit; verdict ENFORCED only when host rc==0 and unit rc!=0; UNKNOWN when host denies unprivileged userns; tests cover both branches; no regression to other directives: Criterion 1 (host control outside unit; ENFORCED only host rc==0 & unit rc!=0; UNKNOWN when host denies; tests both branches; no regression):
- _host_unshare_baseline (scripts/systemd-directive-probe.py:264-296) runs [unshare,"--user","--pid","true"] via subprocess.run directly, no unit switches, bounded timeout 10s. Returns (None,reason) on missing/exec-error/timeout.
- _judge_restrict_namespaces (lines 303-331): baseline_rc None -> UNKNOWN; baseline_rc!=0 -> UNKNOWN "host denies unprivileged user namespaces"; observed!=0 -> ENFORCED (only when host rc==0); else NOT_ENFORCED.
- Tests: plugin/test_systemd_directive_probe.py test_rns_host_denies_is_unknown_despite_inunit_denial (UNKNOWN branch), test_rns_host_allows_and_unit_denies_is_enforced (ENFORCED branch), test_rns_host_allows_and_unit_allows_is_not_enforced, test_rns_host_baseline_timeout_is_unknown, test_host_baseline_missing_executable_is_unknown, test_host_baseline_executable_error_is_unknown.
- Targeted run: 17 passed in 10.98s (incl live host test).
- Commit 108bc78 diff touches only _host_unshare_baseline + _judge_restrict_namespaces; grep for def _judge/_JUDGES/_PAYLOADS in diff = no matches -> no other directive judges changed.
- Full suite: RUNNING (pending).

Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
