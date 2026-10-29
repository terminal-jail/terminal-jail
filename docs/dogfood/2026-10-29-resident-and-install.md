# Terminal Jail dogfood — 2026-10-29

Tick: `terminal-jail-dogfood-2026-10-29-10-09-24`
HEAD: `fd2638563a65dfb2932b7e111eda1d49a18b9eb8`

## Promise

A fresh user can install Terminal Jail from the documented GitHub source, classify host capabilities, run the standalone CLI and firewall, and optionally use the resident bridge for repeated verdicts.

## Real-use result

The local scratch-HOME install followed the documented command shape:

`CI=true TERMINAL_JAIL_INSTALL_DIR=<scratch>/prefix/bin TERMINAL_JAIL_RULES_DIR=<scratch>/rules ./install.sh --no-path`

It returned rc=0 in 483 ms and installed `terminal-jail 1.3.0`. The installed bridge produced an allow verdict for `echo hello`, a block verdict for `rm -rf /` with `builtin-rm-rf-root`, an enforce-mode `[bridge-error]` block for a missing `command` key, and a warn-mode allow-with-warning for the same malformed input. The installed CLI ran with `--user`, scrubbed `USER`/`HOME`, and reported `proc_view=private` through the bubblewrap backend.

The resident bridge worked with an explicit short socket: it created a 0600 socket, served client verdicts, handled ten concurrent clients with rc=0, and removed the socket after SIGTERM to the Python daemon. With a deeply nested HOME/XDG runtime path, the default socket failed with rc=1 and `[resident-bridge] bind failed: AF_UNIX path too long`. This is a real runtime usability gap. QA-TERMINAL-JAIL-22 covers related deep-path test brittleness, but does not cover the shipped daemon's default socket path. This read-only lane did not mint a board id.

## Performance

Measured command: `python3 plugin/terminal_jail/interruptor_bridge.py` with `{"command":"echo hello"}` on stdin, and the resident client with `--command 'echo hello'`; `TERMINAL_JAIL_VERDICT_LOG=0`; ten warm samples per arm.

One-shot: cold 85.43 ms, warm median 88.34 ms.
Resident: cold 49.62 ms, warm median 34.32 ms.

Both paths were rc=0. The resident path is materially faster, but neither cost is user-noticeable at the documented low-cadence use, so no PERF row was filed.

## Fresh-machine install leg

`bunker-qa.sh launch` was run literally with `HOME=/home/kara`, `BUNKER_QA_SERVER=bunker-mvp`, and evidence at `/tmp/df-terminal-jail-2026-10-29-10-09-24/bunker-evidence.jsonl`. The owned agent was `f02af844` on `bunker-mvp` and tested the exact HEAD. Launch returned rc=0. Agent evidence showed repo-head OK, toolchain bootstrap OK, and fresh-install OK: build-only install rc=0 with PyYAML 6.0.3 and terminal-jail 1.3.0.

The detached battery was still running in its ci-pass arm when collect was attempted. Collect correctly returned RUNNING and kept the agent, so the battery was not reported as PASS. Destroy initially refused because nine agent-owned processes remained. After terminating those agent-owned runner processes, destroy succeeded; a later `bunker info` returned `not_found`, and the server list contained only the pre-existing `crier-lab` agent. The install leg is therefore PARTIAL/UNPROVEN for full battery completion, not a silent pass and not SKIPPED-install-bunker.

## Findings and residue

No board rows were filed: this scheduler lane is read-only and did not mint task IDs or mutate tasks/events. The resident deep-default-socket observation is row-ready for the owning foreman, with the exact reproduction and stderr above.

No target source, board, scheduler, or existing artifact was changed. Existing unrelated working-tree dirt was preserved: `.gitreins/tasks.yaml`, `.gitreins/usage.jsonl`, `.vfs/graph/edges.jsonl`, and `.coding-hermes/waves/terminal-jail-foreman-2026-10-28-08-31-35.json`. Scratch daemon state and the run-owned bunker agent were cleaned up. DuckBrain was recorded at `/dogfood/2026-10-29/terminal-jail` in namespace `terminal-jail` and read back successfully.
