# Verdict: TJ-GAP-096-R1

**Task:** Verify TJ-GAP-096 acceptance: foreign core.hooksPath shadow and /var/tmp/foreign-hooks residue both cleared
**Evaluated:** 2026-11-03T02:49:46.972493
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: scanners=gitleaks+builtin cross-check
  ✓ tests: scanners: nice=nice -n 10
- ✗ **tier2**
  - INCOMPLETE
  ✓ Clause 1 of the TJ-GAP-096 written acceptance: run `git config core.hooksPath` and `git config --global --get core.hooksPath` from the repository root — both must print no value and exit non-zero, proving no local, global or effective core.hooksPath shadows the repository's own .git/hooks (the 2026-10-22 leak was core.hooksPath=/var/tmp/foreign-hooks).: Ran from repo root /home/kara/worktrees/terminal-jail-TJ-GAP-096-R1: `git config core.hooksPath` -> no output, exit=1; `git config --global --get core.hooksPath` -> no output, exit=1; effective `git config --get core.hooksPath` -> no output, exit=1. No local/global/effective shadow exists.
  ✓ Clause 2 of the TJ-GAP-096 written acceptance — the surviving gate named in the row's blocked_reason: `test ! -e /var/tmp/foreign-hooks/pre-commit` exits 0. The leftover foreign hook directory recorded 2026-10-22 (dir mtime 2026-10-22 15:48:33 -0500, contents [pre-commit]) must be gone from the host.: `ls -la /var/tmp/foreign-hooks` -> "ls: cannot access '/var/tmp/foreign-hooks': No such file or directory" (exit 2); `test ! -e /var/tmp/foreign-hooks/pre-commit` -> exit=0. The residue directory is gone from the host.
  ✓ The TJ-GAP-096 row in .coding-hermes/board/tasks.jsonl at the judged commit carries a foreman_note recording the exact probe commands and observed results for clauses 1-2, the executable .git/hooks/prepare-commit-msg trailer hook, and the trailer audit of the last three commits (3/3 carry exactly one Co-authored-by: Alexis Okuwa <wojonstech@gmail.com> trailer).: `git show HEAD:.coding-hermes/board/tasks.jsonl` line 302 (id TJ-GAP-096) has foreman_note "ACCEPTANCE VERIFICATION 2026-11-03T02:09Z ..." containing: clause 1 `git config core.hooksPath` -> no value (exit 1) and `git config --global --get core.hooksPath` -> no value (exit 1); clause 2 `test ! -e /var/tmp/foreign-hooks/pre-commit` -> exit 0; ".git/hooks/prepare-commit-msg present and executable (-rwxr-xr-x)"; trailer audit `git log -3` at 02682ae/6a3e9d6/390fcaf — 3/3 commits carry exactly one Co-authored-by trailer. All four required elements are recorded verbatim.
  ✗ Live trailer check at the judged commit: `git log -3 --format=%b <judged-commit>` shows each of the three most recent commits carries exactly one Co-authored-by: Alexis Okuwa <wojonstech@gmail.com> line, and `test -x .git/hooks/prepare-commit-msg` exits 0.: Live check at judged commit af8caf396e2ffa6f2beb20a2a74b1296cc1b0f9b contradicts the claim. Per-commit exact-line count of '^Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>$': af8caf3 trailers=0, 02682ae trailers=1, 6a3e9d6 trailers=1 — i.e. 2/3, not 3/3. `git log -1 --format=%B | cat -A` shows HEAD's body ends at the ch:trace line with no trailer (the only 'Co-authored-by' occurrence is prose inside the body at line 13). Additionally `test -x .git/hooks/prepare-commit-msg` from the repo root exits 1: the worktree's .git is a file pointing at /home/kara/terminal-jail/.git/worktrees/terminal-jail-TJ-GAP-096-R1, which has no hooks directory; the hook is executable only in the main repo (/home/kara/terminal-jail/.git/hooks/prepare-commit-msg, exit 0). Both halves of the criterion fail as written.
Clauses 1-2 and the board foreman_note are verified, but the live trailer check fails: the judged commit af8caf3 itself carries no Co-authored-by trailer (2/3, not 3/3) and `test -x .git/hooks/prepare-commit-msg` exits 1 from the repo root.

