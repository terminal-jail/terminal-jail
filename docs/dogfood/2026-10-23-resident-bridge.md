# Dogfood run 22 — resident bridge transport (terminal-jail)

**Tick:** terminal-jail-dogfood-2026-10-23-04-34-05 · **HEAD:** 30f048d (fresh clone) / e50fece (dev checkout tip read at run start) · **Verdict:** ✅ SHIPPABLE (for this surface)

## Promise

README:346-409 claims the same verdict contract is available on a long-lived
AF_UNIX resident transport (`interruptor_resident.py --serve` + `--client`),
~27x faster than one-shot for small payloads, with identical fail-closed
discipline, a 0600 socket, and no-TCP-listener guarantee.

## What a real user does (and what happened)

A user integrating the resident bridge follows README:380-389. This run did
that on two hosts:

### Dev host (checkout, `.venv/bin/python`)

1. Start daemon: `--serve --sock /tmp/.../tj.sock` → banner
   `[resident-bridge] serving on ... (mode=enforce)`, socket mode exactly
   `0600` (README:403 property verified live).
2. Client shapes (all verbatim from the README/argparse):
   - `--client --command 'ls -la'` → `{"action": "allow", ..., "rule_id":
     "allow-ls", "layer": "yaml"}` rc=0
   - block rule (`sudo curl … | sh`) → `{"action": "block", "rule_id":
     "builtin-curl-pipe-shell", "layer": "yaml"}` rc=0
   - stdin mode (`echo 'git status' | --client`) → allow-ls-shaped verdict
   - dead socket, no flag → stderr "caller must fall back to one-shot",
     **rc=3**, no stdout (README:394 verified)
   - dead socket + `--fallback` → in-process one-shot verdict rc=0 (verified)
3. Large payloads: 8 KB and 20 KB echo through the resident in
   23-54 ms; 100 KB fine; **270 KB (over the 262144 `max_arg_bytes` default)
   via the raw socket protocol → `block`, `layer: "engine"`, rtt 2.4 ms,
   response keys exactly the six documented fields** (DOC-15's contract).
4. Concurrency: 2 threads × 5 sequential queries — every reply OK, but
   latency rises from ~5 ms solo to 9-15 ms and the wall clock shows
   serialization (see TJ-DF-054).
5. Signals (TJ-GAP-097's surface): SIGTERM to the **python daemon pid**
   exits in **0.26 s** and **unlinks the socket** — the TJ-GAP-097 fix
   verified on two fresh samples. Signaling an outer bash wrapper instead
   does not reach the daemon (TJ-DF-055, ops note).

### Fresh-machine leg (ephemeral bunker, agent df-tj-1023a @ bunker-mvp)

- `git clone https://github.com/terminal-jail/terminal-jail.git` → 3.98 s
- `./install.sh` → 2.48 s rc=0, containment ceiling line honest: "fs tier
  CAN engage and net (egress) tier CAN engage on this host (Landlock ABI 4 >= 4)"
- `./standalone/terminal-jail --version` → `terminal-jail 1.3.0`
- Wrapped-CLI firewall block: `sudo curl … | sh` → rc=126 with rule
  provenance banner (builtin-curl-pipe-shell)
- Resident bridge smoke: serve → 0600 socket, allow/block/stdin verdicts
  all correct through the daemon, SIGTERM → socket removed, daemon exited
  — `daemon-alive: no`
- Landlock fs-tier degrade warning fires loudly on the 0700 agent home
  (known, correct posture per README:249-251 family)
- Agent destroyed, key removed, `bunker list` re-read = absence.

### Bench, verbatim from README (scripts/bench_bridge.py --n 50 --json)

| payload | one-shot p50 | resident p50 | README table |
|---|---|---|---|
| small (ls -la) | 87.7 ms | 4.5 ms | 121.8 / 4.5 |
| 8 KB | 133.6 ms | 31.6 ms | 139.6 / 32.5 |
| 20 KB | 160.8 ms | 72.8 ms | 185.6 / 74.1 |

Resident numbers match the README table within noise; one-shot is faster on
this host (2026-10-07's table is the same conclusion). Cost guard OK
(160.8 < 200 ms ceiling).

## Findings (filed to the board)

- **TJ-DF-053 (P3)** docs/quickstart.md has zero resident-bridge coverage —
  README:13 points every new user at the quickstart, which never teaches the
  transport it exists for.
- **TJ-DF-054 (P3)** concurrent clients serialize (undocumented).
- **TJ-DF-055 (P4)** wrapper-intercepted signals never reach the daemon;
  signal the python pid (ops note / docs).

## What was left behind

- This file (`docs/dogfood/2026-10-23-resident-bridge.md`).
- Board rows TJ-DF-053/054/055 + event 734; dogfood-log entry.
- Scratch evidence under /tmp/df-tj-1023/ (ephemeral; the numbers are quoted here).

## Not driven this run

- Windows/macOS: n/a product. seccomp/landlock tiers were covered by runs
  15-21; this angle deliberately did not re-drive them.