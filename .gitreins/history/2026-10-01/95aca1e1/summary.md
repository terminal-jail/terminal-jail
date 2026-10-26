# Verdict: TJ-GAP-085

**Task:** Expose rule resolution provenance in verdict
**Evaluated:** 2026-10-01T04:29:21.479306
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out
- ✓ **tier2**
  - COMPLETE
  ✓ A 'layer' field exists on InterceptResult (engine/yaml/user/pack) populated in Decider based on which rule source matched; shipped-mirror-as-user-dir shadowing and same-id downgrade are visible at decision time; JSON bridge serializes layer on engine verdicts and null on error envelopes; tests pin builtin/yaml/user/pack layers including the downgraded-builtin case; .venv/bin/python -m pytest plugin/test_interruptor.py passes with the new assertions.: Layer field: types.py:51 __slots__ includes 'layer', types.py:60 default Layer.ENGINE, Layer class types.py:17-38 defines ENGINE/YAML/USER/PACK. Populated in Decider: decider.py:94-139 _build_rule_layers re-walks loader dirs mapping rule id->layer; _layer_for decider.py:479-487; _rule_result decider.py:489-540 and _result_for decider.py:542-556 pass layer; aggregate paths decider.py:243-247,258,268,276,300-330. Shipped-mirror-as-user-dir shadowing: decider.py:44-46 _SHIPPED_MIRROR_NAMES; verified live with user_rules_dir=plugin/terminal_jail/rules -> layer 'yaml'. Same-id downgrade: test_interruptor.py:3819 test_downgraded_builtin_names_the_user_layer overrides real builtin builtin-fdisk (blocklist.py:126) to warn -> layer 'user' (PASSED). JSON bridge: interruptor_bridge.py:102 layer on engine verdicts, :124/:150 layer None on fail-open/fail-closed error envelopes; verified live: engine verdict layer 'engine', invalid-JSON envelope layer null, fail-closed envelope layer null. Tests: TestRuleLayerProvenance (test_interruptor.py:3730-3902) pins engine/yaml/user/pack + downgraded-builtin; TestBridgeVerdictLayerField (:3905-3944) pins bridge engine layer. Test command `.venv/bin/python -m pytest plugin/test_interruptor.py -q -p no:cacheprovider` -> exit_code 0, '515 passed in 2.12s'; 42 layer/provenance tests pass; LSP diagnostics 0. [resolution 0.15; plugin/test_interruptor.py]
The layer provenance field is fully implemented on InterceptResult, populated in Decider for all rule sources, serialized by the JSON bridge (engine value / null on error envelopes), pinned by builtin/yaml/user/pack + downgraded-builtin tests, and plugin/test_interruptor.py passes 515/515.

## Summary

Judge Result: TJ-GAP-085

Stage tier1: FAIL
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: Command timed out

Stage tier2: PASS
  COMPLETE
  ✓ A 'layer' field exists on InterceptResult (engine/yaml/user/pack) populated in Decider based on which rule source matched; shipped-mirror-as-user-dir shadowing and same-id downgrade are visible at decision time; JSON bridge serializes layer on engine verdicts and null on error envelopes; tests pin builtin/yaml/user/pack layers including the downgraded-builtin case; .venv/bin/python -m pytest plugin/test_interruptor.py passes with the new assertions.: Layer field: types.py:51 __slots__ includes 'layer', types.py:60 default Layer.ENGINE, Layer class types.py:17-38 defines ENGINE/YAML/USER/PACK. Populated in Decider: decider.py:94-139 _build_rule_layers re-walks loader dirs mapping rule id->layer; _layer_for decider.py:479-487; _rule_result decider.py:489-540 and _result_for decider.py:542-556 pass layer; aggregate paths decider.py:243-247,258,268,276,300-330. Shipped-mirror-as-user-dir shadowing: decider.py:44-46 _SHIPPED_MIRROR_NAMES; verified live with user_rules_dir=plugin/terminal_jail/rules -> layer 'yaml'. Same-id downgrade: test_interruptor.py:3819 test_downgraded_builtin_names_the_user_layer overrides real builtin builtin-fdisk (blocklist.py:126) to warn -> layer 'user' (PASSED). JSON bridge: interruptor_bridge.py:102 layer on engine verdicts, :124/:150 layer None on fail-open/fail-closed error envelopes; verified live: engine verdict layer 'engine', invalid-JSON envelope layer null, fail-closed envelope layer null. Tests: TestRuleLayerProvenance (test_interruptor.py:3730-3902) pins engine/yaml/user/pack + downgraded-builtin; TestBridgeVerdictLayerField (:3905-3944) pins bridge engine layer. Test command `.venv/bin/python -m pytest plugin/test_interruptor.py -q -p no:cacheprovider` -> exit_code 0, '515 passed in 2.12s'; 42 layer/provenance tests pass; LSP diagnostics 0. [resolution 0.15; plugin/test_interruptor.py]
The layer provenance field is fully implemented on InterceptResult, populated in Decider for all rule sources, serialized by the JSON bridge (engine value / null on error envelopes), pinned by builtin/yaml/user/pack + downgraded-builtin tests, and plugin/test_interruptor.py passes 515/515.

Overall: FAIL ✗
