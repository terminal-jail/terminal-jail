# Dogfood run 15 — Landlock filesystem + TCP-egress tiers (TJ-GAP-082/083), 2026-10-13

**Angle:** the Landlock fs tier (default-on) and the opt-in Landlock TCP-egress tier
(`TERMINAL_JAIL_LANDLOCK_NET=1`), both shipped 2026-10-07 (376dab2) for the unreleased
1.3.0. No prior dogfood run (1-14) touched either tier. First drive of both surfaces.

**Promise tested:** "with the fs tier active the payload gains a kernel-enforced
filesystem deny layer (workdir/tmp writable, toolchain+home read grants, credential
surfaces carved out); with `TERMINAL_JAIL_LANDLOCK_NET=1` every `connect(2)` to a TCP
port outside the allowlist fails at the kernel, in the payload and every descendant,
through the auto-sandbox/modify wrap."

## What held up (repo-checkout wrapper, dev host kernel 7.0.0-31)

- fs tier default-on: HOME-root writes denied (probe file at `~/probe-tj-write` →
  Permission denied), `~/.duckbrain/kara.token` read denied, workdir + /tmp writes OK.
- Stacked modify verdict is real: bridge verdict for `python3 <probe>` is
  `modify auto-script` → `unshare … bash -c 'landlock-loader -- landlock-net-loader --
  <cmd>'`; executed as the wrapper would run it, the payload's connect to a live
  non-allowlisted listener (127.0.0.1:9151) returns **EPERM** with the
  `kernel egress tier APPLIED` banner. Allowed port (443/pypi.org) connects fine.
- Fail-closed preflight: invalid allowlist token refuses the tier (named cause),
  ABI<4 hosts refuse with a named cause (verified by code-walk + docs cells).

## What broke (findings TJ-DF-044/045)

1. **TJ-DF-044 (P1): the tier is silently inert through the INSTALLED CLI.** Fresh
   clone + `./install.sh`, then `TERMINAL_JAIL_LANDLOCK_NET=1 ~/.local/bin/terminal-jail
   python3 <connect probe>` → **CONNECT-OK** (zero containment), while the
   repo-checkout wrapper on the same box enforces (EPERM). Two causes:
   install.sh copies seccomp + fs loaders but never `standalone/landlock-net-loader.py`
   (install.sh:1219-1227), so the bridge degrades with
   "landlock-net-loader.py not found next to the plugin"; AND the wrapper discards the
   bridge's stderr (`standalone/terminal-jail:271 … 2>/dev/null`), so the loud degrade
   warning never reaches the user. The operator who enabled the documented opt-in
   gets neither enforcement nor a signal.
2. **TJ-DF-045 (P2): the fs tier denies reads the grant implies.** Jailed
   `cat /etc/hostname` → Permission denied (unjailed works; /etc is in the documented
   read list in landlock.py), `head -1 ~/.hermes/config.yaml` denied. Real agent
   tooling that reads hostname/OS config breaks under the default jail.

## Perf (Step 2b)

Wrapped `true` through the CLI: ~354ms/run warm (5 runs, installed CLI, bwrap backend);
checkout wrapper with both Landlock tiers + fs-loader stack: ~424ms/run (5 runs).
Delta ≈ +70ms for both tiers — not user-noticeable, no PERF row.

## Install leg (fresh bunker agent)

Fresh Ubuntu 24.04 agent (df-tj-1013 on bunker-mvp, destroyed after): clone-equivalent
tar + `./install.sh` = **1s**, `--version` reports 1.2.0, tier report honestly prints
DEGRADED (Ubuntu AppArmor unprivileged_userns — expected, documented). Smoke:
`--user` launch runs and writes (W-SMOKE-OK); full pidns launch correctly refuses with
named cause + options; composed-mode banner honest. The net tier could not be
smoked on the fresh box (container denies unshare for the bare launch) — consistent
with the dev-host evidence above.

**Verdict: PROMISING-BUT-ROUGH** — kernel-layer design is sound and the stacked
launch shape works, but the shipped install path breaks the headline opt-in tier
silently, and the default fs tier over-denies reads.
