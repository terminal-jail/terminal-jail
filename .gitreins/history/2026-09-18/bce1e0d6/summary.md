# Verdict: DF-TERMINAL-JAIL-12

**Task:** Allow verdict provenance + default-allow posture docs
**Evaluated:** 2026-09-18T03:28:55.696384
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m10:27PM[0m [32mINF[0m [1mscanned ~4278644 bytes (4.28 MB) in 337ms[0m
[90m10:27PM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ bridge returns rule_id=allow-pwd for 'pwd' and allow-git-read for 'git status' (live probe): Live probe: `printf '{"command": "pwd"}' | python3 plugin/terminal_jail/interruptor_bridge.py` -> {"action": "allow", "command": "pwd", "modified": null, "rule_id": "allow-pwd", "reason": ""}; `'git status'` -> {"action": "allow", "rule_id": "allow-git-read"}. Backed by decider.py:189-196 (aggregate ALLOW now returns rule_id=allow_rule_id) and allowlist.py:22-28 (allow-pwd `^pwd$`), allowlist.py:60-68 (allow-git-read `^git\s+(status|log|diff)\b`).
  ✓ unmatched command 'psql -c x' still returns rule_id=null action=allow (default-allow preserved): Live probe: `printf '{"command": "psql -c x"}' | python3 plugin/terminal_jail/interruptor_bridge.py` -> {"action": "allow", "command": "psql -c x", "modified": null, "rule_id": null, "reason": ""}. decider.py:189-196 keeps rule_id None when no rule matched (allow_rule_id stays None).
  ✓ regression tests added to plugin/test_interruptor.py for allow provenance, green: plugin/test_interruptor.py adds class TestAllowProvenance (15 tests: parametrized allow provenance for pwd/git status/cat /tmp/x/echo hi/ls/ls -la, default-allow for psql -c x, psql -c 'SELECT 1', cat /etc/passwd, negative cat-/etc attribution, warn-precedence, block-unchanged). Command output: `.venv/bin/pytest plugin/test_interruptor.py -q -k AllowProvenance` -> '15 passed, 175 deselected in 0.11s'; full suite `.venv/bin/pytest -x --tb=short -q` -> '435 passed, 14 skipped in 10.94s' (exit_code 0); `ruff check plugin/` -> 'All checks passed!'.
  ✓ README.md + docs/quickstart.md + specs/interruptor.md each state the deny-list default-allow posture: README.md:52-70 — '**Default-allow posture (DF-TERMINAL-JAIL-12).** The interruptor is a **deny-list** pattern firewall ... **every command that matches no rule at all is ALLOWED by default**' plus rule_id:null explanation. docs/quickstart.md:108-112 — '**Default-allow posture.** The firewall is a deny-list: a command that matches no rule is **allowed**, and "rule_id": null on an allow verdict means no rule matched at all'. specs/interruptor.md:151-175 — new section '### 4.4 Default-Allow Posture and Rule Provenance (DF-TERMINAL-JAIL-12)': 'The engine is a **deny-list pattern firewall**, not an allow-list policy engine ... **any command that matches no rule at all ... is ALLOWED**'. Doc examples verified live (`ls` -> rule_id allow-ls; `cat /etc/passwd` -> rule_id null).
All four criteria pass: live bridge probes confirm allow provenance (allow-pwd/allow-git-read) and preserved default-allow (rule_id null for 'psql -c x'), 15 new green regression tests plus a fully green 435-test suite, and all three docs state the deny-list default-allow posture.

## Summary

Judge Result: DF-TERMINAL-JAIL-12

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m10:27PM[0m [32mINF[0m [1mscanned ~4278644 bytes (4.28 MB) in 337ms[0m
[90m10:27PM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ bridge returns rule_id=allow-pwd for 'pwd' and allow-git-read for 'git status' (live probe): Live probe: `printf '{"command": "pwd"}' | python3 plugin/terminal_jail/interruptor_bridge.py` -> {"action": "allow", "command": "pwd", "modified": null, "rule_id": "allow-pwd", "reason": ""}; `'git status'` -> {"action": "allow", "rule_id": "allow-git-read"}. Backed by decider.py:189-196 (aggregate ALLOW now returns rule_id=allow_rule_id) and allowlist.py:22-28 (allow-pwd `^pwd$`), allowlist.py:60-68 (allow-git-read `^git\s+(status|log|diff)\b`).
  ✓ unmatched command 'psql -c x' still returns rule_id=null action=allow (default-allow preserved): Live probe: `printf '{"command": "psql -c x"}' | python3 plugin/terminal_jail/interruptor_bridge.py` -> {"action": "allow", "command": "psql -c x", "modified": null, "rule_id": null, "reason": ""}. decider.py:189-196 keeps rule_id None when no rule matched (allow_rule_id stays None).
  ✓ regression tests added to plugin/test_interruptor.py for allow provenance, green: plugin/test_interruptor.py adds class TestAllowProvenance (15 tests: parametrized allow provenance for pwd/git status/cat /tmp/x/echo hi/ls/ls -la, default-allow for psql -c x, psql -c 'SELECT 1', cat /etc/passwd, negative cat-/etc attribution, warn-precedence, block-unchanged). Command output: `.venv/bin/pytest plugin/test_interruptor.py -q -k AllowProvenance` -> '15 passed, 175 deselected in 0.11s'; full suite `.venv/bin/pytest -x --tb=short -q` -> '435 passed, 14 skipped in 10.94s' (exit_code 0); `ruff check plugin/` -> 'All checks passed!'.
  ✓ README.md + docs/quickstart.md + specs/interruptor.md each state the deny-list default-allow posture: README.md:52-70 — '**Default-allow posture (DF-TERMINAL-JAIL-12).** The interruptor is a **deny-list** pattern firewall ... **every command that matches no rule at all is ALLOWED by default**' plus rule_id:null explanation. docs/quickstart.md:108-112 — '**Default-allow posture.** The firewall is a deny-list: a command that matches no rule is **allowed**, and "rule_id": null on an allow verdict means no rule matched at all'. specs/interruptor.md:151-175 — new section '### 4.4 Default-Allow Posture and Rule Provenance (DF-TERMINAL-JAIL-12)': 'The engine is a **deny-list pattern firewall**, not an allow-list policy engine ... **any command that matches no rule at all ... is ALLOWED**'. Doc examples verified live (`ls` -> rule_id allow-ls; `cat /etc/passwd` -> rule_id null).
All four criteria pass: live bridge probes confirm allow provenance (allow-pwd/allow-git-read) and preserved default-allow (rule_id null for 'psql -c x'), 15 new green regression tests plus a fully green 435-test suite, and all three docs state the deny-list default-allow posture.

Overall: PASS ✓
