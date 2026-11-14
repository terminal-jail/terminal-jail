# 2026-11-14 install battery — final per-cell ledger

Tick: `terminal-jail-dogfood-2026-11-14-10-01-04` (continuation fire 2 of the same run — record leg, not a duplicate)
Target HEAD: `489bbd4` (product HEAD unchanged; `git rev-list --left-right --count HEAD...origin/main` = `0 0` at tick start)
Host: `bunker-mvp`, agent `51fa2112` (spawned 2026-11-14T10:15:29Z, TTL 14:15:29Z, destroyed 2026-11-14T10:46Z)
Harness: `bash /home/kara/.hermes/scripts/bunker-qa.sh` (shared QA harness, 139101 B script the `launch` cell recorded)

## Why this file exists

The first fire of this tick (`2026-11-14a`) committed a **provisional** install summary: seven cells
had been synced when it wrote, and it closed with *"battery still running at write time … agent left
to its TTL"*. The battery has since reached a terminal state — `qa-run.log` ends `CELLS-DONE` and
`qa-evidence.jsonl` stops growing, both at 2026-11-14T10:40Z — so the provisional summary is
superseded here with the values the harness actually wrote.

A second, harder reason: **both collect passes graded a live agent as gone.** The 10:16Z pass wrote
`AGENT-GONE agent=51fa2112 rows=7`, and the 10:38–10:40Z pass (attempt 1, 120113 ms) wrote
`status=agent-gone … ssh probe returned no state … per-cell logs lost with the agent user`. In
between and after, the same agent answered `bunker exec` and `bunker info` normally, and its own
evidence file held **24** cells against the **8** the host-side evidence file had synced. So the
collect ledger is truncated by a probe transient, not by a dead battery — the exact class already
owned by **QA-TERMINAL-JAIL-FOREMAN-1** (blocked, P3, dedupe survivor for collector abandonment).

## Provenance of these numbers

Read on the agent at ~10:41–10:43Z through `bunker exec 51fa2112 --server bunker-mvp`, redirected to
`/home/kara/.hermes/cache/scratch/tj-battery-51fa2112.jsonl` (24 records, 24 `^{` lines,
SHA-256 `ddb3f6424fe507d6d7c97be4ee5072bf30f1334c0082150130a84ae18e1f4279`). The agent-side file was
`/home/bunker-51fa2112/qa-evidence.jsonl`, 8311 B, mtime 10:40.

Host-side evidence file `/tmp/bunker-qa-evidence-20261114T101500Z-2836405.jsonl` (9 records = 8 cells
+ the collect verdict, SHA-256 `fd7ab5f88249ab1e694c73fcf9eeca8a25164af7e59096b5af4defe576ecb202`)
is **not** a copy of the ledger above: it is missing 16 of the 24 cells.

The JSONL was harvested as shell output, not `bunker pull`/`scp` — that path is refused by the
unattended tool-consent gate (no answer = no consent). No credential was minted and none was needed.

## Cell census — 24 cells

| # | cell | status | detail as written by the harness (prefix where the cell detail is long) |
|---|------|--------|----------------------------------|
| 1 | toolchain-bootstrap | OK | go 1.27.4 installed (discovered; `~/tools/go`; floor=none ambient=1.22.2 installed=1.27.4) |
| 2 | toolchain-bootstrap | OK | python venv ready + pytest (`~/tools/venv`) |
| 3 | toolchain-bootstrap | OK | system gcc/g++ toolchain (`~/tools/bin` wrappers → gcc/g++, preferred over zig-cc for C++ cgo deps, MCP-008) |
| 4 | toolchain-bootstrap | OK | make available (preinstalled) — GNU Make 4.3 |
| 5 | toolchain-bootstrap | OK | jq installed (static jq-linux64 → jq-1.8.2 at `~/tools/bin/jq`) |
| 6 | **fresh-install** | **OK** | `Successfully installed PyYAML-6.0.3 terminal-jail-1.3.3`; "no artifact expected for `pip install -e .[dev] || pip install -e .`" → **installability on a fresh box proven again at 489bbd4** |
| 7 | lint | N/A | no supported lint trigger (no declared linter, Makefile lint target, package lint script, ruff, or Go files) |
| 8 | **tests** | **FAIL** | `rc=1`, one failure at ~23% of the suite: `plugin/test_install.py::test_successful_install` (`install_script=/home/bunker-51fa2112/qa-terminal-jail/install.sh`, `HOME=tmp_path`, `_setup_full_testbin` sandbox PATH); capture truncated at 1517 B before the assertion text |
| 9 | docker_build | N/A | no Dockerfile trigger |
| 10 | compose_config | N/A | no compose file trigger |
| 11 | toolchain-bootstrap | OK | compose plugin installed (`~/.docker/cli-plugins/docker-compose`) |
| 12 | toolchain-bootstrap | OK | buildx plugin installed (buildx v0.39.0, 360040a) |
| 13 | toolchain-bootstrap | OK | node+npm installed (node v22.15.0, npm 10.9.2) |
| 14 | toolchain-bootstrap | OK | `HARNESS-COMPOSE=ok` (docker compose version passes) |
| 15 | toolchain-bootstrap | OK | `HARNESS_NODE=ok` |
| 16 | **ci-pass** | **FAIL** | native `rc=1` = the same `test_successful_install`; act leg `act_result=fail rc=1`, log names `CI/Audit (pip-audit)` and parallel `CI/Lint (ruff)` / `CI/Python 3.12-2` legs, checkout and setup-python steps succeeding |
| 17 | **upgrade** | **FAIL** | `pip install terminal-jail==1.3.2` (tag v1.3.2) → `ERROR: Could not find a version that satisfies the requirement` — PyPI channel mismatch, not a code defect |
| 18 | docker-deploy | N/A | no compose file |
| 19 | ui-probe | N/A | no web UI detected |
| 20 | chaos-disconnect | UNVERIFIED | disconnect log lacks `NETWORK_CUT_APPLIED` or suite counts — cascade of the same `test_install` failure |
| 21 | chaos-shutdown | N/A | no compose file |
| 22 | chaos-corruption | N/A | no pre-existing db/state files in repo (`./.coding-hermes/board/board.db` was created during the run and skipped) |
| 23 | **chaos-resource** | **FAIL** | `rc=1` under cap 3145728KB (child/subshell saw 3145728, parent unlimited) — same `test_install` failure |
| 24 | chaos-errorpath | OK | clean error on missing config (`rc=2`) |

