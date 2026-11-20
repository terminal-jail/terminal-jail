# Evidence — dogfood 2026-11-20, tick terminal-jail-dogfood-2026-11-20-15-00-01

Provenance: product HEAD `e67e07e` (== origin/main at fire start), v1.3.4, dev host
kernel 7.0.0-43-generic, 16 cores, loadavg 28-44 during measurement. Two fresh
`./install.sh --no-path` installs: `home-a` = /tmp/tj-df-1120/home-a (rig-arm A),
`home-b` = /home/kara/tj-df-1120/home-b (rig-arm B, OUTSIDE the tmp grants — the
only valid host for credential-surface arms; see diagnostics 26.2). All commands ran
with a clean `PATH=/usr/local/bin:/usr/bin:/bin` unless the arm name says otherwise,
and with every `TERMINAL_JAIL_*` var explicitly unset except the arm's own.

## What is here

- `scripts/probe0_rig.sh` … `probe8b_perf.sh` — the exact generators of every number
  in docs/dogfood/2026-11-20-interpreter-contract.md. `probe7_outside_tmp.sh` is the
  valid rig (rig D); probes 2/3/3b/4's hostile arms ran under the INVALID /tmp rig
  and are kept because their CONTROL arms (canary e1/e2, pin a3-a6) remain valid.
- `scripts/probe5_layout.py` — the layout dump that proved the /tmp grant trap
  (`hostile-covered-by: ['/tmp']`).
- `scripts/stage_rows.py` — the boardctl create driver for TJ-DF-072/073.
- `arms/<arm>.out/.err/.rc` — raw stdout/stderr/rc per arm. Load-bearing arms:
  - `a3/a4/a5` — broken pin, firewall ON: rc=126, wrong box, fault note (TJ-DF-073).
  - `a6` — warn-mode degradation (holds).
  - `e1`/`e2` — the canary DECISIVE pair: tiered launch denies the 0600 read, tier
    off reads it; BOTH print the false warning in e1's stderr (TJ-DF-072).
  - `f1` — the flagship TJ-REVIEW-074-R2 repro on the valid rig: rc=2 named verdict.
  - `f2/f3` — the two documented remedies (rc=0).
  - `f4` — symlink-to-/usr control (runs; Landlock resolves the final inode).
  - `f5` — canary pair repeated on the second fresh install.
- `arms/perf2-*.txt` — hyperfine raw (n=20/20/10, warmup 3/3/2).
- `arms/install*.out/.err` — both fresh-install transcripts (3.60 s wall, ceiling
  report `fs tier CAN engage and net (egress) tier CAN engage (ABI 8 >= 4)`).

## Transformations

None: every file here is a byte copy of the /tmp/tj-df-1120 run artifacts. The
session environment dump that one rig script accidentally printed to the terminal
(`env` without a command) was NEVER written to any of these files and is not
reproduced here.

## What is NOT here

- The bunker battery ledger for this tick: the bunker-mvp launch was refused at
  admission (disk 95% > 94% threshold, 1-row ledger at
  `~/.hermes/qa/terminal-jail-dogfood-20261120-evidence.jsonl`); the bunker-las-03
  battery is filed beside the run report when collected.
- Page-cache-cold timings (need root; unverified as in every prior fire).
