# Verdict: DOC-15

**Task:** quickstart bridge schema documents the sixth response field layer
**Evaluated:** 2026-10-23T04:31:04.453187
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ docs/quickstart.md response schema block names all six response fields including layer, states layer's value domain and what a null layer means, and no longer claims the envelope has five fields: docs/quickstart.md:257 now reads 'response — one JSON object, one line, always these six fields:' and lists action/command/modified/rule_id/reason plus 'layer  which rule source decided — "engine" | "yaml" | "user" | "pack" | null (semantics below)' at lines 263-264. The 'layer semantics' section (lines 314-334) enumerates the closed domain (engine/yaml/user/pack) and states null explicitly: '`null` — the `[bridge-error]` envelopes only (transport failure, engine failure, or the warn-mode fail-open), where no rule decided anything.' grep for 'five fields' in docs/quickstart.md returns no hits. Domain matches the engine: plugin/terminal_jail/interruptor/types.py:35-37 Layer enum ENGINE/YAML/USER/PACK and interruptor_bridge.py:276,291,318 emit layer None on error envelopes. Test run: `.venv/bin/python -m pytest tests/test_quickstart_doc.py -q` -> '8 passed in 0.09s' (exit 0). [resolution 0.22; docs/quickstart.md]
  ✓ All four bridge transcripts in docs/quickstart.md include the layer key with the value produced by a live bridge run under the documented empty-rules env pins: All four transcripts carry the key: docs/quickstart.md:278 (echo hello), :281 (date), :284 (rm -rf /), :288 (make test), each ending '"layer": "engine"'. Live verification with the documented pins (TERMINAL_JAIL_INTERRUPTOR_RULES_DIR=/tmp/tj-empty-rules, TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=/tmp/tj-empty-rules) produced exactly: {"action": "allow", "command": "echo hello", "modified": null, "rule_id": "allow-echo", "reason": "", "layer": "engine"}; {"action": "allow", "command": "date", ... "rule_id": null, "reason": "", "layer": "engine"}; {"action": "block", "command": "rm -rf /", ... "rule_id": "builtin-rm-rf-root", ... "layer": "engine"}; {"action": "modify", "command": "make test", ... "rule_id": "auto-make", "reason": "Command modified by auto-sandbox", "layer": "engine"} — all exit 0, matching the doc values field-for-field (only the host-specific landlock-loader path in `modified` differs, which the doc already explains as opaque). [resolution 0.22; docs/quickstart.md]
  ✓ The change touches only docs/quickstart.md against base 8730de5: `git diff --name-only 8730de5 9448549` returns exactly one path: docs/quickstart.md (git diff --stat: 1 file changed, 40 insertions(+), 8 deletions(-)). The DOC-15 commit 9448549 modifies no other file; the later working-tree changes to .gitreins/tasks.yaml, install.sh, plugin/* and tests/test_quickstart_doc.py belong to other tasks (TJ-GAP-095, TJ-GAP-097, INT-CI-014, e50fece) landed after the DOC-15 merge b1de4ab. [resolution 0.22; docs/quickstart.md]
All three DOC-15 criteria verified: the schema block names six fields with the layer domain and null semantics, all four transcripts carry layer:"engine" matching a live bridge run under the documented empty-rules pins, and the DOC-15 commit touches only docs/quickstart.md.

## Summary

Judge Result: DOC-15

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ docs/quickstart.md response schema block names all six response fields including layer, states layer's value domain and what a null layer means, and no longer claims the envelope has five fields: docs/quickstart.md:257 now reads 'response — one JSON object, one line, always these six fields:' and lists action/command/modified/rule_id/reason plus 'layer  which rule source decided — "engine" | "yaml" | "user" | "pack" | null (semantics below)' at lines 263-264. The 'layer semantics' section (lines 314-334) enumerates the closed domain (engine/yaml/user/pack) and states null explicitly: '`null` — the `[bridge-error]` envelopes only (transport failure, engine failure, or the warn-mode fail-open), where no rule decided anything.' grep for 'five fields' in docs/quickstart.md returns no hits. Domain matches the engine: plugin/terminal_jail/interruptor/types.py:35-37 Layer enum ENGINE/YAML/USER/PACK and interruptor_bridge.py:276,291,318 emit layer None on error envelopes. Test run: `.venv/bin/python -m pytest tests/test_quickstart_doc.py -q` -> '8 passed in 0.09s' (exit 0). [resolution 0.22; docs/quickstart.md]
  ✓ All four bridge transcripts in docs/quickstart.md include the layer key with the value produced by a live bridge run under the documented empty-rules env pins: All four transcripts carry the key: docs/quickstart.md:278 (echo hello), :281 (date), :284 (rm -rf /), :288 (make test), each ending '"layer": "engine"'. Live verification with the documented pins (TERMINAL_JAIL_INTERRUPTOR_RULES_DIR=/tmp/tj-empty-rules, TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=/tmp/tj-empty-rules) produced exactly: {"action": "allow", "command": "echo hello", "modified": null, "rule_id": "allow-echo", "reason": "", "layer": "engine"}; {"action": "allow", "command": "date", ... "rule_id": null, "reason": "", "layer": "engine"}; {"action": "block", "command": "rm -rf /", ... "rule_id": "builtin-rm-rf-root", ... "layer": "engine"}; {"action": "modify", "command": "make test", ... "rule_id": "auto-make", "reason": "Command modified by auto-sandbox", "layer": "engine"} — all exit 0, matching the doc values field-for-field (only the host-specific landlock-loader path in `modified` differs, which the doc already explains as opaque). [resolution 0.22; docs/quickstart.md]
  ✓ The change touches only docs/quickstart.md against base 8730de5: `git diff --name-only 8730de5 9448549` returns exactly one path: docs/quickstart.md (git diff --stat: 1 file changed, 40 insertions(+), 8 deletions(-)). The DOC-15 commit 9448549 modifies no other file; the later working-tree changes to .gitreins/tasks.yaml, install.sh, plugin/* and tests/test_quickstart_doc.py belong to other tasks (TJ-GAP-095, TJ-GAP-097, INT-CI-014, e50fece) landed after the DOC-15 merge b1de4ab. [resolution 0.22; docs/quickstart.md]
All three DOC-15 criteria verified: the schema block names six fields with the layer domain and null semantics, all four transcripts carry layer:"engine" matching a live bridge run under the documented empty-rules pins, and the DOC-15 commit touches only docs/quickstart.md.

Overall: PASS ✓
