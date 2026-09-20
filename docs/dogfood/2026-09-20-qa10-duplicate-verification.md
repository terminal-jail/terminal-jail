# QA-TERMINAL-JAIL-10 — verified duplicate of DF-TERMINAL-JAIL-28

**Date:** 2026-09-20
**Branch:** wt/QA-TERMINAL-JAIL-10 (base 5914dd6)
**Verdict:** No code change required. The defect described by
QA-TERMINAL-JAIL-10 is DF-TERMINAL-JAIL-28, already fixed by commit
`7eaf8e0` (ancestor of this branch's base). The QA battery that filed the
row ran at HEAD `40cbb09`, which still carried the brittle assertion and
predates the fix.

## Why the row fired anyway

- QA-TERMINAL-JAIL-10 reports
  `plugin/test_rule_packs.py::TestValidatorRefusals::test_builtin_id_collision_is_refused`
  failing because `_assert_refused` asserts `len(stderr_lines) == 1` while
  degraded-FS hosts prepend
  `terminal-jail: WARNING: no filesystem isolation — ...`.
- At battery HEAD `40cbb09` that is exactly the code:
  `git show 40cbb09:plugin/test_rule_packs.py` line 236 is
  `assert len(stderr_lines) == 1, stderr_lines`.
- `40cbb09` is NOT an ancestor of the fix commit `7eaf8e0`
  (`git merge-base --is-ancestor 40cbb09 7eaf8e0` → false), so the battery
  tested the pre-fix tree.
- The current base `5914dd6` contains `7eaf8e0` ("DF-TERMINAL-JAIL-28:
  test_rule_packs asserts refusal-presence not exact line-count").

## Acceptance-criteria verification (on this tree)

| Criterion | Result |
| --- | --- |
| 1. No exact stderr line count; refusal asserted by presence, robust to the WARNING | `_assert_refused` anchors on `rule-pack-tool: refused:` (exactly once + expected reason); only `DOCUMENTED_SANDBOX_BANNERS` prefixes are tolerated, each at most once; any other line is a hard failure (`TestAssertRefusedContract::test_unexpected_line_beside_the_refusal_fails`). `grep` finds zero residual `len(stderr_lines)`-style assertions in `plugin/`. |
| 2. Refusal behavior still asserted: rc=2 + collision message | `assert result.returncode == 2` plus `needle in refusal_lines[0]`; the target test pins `"collide with engine builtin ids"`. Not loosened beyond banner tolerance. |
| 3. WARNING-proof on a host that does not emit it naturally | `TestAssertRefusedContract` (8 tests, all pass) drives `_assert_refused` with CONSTRUCTED stderr shapes, including `test_refusal_plus_df15_warning_passes` — the battery's observed WARNING-then-refusal 2-line case — plus negative controls (repeated banner, near-miss line, missing refusal, wrong rc). |
| 4. Full suite green, no regressions | Baseline (pre-edit): 1081 passed, 7 skipped in ~33s. After (no code change): 1081 passed, 7 skipped in ~29s. `ruff check plugin/` clean. |

## Host-behavior notes

- This dev host has full filesystem isolation: the WARNING does not fire;
  the target test passes as-is (1 passed, 34 deselected).
- `TERMINAL_JAIL_UID_MAP=0` (the documented degraded-mode env hook) does
  not reproduce the WARNING on this host either — per DF-TERMINAL-JAIL-15
  it fires only on subuid hosts where the uid-mapped launch is creatable
  but not file-access preserving (the battery's bunker). A live probe of
  the refusal command under that env still returned rc=2 with the single
  refusal line, and the current helper accepted it.
- The bunker's 2-line stderr shape is therefore covered by the
  constructed-shape self-tests, which run on every host.

## Recommended board action

Close QA-TERMINAL-JAIL-10 as a verified duplicate of DF-TERMINAL-JAIL-28
(fix `7eaf8e0`, CI run 35503096839 success on merge fe5922e). No further
code work.
