# Battery ledger — dogfood 2026-11-20 install leg (terminal)

Agent f884d320 @ bunker-las-03, ttl from launch 2026-11-20T15:33:47Z; tested HEAD
`e67e07e3d34863fa26856e8b81575b288ae44979` (repo-head row binds the sha; the clone
was dirty with the active foreman wave's files so the launcher skipped pull and
tested the recorded sha — the sha IS the published product tree). Ledger committed
beside this file: `tj-battery-f884d320.jsonl` (28 rows, sha256 prefix
8f513f2d40140066) + its `.meta`.

## Terminal shape (28 rows, 18 distinct cells)

| verdict | cells |
|---|---|
| OK | launch, repo-head ×2, toolchain-bootstrap ×10, **fresh-install**, chaos-errorpath, chaos-disconnect, collect |
| N/A | lint, docker_build, compose_config, ui-probe, chaos-corruption |
| SKIPPED | docker-deploy, chaos-shutdown (safety gate: controller is the live Hermes host) |
| FAIL | tests, ci-pass, chaos-resource, upgrade |

**fresh-install OK** — `Successfully installed PyYAML-6.0.3 terminal-jail-1.3.4`
into a machine that had never seen the project: 1.3.4 installability re-proven on
the documented channel.

**All four FAILs collapse to two named causes:**

1. `tests` / `ci-pass` / `chaos-resource` — ONE test:
   `tests/test_composed_mode.py:474 test_unreachable_daemon_environment_skips_live_battery`
   (suite 1 failed / 2041 passed / 16 skipped in 132.39s; `pytest -x` stops at the
   first failure, so ci-pass's act 3.12-2 job red is the same premise). The probe
   `_docker_available()` returned None — i.e. `docker info` SUCCEEDED — under
   `DOCKER_HOST=unix:///tmp/nonexistent-docker.sock` on the agent's harness-provisioned
   rootless docker (buildx v0.39.1). Dev-host control: the same test passes
   (0.63s) and raw `docker info` with the bogus socket exits 1. Filed as
   **TJ-DF-074**. chaos-resource failing the SAME test under the 3 GB cap proves the
   red is not cap-induced.
2. `upgrade` — `pip install terminal-jail==1.3.3` finds no version (release channel
   mismatch): the standing class owned by **QA-TERMINAL-JAIL-11**, cited not filed.

**TJ-DF-071 (unzip host premise) is CONFIRMED FIXED on a fresh box**: the suite ran
to 96% with 2041 passed — the premise that stopped every 2026-11-17-era fresh
battery at 3% no longer exists.

chaos-disconnect graded OK this run (the QA-TERMINAL-JAIL-27-R2 grader-regex class
did not fire). Collection: `COLLECTED agent=f884d320 rows=25` on the first collect
(BUNKER_QA_EVIDENCE exported); teardown proven — the agent is absent from
`bunker list --server bunker-las-03 --status all` and its key file is gone.

The first launch attempt (bunker-mvp) was refused at admission — disk 95% > 94%
threshold, no spawn; its 1-row ledger is
`~/.hermes/qa/terminal-jail-dogfood-20261120-evidence.jsonl`.
