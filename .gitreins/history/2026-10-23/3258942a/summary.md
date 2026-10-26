# Verdict: INT-CI-014

**Task:** SIGTERM resident-bridge cells get the bounded runner-stall retry plus stderr evidence
**Evaluated:** 2026-10-23T03:58:40.271226
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ Both SIGTERM cells in plugin/test_resident_bridge.py still assert the daemon exit code equals 128 + signal.SIGTERM AND that the socket path no longer exists after the signal: plugin/test_resident_bridge.py:573-577 (test_sigterm_removes_socket) asserts `rc == 128 + signal.SIGTERM` and `assert clean` where clean = `not sock.exists()` from _sigterm_once (L536); plugin/test_resident_bridge.py:637-641 (test_sigterm_mid_stream_still_cleans_up) has the identical pair of assertions. [resolution 0.12; plugin/test_resident_bridge.py]
  ✓ A shared _sigterm_once helper in plugin/test_resident_bridge.py retries exactly once on a fresh socket path and reads the daemon stderr before killing it, printing a [sigterm-cell] daemon stderr at hang marker: plugin/test_resident_bridge.py:490-536 defines _sigterm_once(sock, mid_stream) which starts a fresh daemon, and on TimeoutExpired does select.select([proc.stderr]) + os.read(...) to capture stderr BEFORE proc.kill() (L514-527), then prints f"[sigterm-cell] daemon stderr at hang:\n{daemon_err}" to sys.stderr (L528-531). _sigterm_with_retry (L538-558) retries exactly once on a fresh path tmp_path/'s2.sock' (L552, L555-557) after the first attempt on tmp_path/'s.sock' (L550). [resolution 0.12; plugin/test_resident_bridge.py]
  ✓ Running .venv/bin/python -m pytest plugin/test_resident_bridge.py passes, with TestSignalShutdown reporting 3 passed: `.venv/bin/python -m pytest plugin/test_resident_bridge.py -q` -> exit_code 0, '29 passed in 2.05s'. `-k TestSignalShutdown -v` -> exit_code 0, 'collected 29 items / 26 deselected / 3 selected ... 3 passed, 26 deselected in 0.28s'. [resolution 0.12; plugin/test_resident_bridge.py]
  ✓ The change touches only plugin/test_resident_bridge.py against base 8730de5; no production module is modified: `git diff 8730de5 4bdec78 --stat` (the INT-CI-014 implementation commit, merged as f3eca48) shows exactly one file: 'plugin/test_resident_bridge.py | 124 +++++++++++++++++++++++----------, 1 file changed, 96 insertions(+), 28 deletions(-)'. No production module (e.g. plugin/terminal_jail/interruptor_resident.py) appears in that diff. [resolution 0.12; plugin/test_resident_bridge.py]
  ✓ uvx ruff check . reports All checks passed: `uvx ruff check .` -> exit_code 0, output 'All checks passed!'.
All five criteria verified: both SIGTERM cells keep the exit-code and socket-removed assertions, the shared _sigterm_once helper captures stderr before kill and retries once on a fresh socket, pytest reports 29 passed with TestSignalShutdown at 3 passed, the diff against 8730de5 touches only plugin/test_resident_bridge.py, and ruff reports All checks passed.

## Summary

Judge Result: INT-CI-014

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ Both SIGTERM cells in plugin/test_resident_bridge.py still assert the daemon exit code equals 128 + signal.SIGTERM AND that the socket path no longer exists after the signal: plugin/test_resident_bridge.py:573-577 (test_sigterm_removes_socket) asserts `rc == 128 + signal.SIGTERM` and `assert clean` where clean = `not sock.exists()` from _sigterm_once (L536); plugin/test_resident_bridge.py:637-641 (test_sigterm_mid_stream_still_cleans_up) has the identical pair of assertions. [resolution 0.12; plugin/test_resident_bridge.py]
  ✓ A shared _sigterm_once helper in plugin/test_resident_bridge.py retries exactly once on a fresh socket path and reads the daemon stderr before killing it, printing a [sigterm-cell] daemon stderr at hang marker: plugin/test_resident_bridge.py:490-536 defines _sigterm_once(sock, mid_stream) which starts a fresh daemon, and on TimeoutExpired does select.select([proc.stderr]) + os.read(...) to capture stderr BEFORE proc.kill() (L514-527), then prints f"[sigterm-cell] daemon stderr at hang:\n{daemon_err}" to sys.stderr (L528-531). _sigterm_with_retry (L538-558) retries exactly once on a fresh path tmp_path/'s2.sock' (L552, L555-557) after the first attempt on tmp_path/'s.sock' (L550). [resolution 0.12; plugin/test_resident_bridge.py]
  ✓ Running .venv/bin/python -m pytest plugin/test_resident_bridge.py passes, with TestSignalShutdown reporting 3 passed: `.venv/bin/python -m pytest plugin/test_resident_bridge.py -q` -> exit_code 0, '29 passed in 2.05s'. `-k TestSignalShutdown -v` -> exit_code 0, 'collected 29 items / 26 deselected / 3 selected ... 3 passed, 26 deselected in 0.28s'. [resolution 0.12; plugin/test_resident_bridge.py]
  ✓ The change touches only plugin/test_resident_bridge.py against base 8730de5; no production module is modified: `git diff 8730de5 4bdec78 --stat` (the INT-CI-014 implementation commit, merged as f3eca48) shows exactly one file: 'plugin/test_resident_bridge.py | 124 +++++++++++++++++++++++----------, 1 file changed, 96 insertions(+), 28 deletions(-)'. No production module (e.g. plugin/terminal_jail/interruptor_resident.py) appears in that diff. [resolution 0.12; plugin/test_resident_bridge.py]
  ✓ uvx ruff check . reports All checks passed: `uvx ruff check .` -> exit_code 0, output 'All checks passed!'.
All five criteria verified: both SIGTERM cells keep the exit-code and socket-removed assertions, the shared _sigterm_once helper captures stderr before kill and retries once on a fresh socket, pytest reports 29 passed with TestSignalShutdown at 3 passed, the diff against 8730de5 touches only plugin/test_resident_bridge.py, and ruff reports All checks passed.

Overall: PASS ✓
