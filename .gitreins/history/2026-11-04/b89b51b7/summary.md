# Verdict: TJ-GAP-098

**Task:** prepare-commit-msg trailer hook must match standalone trailer LINES, not a substring of the co-author name
**Evaluated:** 2026-11-04T15:57:21.913865
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: scanners=gitleaks+builtin cross-check
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ Probe in a scratch repo: a commit whose body mentions 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' as prose still receives exactly one standalone trailer line; a message already carrying the real trailer gets no duplicate; a message with no mention still gets one. Hook resolved via git rev-parse --git-path hooks.: Executed the probe live in scratch repo /tmp/tjgap098.X5k60m: `git init`, then `HOOKS=$(git rev-parse --git-path hooks)` -> `.git/hooks`, copied the repo's hook from /home/kara/terminal-jail/.git/hooks/prepare-commit-msg and chmod +x. ARM1 (prose mention, body 'The body mentions Co-authored-by: Alexis Okuwa <wojonstech@gmail.com> as prose only.') -> `grep -cxE 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>'` = 1, and `cat -A` shows the appended standalone line after a blank separator. ARM2 (message already carrying the real trailer) -> count = 1, no duplicate. ARM3 (no mention) -> count = 1. Hook source .git/hooks/prepare-commit-msg:16-27 uses an anchored per-line regex `^[[:space:]]*Co-authored-by:[[:space:]]*Alexis Okuwa[[:space:]]*<wojonstech@gmail\.com>[[:space:]]*$` plus a `git interpret-trailers --parse` fallback — no bare substring `grep -q`. Corroborated in-repo: HEAD cdc8f05's message quotes the trailer as prose (`grep -c 'Co-authored-by'` = 2) yet the standalone count is 1, while the pre-fix incident commit af8caf3 yields 0. Note: no pytest test covers this hook (grep for prepare-commit-msg/interpret-trailers in plugin/, scripts/, tests/ returned no hits); the criterion is a live probe, which I ran directly.
The prepare-commit-msg hook now matches a standalone trailer LINE (anchored regex + git interpret-trailers), and a live scratch-repo probe via `git rev-parse --git-path hooks` confirms 1/1/1 trailer lines for the prose-mention, already-trailered, and no-mention cases.

## Summary

Judge Result: TJ-GAP-098

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: scanners=gitleaks+builtin cross-check
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ Probe in a scratch repo: a commit whose body mentions 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>' as prose still receives exactly one standalone trailer line; a message already carrying the real trailer gets no duplicate; a message with no mention still gets one. Hook resolved via git rev-parse --git-path hooks.: Executed the probe live in scratch repo /tmp/tjgap098.X5k60m: `git init`, then `HOOKS=$(git rev-parse --git-path hooks)` -> `.git/hooks`, copied the repo's hook from /home/kara/terminal-jail/.git/hooks/prepare-commit-msg and chmod +x. ARM1 (prose mention, body 'The body mentions Co-authored-by: Alexis Okuwa <wojonstech@gmail.com> as prose only.') -> `grep -cxE 'Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>'` = 1, and `cat -A` shows the appended standalone line after a blank separator. ARM2 (message already carrying the real trailer) -> count = 1, no duplicate. ARM3 (no mention) -> count = 1. Hook source .git/hooks/prepare-commit-msg:16-27 uses an anchored per-line regex `^[[:space:]]*Co-authored-by:[[:space:]]*Alexis Okuwa[[:space:]]*<wojonstech@gmail\.com>[[:space:]]*$` plus a `git interpret-trailers --parse` fallback — no bare substring `grep -q`. Corroborated in-repo: HEAD cdc8f05's message quotes the trailer as prose (`grep -c 'Co-authored-by'` = 2) yet the standalone count is 1, while the pre-fix incident commit af8caf3 yields 0. Note: no pytest test covers this hook (grep for prepare-commit-msg/interpret-trailers in plugin/, scripts/, tests/ returned no hits); the criterion is a live probe, which I ran directly.
The prepare-commit-msg hook now matches a standalone trailer LINE (anchored regex + git interpret-trailers), and a live scratch-repo probe via `git rev-parse --git-path hooks` confirms 1/1/1 trailer lines for the prose-mention, already-trailered, and no-mention cases.

Overall: PASS ✓
