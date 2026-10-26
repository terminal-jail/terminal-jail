# Verdict: TJ-DF-029

**Task:** systemd-directive-probe RestrictNamespaces missing host-baseline negative control
**Evaluated:** 2026-10-01T06:41:34.283977
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ 1) scripts/systemd-directive-probe.py runs the same unshare --user --pid probe once OUTSIDE the transient unit and stores the host rc.: scripts/systemd-directive-probe.py:264-299 defines _host_unshare_baseline() which runs subprocess.run([unshare, '--user', '--pid', 'true'], ...) directly on the host (argv list, no unit switches) and returns (rc, reason). It is invoked from _judge_restrict_namespaces at line 313 (baseline_rc, baseline_note = _host_unshare_baseline(_HOST_BASELINE_TIMEOUT_S)). test_built_argv_never_touches_gateway_or_etc_or_control_verbs asserts the host-control argv carries no --wait/--collect/--unit switches. PASSED. [resolution 0.14; scripts/systemd-directive-probe.py, plugin/test_packaging.py]
  ✓ 2) Verdict = ENFORCED only when host rc==0 AND unit rc!=0.: scripts/systemd-directive-probe.py:325-328: after baseline_rc==0 check, `if observed != "0": return "ENFORCED"`. Direct invocation confirmed: host rc=0 + unit RNS_RC=1 -> ('ENFORCED', 'unshare --user --pid denied (rc=1); host-baseline rc=0'). Test test_rns_host_allows_and_unit_denies_is_enforced PASSED.
  ✓ 3) When host rc!=0 the verdict is UNKNOWN with a message naming the host denial.: scripts/systemd-directive-probe.py:319-324: `if baseline_rc != 0: return "UNKNOWN", f"host denies unprivileged user namespaces (host-baseline unshare rc={baseline_rc}); ..."`. Direct invocation confirmed host rc=1 -> ('UNKNOWN', 'host denies unprivileged user namespaces (host-baseline unshare rc=1)...'). Test test_rns_host_denies_is_unknown_despite_inunit_denial PASSED (asserts 'host denies' and 'host-baseline' in evidence).
  ✓ 4) CloseOnExec=true control remains UNSUPPORTED (classifier sanity).: scripts/systemd-directive-probe.py: _PAYLOADS['CloseOnExec']=('CloseOnExec=true','true'); _probe_one returns UNSUPPORTED on load rejection for CloseOnExec with the negative-control message; _judge_close_on_exec never returns ENFORCED. test_full_table_rejected_by_manager_is_all_unsupported asserts coe verdict != ENFORCED (PASSED); live test test_live_host_close_on_exec_control_and_enforcement asserts verdict == 'UNSUPPORTED' and PASSED (not skipped) on this host.
  ✓ 5) plugin/test_packaging.py or a new test asserts the UNKNOWN branch on a simulated host-deny scenario.: plugin/test_systemd_directive_probe.py:249 test_rns_host_denies_is_unknown_despite_inunit_denial simulates host-deny via a fake `unshare` on PATH (TJ_FAKE_HOST_UNSHARE_RC=1) and asserts record['verdict']=='UNKNOWN' and 'host denies' in evidence. PASSED. Additional coverage: test_rns_host_baseline_timeout_is_unknown, test_host_baseline_missing_executable_is_unknown, test_host_baseline_executable_error_is_unknown all PASSED.
  ✓ 6) Full pytest suite passes, gitreins guard --full 4/4.: `.venv/bin/python -u -m pytest --tb=short -q -p no:cacheprovider` -> '1558 passed, 7 skipped in 90.60s' (exit 0). `gitreins guard --full` -> 'Tier 1 Guards: PASS (test mode: full, whole tree)' with secrets/lint/tests(full)/static_analysis all PASS; log .gitreins/logs/guard-20261001T064116.825195Z.log shows 'guards: 4 (0 failed, 0 skipped)' and tests exit_code=0, '1558 passed, 7 skipped'.
All six criteria verified: the host-baseline unshare control gates RestrictNamespaces ENFORCED/UNKNOWN correctly, CloseOnExec stays UNSUPPORTED, the simulated host-deny UNKNOWN branch is tested, and both the full pytest suite (1558 passed) and gitreins guard --full (4/4) pass.

