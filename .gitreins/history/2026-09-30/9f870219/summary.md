# Verdict: TJ-GAP-085

**Task:** Expose rule resolution provenance in verdict
**Evaluated:** 2026-09-30T06:34:22.813692
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out
- ✓ **tier2**
  - COMPLETE
  ✓ The engine returns rule_id and reason but not which layer won (engine builtin vs shipped YAML mirror vs user rule dir vs rule pack). Add a 'layer' field to InterceptResult (engine/yaml/user/pack) and populate it in Decider.evaluate() based on which rule source matched. Update plugin/test_interruptor.py to assert the layer field is present and correct for a builtin rule, a YAML mirror rule, and a user rule. Update the JSON bridge output in plugin/terminal_jail/interruptor_bridge.py to include the layer field. Run .venv/bin/python -m pytest plugin/test_interruptor.py -v and confirm all tests pass including the new layer assertions.: Layer class (ENGINE/YAML/USER/PACK) added at plugin/terminal_jail/interruptor/types.py:17-37; InterceptResult gains 'layer' slot/param defaulting to Layer.ENGINE (types.py:51,60,67). Decider._build_rule_layers classifies each loaded file (shipped mirror 00-builtins.yaml -> YAML, terminal-jail-pack-*.yaml -> PACK, other rules.d files -> USER) at decider.py:94-139; _layer_for returns the map value or ENGINE (decider.py:382-390); _rule_result/_result_for populate layer (decider.py:410,417,427,435,439,448,463) and evaluate()'s aggregate allow/modify/warn paths carry the deciding layer (decider.py:245-311). Bridge emits "layer": getattr(result,"layer",None) at plugin/terminal_jail/interruptor_bridge.py:102 (plus layer:None in fail-open/fail-closed envelopes at :124,:150). Tests added: TestRuleLayerProvenance asserts layer=='engine' for builtin block/allowlist/default, 'yaml' for the mirror as system dir AND as user dir, 'user' for a custom rule and a downgraded builtin, 'pack' for a pack file, and 'user' for an aggregate modify (plugin/test_interruptor.py:3727-3903); TestBridgeVerdictLayerField asserts the JSON verdict carries layer=='engine' (plugin/test_interruptor.py:3905-3944). Ran `.venv/bin/python -m pytest plugin/test_interruptor.py -v` -> exit_code 0, output '515 passed in 3.78s', with every TestRuleLayerProvenance and TestBridgeVerdictLayerField test PASSED. [resolution 0.12; plugin/test_interruptor.py, plugin/terminal_jail/interruptor_bridge.py]
The layer provenance field is implemented end-to-end (types, decider, bridge) with tests covering builtin/yaml/user/pack, and the full test file passes 515/515.

## Summary

Judge Result: TJ-GAP-085

Stage tier1: FAIL
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out

Stage tier2: PASS
  COMPLETE
  ✓ The engine returns rule_id and reason but not which layer won (engine builtin vs shipped YAML mirror vs user rule dir vs rule pack). Add a 'layer' field to InterceptResult (engine/yaml/user/pack) and populate it in Decider.evaluate() based on which rule source matched. Update plugin/test_interruptor.py to assert the layer field is present and correct for a builtin rule, a YAML mirror rule, and a user rule. Update the JSON bridge output in plugin/terminal_jail/interruptor_bridge.py to include the layer field. Run .venv/bin/python -m pytest plugin/test_interruptor.py -v and confirm all tests pass including the new layer assertions.: Layer class (ENGINE/YAML/USER/PACK) added at plugin/terminal_jail/interruptor/types.py:17-37; InterceptResult gains 'layer' slot/param defaulting to Layer.ENGINE (types.py:51,60,67). Decider._build_rule_layers classifies each loaded file (shipped mirror 00-builtins.yaml -> YAML, terminal-jail-pack-*.yaml -> PACK, other rules.d files -> USER) at decider.py:94-139; _layer_for returns the map value or ENGINE (decider.py:382-390); _rule_result/_result_for populate layer (decider.py:410,417,427,435,439,448,463) and evaluate()'s aggregate allow/modify/warn paths carry the deciding layer (decider.py:245-311). Bridge emits "layer": getattr(result,"layer",None) at plugin/terminal_jail/interruptor_bridge.py:102 (plus layer:None in fail-open/fail-closed envelopes at :124,:150). Tests added: TestRuleLayerProvenance asserts layer=='engine' for builtin block/allowlist/default, 'yaml' for the mirror as system dir AND as user dir, 'user' for a custom rule and a downgraded builtin, 'pack' for a pack file, and 'user' for an aggregate modify (plugin/test_interruptor.py:3727-3903); TestBridgeVerdictLayerField asserts the JSON verdict carries layer=='engine' (plugin/test_interruptor.py:3905-3944). Ran `.venv/bin/python -m pytest plugin/test_interruptor.py -v` -> exit_code 0, output '515 passed in 3.78s', with every TestRuleLayerProvenance and TestBridgeVerdictLayerField test PASSED. [resolution 0.12; plugin/test_interruptor.py, plugin/terminal_jail/interruptor_bridge.py]
The layer provenance field is implemented end-to-end (types, decider, bridge) with tests covering builtin/yaml/user/pack, and the full test file passes 515/515.

Overall: FAIL ✗
