# Verdict: DF-TERMINAL-JAIL-6

**Task:** Validate bridge JSON schema before evaluation
**Evaluated:** 2026-09-17T02:56:49.680713
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m9:55PM[0m [32mINF[0m [1mscanned ~3454851 bytes (3.45 MB) in 293ms[0m
[90m9:55PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ Missing or misnamed command key returns the existing bridge-error JSON envelope with exit 0 rather than an empty reason.: plugin/terminal_jail/interruptor_bridge.py:54-56 adds `if "command" not in payload: _emit_fail_open("missing 'command' key")`. Live subprocess runs: `{}`, `{"Command":"echo hi"}`, `{"cmd":"echo hi"}` each -> rc=0 with reason="[bridge-error] missing 'command' key — fail-open: allowing command". Pre-fix bridge (HEAD~1, run in-place) returned rc=0 with reason="" (the empty-reason bug), confirming RED->GREEN. Tests: `pytest plugin/test_interruptor_integration.py -q -k "schema or valid_controls or covers_missing"` => 16 passed, 19 deselected.
  ✓ Non-object JSON values return a bridge-error JSON response with no traceback; non-string commands retain their error behavior.: interruptor_bridge.py:49-51 `if not isinstance(payload, dict): _emit_fail_open(f"payload must be a JSON object, got {type(payload).__name__}")`. Live runs: null->"got NoneType", []->"got list", "echo hi"->"got str", 42->"got int", true->"got bool" — all rc=0, stderr empty, no traceback. Pre-fix: null/[] exited rc=1 with "Traceback (most recent call last)" on stderr. Non-string retained: `{"command":123}` -> rc=0 reason="[bridge-error] command field must be a string", byte-identical to pre-fix HEAD~1 output (lines 58-60 logic unchanged).
  ✓ Explicit empty string remains a valid command and harmless valid commands preserve their behavior.: interruptor_bridge.py:54-60 only rejects a missing key or non-str value, so `{"command": ""}` passes the gate. Live run: `{"command":""}` -> rc=0, action=allow, command="", reason="" (no [bridge-error]). `{"command":"echo hello"}` -> rc=0, action=allow, command="echo hello", reason="". Block path intact: `{"command":"rm -rf /"}` -> action=block, rule_id=builtin-rm-rf-root (test_interruptor_integration.py:668-670). test_bridge_valid_controls_unaffected_by_schema_checks (line 652) passes.
  ✓ Subprocess regression tests cover missing keys, non-object values, non-string commands and valid controls; README and quickstart describe schema errors accurately.: plugin/test_interruptor_integration.py:574 `_run_bridge_raw` invokes the real bridge via subprocess.run and asserts rc==0, no "Traceback" in stderr, exactly one JSON line. test_bridge_schema_errors_reported_fail_open (line 620) is parametrized over 14 cases spanning missing/misnamed keys ({}, {"nope"}, {"Command"}, {"cmd"}), non-objects (null, [], "echo hello", 42, 3.14, true) and non-strings ({"command":123}, ["echo"], null, {"cmd":"echo"}); test_bridge_valid_controls_unaffected_by_schema_checks (line 652) covers empty-string/echo/block controls; test_bridge_covers_missing_keys_non_objects_non_strings_and_valid (line 674) is an anti-shrink guard over all four classes. Docs: README.md:68-81 and docs/quickstart.md:244-258 both state the object/key/type contract, name missing/misnamed key, non-object payload and non-string command, distinguish error reporting from blocking, and note {"command":""} is valid. Test output: `pytest plugin/test_interruptor_integration.py --tb=short -q` => "34 passed, 1 skipped in 4.26s"; full suite `pytest -x --tb=short -q` => "420 passed, 14 skipped in 13.68s"; `ruff check` => "All checks passed!"; LSP diagnostics count 0.
The bridge now validates payload shape before evaluation, emitting the documented fail-open [bridge-error] envelope with exit 0 for missing/misnamed keys and non-object JSON (previously an empty reason and an AttributeError traceback respectively), while empty-string and valid commands are unchanged — verified by live subprocess runs, RED-proof against the pre-fix bridge, 34 passing integration tests, a green 420-test full suite, and accurate README/quickstart docs.

## Summary

Judge Result: DF-TERMINAL-JAIL-6

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m9:55PM[0m [32mINF[0m [1mscanned ~3454851 bytes (3.45 MB) in 293ms[0m
[90m9:55PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ Missing or misnamed command key returns the existing bridge-error JSON envelope with exit 0 rather than an empty reason.: plugin/terminal_jail/interruptor_bridge.py:54-56 adds `if "command" not in payload: _emit_fail_open("missing 'command' key")`. Live subprocess runs: `{}`, `{"Command":"echo hi"}`, `{"cmd":"echo hi"}` each -> rc=0 with reason="[bridge-error] missing 'command' key — fail-open: allowing command". Pre-fix bridge (HEAD~1, run in-place) returned rc=0 with reason="" (the empty-reason bug), confirming RED->GREEN. Tests: `pytest plugin/test_interruptor_integration.py -q -k "schema or valid_controls or covers_missing"` => 16 passed, 19 deselected.
  ✓ Non-object JSON values return a bridge-error JSON response with no traceback; non-string commands retain their error behavior.: interruptor_bridge.py:49-51 `if not isinstance(payload, dict): _emit_fail_open(f"payload must be a JSON object, got {type(payload).__name__}")`. Live runs: null->"got NoneType", []->"got list", "echo hi"->"got str", 42->"got int", true->"got bool" — all rc=0, stderr empty, no traceback. Pre-fix: null/[] exited rc=1 with "Traceback (most recent call last)" on stderr. Non-string retained: `{"command":123}` -> rc=0 reason="[bridge-error] command field must be a string", byte-identical to pre-fix HEAD~1 output (lines 58-60 logic unchanged).
  ✓ Explicit empty string remains a valid command and harmless valid commands preserve their behavior.: interruptor_bridge.py:54-60 only rejects a missing key or non-str value, so `{"command": ""}` passes the gate. Live run: `{"command":""}` -> rc=0, action=allow, command="", reason="" (no [bridge-error]). `{"command":"echo hello"}` -> rc=0, action=allow, command="echo hello", reason="". Block path intact: `{"command":"rm -rf /"}` -> action=block, rule_id=builtin-rm-rf-root (test_interruptor_integration.py:668-670). test_bridge_valid_controls_unaffected_by_schema_checks (line 652) passes.
  ✓ Subprocess regression tests cover missing keys, non-object values, non-string commands and valid controls; README and quickstart describe schema errors accurately.: plugin/test_interruptor_integration.py:574 `_run_bridge_raw` invokes the real bridge via subprocess.run and asserts rc==0, no "Traceback" in stderr, exactly one JSON line. test_bridge_schema_errors_reported_fail_open (line 620) is parametrized over 14 cases spanning missing/misnamed keys ({}, {"nope"}, {"Command"}, {"cmd"}), non-objects (null, [], "echo hello", 42, 3.14, true) and non-strings ({"command":123}, ["echo"], null, {"cmd":"echo"}); test_bridge_valid_controls_unaffected_by_schema_checks (line 652) covers empty-string/echo/block controls; test_bridge_covers_missing_keys_non_objects_non_strings_and_valid (line 674) is an anti-shrink guard over all four classes. Docs: README.md:68-81 and docs/quickstart.md:244-258 both state the object/key/type contract, name missing/misnamed key, non-object payload and non-string command, distinguish error reporting from blocking, and note {"command":""} is valid. Test output: `pytest plugin/test_interruptor_integration.py --tb=short -q` => "34 passed, 1 skipped in 4.26s"; full suite `pytest -x --tb=short -q` => "420 passed, 14 skipped in 13.68s"; `ruff check` => "All checks passed!"; LSP diagnostics count 0.
The bridge now validates payload shape before evaluation, emitting the documented fail-open [bridge-error] envelope with exit 0 for missing/misnamed keys and non-object JSON (previously an empty reason and an AttributeError traceback respectively), while empty-string and valid commands are unchanged — verified by live subprocess runs, RED-proof against the pre-fix bridge, 34 passing integration tests, a green 420-test full suite, and accurate README/quickstart docs.

Overall: PASS ✓
