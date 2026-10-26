# Verdict: tj-gap-026

**Task:** quickstart seccomp example needs --user fallback (TJ-GAP-026)
**Evaluated:** 2026-08-11T16:06:11.950160
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m11:05AM[0m [32mINF[0m [1mscanned ~7409729 bytes (7.41 MB) in 766ms[0m
[90m11:05AM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ docs/quickstart.md section 3c seccomp example uses --user --seccomp or carries an inline host-limitation note (grep -n --user --seccomp docs/quickstart.md returns at least 1 hit): grep -n --user --seccomp docs/quickstart.md returns hits at lines 22, 72, 125; section 3c line 72 uses 'terminal-jail --user --seccomp echo ...'
  ✓ no un-annotated bare --seccomp example remains in docs/quickstart.md (every terminal-jail --seccomp line within section 3c either has --user or an EPERM note): Section 3c's only terminal-jail --seccomp command (line 72) has --user; the bare --seccomp mention at line 74 is inside the EPERM note comment ('unshare: Operation not permitted... use the --user variant above'), so no un-annotated bare --seccomp example remains
Both criteria pass: the quickstart section 3c seccomp example uses --user --seccomp and the bare --seccomp form is only referenced within the EPERM host-limitation note.

## Summary

Judge Result: tj-gap-026

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m11:05AM[0m [32mINF[0m [1mscanned ~7409729 bytes (7.41 MB) in 766ms[0m
[90m11:05AM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ docs/quickstart.md section 3c seccomp example uses --user --seccomp or carries an inline host-limitation note (grep -n --user --seccomp docs/quickstart.md returns at least 1 hit): grep -n --user --seccomp docs/quickstart.md returns hits at lines 22, 72, 125; section 3c line 72 uses 'terminal-jail --user --seccomp echo ...'
  ✓ no un-annotated bare --seccomp example remains in docs/quickstart.md (every terminal-jail --seccomp line within section 3c either has --user or an EPERM note): Section 3c's only terminal-jail --seccomp command (line 72) has --user; the bare --seccomp mention at line 74 is inside the EPERM note comment ('unshare: Operation not permitted... use the --user variant above'), so no un-annotated bare --seccomp example remains
Both criteria pass: the quickstart section 3c seccomp example uses --user --seccomp and the bare --seccomp form is only referenced within the EPERM host-limitation note.

Overall: PASS ✓
