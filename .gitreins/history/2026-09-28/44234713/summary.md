# Verdict: QA-TERMINAL-JAIL-13

**Task:** Fix clean-host unshare orphan teardown
**Evaluated:** 2026-09-28T03:27:28.773207
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✗ **tier2**
  - INCOMPLETE
  ✗ On a clean PIDNS-FULL host, SIGKILL of the unshare terminal-jail wrapper must reap the sleep payload within 15 seconds; implement and test the narrow teardown fix or encode an explicit kernel contract with truthful evidence.: Neither acceptable path was completed. (1) No teardown fix: standalone/terminal-jail is unchanged since 2026-09-23 (commit 0fc950a); flags remain `--pid --fork --kill-child=SIGKILL` (lines 483-485) with no PDEATHSIG/prctl/setsid plumbing change; `git log --since='2026-09-27 22:00' --until='2026-09-28 23:59' --all` is EMPTY — the only diff for this task is .gitreins/tasks.yaml + board metadata. (2) No explicit kernel contract with truthful evidence produced by this task: the kernel-matrix harness (scripts/kernel-matrix-teardown.py, tests/test_kernel_matrix_teardown.py, docs/backend-parity.md section) was committed 2026-09-27 17:23 (e39ba82) explicitly 'Addresses TJ-DF-037' — a different task closed at tick #327 — and docs/backend-parity.md:151-158 records the Debian 13.7/6.12.107 unshare cell as 'UNVERIFIED external cell ... raw output ... was not attached to this repo; the row stays unresolved' with 'Matrix verdict: NOT GREEN.' The board row itself self-reports failure: .coding-hermes/board/tasks.jsonl QA-TERMINAL-JAIL-13 has worker_status='failed', worker_summary='No code landed: first glm-5.3-flash worker stalled after source inspection; rework minimax-m3 also stalled before producing a diff or commit.', guard_result='SKIP', ci_result='SKIP', foreman_note='...GitReins task flipped complete but tier-2 produced no verdict artifact before the evaluator was stopped; do not treat this as judged or resolved.' Test evidence gathered is dev-host only (kernel 7.0.0-31-generic, PIDNS-FULL per scripts/pidns-capability-probe.py => FULL), where the bug never reproduced: `pytest plugin/test_backend_parity.py tests/test_kernel_matrix_teardown.py -q` => 56 passed in 8.86s (exit 0); `scripts/kernel-matrix-teardown.py --raw` => unshare PASS 20ms; manual SIGKILL repro => 8ms teardown. None of this covers the clean PIDNS-FULL host (bare Debian 13.7/6.12.107) the criterion targets, where the payload survived 15s and remains unfixed and unevidenced.
QA-TERMINAL-JAIL-13 was marked complete with only board metadata — no teardown fix landed and no truthful clean-host kernel contract/evidence was produced, so the criterion fails.

## Summary

Judge Result: QA-TERMINAL-JAIL-13

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: FAIL
  INCOMPLETE
  ✗ On a clean PIDNS-FULL host, SIGKILL of the unshare terminal-jail wrapper must reap the sleep payload within 15 seconds; implement and test the narrow teardown fix or encode an explicit kernel contract with truthful evidence.: Neither acceptable path was completed. (1) No teardown fix: standalone/terminal-jail is unchanged since 2026-09-23 (commit 0fc950a); flags remain `--pid --fork --kill-child=SIGKILL` (lines 483-485) with no PDEATHSIG/prctl/setsid plumbing change; `git log --since='2026-09-27 22:00' --until='2026-09-28 23:59' --all` is EMPTY — the only diff for this task is .gitreins/tasks.yaml + board metadata. (2) No explicit kernel contract with truthful evidence produced by this task: the kernel-matrix harness (scripts/kernel-matrix-teardown.py, tests/test_kernel_matrix_teardown.py, docs/backend-parity.md section) was committed 2026-09-27 17:23 (e39ba82) explicitly 'Addresses TJ-DF-037' — a different task closed at tick #327 — and docs/backend-parity.md:151-158 records the Debian 13.7/6.12.107 unshare cell as 'UNVERIFIED external cell ... raw output ... was not attached to this repo; the row stays unresolved' with 'Matrix verdict: NOT GREEN.' The board row itself self-reports failure: .coding-hermes/board/tasks.jsonl QA-TERMINAL-JAIL-13 has worker_status='failed', worker_summary='No code landed: first glm-5.3-flash worker stalled after source inspection; rework minimax-m3 also stalled before producing a diff or commit.', guard_result='SKIP', ci_result='SKIP', foreman_note='...GitReins task flipped complete but tier-2 produced no verdict artifact before the evaluator was stopped; do not treat this as judged or resolved.' Test evidence gathered is dev-host only (kernel 7.0.0-31-generic, PIDNS-FULL per scripts/pidns-capability-probe.py => FULL), where the bug never reproduced: `pytest plugin/test_backend_parity.py tests/test_kernel_matrix_teardown.py -q` => 56 passed in 8.86s (exit 0); `scripts/kernel-matrix-teardown.py --raw` => unshare PASS 20ms; manual SIGKILL repro => 8ms teardown. None of this covers the clean PIDNS-FULL host (bare Debian 13.7/6.12.107) the criterion targets, where the payload survived 15s and remains unfixed and unevidenced.
QA-TERMINAL-JAIL-13 was marked complete with only board metadata — no teardown fix landed and no truthful clean-host kernel contract/evidence was produced, so the criterion fails.

Overall: FAIL ✗
