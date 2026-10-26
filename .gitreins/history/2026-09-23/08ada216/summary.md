# Verdict: TJ-GAP-074

**Task:** Restore the E2E battery live-probe script
**Evaluated:** 2026-09-23T04:38:20.163355
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ scripts/e2e-battery-live-probe.py exists and runs green via .venv/bin/python: prints LIVE-PROBE 13/13 PASS and exits 0: scripts/e2e-battery-live-probe.py exists (10891 bytes, committed as b86930d). Ran `cd /home/kara/terminal-jail && .venv/bin/python scripts/e2e-battery-live-probe.py` -> 14 `PASS <case> -> action=... rule_id=...` lines, final line exactly `LIVE-PROBE: 13/13 PASS` (grep -c '^LIVE-PROBE: 13/13 PASS$' = 1), EXIT=0. [resolution 0.14; scripts/e2e-battery-live-probe.py]
  ✓ every block case returns action=block with the expected builtin rule_id and every allow case action=allow, including allow-provenance pins and a rule_id=null default-allow case: Independently re-ran all 13 cases through the live bridge (plugin/terminal_jail/interruptor_bridge.py) with empty rule dirs. All 8 block cases returned action=block with the expected builtin rule_id: builtin-rm-rf-root (rm -rf /, rm -rf / --no-preserve-root), builtin-curl-pipe-shell (curl|sh AND wget|sh), builtin-kill-all (kill -9 -1), builtin-killpg-pid1 (os.killpg(1, 9)), builtin-mkfs, builtin-dd-root. All rule_ids grep-verified in plugin/terminal_jail/interruptor/blocklist.py:13,40,72,97,108,168. Allow cases returned action=allow: provenance pins allow-echo/allow-ls/allow-git-read (allowlist.py:12,19,60) plus rule_id=null default-allow cases rm-rf-var-scope-allowed, killpg-shell-form-allowed and default-allow-provenance (printf matches no rule; decider.py:223-229 'rule_id stays None when NO rule'). Positive control requiring both an allow-with-rule and a default-allow is enforced at lines 268-275.
  ✓ the probe points TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR at an empty dir for every bridge call so installed user-rule overrides cannot mask builtins: scripts/e2e-battery-live-probe.py:195-196 sets env[SYSTEM_RULES_ENV]=empty_rules_dir and env[USER_RULES_ENV]=empty_rules_dir inside run_bridge(), the sole bridge-call path (called at line 240). empty_rules_dir is a fresh tempfile.TemporaryDirectory (line 235). Env names match plugin/terminal_jail/interruptor/config.py:47,51 exactly. Load-bearing proven empirically: a same-id override in /tmp/masktest flips `rm -rf /` from block to allow when fed directly to the bridge, yet `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=/tmp/masktest .venv/bin/python scripts/e2e-battery-live-probe.py` still printed LIVE-PROBE: 13/13 PASS. Masking is a live risk on this host: ~/.config/terminal-jail/rules.d/ holds 00-builtins.yaml (54 rules) and 99-dogfood.yaml.
  ✓ uvx ruff check on the new script is clean: `cd /home/kara/terminal-jail && uvx ruff check scripts/e2e-battery-live-probe.py` -> 'All checks passed!' EXIT=0. LSP diagnostics also returned 0 findings.
All four criteria verified with live command output: the restored probe exists, prints LIVE-PROBE 13/13 PASS with exit 0, its 13-case block/allow matrix matches the live engine's builtin rule_ids and provenance semantics, it pins both rule-dir env vars to a fresh empty tempdir per bridge call (empirically defeating a hostile same-id override), and uvx ruff check is clean.

## Summary

Judge Result: TJ-GAP-074

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ scripts/e2e-battery-live-probe.py exists and runs green via .venv/bin/python: prints LIVE-PROBE 13/13 PASS and exits 0: scripts/e2e-battery-live-probe.py exists (10891 bytes, committed as b86930d). Ran `cd /home/kara/terminal-jail && .venv/bin/python scripts/e2e-battery-live-probe.py` -> 14 `PASS <case> -> action=... rule_id=...` lines, final line exactly `LIVE-PROBE: 13/13 PASS` (grep -c '^LIVE-PROBE: 13/13 PASS$' = 1), EXIT=0. [resolution 0.14; scripts/e2e-battery-live-probe.py]
  ✓ every block case returns action=block with the expected builtin rule_id and every allow case action=allow, including allow-provenance pins and a rule_id=null default-allow case: Independently re-ran all 13 cases through the live bridge (plugin/terminal_jail/interruptor_bridge.py) with empty rule dirs. All 8 block cases returned action=block with the expected builtin rule_id: builtin-rm-rf-root (rm -rf /, rm -rf / --no-preserve-root), builtin-curl-pipe-shell (curl|sh AND wget|sh), builtin-kill-all (kill -9 -1), builtin-killpg-pid1 (os.killpg(1, 9)), builtin-mkfs, builtin-dd-root. All rule_ids grep-verified in plugin/terminal_jail/interruptor/blocklist.py:13,40,72,97,108,168. Allow cases returned action=allow: provenance pins allow-echo/allow-ls/allow-git-read (allowlist.py:12,19,60) plus rule_id=null default-allow cases rm-rf-var-scope-allowed, killpg-shell-form-allowed and default-allow-provenance (printf matches no rule; decider.py:223-229 'rule_id stays None when NO rule'). Positive control requiring both an allow-with-rule and a default-allow is enforced at lines 268-275.
  ✓ the probe points TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR at an empty dir for every bridge call so installed user-rule overrides cannot mask builtins: scripts/e2e-battery-live-probe.py:195-196 sets env[SYSTEM_RULES_ENV]=empty_rules_dir and env[USER_RULES_ENV]=empty_rules_dir inside run_bridge(), the sole bridge-call path (called at line 240). empty_rules_dir is a fresh tempfile.TemporaryDirectory (line 235). Env names match plugin/terminal_jail/interruptor/config.py:47,51 exactly. Load-bearing proven empirically: a same-id override in /tmp/masktest flips `rm -rf /` from block to allow when fed directly to the bridge, yet `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=/tmp/masktest .venv/bin/python scripts/e2e-battery-live-probe.py` still printed LIVE-PROBE: 13/13 PASS. Masking is a live risk on this host: ~/.config/terminal-jail/rules.d/ holds 00-builtins.yaml (54 rules) and 99-dogfood.yaml.
  ✓ uvx ruff check on the new script is clean: `cd /home/kara/terminal-jail && uvx ruff check scripts/e2e-battery-live-probe.py` -> 'All checks passed!' EXIT=0. LSP diagnostics also returned 0 findings.
All four criteria verified with live command output: the restored probe exists, prints LIVE-PROBE 13/13 PASS with exit 0, its 13-case block/allow matrix matches the live engine's builtin rule_ids and provenance semantics, it pins both rule-dir env vars to a fresh empty tempdir per bridge call (empirically defeating a hostile same-id override), and uvx ruff check is clean.

Overall: PASS ✓
