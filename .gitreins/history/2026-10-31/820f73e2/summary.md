# Verdict: QA-TERMINAL-JAIL-22

**Task:** tests: resident-bridge socket paths beyond sun_path limit
**Evaluated:** 2026-10-31T16:36:15.025715
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_egress_no_delivery.py::test_curl_upload_reaches_no_collector [first failing id])
- ✓ **tier2**
  - COMPLETE
  ✓ plugin/test_resident_bridge.py resident-bridge tests pass on a deep pytest tmp_path (basetemp >108 chars) via a short /tmp socket fallback; no silent skips in default runs; plugin suite equal-or-better with the helper pinned by unit tests: All three sub-claims verified with live command output. (1) DEEP BASETEMP: `.venv/bin/python -m pytest plugin/test_resident_bridge.py -q --basetemp=/tmp/aaaa...(60)/bbbb...(60)/deepbase` (len=135) => `31 passed in 2.76s`, exit 0. RED proof: the pre-fix file (git show a65d946^:plugin/test_resident_bridge.py) at the same 135-char basetemp => `13 failed, 16 passed`, failures being 'AF_UNIX path too long'; a direct socket.bind() on the deep path confirms `OSError: AF_UNIX path too long`, so the fallback is what makes the deep run green. (2) SHORT /tmp FALLBACK: plugin/test_resident_bridge.py:63-80 `_daemon_sock_path` returns paths <100 bytes unchanged and otherwise mkdtemp(prefix='tjr-', dir='/tmp'); invoked directly it returned `/tmp/tjr-jdrua56y/s.sock` (24 bytes, parent is_dir True, registered in _DAEMON_SOCK_FALLBACKS, removed by _cleanup_daemon_sock_dirs). All 12 daemon-starting cells route through the helper (lines 250, 270, 282, 309, 324, 431, 522, 632, 636, 641, 703, 705). (3) NO SILENT SKIPS: default run `31 passed in 2.19s` and deep run `31 passed in 2.09s`, both with `-rs` reporting zero skips; only two pytest.skip calls exist (lines 116, 121) and they are gated at lines 88-96 on `sock_path in _DAEMON_SOCK_FALLBACKS and len(...) <= _SUN_PATH_LIMIT` after an EADDRINUSE unlink-and-rebind retry, so default CI never reaches them. (4) EQUAL-OR-BETTER + HELPER PINNED: test-function count 25 (pre-fix) -> 27 (current), the +2 being TestDaemonSockPathHelper::test_short_path_returned_unchanged and ::test_deep_path_gets_short_tmp_fallback (lines 729-760), both PASSED on the deep basetemp; the stale-socket cell fixed by 62a2743 also PASSED. Full plugin suite: `75 failed, 1815 passed, 29 skipped in 112.91s` — every failure is environmental and in files untouched by this change (test_install: 'PyYAML is not installed', test_standalone_cli/test_userns: 'HOST-DEGRADED-PIDNS', plus landlock/seccomp/egress), while `git show --stat a65d946` and `62a2743` touch only plugin/test_resident_bridge.py and plugin/terminal_jail/interruptor_resident.py. LSP diagnostics: 0 findings. [resolution 0.44; plugin/test_resident_bridge.py]
The resident-bridge suite passes 31/31 with zero skips on a 135-char basetemp via the /tmp fallback (pre-fix: 13 failed), the helper is pinned by two new unit tests, and the only suite failures are pre-existing environmental ones in unrelated files.

## Summary

Judge Result: QA-TERMINAL-JAIL-22

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_egress_no_delivery.py::test_curl_upload_reaches_no_collector [first failing id])

Stage tier2: PASS
  COMPLETE
  ✓ plugin/test_resident_bridge.py resident-bridge tests pass on a deep pytest tmp_path (basetemp >108 chars) via a short /tmp socket fallback; no silent skips in default runs; plugin suite equal-or-better with the helper pinned by unit tests: All three sub-claims verified with live command output. (1) DEEP BASETEMP: `.venv/bin/python -m pytest plugin/test_resident_bridge.py -q --basetemp=/tmp/aaaa...(60)/bbbb...(60)/deepbase` (len=135) => `31 passed in 2.76s`, exit 0. RED proof: the pre-fix file (git show a65d946^:plugin/test_resident_bridge.py) at the same 135-char basetemp => `13 failed, 16 passed`, failures being 'AF_UNIX path too long'; a direct socket.bind() on the deep path confirms `OSError: AF_UNIX path too long`, so the fallback is what makes the deep run green. (2) SHORT /tmp FALLBACK: plugin/test_resident_bridge.py:63-80 `_daemon_sock_path` returns paths <100 bytes unchanged and otherwise mkdtemp(prefix='tjr-', dir='/tmp'); invoked directly it returned `/tmp/tjr-jdrua56y/s.sock` (24 bytes, parent is_dir True, registered in _DAEMON_SOCK_FALLBACKS, removed by _cleanup_daemon_sock_dirs). All 12 daemon-starting cells route through the helper (lines 250, 270, 282, 309, 324, 431, 522, 632, 636, 641, 703, 705). (3) NO SILENT SKIPS: default run `31 passed in 2.19s` and deep run `31 passed in 2.09s`, both with `-rs` reporting zero skips; only two pytest.skip calls exist (lines 116, 121) and they are gated at lines 88-96 on `sock_path in _DAEMON_SOCK_FALLBACKS and len(...) <= _SUN_PATH_LIMIT` after an EADDRINUSE unlink-and-rebind retry, so default CI never reaches them. (4) EQUAL-OR-BETTER + HELPER PINNED: test-function count 25 (pre-fix) -> 27 (current), the +2 being TestDaemonSockPathHelper::test_short_path_returned_unchanged and ::test_deep_path_gets_short_tmp_fallback (lines 729-760), both PASSED on the deep basetemp; the stale-socket cell fixed by 62a2743 also PASSED. Full plugin suite: `75 failed, 1815 passed, 29 skipped in 112.91s` — every failure is environmental and in files untouched by this change (test_install: 'PyYAML is not installed', test_standalone_cli/test_userns: 'HOST-DEGRADED-PIDNS', plus landlock/seccomp/egress), while `git show --stat a65d946` and `62a2743` touch only plugin/test_resident_bridge.py and plugin/terminal_jail/interruptor_resident.py. LSP diagnostics: 0 findings. [resolution 0.44; plugin/test_resident_bridge.py]
The resident-bridge suite passes 31/31 with zero skips on a 135-char basetemp via the /tmp fallback (pre-fix: 13 failed), the helper is pinned by two new unit tests, and the only suite failures are pre-existing environmental ones in unrelated files.

Overall: FAIL ✗
