# Verdict: TJ-GAP-097

**Task:** Resident bridge accept loop cannot spin on a closed listening socket
**Evaluated:** 2026-10-23T03:55:23.836934
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ A SIGINT or SIGTERM delivered while plugin/terminal_jail/interruptor_resident.py is blocked in accept() terminates the daemon with exit code 128 plus the signal number instead of leaving it looping: Live probe (/tmp/sig_probe.py) started the real daemon, waited for socket readiness, then signalled it: 'SIGTERM rc= 143 expected= 143 sock_exists= False' and 'SIGINT rc= 130 expected= 130 sock_exists= False' — no hang. Code: interruptor_resident.py _clean_exit sets _shutting_down/_shutdown_signum BEFORE _cleanup() then raises SystemExit(128+signum); _accept_loop raises SystemExit(128 + _shutdown_signum) when _listener_gone() and _shutting_down. TestSignalShutdown cells (test_sigterm_removes_socket, test_sigint_removes_socket, test_sigterm_mid_stream_still_cleans_up) assert rc == 128+signal and pass in the 29-passed run. [resolution 0.04; plugin/terminal_jail/interruptor_resident.py]
  ✓ The accept loop stops when the listening socket is closed (EBADF or a marked shutdown) and still continues on a genuine transient OSError: interruptor_resident.py _listener_gone(): returns True on _shutting_down marker, exc.errno == errno.EBADF, or server.fileno() == -1. _accept_loop: 'if not _listener_gone(exc, server): continue' (transient EINTR/ECONNABORTED retried), else SystemExit(128+signum) when shutting down, else SystemExit(1) with a stderr note. test_transient_error_keeps_serving proves EINTR then ECONNABORTED are retried, the connection is served, and the loop stops on EBADF (calls == 4).
  ✓ plugin/test_resident_bridge.py contains a regression test that drives the loop with a listener raising EBADF and asserts it stops, plus the transient-error direction, and that test fails against the pre-fix loop: TestAcceptLoopOnDeadListener (test_resident_bridge.py:700-760) with _ScriptedListener: test_closed_listener_ends_the_loop (EBADF, asserts listener.calls == 1 and SystemExit code not in (0, None)), test_shutdown_marker_ends_the_loop_with_the_signal_exit_code (asserts 128+SIGTERM), test_transient_error_keeps_serving (EINTR/ECONNABORTED retried, conn served, calls == 4). Pre-fix verification: restoring a623273^ interruptor_resident.py (inline 'while True: try accept except OSError: continue') made all 3 cells FAIL — 'AttributeError: module terminal_jail.interruptor_resident has no attribute _accept_loop' — i.e. the cells cannot pass against the pre-fix loop. Files restored afterwards (git status clean for plugin/). [resolution 0.04; plugin/test_resident_bridge.py]
  ✓ .venv/bin/python -m pytest plugin/test_resident_bridge.py passes and uvx ruff check . reports All checks passed: '.venv/bin/python -m pytest plugin/test_resident_bridge.py -q' -> exit_code 0, '29 passed in 2.31s' (re-run after restoring files: '29 passed in 2.34s'). 'uvx ruff check .' -> exit_code 0, 'All checks passed!'. [resolution 0.04; plugin/test_resident_bridge.py]
The accept loop now stops on a dead listener (EBADF/shutdown marker) while retrying genuine transient errors, signals exit with 128+signum (verified live: 143/130), the new regression cells fail against the pre-fix loop, and pytest (29 passed) plus ruff (All checks passed) are green.

## Summary

Judge Result: TJ-GAP-097

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ A SIGINT or SIGTERM delivered while plugin/terminal_jail/interruptor_resident.py is blocked in accept() terminates the daemon with exit code 128 plus the signal number instead of leaving it looping: Live probe (/tmp/sig_probe.py) started the real daemon, waited for socket readiness, then signalled it: 'SIGTERM rc= 143 expected= 143 sock_exists= False' and 'SIGINT rc= 130 expected= 130 sock_exists= False' — no hang. Code: interruptor_resident.py _clean_exit sets _shutting_down/_shutdown_signum BEFORE _cleanup() then raises SystemExit(128+signum); _accept_loop raises SystemExit(128 + _shutdown_signum) when _listener_gone() and _shutting_down. TestSignalShutdown cells (test_sigterm_removes_socket, test_sigint_removes_socket, test_sigterm_mid_stream_still_cleans_up) assert rc == 128+signal and pass in the 29-passed run. [resolution 0.04; plugin/terminal_jail/interruptor_resident.py]
  ✓ The accept loop stops when the listening socket is closed (EBADF or a marked shutdown) and still continues on a genuine transient OSError: interruptor_resident.py _listener_gone(): returns True on _shutting_down marker, exc.errno == errno.EBADF, or server.fileno() == -1. _accept_loop: 'if not _listener_gone(exc, server): continue' (transient EINTR/ECONNABORTED retried), else SystemExit(128+signum) when shutting down, else SystemExit(1) with a stderr note. test_transient_error_keeps_serving proves EINTR then ECONNABORTED are retried, the connection is served, and the loop stops on EBADF (calls == 4).
  ✓ plugin/test_resident_bridge.py contains a regression test that drives the loop with a listener raising EBADF and asserts it stops, plus the transient-error direction, and that test fails against the pre-fix loop: TestAcceptLoopOnDeadListener (test_resident_bridge.py:700-760) with _ScriptedListener: test_closed_listener_ends_the_loop (EBADF, asserts listener.calls == 1 and SystemExit code not in (0, None)), test_shutdown_marker_ends_the_loop_with_the_signal_exit_code (asserts 128+SIGTERM), test_transient_error_keeps_serving (EINTR/ECONNABORTED retried, conn served, calls == 4). Pre-fix verification: restoring a623273^ interruptor_resident.py (inline 'while True: try accept except OSError: continue') made all 3 cells FAIL — 'AttributeError: module terminal_jail.interruptor_resident has no attribute _accept_loop' — i.e. the cells cannot pass against the pre-fix loop. Files restored afterwards (git status clean for plugin/). [resolution 0.04; plugin/test_resident_bridge.py]
  ✓ .venv/bin/python -m pytest plugin/test_resident_bridge.py passes and uvx ruff check . reports All checks passed: '.venv/bin/python -m pytest plugin/test_resident_bridge.py -q' -> exit_code 0, '29 passed in 2.31s' (re-run after restoring files: '29 passed in 2.34s'). 'uvx ruff check .' -> exit_code 0, 'All checks passed!'. [resolution 0.04; plugin/test_resident_bridge.py]
The accept loop now stops on a dead listener (EBADF/shutdown marker) while retrying genuine transient errors, signals exit with 128+signum (verified live: 143/130), the new regression cells fail against the pre-fix loop, and pytest (29 passed) plus ruff (All checks passed) are green.

Overall: PASS ✓
