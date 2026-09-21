# Verdict: DF-TERMINAL-JAIL-27

**Task:** Leaked live bunkerd token from dogfood scratch HOME: rotate, purge, and make scratch-HOME hygiene structural
**Evaluated:** 2026-09-21T04:10:12.309977
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ Rotated token on las-03 verified (old 401/new 200), scratch-HOME hygiene checker exists in scripts/, docs/dogfood/checklist.md and diagnostics.md updated, guard green: All components verified. (1) Checker exists: scripts/scratch-home-hygiene.sh (executable, committed 49caaa8); live-tested — clean /tmp exits 0 ('scanned 24 scratch dir(s); 0 finding(s)'), synthetic 0755 dir + 644 config.yaml with token yields 'FINDING dir-mode=755 file-mode=644' exit 1, bad root exits 2, and it prints only paths/modes (never contents). (2) docs/dogfood/checklist.md lines 10-13 add the standing item (scratch HOMEs 0700, run the checker each tick, non-zero exit = blocker). (3) docs/dogfood/diagnostics.md §8.6 lines 268-278 add the resolution paragraph (purge + rotation + two-part structural guard). (4) Guard green: .gitreins/logs/guard-20260921T040822.595716Z.log (last run, post-commit) shows 'overall: PASS', 'guards: 4 (0 failed, 0 skipped)', [PASS] secrets (gitleaks clean), [PASS] lint (ruff clean, 53 files), [PASS] tests (1348 passed, 7 skipped), [PASS] static_analysis. (5) Rotation live-verified: `bunker status --server bunker-las-03` -> Status: ONLINE (new token accepted, 200-equiv); a wrong token -> 'server info: unauthenticated: invalid token' (401-equiv); leaked /tmp/dogfood-tj/home/.bunker/config.yaml and secret.txt are GONE and /tmp/dogfood-tj is now mode 0700; rotation documented at diagnostics.md:270-273 (old 401 / new ServerInfo 200); ~/.bunker/config.yaml backup is mode 0600 as claimed. (6) tests/test_scratch_home_hygiene.py: 7 passed in 0.15s (explicit run). Note: pyproject testpaths=["plugin"] so the guard's tests lane does not collect tests/ — the new tests are not in the guard run, but the criterion only requires the guard to be green, which it is, and the tests pass when run explicitly.
The scratch-HOME hygiene checker, checklist/diagnostics updates, live-verified las-03 token rotation (new token ONLINE / invalid token rejected), and a green 4/4 guard all satisfy the single composite criterion.

## Summary

Judge Result: DF-TERMINAL-JAIL-27

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ Rotated token on las-03 verified (old 401/new 200), scratch-HOME hygiene checker exists in scripts/, docs/dogfood/checklist.md and diagnostics.md updated, guard green: All components verified. (1) Checker exists: scripts/scratch-home-hygiene.sh (executable, committed 49caaa8); live-tested — clean /tmp exits 0 ('scanned 24 scratch dir(s); 0 finding(s)'), synthetic 0755 dir + 644 config.yaml with token yields 'FINDING dir-mode=755 file-mode=644' exit 1, bad root exits 2, and it prints only paths/modes (never contents). (2) docs/dogfood/checklist.md lines 10-13 add the standing item (scratch HOMEs 0700, run the checker each tick, non-zero exit = blocker). (3) docs/dogfood/diagnostics.md §8.6 lines 268-278 add the resolution paragraph (purge + rotation + two-part structural guard). (4) Guard green: .gitreins/logs/guard-20260921T040822.595716Z.log (last run, post-commit) shows 'overall: PASS', 'guards: 4 (0 failed, 0 skipped)', [PASS] secrets (gitleaks clean), [PASS] lint (ruff clean, 53 files), [PASS] tests (1348 passed, 7 skipped), [PASS] static_analysis. (5) Rotation live-verified: `bunker status --server bunker-las-03` -> Status: ONLINE (new token accepted, 200-equiv); a wrong token -> 'server info: unauthenticated: invalid token' (401-equiv); leaked /tmp/dogfood-tj/home/.bunker/config.yaml and secret.txt are GONE and /tmp/dogfood-tj is now mode 0700; rotation documented at diagnostics.md:270-273 (old 401 / new ServerInfo 200); ~/.bunker/config.yaml backup is mode 0600 as claimed. (6) tests/test_scratch_home_hygiene.py: 7 passed in 0.15s (explicit run). Note: pyproject testpaths=["plugin"] so the guard's tests lane does not collect tests/ — the new tests are not in the guard run, but the criterion only requires the guard to be green, which it is, and the tests pass when run explicitly.
The scratch-HOME hygiene checker, checklist/diagnostics updates, live-verified las-03 token rotation (new token ONLINE / invalid token rejected), and a green 4/4 guard all satisfy the single composite criterion.

Overall: PASS ✓
