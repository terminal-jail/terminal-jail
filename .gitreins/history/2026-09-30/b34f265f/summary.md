# Verdict: TJ-GAP-085

**Task:** Expose rule resolution provenance in verdict
**Evaluated:** 2026-09-30T06:20:10.575613
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out
- ✓ **tier2**
  - COMPLETE
  ✓ The engine returns rule_id and reason but not which layer won (engine builtin vs shipped YAML mirror vs user rule dir vs rule pack). Add a 'layer' field to InterceptResult (engine/yaml/user/pack) and populate it in Decider.evaluate() based on which rule source matched. Update plugin/test_interruptor.py to assert the layer field is present and correct for a builtin rule, a YAML mirror rule, and a user rule. Update the JSON bridge output in plugin/terminal_jail/interruptor_bridge.py to include the layer field. Run .venv/bin/python -m pytest plugin/test_interruptor.py -v and confirm all tests pass including the new layer assertions.: (1) Layer field: plugin/terminal_jail/interruptor/types.py:17-36 defines Layer.ENGINE/YAML/USER/PACK; :51 __slots__ includes 'layer'; :60 constructor default layer=Layer.ENGINE. (2) Populated in Decider.evaluate(): plugin/terminal_jail/interruptor/decider.py:94-139 _build_rule_layers re-walks system/user rules dirs classifying 00-builtins.yaml->YAML, terminal-jail-pack-*.yaml->PACK, else USER; :382-390 _layer_for() returns map value or Layer.ENGINE for builtins; :410-448 _rule_result passes layer=layer on BLOCK/MODIFY/WARN/ALLOW paths; :456-465 _result_for (whole-command blocklist pass) passes layer=self._layer_for(rule). (3) Tests: plugin/test_interruptor.py:3878-3902 TestRuleLayerProvenance asserts layer=='engine' for builtin (test_builtin_block_rule_reports_layer_engine, test_allowlist_builtin_match_also_reports_engine), 'yaml' for shipped mirror loaded as system dir AND as user dir (:3806-3830), 'user' for a user rule and a downgraded builtin (:3797-3843), 'pack' for terminal-jail-pack-*.yaml (:3845-3870), plus default-allow and aggregate-modify cases. (4) Bridge: plugin/terminal_jail/interruptor_bridge.py:102 emits "layer": getattr(result, "layer", None) in the main verdict; :124 and :150 set layer:None in the fail-open/fail-closed envelopes; test at plugin/test_interruptor.py:3905-3944 runs the real bridge_module.main() and asserts verdict["layer"]=="engine". TEST EVIDENCE: `.venv/bin/python -m pytest plugin/test_interruptor.py -v` -> exit_code 0, tail line '============================= 515 passed in 4.01s =============================='; targeted `-k "Layer or layer or BridgeVerdict"` -> exit_code 0, '11 passed, 504 deselected in 0.40s'. LSP diagnostics: 0 findings. [resolution 0.10; plugin/test_interruptor.py, plugin/terminal_jail/interruptor_bridge.py]


## Summary

Judge Result: TJ-GAP-085

Stage tier1: FAIL
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out

Stage tier2: PASS
  COMPLETE
  ✓ The engine returns rule_id and reason but not which layer won (engine builtin vs shipped YAML mirror vs user rule dir vs rule pack). Add a 'layer' field to InterceptResult (engine/yaml/user/pack) and populate it in Decider.evaluate() based on which rule source matched. Update plugin/test_interruptor.py to assert the layer field is present and correct for a builtin rule, a YAML mirror rule, and a user rule. Update the JSON bridge output in plugin/terminal_jail/interruptor_bridge.py to include the layer field. Run .venv/bin/python -m pytest plugin/test_interruptor.py -v and confirm all tests pass including the new layer assertions.: (1) Layer field: plugin/terminal_jail/interruptor/types.py:17-36 defines Layer.ENGINE/YAML/USER/PACK; :51 __slots__ includes 'layer'; :60 constructor default layer=Layer.ENGINE. (2) Populated in Decider.evaluate(): plugin/terminal_jail/interruptor/decider.py:94-139 _build_rule_layers re-walks system/user rules dirs classifying 00-builtins.yaml->YAML, terminal-jail-pack-*.yaml->PACK, else USER; :382-390 _layer_for() returns map value or Layer.ENGINE for builtins; :410-448 _rule_result passes layer=layer on BLOCK/MODIFY/WARN/ALLOW paths; :456-465 _result_for (whole-command blocklist pass) passes layer=self._layer_for(rule). (3) Tests: plugin/test_interruptor.py:3878-3902 TestRuleLayerProvenance asserts layer=='engine' for builtin (test_builtin_block_rule_reports_layer_engine, test_allowlist_builtin_match_also_reports_engine), 'yaml' for shipped mirror loaded as system dir AND as user dir (:3806-3830), 'user' for a user rule and a downgraded builtin (:3797-3843), 'pack' for terminal-jail-pack-*.yaml (:3845-3870), plus default-allow and aggregate-modify cases. (4) Bridge: plugin/terminal_jail/interruptor_bridge.py:102 emits "layer": getattr(result, "layer", None) in the main verdict; :124 and :150 set layer:None in the fail-open/fail-closed envelopes; test at plugin/test_interruptor.py:3905-3944 runs the real bridge_module.main() and asserts verdict["layer"]=="engine". TEST EVIDENCE: `.venv/bin/python -m pytest plugin/test_interruptor.py -v` -> exit_code 0, tail line '============================= 515 passed in 4.01s =============================='; targeted `-k "Layer or layer or BridgeVerdict"` -> exit_code 0, '11 passed, 504 deselected in 0.40s'. LSP diagnostics: 0 findings. [resolution 0.10; plugin/test_interruptor.py, plugin/terminal_jail/interruptor_bridge.py]


Overall: FAIL ✗
