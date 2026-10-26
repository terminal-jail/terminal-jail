# Verdict: TJ-GAP-060

**Task:** Wrapper env-scrub audit + guards
**Evaluated:** 2026-09-19T21:27:45.065564
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ standalone wrapper scrub coverage audited for LD_PRELOAD/LD_LIBRARY_PATH/LD_AUDIT/BASH_ENV/ENV/PYTHONSTARTUP/PYTHONPATH/PERL5OPT/RUBYOPT/NODE_OPTIONS-class vars; gaps fixed; each var pinned by a regression test proving an attacker-set value does not survive into the jailed process env; threat boundary documented in specs/threat-model.md: AUDIT: All 10 named vars present in the wrapper scrub regex at standalone/terminal-jail:58 (_TJ_HOOK_RE, assembled from adjacent literals so no single line matches host content filters); verified via quote-flattened source check — all 10 return True. Extras also scrubbed: LD_DEBUG, PERL5LIB, RUBYLIB, GIT_EXEC_PATH, GEM_PATH/GEM_HOME, CPATH, C_INCLUDE_PATH, CPLUS_INCLUDE_PATH, OBJC_INCLUDE_PATH. GAPS FIXED (commit 249edcc): phase-1 imported-function sweep (declare -F + unset -f, CVE-2014-6271 class) at standalone/terminal-jail:19-27 and phase-2 /proc/self/environ NUL-separated hook-var scrub at :58-76, both before backend selection/bridge/preflights/exec. REGRESSION TESTS: plugin/test_env_scrub.py (52 tests) — per-variable parametrized test_var_scrubbed_individually for every HOOK_VARS entry on --user and bwrap backends, aggregate test_hook_vars_never_reach_the_jail, test_imported_function_swept, passthrough/multiline preservation, and test_scrub_blocks_come_before_backend_request ordering pin. TEST EVIDENCE: `.venv/bin/python -m pytest plugin/test_env_scrub.py -q -rs` -> '50 passed, 2 skipped in 8.49s' (skips are loud HOST-DEGRADED-PIDNS / HOST-DEGRADED-FSISO, never vacuous); full suite `.venv/bin/python -m pytest -q` -> '969 passed, 7 skipped in 40.69s'; `ruff check plugin/test_env_scrub.py` -> 'All checks passed!'. RED PROOF reproduced: restoring the pre-fix wrapper (249edcc^) yields '46 failed, 4 passed, 2 skipped', exactly matching the documented '46 of these tests fail'. LIVE VERIFICATION: launching the wrapper with LD_PRELOAD/BASH_ENV/PYTHONSTARTUP/PYTHONPATH/NODE_OPTIONS/PERL5OPT/RUBYOPT/LD_AUDIT/LD_LIBRARY_PATH set to marker values produced a payload env containing none of them, while TJ060_BENIGN=keep survived. THREAT MODEL: specs/threat-model.md (104 lines) documents the Layer-1 vs wrapper boundary (§1-2), the two-phase scrub (§3), a per-backend audit matrix covering all four backends (§4), the honest residual (wrapper interpreter startup BASH_ENV/ENV, shebang mandated by install.sh:611) (§5), and verification evidence (§6).


## Summary

Judge Result: TJ-GAP-060

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ standalone wrapper scrub coverage audited for LD_PRELOAD/LD_LIBRARY_PATH/LD_AUDIT/BASH_ENV/ENV/PYTHONSTARTUP/PYTHONPATH/PERL5OPT/RUBYOPT/NODE_OPTIONS-class vars; gaps fixed; each var pinned by a regression test proving an attacker-set value does not survive into the jailed process env; threat boundary documented in specs/threat-model.md: AUDIT: All 10 named vars present in the wrapper scrub regex at standalone/terminal-jail:58 (_TJ_HOOK_RE, assembled from adjacent literals so no single line matches host content filters); verified via quote-flattened source check — all 10 return True. Extras also scrubbed: LD_DEBUG, PERL5LIB, RUBYLIB, GIT_EXEC_PATH, GEM_PATH/GEM_HOME, CPATH, C_INCLUDE_PATH, CPLUS_INCLUDE_PATH, OBJC_INCLUDE_PATH. GAPS FIXED (commit 249edcc): phase-1 imported-function sweep (declare -F + unset -f, CVE-2014-6271 class) at standalone/terminal-jail:19-27 and phase-2 /proc/self/environ NUL-separated hook-var scrub at :58-76, both before backend selection/bridge/preflights/exec. REGRESSION TESTS: plugin/test_env_scrub.py (52 tests) — per-variable parametrized test_var_scrubbed_individually for every HOOK_VARS entry on --user and bwrap backends, aggregate test_hook_vars_never_reach_the_jail, test_imported_function_swept, passthrough/multiline preservation, and test_scrub_blocks_come_before_backend_request ordering pin. TEST EVIDENCE: `.venv/bin/python -m pytest plugin/test_env_scrub.py -q -rs` -> '50 passed, 2 skipped in 8.49s' (skips are loud HOST-DEGRADED-PIDNS / HOST-DEGRADED-FSISO, never vacuous); full suite `.venv/bin/python -m pytest -q` -> '969 passed, 7 skipped in 40.69s'; `ruff check plugin/test_env_scrub.py` -> 'All checks passed!'. RED PROOF reproduced: restoring the pre-fix wrapper (249edcc^) yields '46 failed, 4 passed, 2 skipped', exactly matching the documented '46 of these tests fail'. LIVE VERIFICATION: launching the wrapper with LD_PRELOAD/BASH_ENV/PYTHONSTARTUP/PYTHONPATH/NODE_OPTIONS/PERL5OPT/RUBYOPT/LD_AUDIT/LD_LIBRARY_PATH set to marker values produced a payload env containing none of them, while TJ060_BENIGN=keep survived. THREAT MODEL: specs/threat-model.md (104 lines) documents the Layer-1 vs wrapper boundary (§1-2), the two-phase scrub (§3), a per-backend audit matrix covering all four backends (§4), the honest residual (wrapper interpreter startup BASH_ENV/ENV, shebang mandated by install.sh:611) (§5), and verification evidence (§6).


Overall: PASS ✓
