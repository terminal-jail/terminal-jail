# Verdict: tj-gap-026

**Task:** quickstart seccomp example needs --user fallback (TJ-GAP-026)
**Evaluated:** 2026-08-11T16:07:25.494287
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m11:07AM[0m [32mINF[0m [1mscanned ~7409729 bytes (7.41 MB) in 750ms[0m
[90m11:07AM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ docs/quickstart.md section 3c seccomp example uses --user --seccomp or carries an inline host-limitation note (grep -n --user --seccomp docs/quickstart.md returns at least 1 hit): docs/quickstart.md:72 uses `terminal-jail --user --seccomp echo "seccomp BPF active"`; grep -n --user --seccomp returns hits at lines 22, 72, 125
  ✓ no un-annotated bare --seccomp example remains in docs/quickstart.md (every terminal-jail --seccomp line within section 3c either has --user or an EPERM note): All --seccomp occurrences in section 3c: line 72 has --user; line 74 bare --seccomp is inside the EPERM note ('the bare `--seccomp` form fails — use the --user variant above'). No un-annotated bare --seccomp example remains.
Both criteria satisfied: section 3c uses --user --seccomp and the only bare --seccomp mention is annotated with the EPERM host-limitation note.

## Summary

Judge Result: tj-gap-026

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m11:07AM[0m [32mINF[0m [1mscanned ~7409729 bytes (7.41 MB) in 750ms[0m
[90m11:07AM[0m [3
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ docs/quickstart.md section 3c seccomp example uses --user --seccomp or carries an inline host-limitation note (grep -n --user --seccomp docs/quickstart.md returns at least 1 hit): docs/quickstart.md:72 uses `terminal-jail --user --seccomp echo "seccomp BPF active"`; grep -n --user --seccomp returns hits at lines 22, 72, 125
  ✓ no un-annotated bare --seccomp example remains in docs/quickstart.md (every terminal-jail --seccomp line within section 3c either has --user or an EPERM note): All --seccomp occurrences in section 3c: line 72 has --user; line 74 bare --seccomp is inside the EPERM note ('the bare `--seccomp` form fails — use the --user variant above'). No un-annotated bare --seccomp example remains.
Both criteria satisfied: section 3c uses --user --seccomp and the only bare --seccomp mention is annotated with the EPERM host-limitation note.

Overall: PASS ✓
