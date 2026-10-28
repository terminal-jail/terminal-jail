# Traceability Doctrine

Status: active doctrine. Born as board finding DOC-25 — this board had already
recorded the gap twice as
`spec=none:repo-has-no-traceability-doctrine-doc-DOC-25-pending` before this
file existed.

This document defines how work in this repository stays traceable: the marker
fields used on the task board, what counts as evidence and witness, and what a
board row must accumulate before it can be closed. It describes what this repo
already does; it does not invent a new standard. Every example below is quoted
from `.coding-hermes/board/events.jsonl` or `.gitreins/` as of 2026-10-27.

Related reading: [AGENTS.md](../AGENTS.md) (repo rules, GitReins harness),
[CONTRIBUTING.md](../CONTRIBUTING.md) (contributor workflow),
`.gitreins/config.yaml` (guard lanes and pinned interpreter).

## 1. The `ch:trace` marker

A `ch:trace` token is a compact, machine-greppable `key=value` string appended
to board event summaries and worker reports. It is the minimum traceability
record for closed work: one line lets any later reader walk from a row id to
the commit, the verification verdict, and the runtime witness without opening
a single log.

Full field set in use on this board:

| Field | Carries | Real example from this board |
|---|---|---|
| `row=` | The board row id the marker belongs to | `row=TJ-GAP-082` |
| `spec=` | The design authority the work implements — a spec/contract section, doc anchor, or test that pins the requirement | `spec=install.sh#containment-ceiling`, `spec=docs/quickstart.md` |
| `wave=` | The foreman wave/tick that dispatched the work | `wave=terminal-jail-foreman-2026-10-07-13-18-44`; `wave=none:serial` for serial dispatch |
| `test=` | The test(s) that pin the behavior | `test=plugin/test_modify_preflight.py` |
| `doc=` | The user-facing doc surface updated | `doc=README.md#install` |
| `prompt=` | Where the dispatched worker brief lives | `prompt=/tmp/tjdf055-worker-brief.txt` |
| `evidence=` | Static artifact pointer: file, test name, log path, or GitReins verdict artifact | `evidence=.gitreins/history/2026-10-20/bca620ea/verdict.json` |
| `witness=` | Runtime observation that the claim is live (see §3) | `witness=live:origin/main@7fe6f03` |
| `verdict=` | GitReins judge/guard verdict id | `verdict=d06d8032` |
| `commit=` | The implementation commit sha (one exact commit) | `commit=5429bdb+1f830c5` for a two-commit landing |
| `memory=` | DuckBrain memory key written for the tick, if any | `memory=/project/terminal-jail/tick-362` |

Not every marker carries a value on every row — counts on this board range from
`memory=` at 70 occurrences to `row=` at 93 of 97 traced events.

**The `none:` rule.** A field with nothing to report is written as
`none:<short-reason>` — it is never silently omitted and never left bare. The
reason is load-bearing: it tells the next reader whether the field is empty
because it does not apply (`wave=none:idle-no-dispatch`,
`spec=none:docs-gap`), because the work produced no artifact
(`witness=none:worker-zero-write`), or because the write went elsewhere
(`memory=none:foreman-writes-memory`). Real examples from this board:

- `verdict=none:task-complete-timeout-no-artifact`
- `commit=none`, `memory=none` on rows where the worker stalled
- `test=none:documentation-only` on a docs-only row

Older entries occasionally wrote a bare `spec=none` without a reason; the
current convention is the reason-carrying form and new rows must use it.

## 2. Evidence and witness rules

### 2.1 Evidence

`evidence=` points at a static artifact that can be re-read later: a test name,
a log, a doc anchor, or — for verified work — a GitReins verdict artifact.
Verification artifacts live under the GitReins history tree:

```
.gitreins/history/<date>/<verdict-id>/verdict.json
```

for example `.gitreins/history/2026-10-25/71baae53/verdict.json`. The
`<verdict-id>` in the path is the same id recorded in `verdict=`.

