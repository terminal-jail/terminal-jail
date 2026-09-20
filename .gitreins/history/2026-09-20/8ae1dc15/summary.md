# Verdict: DF-TERMINAL-JAIL-10

**Task:** Document the script-body exemption in specs and quickstart
**Evaluated:** 2026-09-20T20:21:44.084219
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ specs/interruptor.md + README quickstart state explicitly that the rules engine evaluates only the top-level command string, script bodies are covered by namespace/seccomp layers not the firewall, with a short do-not-over-credit warning for bridge callers; docs-only change, no engine code: specs/interruptor.md:14-26 new '### 1.1 Scope and Limits (DF-TERMINAL-JAIL-10)' states the rules engine evaluates 'only the top-level command string', script bodies (./deploy.sh, bash setup.sh, Makefile recipe, python3 script.py) are 'invisible to every rule in §3–§4, including the critical blocklist', and are 'covered by the namespace layers (--user uid-mapped launch, the optional --seccomp filter, PID-namespace containment), NOT by this firewall'. README.md:121-128, inside '### Quick Start' (line 90) of '## Interruptor Bash Command Firewall', states 'Scope: the firewall rules on the command string only' and carries the do-not-over-credit warning: 'If you call the bridge, do not over-credit an ALLOW: "the firewall checked my command" never implies the script's contents were ruled on.' CHANGELOG.md:3-11 adds an Unreleased entry naming DF-TERMINAL-JAIL-10. Docs-only confirmed: commit 146315f touches only CHANGELOG.md, README.md, specs/interruptor.md (git show --name-only shows no .py/.yaml/.sh), and git diff HEAD -- plugin/ standalone/ specs/ README.md CHANGELOG.md is empty. Tests: `.venv/bin/python -m pytest plugin/test_install.py plugin/test_packaging.py` -> '64 passed in 3.95s'; `plugin/test_interruptor.py plugin/test_escape_waves.py plugin/test_modify_preflight.py` -> '731 passed in 3.49s'; LSP diagnostics empty (0 findings).
Both specs/interruptor.md §1.1 and the README bridge Quick Start explicitly document the top-level-command-only firewall scope with the script-body exemption, namespace/seccomp coverage, and a do-not-over-credit warning, as a docs-only change with no engine code.

## Summary

Judge Result: DF-TERMINAL-JAIL-10

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ specs/interruptor.md + README quickstart state explicitly that the rules engine evaluates only the top-level command string, script bodies are covered by namespace/seccomp layers not the firewall, with a short do-not-over-credit warning for bridge callers; docs-only change, no engine code: specs/interruptor.md:14-26 new '### 1.1 Scope and Limits (DF-TERMINAL-JAIL-10)' states the rules engine evaluates 'only the top-level command string', script bodies (./deploy.sh, bash setup.sh, Makefile recipe, python3 script.py) are 'invisible to every rule in §3–§4, including the critical blocklist', and are 'covered by the namespace layers (--user uid-mapped launch, the optional --seccomp filter, PID-namespace containment), NOT by this firewall'. README.md:121-128, inside '### Quick Start' (line 90) of '## Interruptor Bash Command Firewall', states 'Scope: the firewall rules on the command string only' and carries the do-not-over-credit warning: 'If you call the bridge, do not over-credit an ALLOW: "the firewall checked my command" never implies the script's contents were ruled on.' CHANGELOG.md:3-11 adds an Unreleased entry naming DF-TERMINAL-JAIL-10. Docs-only confirmed: commit 146315f touches only CHANGELOG.md, README.md, specs/interruptor.md (git show --name-only shows no .py/.yaml/.sh), and git diff HEAD -- plugin/ standalone/ specs/ README.md CHANGELOG.md is empty. Tests: `.venv/bin/python -m pytest plugin/test_install.py plugin/test_packaging.py` -> '64 passed in 3.95s'; `plugin/test_interruptor.py plugin/test_escape_waves.py plugin/test_modify_preflight.py` -> '731 passed in 3.49s'; LSP diagnostics empty (0 findings).
Both specs/interruptor.md §1.1 and the README bridge Quick Start explicitly document the top-level-command-only firewall scope with the script-body exemption, namespace/seccomp coverage, and a do-not-over-credit warning, as a docs-only change with no engine code.

Overall: PASS ✓