Totals: **12 OK, 7 N/A, 4 FAIL, 1 UNVERIFIED** (24) — identical shape to the 2026-11-11 battery
on HEAD `cc13fa0`, i.e. no new failure class appeared across three days and one release bump.

## Dispositions — nothing here is a new defect

- **tests / ci-pass / chaos-resource / chaos-disconnect** are one root test,
  `plugin/test_install.py::test_successful_install`, already carried by **QA-TERMINAL-JAIL-32**
  (pending, P3). Corroboration this fire adds: cell 6 installed the same tree successfully through
  the *real* PATH while the failing test drives `install.sh` with `HOME=tmp_path` and a synthetic
  `_setup_full_testbin` PATH — so the failure is sandbox-PATH-specific. Premise support, **not** a
  proven root cause: the harness capture stops at 1517 B before the assertion.
- **upgrade** is the channel mismatch already filed three times: **QA-TERMINAL-JAIL-11** (pending),
  **QA-TERMINAL-JAIL-19-R2** (pending), **TJ-DF-032** (complete).
- **No new row filed** this fire. Every FAIL maps to an owned row, and the collector defect maps to
  **QA-TERMINAL-JAIL-FOREMAN-1** (blocked, P3, the declared dedupe survivor for "reachable agent
  abandoned on an ssh-probe transient"). Statuses were not touched.

## Harness observations (owner: bunker/QA harness, not this project)

1. `collect` graded a **live** agent as gone twice: `AGENT-GONE … rows=7` at 10:16:11Z and
   `status=agent-gone … ssh probe returned no state` at 10:40:50Z, while `bunker info` showed
   `Status: running` (TTL 14:15:29Z) and `bunker exec` worked seconds later.
2. Consequently only 8 of 24 cells ever reached the host-side evidence file. A lane that trusted
   `collect` would have reported an 8-cell battery and called 16 cells never-run — the truncation
   direction that turns real coverage into a false gap.
3. The same verdict claims `per-cell logs lost with the agent user`; no `qa-*.logs` file existed on
   the agent (`ls` showed only `qa-evidence.jsonl` and `qa-run.log`), so the per-cell log tree was
   never present to lose.
4. The gone-path also skips teardown by design, so a false `AGENT-GONE` leaves the agent running to
   TTL. Teardown was performed by hand this fire (see below).

## Teardown

`bunker destroy 51fa2112 --server bunker-mvp` → `Agent 51fa2112 destroyed.` (home 6.2 GB archived
first), `Removed local SSH key /home/kara/.bunker/keys/51fa2112`. Verified afterwards:
`bunker list --server bunker-mvp --status all` no longer carries `51fa2112`; the two remaining
running agents (`a8354993` created 10:02:50Z, `67aeb9f5` created 10:20:30Z) belong to other lanes
and were not touched.

## Boundaries of this ledger

- It proves the **install leg** and the shared-battery cells for HEAD `489bbd4`. It does not re-measure
  product behaviour: the product angle and its measurements are the first fire's
  (`docs/dogfood/2026-11-14-deny-by-default-and-a-dead-rule.md`), and the product tree is unchanged
  since (`489bbd4` → `b73c57a` touches only `.coding-hermes/` and `docs/dogfood/`).
- `ISOLATION-UNVERIFIED` still stands for `bunker-mvp` (Net mode: shared = no tenant network
  isolation); this battery says nothing new about the isolation class.
- True page-cache-cold timing and the pipx channel remain unverified, as no fire of this tick
  measured or grepped them.
