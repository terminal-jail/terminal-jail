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

## TJ-DF-072 — the fs-tier reporting contract, red and green

`scripts/probe9_tjdf072_canary.sh` is the fork's own rig for the fix (rig D
shape: throwaway `HOME=/home/kara/tj-df-072/home`, OUTSIDE the tmp grants,
`PATH=/usr/local/bin:/usr/bin:/bin`, every `TERMINAL_JAIL_*` unset per arm). It
re-installs from the tree it is pointed at (`REPO=…`) and runs four arms:

- `e1-tiered` — the production tiered launch (`terminal-jail make canary`):
  the canary read must be DENIED **and** the launch must state the fs tier is
  enforced.
- `e2-tier-off` — the identical launch with `TERMINAL_JAIL_LANDLOCK=0`, one
  variable: the canary must be READABLE (AC2's negative-arm control).
- `n1-no-ancestor` — the loader nested in `unshare --user --pid --fork` with
  **no** ancestor domain and `XDG_RUNTIME_DIR` unset (the genuine degraded
  shape): the not-applied warning MUST still print and the canary IS readable.
- `n1b-no-ancestor-xdg` — the same namespace WITH a writable probe host
  (`XDG_RUNTIME_DIR=/run/user/1000`): the attach PROVES, enforces silently, and
  the canary is denied. This arm is the mechanism control — it shows the
  namespace uid is NOT what breaks the production probe, so the board row's
  "the mapped/overflow uid cannot write the probe file" hypothesis is wrong for
  this host (the AppArmor policy denies uid mappings outright, so no mapping
  happens at all and the payload keeps kuid 1000). What breaks the probe is the
  INHERITED DOMAIN denying the probe host.
- `n2-inherited` — the production nesting without the CLI: an outer loader that
  PROVES the tier, the namespace, then a re-attaching loader that cannot
  re-prove it: the canary must be DENIED and the line must report enforcement.

Raw arms are `arms/tjdf072-{prefix,post}-<arm>.{out,err,rc}` — `prefix` = the
tree at `ec6e85a` before the fix (the RED evidence: e1 and n2 print
`WARNING: … commands run unchanged without kernel filesystem enforcement` next
to a `Permission denied` canary), `post` = the patched tree (both print
`kernel filesystem tier APPLIED — inherited from the launch's outer attach …`,
the canary still denied, and `n1` unchanged: warning + readable). Run logs:
`arms/tjdf072-{prefix,post}-run.log`.

Mechanism note worth keeping: on this host class the inner attach's probe fails
*chemically* because the inherited domain denies the probe host — `/run/user/1000`
is unwritable under the domain, `HOME` and the tmpdirs are granted, so
`apply_tier(..., dry_probe=True)` finds "no caller-writable ungranted path".
That is simultaneously the proof of containment and the reason the old sentence
lied. `n1` (no ancestor, no `XDG_RUNTIME_DIR`) reproduces the same cause string
with NO enforcement behind it — which is why the fix keys on an explicit,
post-proof marker (`TERMINAL_JAIL_LANDLOCK_INHERITED`) plus the kernel's
`NoNewPrivs` flag instead of guessing from the cause text.

## Transformations

None: every file here is a byte copy of its run artifacts (the original
/tmp/tj-df-1120 run for arms `<x>`, and the TJ-DF-072 rig's own
`/home/kara/tj-df-072/{prefix,post}-arms` for the `tjdf072-*` files). The
session environment dump that one rig script accidentally printed to the terminal
(`env` without a command) was NEVER written to any of these files and is not
reproduced here.

## What is NOT here

- The bunker battery ledger for this tick: the bunker-mvp launch was refused at
  admission (disk 95% > 94% threshold, 1-row ledger at
  `~/.hermes/qa/terminal-jail-dogfood-20261120-evidence.jsonl`); the bunker-las-03
  battery is filed beside the run report when collected.
- Page-cache-cold timings (need root; unverified as in every prior fire).
