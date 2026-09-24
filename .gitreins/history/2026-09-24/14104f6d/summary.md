# Verdict: TJ-DF-026

**Task:** Document the JSON bridge firewall API in docs/quickstart.md
**Evaluated:** 2026-09-24T19:14:36.334035
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ docs/quickstart.md contains a Scripting the firewall subsection covering the one-JSON-line request and response schema with the exact field names from interruptor_bridge.py; it states rule_id null means default-allow pass-through and not an approval; it documents the transport-failure fail-open envelope with the bracket-bridge-error reason prefix and the engine-evaluation fail-closed split from TJ-GAP-070; it carries a pointer that the matcher length limitation is tracked by TJ-DF-024; every example transcript was produced by running the bridge, not fabricated: docs/quickstart.md:205 §3a2 'Scripting the firewall (the JSON bridge)' documents the one-JSON-line request {"command": "<shell command>"} and the response with the exact five fields action/command/modified/rule_id/reason (lines 218-227), matching interruptor_bridge.py:100-106 and the _emit_fail_open/_emit_fail_closed envelopes. rule_id null = default-allow pass-through not approval at lines 256-266 and 349. Transport fail-open with [bridge-error] prefix at lines 268-282; engine-evaluation fail-closed split (TJ-GAP-070) at lines 284-300. TJ-DF-024 pointer at line 331. Transcripts verified by ACTUALLY RUNNING the bridge: `printf '{"command": "echo hello"}' | python3 plugin/terminal_jail/interruptor_bridge.py` → {"action": "allow", "command": "echo hello", "modified": null, "rule_id": "allow-echo", "reason": ""}; date → rule_id null; rm -rf / → block builtin-rm-rf-root; make test → modify auto-make; invalid JSON → [bridge-error] invalid JSON on stdin — fail-open (rc=0); poison rule file → block rule_id "[bridge-error]" fail-closed; warn mode → [WARN MODE] allow. All outputs match the documented transcripts exactly. Referenced docs exist: docs/dogfood/2026-09-24-firewall-library-integration.md (7.491s engine time, 20KB+ never returns) and specs/interruptor.md §3.5–§3.6 (TJ-GAP-070). [resolution 0.24; docs/quickstart.md, interruptor_bridge.py]
docs/quickstart.md §3a2 fully documents the JSON bridge API with exact field names, rule_id-null semantics, the fail-open/fail-closed TJ-GAP-070 split, the TJ-DF-024 pointer, and transcripts independently reproduced by running the bridge.

## Summary

Judge Result: TJ-DF-026

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ docs/quickstart.md contains a Scripting the firewall subsection covering the one-JSON-line request and response schema with the exact field names from interruptor_bridge.py; it states rule_id null means default-allow pass-through and not an approval; it documents the transport-failure fail-open envelope with the bracket-bridge-error reason prefix and the engine-evaluation fail-closed split from TJ-GAP-070; it carries a pointer that the matcher length limitation is tracked by TJ-DF-024; every example transcript was produced by running the bridge, not fabricated: docs/quickstart.md:205 §3a2 'Scripting the firewall (the JSON bridge)' documents the one-JSON-line request {"command": "<shell command>"} and the response with the exact five fields action/command/modified/rule_id/reason (lines 218-227), matching interruptor_bridge.py:100-106 and the _emit_fail_open/_emit_fail_closed envelopes. rule_id null = default-allow pass-through not approval at lines 256-266 and 349. Transport fail-open with [bridge-error] prefix at lines 268-282; engine-evaluation fail-closed split (TJ-GAP-070) at lines 284-300. TJ-DF-024 pointer at line 331. Transcripts verified by ACTUALLY RUNNING the bridge: `printf '{"command": "echo hello"}' | python3 plugin/terminal_jail/interruptor_bridge.py` → {"action": "allow", "command": "echo hello", "modified": null, "rule_id": "allow-echo", "reason": ""}; date → rule_id null; rm -rf / → block builtin-rm-rf-root; make test → modify auto-make; invalid JSON → [bridge-error] invalid JSON on stdin — fail-open (rc=0); poison rule file → block rule_id "[bridge-error]" fail-closed; warn mode → [WARN MODE] allow. All outputs match the documented transcripts exactly. Referenced docs exist: docs/dogfood/2026-09-24-firewall-library-integration.md (7.491s engine time, 20KB+ never returns) and specs/interruptor.md §3.5–§3.6 (TJ-GAP-070). [resolution 0.24; docs/quickstart.md, interruptor_bridge.py]
docs/quickstart.md §3a2 fully documents the JSON bridge API with exact field names, rule_id-null semantics, the fail-open/fail-closed TJ-GAP-070 split, the TJ-DF-024 pointer, and transcripts independently reproduced by running the bridge.

Overall: PASS ✓
