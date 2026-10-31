# Verdict: TJ-DF-057-VERIFY

**Task:** TJ-DF-057 narrow verification: tracked-litter reap recipe documented at the project skill (path-corrected; supersedes the stale-path grade in runs adfc5d40/e03b08d6)
**Evaluated:** 2026-10-31T19:24:58.923545
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_backend_parity.py::test_live_unshare_orphan_teardown [first failing id])
- ✗ **tier2**
  - INCOMPLETE
  ✗ test -f /home/kara/.hermes/skills/coding-hermes/coding-hermes-foreman-terminal-jail/SKILL.md && grep -q 'restore the files to HEAD' /home/kara/.hermes/skills/coding-hermes/coding-hermes-foreman-terminal-jail/SKILL.md && grep -q 'explicit recorded retention decision' /home/kara/.hermes/skills/coding-hermes/coding-hermes-foreman-terminal-jail/SKILL.md; every command must exit 0, proving the reap recipe for tracked harness-state litter (merged-branch proof via merge-base --is-ancestor plus ahead>0, harness-state-only confirmation, restore-or-move-aside then re-run reap) and the explicit-retention-decision rule are documented at the project skill. The single path in this criterion is authoritative; earlier runs graded a stale typo'd sibling path and are superseded on this point: Ran the exact criterion command: `test -f ... && grep -q 'restore the files to HEAD' ... && grep -q 'explicit recorded retention decision' ...` -> CRITERION_EXIT=1 (not 0). Isolating the parts: `test -f /home/kara/.hermes/skills/coding-hermes/coding-hermes-foreman-terminal-jail/SKILL.md` -> exit 0 (file exists, 239 lines); `grep -q 'explicit recorded retention decision'` -> exit 0 (1 match at line 229); but `grep -q 'restore the files to HEAD'` -> exit 1 (grep -c = 0; also 'restore the files' = 0 and 'to HEAD' = 0 anywhere in the file). The substantive recipe IS documented at SKILL.md:229 (merge-base --is-ancestor + `git rev-list --count origin/main..<branch>` > 0, harness-state-only confirmation, and step (3) `git -C <wt> checkout -- <those files>` (or move them aside) then re-run `reap`, plus the explicit recorded retention decision rule), but the doc uses 'checkout --' wording rather than the literal phrase 'restore the files to HEAD' the criterion greps for. Since the criterion is a literal-command gate requiring every command to exit 0, it fails as written.
The project skill file exists and documents the tracked-litter reap recipe and retention rule at line 229, but the criterion's mandated grep for the literal phrase 'restore the files to HEAD' returns no match, so the compound command exits 1 instead of 0.

## Summary

Judge Result: TJ-DF-057-VERIFY

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_backend_parity.py::test_live_unshare_orphan_teardown [first failing id])

Stage tier2: FAIL
  INCOMPLETE
  ✗ test -f /home/kara/.hermes/skills/coding-hermes/coding-hermes-foreman-terminal-jail/SKILL.md && grep -q 'restore the files to HEAD' /home/kara/.hermes/skills/coding-hermes/coding-hermes-foreman-terminal-jail/SKILL.md && grep -q 'explicit recorded retention decision' /home/kara/.hermes/skills/coding-hermes/coding-hermes-foreman-terminal-jail/SKILL.md; every command must exit 0, proving the reap recipe for tracked harness-state litter (merged-branch proof via merge-base --is-ancestor plus ahead>0, harness-state-only confirmation, restore-or-move-aside then re-run reap) and the explicit-retention-decision rule are documented at the project skill. The single path in this criterion is authoritative; earlier runs graded a stale typo'd sibling path and are superseded on this point: Ran the exact criterion command: `test -f ... && grep -q 'restore the files to HEAD' ... && grep -q 'explicit recorded retention decision' ...` -> CRITERION_EXIT=1 (not 0). Isolating the parts: `test -f /home/kara/.hermes/skills/coding-hermes/coding-hermes-foreman-terminal-jail/SKILL.md` -> exit 0 (file exists, 239 lines); `grep -q 'explicit recorded retention decision'` -> exit 0 (1 match at line 229); but `grep -q 'restore the files to HEAD'` -> exit 1 (grep -c = 0; also 'restore the files' = 0 and 'to HEAD' = 0 anywhere in the file). The substantive recipe IS documented at SKILL.md:229 (merge-base --is-ancestor + `git rev-list --count origin/main..<branch>` > 0, harness-state-only confirmation, and step (3) `git -C <wt> checkout -- <those files>` (or move them aside) then re-run `reap`, plus the explicit recorded retention decision rule), but the doc uses 'checkout --' wording rather than the literal phrase 'restore the files to HEAD' the criterion greps for. Since the criterion is a literal-command gate requiring every command to exit 0, it fails as written.
The project skill file exists and documents the tracked-litter reap recipe and retention rule at line 229, but the criterion's mandated grep for the literal phrase 'restore the files to HEAD' returns no match, so the compound command exits 1 instead of 0.

Overall: FAIL ✗