### 2.2 One verdict, one commit

A GitReins verdict binds to ONE exact commit — the short sha graded by the
guard/judge run — never to "the task" as a concept. When work lands as a
sequence of commits, the marker records each one
(`commit=5429bdb+1f830c5`), and the verdict id belongs to the specific tree
the guard actually graded. A verdict from an older sha does not certify a
newer one; re-run the guard or record a new verdict after further commits.

### 2.3 Witness

`witness=` records a runtime observation — proof that something actually ran
or is actually live, as opposed to `evidence=`, which only points at a
artifact that exists. The witness vocabulary on this board:

- `live:<what-was-observed-where>` — a runtime observation at a specific
  place: `witness=live:origin/main@7fe6f03`,
  `witness=live:arg-size-benchmark-run-at-HEAD`,
  `witness=live:CI-run-success-on-6f9ec2d`
- `run:<commands-executed>` — a command/acceptance battery executed:
  `witness=run:acceptance-grep+suite+ruff+ci-40085498969`
- `none:<reason>` — no runtime witness exists:
  `witness=none:no-out-of-band-runtime-witness`,
  `witness=none:local benchmarks cited in README transport docs`

A claim recorded with `witness=none:<reason>` cannot support a close-out of
implementation work. `none:` witnesses are legitimate on rows that genuinely
produced nothing to observe (a stalled worker, an idle tick, a docs-only
finding recorded as closed-verification-only) — but in those cases the row is
closed as *no-op/verification-only*, not as delivered work. If a row claims a
behavior change, it needs a `live:` or `run:` witness.

## 3. Close-out sequence for a board row

A row is closeable only after every step below has produced its artifact:

1. **Implementation commit** — the change lands in its own commit (workers
   commit in a worktree per AGENTS.md); `commit=` gets that sha.
2. **Independent verification** — the row's acceptance legs are re-run in the
   working tree (the exact pytest/ruff/grep commands from the row's
   acceptance criteria), producing the `run:` witness.
3. **GitReins tier-1 guard** — `gitreins guard` (secrets, lint, tests,
   static-analysis lanes; see `.gitreins/config.yaml`) must pass on the staged
   diff. A commit that landed on a hook-timeout FAIL-OPEN early-return is NOT
   gate-verified — if the hook timed out, re-run the guard before claiming it.
4. **Tier-2 judge verdict** — the judge grades the full tree
   (`evaluator.file_scope: full`); its verdict id goes in `verdict=` and its
   artifact is the `evidence=` path from §2.1.
5. **Board event** — the close-out event is appended to
   `.coding-hermes/board/events.jsonl` carrying `commit_hash` and the verdict
   id, with the full `ch:trace` marker embedded.
6. **Push with remote parity** —
   `git rev-list --count origin/main..HEAD` must be `0` after push. An
   unpushed close-out is not a close-out.
7. **`memory=`** — write the DuckBrain memory key if the tick produced one;
   otherwise `memory=none:<reason>`.

The guard's quality floor itself is configuration, not convention: the tests
lane is interpreter-pinned (`.venv/bin/python -m pytest -x --tb=short`,
tick #289), the tests lane budget is `test_timeout: 900` inside a
`hook_timeout: 1200` whole-run budget (TJ-DF-043), and `allow_skips: true`
lets a degenerate no-gradable-diff commit exit 0 while a gate that RUNS and
fails still blocks (TRUST-001).

## 4. Quick reference

```
ch:trace row=<board-row> spec=<authority>#<anchor> wave=<tick-id>
         test=<test> doc=<doc-anchor> prompt=<brief-path>
         evidence=<artifact-path> witness=live:<observation>|run:<commands>|none:<reason>
         verdict=<8-hex-verdict-id> commit=<sha>[+<sha>]
         memory=<duckbrain-key>|none:<reason>
```

Empty field → `none:<short-reason>`, never omitted. No witness → no close-out
of delivered work.
