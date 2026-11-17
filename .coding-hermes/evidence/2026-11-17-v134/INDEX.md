# Evidence — dogfood tick `terminal-jail-dogfood-2026-11-17-11-52-37`

HEAD under test: `9aff5bd` (= `origin/main`), product version **1.3.4** via the documented source
channel. Every script in this directory is the exact script that produced the adjacent output; the
report that cites them is `docs/dogfood/2026-11-17-v134-claims-and-egress.md` and the trail is
`docs/dogfood/diagnostics.md` §25.

| file | what it does | result |
|---|---|---|
| `install-arm.sh` | `./install.sh --no-path` into a fresh HOME (documented source channel) | rc=0, 0.68 s, `terminal-jail 1.3.4` |
| `badtype-arm.sh` | unknown `match.type` vs a `pattern` control (arm 1 of the report) | warning + fail-safe allow; control rc=126 |
| `arm2.sh` | non-allow-listed control (`hostname`) through the same rule, bundled-vs-standalone md5 parity | block rc=126; md5s identical |
| `pack-arm.sh` | external rule pack author → install → enforce → uninstall → refusal | rc=0 / rc=126 / rc=0 / rc=2 with nothing written |
| `net-arm.sh` | first egress attempt, HOME under a 0700 parent | **rig failure** — payload died at exec (see report arm 2) |
| `net-arm-pub.sh` | egress A/B from a world-traversable `/tmp` HOME | 4444 errno=13 with tier on, 443 CONNECTED, deny-all blocks both |
| `off.out` `off.err` `on.out` `on.err` `deny.out` `deny.err` | raw stdout/stderr of the three egress arms | the numbers quoted in the report |
| `connect_probe.py` | the two-connect probe used by both net arms | — |
| `fidelity-arm.sh` `signal-arm.sh` `signal-arm2.sh` `signal-arm3.sh` | script-facing fidelity; arms 1-3 of the signal measurement are **wrong** and kept deliberately (diagnostics §25.1) | final design: rc=130/rc=143, 0 survivors |
| `fs-and-perf.sh` | fs-tier warning reproduction + hyperfine timings | numbers in the report's perf table |
| `action-arm.sh` | unknown `action` claim + pack validator on unknown `match.type` | fail-safe allow with reason; validator exit 2 |
| `unzip-arm.sh` | local RED-proof of the fresh-machine test premise (`PATH` without `unzip`) | `1 passed` → `1 failed` (TJ-DF-071) |
| `bunker-qa-evidence-20261117T120838Z-1919234.jsonl` | the launch-time snapshot of the fresh-machine ledger (16 rows) | fresh-install OK 1.3.4, tests FAIL (attributed) |

Not copied here: the agent-side per-cell log `qa-logs-4189068/tests.log` (24 KB) lives on the agent
until it is destroyed; its decisive lines are quoted verbatim in the report and in `TJ-DF-071`.
The battery was still running when this directory was committed, so later cells are not represented —
the final state is recorded in `.coding-hermes/dogfood-log.md` for this tick.

## Disclosure: one file was reformatted after the run

`connect_probe.py` was committed through the repo's pre-commit guard, whose ruff lane
refused the first attempt (`1 file(s) would be reformatted`). The file was then run through
`ruff format` — a mechanical, semantics-preserving change (it only re-wrapped the `TARGETS`
literal). The probe's behaviour and every number quoted in the report come from the
pre-format bytes; the reformat cannot change which ports were attempted or which errno was
reported. No other file in this directory was touched by the formatter.
