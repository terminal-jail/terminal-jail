# Verdict: TJ-GAP-039

**Task:** --mount-proc ghost flag
**Evaluated:** 2026-08-19T05:45:38.217285
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m12:44AM[0m [32mINF[0m [1mscanned ~9672177 bytes (9.67 MB) in 1.11s[0m
[90m12:44AM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ grep -rn 'mount-proc' docs/ README.md shows no reference presented as a usable option: grep finds mount-proc references but none present it as a usable terminal-jail flag. All describe the internal unshare mechanism: README:13/22 (underlying unshare command), README:217 ('the CLI's bare mode (which appends --mount-proc internally)'), docs/quickstart.md ('the CLI internally mounts a private /proc'), docs/adr/0001, COMPATIBILITY.md, pentest-plan.md, threat-model.md, dogfood/diagnostics.md all describe unshare --mount-proc, not a terminal-jail option. ./standalone/terminal-jail --help lists only --user/--seccomp/--interruptor/--no-interruptor — no --mount-proc option.
  ✓ --help --user text explains the /proc trade-off without naming a nonexistent flag: ./standalone/terminal-jail --help --user: 'Add user namespace isolation (process runs as nobody=65534). The host PID view is exposed (no private /proc mount).' Explains the /proc trade-off without naming --mount-proc. Commit 634f909 changed it from 'Incompatible with --mount-proc; the host PID view is exposed.' to remove the flag name. Test suite: 288 passed, 4 skipped.
Both criteria satisfied: --mount-proc is never presented as a usable terminal-jail option (all references describe the internal unshare mechanism), and the --help --user text explains the /proc trade-off without naming the nonexistent flag.

## Summary

Judge Result: TJ-GAP-039

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m12:44AM[0m [32mINF[0m [1mscanned ~9672177 bytes (9.67 MB) in 1.11s[0m
[90m12:44AM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ grep -rn 'mount-proc' docs/ README.md shows no reference presented as a usable option: grep finds mount-proc references but none present it as a usable terminal-jail flag. All describe the internal unshare mechanism: README:13/22 (underlying unshare command), README:217 ('the CLI's bare mode (which appends --mount-proc internally)'), docs/quickstart.md ('the CLI internally mounts a private /proc'), docs/adr/0001, COMPATIBILITY.md, pentest-plan.md, threat-model.md, dogfood/diagnostics.md all describe unshare --mount-proc, not a terminal-jail option. ./standalone/terminal-jail --help lists only --user/--seccomp/--interruptor/--no-interruptor — no --mount-proc option.
  ✓ --help --user text explains the /proc trade-off without naming a nonexistent flag: ./standalone/terminal-jail --help --user: 'Add user namespace isolation (process runs as nobody=65534). The host PID view is exposed (no private /proc mount).' Explains the /proc trade-off without naming --mount-proc. Commit 634f909 changed it from 'Incompatible with --mount-proc; the host PID view is exposed.' to remove the flag name. Test suite: 288 passed, 4 skipped.
Both criteria satisfied: --mount-proc is never presented as a usable terminal-jail option (all references describe the internal unshare mechanism), and the --help --user text explains the /proc trade-off without naming the nonexistent flag.

Overall: PASS ✓
