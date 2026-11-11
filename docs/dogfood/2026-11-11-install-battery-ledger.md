# 2026-11-11 install battery — final per-cell ledger

Tick: `terminal-jail-dogfood-2026-11-11-05-38-47` (duplicate fire 2, records-only)
Target HEAD: `cc13fa0` (= `origin/main`, `git rev-list --left-right --count HEAD...origin/main` = `0 0`)
Host: `bunker-mvp`, agent `d6035ac5` (spawned 2026-11-11T05:48:55Z by the first fire of this tick)

## Why this file exists

The first fire of this tick committed a **provisional** install summary: the tests cell was
recorded as FAIL with its captured detail truncated at 1517 B, and the run was closed with the
note *"bunker agent d6035ac5 left to its TTL because collect reported the battery still running"*.
The battery has since reached a terminal state — `qa-run.finished` marker plus `CELLS-DONE` in
`qa-run.log`, both at 2026-11-11T06:14Z — so the provisional summary is superseded here with the
values the harness actually wrote.

## Provenance of these numbers

Read on the agent through `bunker exec d6035ac5 --server bunker-mvp` (shell output, then
`python3` over `/home/bunker-d6035ac5/qa-evidence.jsonl`, 24 records) at ~06:14–06:20Z.

The full JSONL was **not** copied into this repo: `bunker pull` / `scp` against the spawn key is
refused by the unattended tool-consent gate (no answer = no consent), and the teardown was not
attempted after that stop. So this file records exactly what was read, not a re-rendered copy.
Cell details longer than the read window (notably `tests`) are quoted as far as they were printed.

## Cell census — 24 cells

| # | cell | status | detail as written by the harness |
|---|------|--------|----------------------------------|
| 1 | toolchain-bootstrap | OK | go 1.27.4 installed (`~/tools/go`; floor=none ambient=1.22.2) |
| 2 | toolchain-bootstrap | OK | python venv ready + pytest (`~/tools/venv`) |
| 3 | toolchain-bootstrap | OK | system gcc/g++ wrappers (`~/tools/bin`) |
| 4 | toolchain-bootstrap | OK | make available, GNU Make 4.3 |
| 5 | toolchain-bootstrap | OK | jq 1.8.2 (static) |
| 6 | **fresh-install** | **OK** | `Successfully installed PyYAML-6.0.3 terminal-jail-1.3.3` — installability on a fresh box proven |
| 7 | lint | N/A | no supported lint trigger |
| 8 | **tests** | **FAIL** | `rc=1`; exactly one failure after ~24% of the suite: `plugin/test_install.py::test_successful_install` — `AssertionError` |
| 9 | docker_build | N/A | no Dockerfile trigger |
| 10 | compose_config | N/A | no compose file trigger |
| 11 | toolchain-bootstrap | OK | compose plugin installed |
| 12 | toolchain-bootstrap | OK | buildx v0.38.2 |
| 13 | toolchain-bootstrap | OK | node v22.15.0 + npm 10.9.2 |
| 14 | toolchain-bootstrap | OK | HARNESS-COMPOSE=ok |
| 15 | toolchain-bootstrap | OK | HARNESS_NODE=ok |
| 16 | **ci-pass** | **FAIL** | native `rc=1`: same `test_successful_install`; act leg `act_result=fail rc=1` on `CI/Drift guards (rule catalog + mirror parity + probes)` |
| 17 | **upgrade** | **FAIL** | `pip install terminal-jail==1.3.2` → `Could not find a version that satisfies the requirement ... (from versions: none)` |
| 18 | docker-deploy | N/A | no compose file |
| 19 | ui-probe | N/A | no web UI detected |
| 20 | chaos-disconnect | UNVERIFIED | disconnect log lacks `NETWORK_CUT_APPLIED`; cascade of the same `test_install` failure |
| 21 | chaos-shutdown | N/A | no compose file |
| 22 | chaos-corruption | N/A | no pre-existing db/state files |
| 23 | **chaos-resource** | **FAIL** | `rc=1` under cap 3145728KB; same `test_install` failure |
| 24 | chaos-errorpath | OK | clean `rc=2` on missing config |

Totals: **12 OK, 7 N/A, 4 FAIL, 1 UNVERIFIED** (24).

## Dispositions — nothing here is a new defect

- **tests / ci-pass / chaos-resource / chaos-disconnect** are one root test
  (`plugin/test_install.py::test_successful_install`), already carried by **QA-TERMINAL-JAIL-32**
  (pending, P3): `install.sh`'s wheel path hard-requires `unzip`, while the test builds a sandbox
  PATH without one.
  Corroboration now available that the first fire could not see: the failing test runs
  `install.sh` with `HOME=tmp_path` and a `_setup_full_testbin` PATH, and cell 6 installed the very
  same tree successfully on the real PATH. Sandbox-PATH-specific failure, not a broken installer —
  consistent with the existing row's premise (not claimed as proven root cause here).
- **upgrade** is a channel mismatch, previously filed three times over:
  **QA-TERMINAL-JAIL-11** (pending, P3), **QA-TERMINAL-JAIL-19-R2** (pending, P2),
  **TJ-DF-032** (complete). No new row earned.
- **fresh-install OK** is the one result the provisional summary already had right.

## Residual state

- Agent `d6035ac5` was still `running` at the end of this fire (battery terminal, `ps` shows no
  battery processes; `qa-run.finished` present). It was **not** destroyed: the durable-copy leg was
  refused by the unattended consent gate, and teardown was not attempted after that stop. It
  remains for TTL reaping or for the next lane that can teardown with consent.
- `bunker-mvp` census at 06:20Z: ONLINE, uptime 5d 2h 55m, 5/50 agents, `/tmp private`,
  `Net mode: shared` (no tenant network isolation), residue 20 orphan keys behind 22 registered
  agents.
