# Verdict: DOC-21

**Task:** Refresh quickstart bridge transcript layer fields
**Evaluated:** 2026-10-25T16:40:47.358935
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ The five later bridge envelopes include layer and a fresh malformed-input probe returns exactly action, command, modified, rule_id, reason, layer: docs/quickstart.md §3a2: all five later envelopes now carry `layer` — malformed-input enforce (lines 349-353, "layer": null), malformed-input warn (355-357, "layer": null), engine-eval failure via poison rules file (381-385, "layer": null), warn-mode blockable command (400-403, "layer": "engine"), max-arg refusal (419-423, "layer": "engine"). Live re-capture with .venv/bin/python and rules dirs pinned to /tmp/tj-empty-rules reproduced each verbatim, e.g. `printf 'not json {\n' | .venv/bin/python plugin/terminal_jail/interruptor_bridge.py` -> {"action": "block", "command": "", "modified": null, "rule_id": "[bridge-error]", "reason": "[bridge-error] invalid JSON on stdin — fail-closed: blocking command (enforce mode)", "layer": null}, rc=0; warn mode -> "layer": null; warn blockable -> "layer": "engine"; 266240-byte command -> rule_id "builtin-max-arg-bytes", "layer": "engine"; poison zz-poison.yaml -> RuleSchemaError reason with "layer": null. Programmatic key check on the fresh probe returned exactly ['action', 'command', 'modified', 'rule_id', 'reason', 'layer'] in emission order (plugin/terminal_jail/interruptor_bridge.py:142-160 builds the dict in that order). Tests: `.venv/bin/python -m pytest tests/test_arg_size_ceiling.py tests/test_composed_mode.py tests/test_quickstart_doc.py -q` -> exit 0, "27 passed, 3 skipped in 19.32s" (full suite exceeds the 30s tool cap; targeted doc/bridge tests green).
All five later quickstart bridge envelopes now include `layer`, each verified against a live bridge capture, and a fresh malformed-input probe returns exactly the six documented keys in order.

## Summary

Judge Result: DOC-21

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ The five later bridge envelopes include layer and a fresh malformed-input probe returns exactly action, command, modified, rule_id, reason, layer: docs/quickstart.md §3a2: all five later envelopes now carry `layer` — malformed-input enforce (lines 349-353, "layer": null), malformed-input warn (355-357, "layer": null), engine-eval failure via poison rules file (381-385, "layer": null), warn-mode blockable command (400-403, "layer": "engine"), max-arg refusal (419-423, "layer": "engine"). Live re-capture with .venv/bin/python and rules dirs pinned to /tmp/tj-empty-rules reproduced each verbatim, e.g. `printf 'not json {\n' | .venv/bin/python plugin/terminal_jail/interruptor_bridge.py` -> {"action": "block", "command": "", "modified": null, "rule_id": "[bridge-error]", "reason": "[bridge-error] invalid JSON on stdin — fail-closed: blocking command (enforce mode)", "layer": null}, rc=0; warn mode -> "layer": null; warn blockable -> "layer": "engine"; 266240-byte command -> rule_id "builtin-max-arg-bytes", "layer": "engine"; poison zz-poison.yaml -> RuleSchemaError reason with "layer": null. Programmatic key check on the fresh probe returned exactly ['action', 'command', 'modified', 'rule_id', 'reason', 'layer'] in emission order (plugin/terminal_jail/interruptor_bridge.py:142-160 builds the dict in that order). Tests: `.venv/bin/python -m pytest tests/test_arg_size_ceiling.py tests/test_composed_mode.py tests/test_quickstart_doc.py -q` -> exit 0, "27 passed, 3 skipped in 19.32s" (full suite exceeds the 30s tool cap; targeted doc/bridge tests green).
All five later quickstart bridge envelopes now include `layer`, each verified against a live bridge capture, and a fresh malformed-input probe returns exactly the six documented keys in order.

Overall: PASS ✓
