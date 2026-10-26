# Verdict: TJ-GAP-063

**Task:** specs/cli.md fail-closed truth
**Evaluated:** 2026-09-19T20:51:23.962498
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ specs/cli.md has no fails-open claim for bridge-unavailable; it documents enforce-mode FAIL CLOSED rc=126 with the interruptor-bridge-unavailable block box; the 126 exit-table row covers bridge-unavailable; TERMINAL_JAIL_SECCOMP rows state the env var alone does not activate the filter; live check: TERMINAL_JAIL_BRIDGE=/missing ./standalone/terminal-jail --user echo x gives rc=126 empty stdout: No fails-open claim: grep -i 'fail.open|fails.open|fail open|fails open' specs/cli.md returned zero matches. specs/cli.md:216 documents 'the wrapper FAILS CLOSED in the default `enforce` mode: it prints the `COMMAND BLOCKED — interruptor-bridge-unavailable` block box to stderr and exits `126` with the payload never executed'. Exit-table row specs/cli.md:340: '| `126` | Command blocked by the interruptor (enforce mode) — either a rule `block` verdict or an unavailable bridge (fail-closed; see section 7).' SECCOMP rows: specs/cli.md:94 ('Setting the env var without the flag does not run the loader and does not activate the filter'), :102-104 ('TERMINAL_JAIL_SECCOMP does not activate seccomp by itself'), :145 (usage text: 'does not activate the filter by itself'), :215 ('Setting TERMINAL_JAIL_SECCOMP=1 without the flag does not route the payload through the loader and does not apply any filter'). Live check executed: `TERMINAL_JAIL_BRIDGE=/missing ./standalone/terminal-jail --user echo x` -> rc=126, stdout_bytes=0 (empty stdout), block box printed to stderr; wrapper source standalone/terminal-jail:210-231 confirms the enforce-mode fail-closed exit 126 path.
specs/cli.md documents fail-closed bridge-unavailable behavior (rc=126, block box, exit-table row, seccomp env-var caveats) with no fails-open claim, and the live check reproduces rc=126 with empty stdout.

## Summary

Judge Result: TJ-GAP-063

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ specs/cli.md has no fails-open claim for bridge-unavailable; it documents enforce-mode FAIL CLOSED rc=126 with the interruptor-bridge-unavailable block box; the 126 exit-table row covers bridge-unavailable; TERMINAL_JAIL_SECCOMP rows state the env var alone does not activate the filter; live check: TERMINAL_JAIL_BRIDGE=/missing ./standalone/terminal-jail --user echo x gives rc=126 empty stdout: No fails-open claim: grep -i 'fail.open|fails.open|fail open|fails open' specs/cli.md returned zero matches. specs/cli.md:216 documents 'the wrapper FAILS CLOSED in the default `enforce` mode: it prints the `COMMAND BLOCKED — interruptor-bridge-unavailable` block box to stderr and exits `126` with the payload never executed'. Exit-table row specs/cli.md:340: '| `126` | Command blocked by the interruptor (enforce mode) — either a rule `block` verdict or an unavailable bridge (fail-closed; see section 7).' SECCOMP rows: specs/cli.md:94 ('Setting the env var without the flag does not run the loader and does not activate the filter'), :102-104 ('TERMINAL_JAIL_SECCOMP does not activate seccomp by itself'), :145 (usage text: 'does not activate the filter by itself'), :215 ('Setting TERMINAL_JAIL_SECCOMP=1 without the flag does not route the payload through the loader and does not apply any filter'). Live check executed: `TERMINAL_JAIL_BRIDGE=/missing ./standalone/terminal-jail --user echo x` -> rc=126, stdout_bytes=0 (empty stdout), block box printed to stderr; wrapper source standalone/terminal-jail:210-231 confirms the enforce-mode fail-closed exit 126 path.
specs/cli.md documents fail-closed bridge-unavailable behavior (rc=126, block box, exit-table row, seccomp env-var caveats) with no fails-open claim, and the live check reproduces rc=126 with empty stdout.

Overall: PASS ✓
