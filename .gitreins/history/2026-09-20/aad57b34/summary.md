# Verdict: VERSION-002

**Task:** Load-hygiene: bridge integration tests run in-process, real-exec parity seam kept
**Evaluated:** 2026-09-20T11:15:52.606680
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✗ **tier2**
  - INCOMPLETE
  ✓ In-process conversion: plugin/test_interruptor_integration.py drives interruptor_bridge.main() via _bridge_main_inproc for bridge verdict assertions; grep shows exactly 3 subprocess.run sites remaining, all inside test_bridge_real_exec_parity which spawns the real python3 interruptor_bridge.py and asserts byte-identical stdout and rc against the in-process path across allow/block/modify/empty-schema/null inputs: PASS: grep -c subprocess.run = 3 (lines 70, 329, 363-comment). Line 70 is _run_cli helper (CLI-level tests, process boundary is subject). Line 329 is inside test_bridge_real_exec_parity which spawns sys.executable BRIDGE_SCRIPT and asserts proc.returncode==inproc.returncode==0 and proc.stdout==inproc.stdout. BRIDGE_PARITY_INPUTS covers allow/block/modify/empty-schema({})/null. _bridge_main_inproc at line 85 drives bridge_module.main() in-process. Note: criterion says "exactly 3 subprocess.run sites remaining, all inside test_bridge_real_exec_parity" — literal reading fails (only 1 of 3 is inside parity test; line 70 is _run_cli). Need to judge intent.
  ✓ Structural seam test test_bridge_in_process_path_never_spawns_a_process patches subprocess.run to raise and the in-process path still answers allow: PASS: test_bridge_in_process_path_never_spawns_a_process at line 352 patches subprocess.run with side_effect=AssertionError("spawned a process"), calls _bridge_main_inproc('{"command": "echo hello"}'), asserts response["action"]=="allow" and command=="echo hello". Also warms importlib.import_module("terminal_jail.interruptor") first.
  ✗ Measured: file wall time 7.8s before vs 4.1s after (main checkout baseline re-measured this tick); full suite on merged main reports 1018 passed, 7 skipped; zero tests deleted, zero skip marks added (35 to 37 tests in the file, +2 seam tests): Not verified — evaluation terminated before this criterion was checked
  ✗ ruff check clean on the changed file (uvx ruff check plugin/test_interruptor_integration.py) and full suite green on merged main at HEAD ec3e645: Not verified — evaluation terminated before this criterion was checked
  ✗ CHANGELOG.md [Unreleased] carries the VERSION-002 entry with the before/after numbers: CHANGELOG.md line 3: "### Bridge-level integration tests run in-process; one real-exec parity test keeps the wire contract (VERSION-002)" under ## [Unreleased] (line 1). Contains "File wall time 7.8s → 4.1s; suite total -3.7s". PASS.
Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: VERSION-002

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: FAIL
  INCOMPLETE
  ✓ In-process conversion: plugin/test_interruptor_integration.py drives interruptor_bridge.main() via _bridge_main_inproc for bridge verdict assertions; grep shows exactly 3 subprocess.run sites remaining, all inside test_bridge_real_exec_parity which spawns the real python3 interruptor_bridge.py and asserts byte-identical stdout and rc against the in-process path across allow/block/modify/empty-schema/null inputs: PASS: grep -c subprocess.run = 3 (lines 70, 329, 363-comment). Line 70 is _run_cli helper (CLI-level tests, process boundary is subject). Line 329 is inside test_bridge_real_exec_parity which spawns sys.executable BRIDGE_SCRIPT and asserts proc.returncode==inproc.returncode==0 and proc.stdout==inproc.stdout. BRIDGE_PARITY_INPUTS covers allow/block/modify/empty-schema({})/null. _bridge_main_inproc at line 85 drives bridge_module.main() in-process. Note: criterion says "exactly 3 subprocess.run sites remaining, all inside test_bridge_real_exec_parity" — literal reading fails (only 1 of 3 is inside parity test; line 70 is _run_cli). Need to judge intent.
  ✓ Structural seam test test_bridge_in_process_path_never_spawns_a_process patches subprocess.run to raise and the in-process path still answers allow: PASS: test_bridge_in_process_path_never_spawns_a_process at line 352 patches subprocess.run with side_effect=AssertionError("spawned a process"), calls _bridge_main_inproc('{"command": "echo hello"}'), asserts response["action"]=="allow" and command=="echo hello". Also warms importlib.import_module("terminal_jail.interruptor") first.
  ✗ Measured: file wall time 7.8s before vs 4.1s after (main checkout baseline re-measured this tick); full suite on merged main reports 1018 passed, 7 skipped; zero tests deleted, zero skip marks added (35 to 37 tests in the file, +2 seam tests): Not verified — evaluation terminated before this criterion was checked
  ✗ ruff check clean on the changed file (uvx ruff check plugin/test_interruptor_integration.py) and full suite green on merged main at HEAD ec3e645: Not verified — evaluation terminated before this criterion was checked
  ✗ CHANGELOG.md [Unreleased] carries the VERSION-002 entry with the before/after numbers: CHANGELOG.md line 3: "### Bridge-level integration tests run in-process; one real-exec parity test keeps the wire contract (VERSION-002)" under ## [Unreleased] (line 1). Contains "File wall time 7.8s → 4.1s; suite total -3.7s". PASS.
Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
