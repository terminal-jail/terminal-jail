# Dogfood re-fire diagnostics: 2026-11-26

Tick: terminal-jail-dogfood-2026-11-26-19-20-23. Local and live remote HEAD at verification: e18b7354232c3831c16c3f15c5487ac3c7347909. The existing uncommitted quickstart report and log entry for this tick predate this delivery; they are not attributed to this run or overwritten.

Existing quickstart report records successful echo and shell task on an immutable archive, first invocation 0.23 s and repeats 0.21, 0.22 and 0.19 s. True cold-cache timing was not measured. This delivery did not independently repeat those use or timing probes; these are previously recorded observations, not new measurements. The report is docs/dogfood/2026-11-26-192023-quickstart.md and is uncommitted.

## Fresh-machine installation: UNVERIFIED

A clean local clone of the tested commit was submitted to `bunker-qa.sh launch` with `--server bunker-las-03 --ttl 4h` and evidence path `/home/kara/.hermes/qa/terminal-jail-dogfood-20261126-192023-refire/evidence.jsonl`. Despite the flag, the launcher announced and used bunker-mvp. Agent 73b250f6 spawned. Before an install command ran, repository sync failed with `/home/kara/.hermes/scripts/bunker-qa.sh: line 979: /usr/bin/timeout: Argument list too long`. The launcher reported TEARDOWN-GONE; a fresh `bunker list --server bunker-mvp --status all` showed no matching agent. The raw evidence has target-binding OK and run_battery FAIL; this is an install-unverified harness failure, not a failed product install. The prior delivery's agent 5225eba4 encountered the same sync failure.

No board rows were filed: the lane explicitly prohibits modifying board state. An install follow-up and the launcher's server-selection behavior remain unfiled; the latter is based on this invocation and should be checked against supported launch configuration before attributing a defect. DuckBrain recall failed when the MCP subprocess disconnected; no memory write was attempted. No code, permissions, credentials or visibility were changed.
