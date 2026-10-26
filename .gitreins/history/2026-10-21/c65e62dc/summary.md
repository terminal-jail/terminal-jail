# Verdict: INT-CI-008

**Task:** Fix test_open_chain_under_tmp_is_traversable failing when TMPDIR not world-traversable
**Evaluated:** 2026-10-21T20:13:38.535619
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✗ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ The test must pass when TMPDIR is set to a non-world-traversable directory. Fix: pin TMPDIR to a known-1777 ancestor path (child of /tmp) before assertions.: plugin/test_landlock.py:2286-2310 (commit c8e3670) now creates `pin_dir = tempfile.mkdtemp(prefix="tj-pin-", dir="/tmp")` + `os.chmod(pin_dir, 0o755)`, then `host = tempfile.mkdtemp(prefix="tj-ll-wt-", dir=pin_dir)` — immune to both ambient TMPDIR and tempfile's cached gettempdir(); both dirs removed in finally. Verified empirically: created /tmp/tj-private-2037546 with mode 0700 (non-world-traversable) and ran `TMPDIR=/tmp/tj-private-2037546 .venv/bin/python -m pytest plugin/test_landlock.py -k test_open_chain_under_tmp_is_traversable -p no:cacheprovider` -> exit_code 0, '1 passed, 129 deselected in 0.26s'. Control: the pre-fix version (git show c8e3670^:plugin/test_landlock.py) under the same TMPDIR -> exit_code 1, '1 failed ... AssertionError: assert False is True ... _world_traversable('/tmp/tj-private-2037546/tj-ll-wt-r605rl8w/loader.py')', proving the fix is what makes it pass. Whole file under hostile TMPDIR: '129 passed, 1 skipped in 1.59s' (exit 0); default TMPDIR: '129 passed, 1 skipped in 2.28s' (exit 0). LSP diagnostics: 0 findings.
The test now pins its temp chain to a 0755 child of /tmp, and it passes with a 0700 TMPDIR while the pre-fix version demonstrably fails under the same condition.

## Summary

Judge Result: INT-CI-008

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✗ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ The test must pass when TMPDIR is set to a non-world-traversable directory. Fix: pin TMPDIR to a known-1777 ancestor path (child of /tmp) before assertions.: plugin/test_landlock.py:2286-2310 (commit c8e3670) now creates `pin_dir = tempfile.mkdtemp(prefix="tj-pin-", dir="/tmp")` + `os.chmod(pin_dir, 0o755)`, then `host = tempfile.mkdtemp(prefix="tj-ll-wt-", dir=pin_dir)` — immune to both ambient TMPDIR and tempfile's cached gettempdir(); both dirs removed in finally. Verified empirically: created /tmp/tj-private-2037546 with mode 0700 (non-world-traversable) and ran `TMPDIR=/tmp/tj-private-2037546 .venv/bin/python -m pytest plugin/test_landlock.py -k test_open_chain_under_tmp_is_traversable -p no:cacheprovider` -> exit_code 0, '1 passed, 129 deselected in 0.26s'. Control: the pre-fix version (git show c8e3670^:plugin/test_landlock.py) under the same TMPDIR -> exit_code 1, '1 failed ... AssertionError: assert False is True ... _world_traversable('/tmp/tj-private-2037546/tj-ll-wt-r605rl8w/loader.py')', proving the fix is what makes it pass. Whole file under hostile TMPDIR: '129 passed, 1 skipped in 1.59s' (exit 0); default TMPDIR: '129 passed, 1 skipped in 2.28s' (exit 0). LSP diagnostics: 0 findings.
The test now pins its temp chain to a 0755 child of /tmp, and it passes with a 0700 TMPDIR while the pre-fix version demonstrably fails under the same condition.

Overall: FAIL ✗