## Summary

Judge Result: TJ-GAP-096-R1

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: scanners=gitleaks+builtin cross-check
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: FAIL
  INCOMPLETE
  ✓ Clause 1 of the TJ-GAP-096 written acceptance: run `git config core.hooksPath` and `git config --global --get core.hooksPath` from the repository root — both must print no value and exit non-zero, proving no local, global or effective core.hooksPath shadows the repository's own .git/hooks (the 2026-10-22 leak was core.hooksPath=/var/tmp/foreign-hooks).: Ran from repo root /home/kara/worktrees/terminal-jail-TJ-GAP-096-R1: `git config core.hooksPath` -> no output, exit=1; `git config --global --get core.hooksPath` -> no output, exit=1; effective `git config --get core.hooksPath` -> no output, exit=1. No local/global/effective shadow exists.
  ✓ Clause 2 of the TJ-GAP-096 written acceptance — the surviving gate named in the row's blocked_reason: `test ! -e /var/tmp/foreign-hooks/pre-commit` exits 0. The leftover foreign hook directory recorded 2026-10-22 (dir mtime 2026-10-22 15:48:33 -0500, contents [pre-commit]) must be gone from the host.: `ls -la /var/tmp/foreign-hooks` -> "ls: cannot access '/var/tmp/foreign-hooks': No such file or directory" (exit 2); `test ! -e /var/tmp/foreign-hooks/pre-commit` -> exit=0. The residue directory is gone from the host.
  ✓ The TJ-GAP-096 row in .coding-hermes/board/tasks.jsonl at the judged commit carries a foreman_note recording the exact probe commands and observed results for clauses 1-2, the executable .git/hooks/prepare-commit-msg trailer hook, and the trailer audit of the last three commits (3/3 carry exactly one Co-authored-by: Alexis Okuwa <wojonstech@gmail.com> trailer).: `git show HEAD:.coding-hermes/board/tasks.jsonl` line 302 (id TJ-GAP-096) has foreman_note "ACCEPTANCE VERIFICATION 2026-11-03T02:09Z ..." containing: clause 1 `git config core.hooksPath` -> no value (exit 1) and `git config --global --get core.hooksPath` -> no value (exit 1); clause 2 `test ! -e /var/tmp/foreign-hooks/pre-commit` -> exit 0; ".git/hooks/prepare-commit-msg present and executable (-rwxr-xr-x)"; trailer audit `git log -3` at 02682ae/6a3e9d6/390fcaf — 3/3 commits carry exactly one Co-authored-by trailer. All four required elements are recorded verbatim.
  ✗ Live trailer check at the judged commit: `git log -3 --format=%b <judged-commit>` shows each of the three most recent commits carries exactly one Co-authored-by: Alexis Okuwa <wojonstech@gmail.com> line, and `test -x .git/hooks/prepare-commit-msg` exits 0.: Live check at judged commit af8caf396e2ffa6f2beb20a2a74b1296cc1b0f9b contradicts the claim. Per-commit exact-line count of '^Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>$': af8caf3 trailers=0, 02682ae trailers=1, 6a3e9d6 trailers=1 — i.e. 2/3, not 3/3. `git log -1 --format=%B | cat -A` shows HEAD's body ends at the ch:trace line with no trailer (the only 'Co-authored-by' occurrence is prose inside the body at line 13). Additionally `test -x .git/hooks/prepare-commit-msg` from the repo root exits 1: the worktree's .git is a file pointing at /home/kara/terminal-jail/.git/worktrees/terminal-jail-TJ-GAP-096-R1, which has no hooks directory; the hook is executable only in the main repo (/home/kara/terminal-jail/.git/hooks/prepare-commit-msg, exit 0). Both halves of the criterion fail as written.
Clauses 1-2 and the board foreman_note are verified, but the live trailer check fails: the judged commit af8caf3 itself carries no Co-authored-by trailer (2/3, not 3/3) and `test -x .git/hooks/prepare-commit-msg` exits 1 from the repo root.

Overall: FAIL ✗
