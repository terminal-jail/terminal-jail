# Verdict: QA-TERMINAL-JAIL-8

**Task:** Make TestUserRules user-modify assertion independent of subordinate-ID mappings
**Evaluated:** 2026-09-19T06:59:43.111406
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ The regression test must pass with and without /etc/subuid and /etc/subgid entries while still asserting the required unshare PID/lifecycle flags and command payload; add no production behavior change.: (a) Host-independence: plugin/test_interruptor.py:2009 replaces the old host-derived `result.modified.startswith(f"{unshare_prefix()}'")` with `_assert_sandboxed_modify(result, "danger-tool --wipe")` (helper at :1837), which partitions on _LAUNCH_CONTRACT = "--pid --fork --kill-child=SIGKILL bash -c " (:1800) and accepts EITHER _LEGACY_LAUNCH_RE (:1802, ^unshare --user <contract>$) OR _MAPPED_LAUNCH_RE (:1806, ^unshare --user --map-users=65534:\d+:1 --map-groups=65534:\d+:1 -S 65534 -G 65534 <contract>$). Verified live: this host HAS subuid/subgid (kara:100000:65536 in both /etc/subuid and /etc/subgid) but unshare_prefix() returns the mapping-less form -> `.venv/bin/python -m pytest plugin/test_interruptor.py -k TestUserRules -q -p no:cacheprovider` => '32 passed'; monkeypatching userns.unshare_prefix to the mapped form => '32 passed'; forcing the legacy/no-subuid form => '32 passed'. Regexes checked directly against legacy, mapped(host 100000), mapped(DEFAULT_SUBID_START) and mapped(arbitrary 999999) prefixes -> all matched=True; bare 'unshare ' -> False. (b) Flags/payload still asserted: the contract pins --pid --fork --kill-child=SIGKILL presence, order and position immediately before the payload introducer, and the payload must equal exactly "'" + command + "'" (ONE quoted arg); rule_id provenance assertion kept at :1998. Mutation RED confirmed: legacy-only regex => 5 failed; weakening payload check to `command in payload` => 2 failed (unquoted/truncated payload negatives). (c) No production change: `git diff --name-only a3c8cd9~1 a3c8cd9` => only plugin/test_interruptor.py; `git diff a3c8cd9~1 a3c8cd9 -- plugin/terminal_jail/` is empty; working tree has no production edits. (d) Tests: full suite `.venv/bin/python -m pytest -q -p no:cacheprovider` => '880 passed, 5 skipped in 22.90s' exit 0; `ruff check plugin/test_interruptor.py` => 'All checks passed!' exit 0; LSP diagnostics empty. File restored to committed sha256 74ad01f960a061e0a655175bb85de9dbeb3a23f58612ef9e11f4f2cb63bcd59e.
The TestUserRules user-modify assertion was rewritten as a host-independent launch-contract check that passes with and without subuid/subgid entries (32 passed in all three simulated host configurations, 880 passed full suite) while still pinning the --pid/--fork/--kill-child flags and the quoted command payload, with only plugin/test_interruptor.py changed.

## Summary

Judge Result: QA-TERMINAL-JAIL-8

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ The regression test must pass with and without /etc/subuid and /etc/subgid entries while still asserting the required unshare PID/lifecycle flags and command payload; add no production behavior change.: (a) Host-independence: plugin/test_interruptor.py:2009 replaces the old host-derived `result.modified.startswith(f"{unshare_prefix()}'")` with `_assert_sandboxed_modify(result, "danger-tool --wipe")` (helper at :1837), which partitions on _LAUNCH_CONTRACT = "--pid --fork --kill-child=SIGKILL bash -c " (:1800) and accepts EITHER _LEGACY_LAUNCH_RE (:1802, ^unshare --user <contract>$) OR _MAPPED_LAUNCH_RE (:1806, ^unshare --user --map-users=65534:\d+:1 --map-groups=65534:\d+:1 -S 65534 -G 65534 <contract>$). Verified live: this host HAS subuid/subgid (kara:100000:65536 in both /etc/subuid and /etc/subgid) but unshare_prefix() returns the mapping-less form -> `.venv/bin/python -m pytest plugin/test_interruptor.py -k TestUserRules -q -p no:cacheprovider` => '32 passed'; monkeypatching userns.unshare_prefix to the mapped form => '32 passed'; forcing the legacy/no-subuid form => '32 passed'. Regexes checked directly against legacy, mapped(host 100000), mapped(DEFAULT_SUBID_START) and mapped(arbitrary 999999) prefixes -> all matched=True; bare 'unshare ' -> False. (b) Flags/payload still asserted: the contract pins --pid --fork --kill-child=SIGKILL presence, order and position immediately before the payload introducer, and the payload must equal exactly "'" + command + "'" (ONE quoted arg); rule_id provenance assertion kept at :1998. Mutation RED confirmed: legacy-only regex => 5 failed; weakening payload check to `command in payload` => 2 failed (unquoted/truncated payload negatives). (c) No production change: `git diff --name-only a3c8cd9~1 a3c8cd9` => only plugin/test_interruptor.py; `git diff a3c8cd9~1 a3c8cd9 -- plugin/terminal_jail/` is empty; working tree has no production edits. (d) Tests: full suite `.venv/bin/python -m pytest -q -p no:cacheprovider` => '880 passed, 5 skipped in 22.90s' exit 0; `ruff check plugin/test_interruptor.py` => 'All checks passed!' exit 0; LSP diagnostics empty. File restored to committed sha256 74ad01f960a061e0a655175bb85de9dbeb3a23f58612ef9e11f4f2cb63bcd59e.
The TestUserRules user-modify assertion was rewritten as a host-independent launch-contract check that passes with and without subuid/subgid entries (32 passed in all three simulated host configurations, 880 passed full suite) while still pinning the --pid/--fork/--kill-child flags and the quoted command payload, with only plugin/test_interruptor.py changed.

Overall: PASS ✓