## Summary

Judge Result: TJ-DF-029

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ 1) scripts/systemd-directive-probe.py runs the same unshare --user --pid probe once OUTSIDE the transient unit and stores the host rc.: scripts/systemd-directive-probe.py:264-299 defines _host_unshare_baseline() which runs subprocess.run([unshare, '--user', '--pid', 'true'], ...) directly on the host (argv list, no unit switches) and returns (rc, reason). It is invoked from _judge_restrict_namespaces at line 313 (baseline_rc, baseline_note = _host_unshare_baseline(_HOST_BASELINE_TIMEOUT_S)). test_built_argv_never_touches_gateway_or_etc_or_control_verbs asserts the host-control argv carries no --wait/--collect/--unit switches. PASSED. [resolution 0.14; scripts/systemd-directive-probe.py, plugin/test_packaging.py]
  ✓ 2) Verdict = ENFORCED only when host rc==0 AND unit rc!=0.: scripts/systemd-directive-probe.py:325-328: after baseline_rc==0 check, `if observed != "0": return "ENFORCED"`. Direct invocation confirmed: host rc=0 + unit RNS_RC=1 -> ('ENFORCED', 'unshare --user --pid denied (rc=1); host-baseline rc=0'). Test test_rns_host_allows_and_unit_denies_is_enforced PASSED.
  ✓ 3) When host rc!=0 the verdict is UNKNOWN with a message naming the host denial.: scripts/systemd-directive-probe.py:319-324: `if baseline_rc != 0: return "UNKNOWN", f"host denies unprivileged user namespaces (host-baseline unshare rc={baseline_rc}); ..."`. Direct invocation confirmed host rc=1 -> ('UNKNOWN', 'host denies unprivileged user namespaces (host-baseline unshare rc=1)...'). Test test_rns_host_denies_is_unknown_despite_inunit_denial PASSED (asserts 'host denies' and 'host-baseline' in evidence).
  ✓ 4) CloseOnExec=true control remains UNSUPPORTED (classifier sanity).: scripts/systemd-directive-probe.py: _PAYLOADS['CloseOnExec']=('CloseOnExec=true','true'); _probe_one returns UNSUPPORTED on load rejection for CloseOnExec with the negative-control message; _judge_close_on_exec never returns ENFORCED. test_full_table_rejected_by_manager_is_all_unsupported asserts coe verdict != ENFORCED (PASSED); live test test_live_host_close_on_exec_control_and_enforcement asserts verdict == 'UNSUPPORTED' and PASSED (not skipped) on this host.
  ✓ 5) plugin/test_packaging.py or a new test asserts the UNKNOWN branch on a simulated host-deny scenario.: plugin/test_systemd_directive_probe.py:249 test_rns_host_denies_is_unknown_despite_inunit_denial simulates host-deny via a fake `unshare` on PATH (TJ_FAKE_HOST_UNSHARE_RC=1) and asserts record['verdict']=='UNKNOWN' and 'host denies' in evidence. PASSED. Additional coverage: test_rns_host_baseline_timeout_is_unknown, test_host_baseline_missing_executable_is_unknown, test_host_baseline_executable_error_is_unknown all PASSED.
  ✓ 6) Full pytest suite passes, gitreins guard --full 4/4.: `.venv/bin/python -u -m pytest --tb=short -q -p no:cacheprovider` -> '1558 passed, 7 skipped in 90.60s' (exit 0). `gitreins guard --full` -> 'Tier 1 Guards: PASS (test mode: full, whole tree)' with secrets/lint/tests(full)/static_analysis all PASS; log .gitreins/logs/guard-20261001T064116.825195Z.log shows 'guards: 4 (0 failed, 0 skipped)' and tests exit_code=0, '1558 passed, 7 skipped'.
All six criteria verified: the host-baseline unshare control gates RestrictNamespaces ENFORCED/UNKNOWN correctly, CloseOnExec stays UNSUPPORTED, the simulated host-deny UNKNOWN branch is tested, and both the full pytest suite (1558 passed) and gitreins guard --full (4/4) pass.

Overall: PASS ✓
