# Verdict: QA-TERMINAL-JAIL-17

**Task:** Landlock home-outside-workdir interpreter access
**Evaluated:** 2026-10-11T22:51:34.620551
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ Add a regression test and implementation so a payload interpreter under HOME outside the workdir can start through the auto-sandbox Landlock path without weakening credential-surface denial; preserve fail-closed behavior, keep engine/YAML and existing tests green, and document any host limitation honestly.: Implementation (commit dcd2e7d, plugin/terminal_jail/interruptor/landlock.py): build_layout gains payload_argv (line 759-764) and read.extend(_toolchain_roots(...)) at line 831; _toolchain_roots (line 919) derives the venv root via pyvenv.cfg walk, the base-install prefix from the `home =` line, the resolved interpreter dir, plus fixed ~/tools & ~/venvs tails; _intersects_credential_surface (line 904) drops any derived root intersecting a credential surface in EITHER direction; _loader_payload_argv (line 741) extracts the payload after the first standalone `--`; apply_tier (line 1314) passes payload_argv=_loader_payload_argv(). REGRESSION TEST: plugin/test_landlock.py +382 lines / 10 new tests, incl. kernel test_toolchain_interpreter_starts_inside_the_domain (forked child, real Landlock domain, fixture home under XDG_RUNTIME_DIR so reads are denied by omission pre-fix). Reverting landlock.py to pre-fix makes 9/10 new tests FAIL (TypeError: build_layout() got unexpected kwarg 'payload_argv'; AttributeError: no _loader_payload_argv/_pyvenv_home_prefix) — genuine regression coverage. E2E probe with the real loader: copied interpreter under HOME outside workdir → PRE-FIX rc=126 'Permission denied', POST-FIX rc=0 'CFG-READ-OK'; ~/.ssh/id_rsa inside the domain → 'SSH-DENIED'. Credential denial not weakened (probe): HOME never granted, .ssh/.aws/.config/terminal-jail never granted, no granted root contains a credential surface, clean ~/tools granted. Fail-closed preserved: apply_tier still returns (False, cause) without touching the process and the loader execs the payload unchanged (landlock.py:1299-1322). Tests green: full guard suite `.venv/bin/python -m pytest -x --tb=short` → 1939 passed, 10 skipped, 0 failed in 150.32s; test_backend_parity.py + test_plugin.py + test_landlock_net.py → 69 passed; test_landlock.py → 127 passed, 1 skipped (skip = host verdict FULL not DEGRADED, unrelated). Docs: docs/backend-parity.md updated honestly (read allowlist, derived roots, credential carve, HOME never granted).
The Landlock home-outside-workdir interpreter fix is implemented with a genuine kernel-level regression test, verified end-to-end (pre-fix Errno 13 → post-fix start), preserves credential denial and fail-closed behavior, and keeps the full suite green (1939 passed, 0 failed).

## Summary

Judge Result: QA-TERMINAL-JAIL-17

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ Add a regression test and implementation so a payload interpreter under HOME outside the workdir can start through the auto-sandbox Landlock path without weakening credential-surface denial; preserve fail-closed behavior, keep engine/YAML and existing tests green, and document any host limitation honestly.: Implementation (commit dcd2e7d, plugin/terminal_jail/interruptor/landlock.py): build_layout gains payload_argv (line 759-764) and read.extend(_toolchain_roots(...)) at line 831; _toolchain_roots (line 919) derives the venv root via pyvenv.cfg walk, the base-install prefix from the `home =` line, the resolved interpreter dir, plus fixed ~/tools & ~/venvs tails; _intersects_credential_surface (line 904) drops any derived root intersecting a credential surface in EITHER direction; _loader_payload_argv (line 741) extracts the payload after the first standalone `--`; apply_tier (line 1314) passes payload_argv=_loader_payload_argv(). REGRESSION TEST: plugin/test_landlock.py +382 lines / 10 new tests, incl. kernel test_toolchain_interpreter_starts_inside_the_domain (forked child, real Landlock domain, fixture home under XDG_RUNTIME_DIR so reads are denied by omission pre-fix). Reverting landlock.py to pre-fix makes 9/10 new tests FAIL (TypeError: build_layout() got unexpected kwarg 'payload_argv'; AttributeError: no _loader_payload_argv/_pyvenv_home_prefix) — genuine regression coverage. E2E probe with the real loader: copied interpreter under HOME outside workdir → PRE-FIX rc=126 'Permission denied', POST-FIX rc=0 'CFG-READ-OK'; ~/.ssh/id_rsa inside the domain → 'SSH-DENIED'. Credential denial not weakened (probe): HOME never granted, .ssh/.aws/.config/terminal-jail never granted, no granted root contains a credential surface, clean ~/tools granted. Fail-closed preserved: apply_tier still returns (False, cause) without touching the process and the loader execs the payload unchanged (landlock.py:1299-1322). Tests green: full guard suite `.venv/bin/python -m pytest -x --tb=short` → 1939 passed, 10 skipped, 0 failed in 150.32s; test_backend_parity.py + test_plugin.py + test_landlock_net.py → 69 passed; test_landlock.py → 127 passed, 1 skipped (skip = host verdict FULL not DEGRADED, unrelated). Docs: docs/backend-parity.md updated honestly (read allowlist, derived roots, credential carve, HOME never granted).
The Landlock home-outside-workdir interpreter fix is implemented with a genuine kernel-level regression test, verified end-to-end (pre-fix Errno 13 → post-fix start), preserves credential denial and fail-closed behavior, and keeps the full suite green (1939 passed, 0 failed).

Overall: PASS ✓
