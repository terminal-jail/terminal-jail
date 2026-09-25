# Terminal Jail — Dogfood 2026-09-25: Deploy Shim + systemd Probe

Run 10. Angle (untouched by runs 1-9): the deploy shim
`standalone/terminal-jail-sh` — the component the gateway deploy doc actually
installs as the shell replacement — plus the documented
`scripts/systemd-directive-probe.py` verification step (deploy doc Step 4).

## Promise under test

docs/deploy-to-karahermes.md claims a fresh user can (1) install the shim,
(2) verify it with three commands (hello / blocked rc=126 / PID 1 in jail),
and (3) run the directive probe to decide which systemd hardening this host
enforces before touching any unit file.

## What I did as a user

- Executed Step 3's three verify commands verbatim on the dev host
  (Ubuntu 26.04, kernel 7.0.0-31).
- Probed the shim's real belt: `setpriv --no-new-privs` -> CLI
  `--user --seccomp --no-interruptor` -> bwrap (auto backend). Verified live
  inside the jail: `NoNewPrivs: 1`, `Seccomp: 2 (filters: 1)`, full
  CapabilityBoundingSet emptied (capsh IAB all-`!`), mount denied.
- Fired the firewall through the shim: `rm -rf /` (payload via file, never on
  a command line) -> `terminal-jail: command blocked (builtin-rm-rf-root)`,
  rc=126. Confirmed the documented scope limit: a script's BODY runs
  (`payload1.sh` printed its own echo — top-level command string is the
  firewall's only scope).
- Drove the documented gateway invocation form:
  `terminal-jail-sh -lic 'set +m; <cmd>'` -> command ran through
  firewall + jail + seccomp. SHLVL=2 inside the jail as expected.
- Ran the probe in both scopes: user scope 13 directives (7 ENFORCED /
  5 NOT_ENFORCED / 1 UNSUPPORTED negative control); system scope (sudo -n)
  12/12 ENFORCED + control UNSUPPORTED. The user-scope NOT_ENFORCED set
  matches the deploy doc's predicted list exactly.
- Fresh-machine leg (ephemeral bunker-las-03 agent, bare Debian 13.7 /
  kernel 6.12): bunker-qa battery + hand reproduction of the one failing
  test, 3x, plus the bwrap-backend control, then destroyed the agent
  (9138d339).

## Results by the skill's four questions

1. Does it work? YES on the dev host: all three Step 3 verifications behave
   as documented (one docs expectation bug, TJ-DF-030), firewall blocks with
   rule provenance, the full belt (NoNewPrivs+seccomp+caps-dropped) is
   observably present, the probe's verdicts match the doc's predictions.
   NO on fresh Debian 13: the unshare backend's orphan-teardown contract
   fails deterministically (TJ-DF-027) — the headline containment guarantee
   is kernel-dependent.
2. Is it useful? Yes — the probe genuinely prevents "copy the drop-in and
   hope"; the shim gives one command that composes firewall + namespace +
   seccomp correctly.
3. Is it usable? Time-to-first-success ~5 min from the doc (clone + install
   shim + three verify commands). Friction count this run: 3 (PID=1
   expectation, las-02 stuck activating, --server flag no-op).
4. Is it trustworthy? Mostly: fail-open bridge fallback in the shim is
   documented in the source; the empty-cmd unwrapped path is not
   (TJ-DF-031); the upgrade/release story is unresolved (TJ-DF-032).

## Performance (Step 2b)

- Warm: `hyperfine --warmup 3 --runs 20 'terminal-jail-sh -c "echo hello"'`
  = 208.8 ms ± 7.7 ms (user 114 ms / sys 62 ms — python-startup dominated).
- Cold (drop_caches): 293 ms.
- Verdict: no PERF row — not user-noticeable for a one-shot shell command,
  consistent with run 8's 131-185 ms numbers.

## Install leg

bunker-qa.sh battery on bunker-las-03 (fresh Debian 13.7, kernel 6.12.107):
- fresh-install OK — "Successfully installed PyYAML-6.0.3 terminal-jail-1.2.0"
- ci-pass FAIL — test_live_unshare_orphan_teardown (TJ-DF-027/028)
- chaos-resource FAIL — same test under 3GB cap (not a memory artifact)
- upgrade FAIL — terminal-jail==1.0.0 not on PyPI (TJ-DF-032)
- chaos-disconnect INFO (no network dep), docker/ui/chaos-shutdown N/A

First spawn attempt failed because bunker-qa.sh ignored `--server
bunker-las-03` on `run` (arg parse bug — line 3031 reads `$3` for the env
form; only `BUNKER_QA_SERVER` works). las-02's bunkerd was also stuck
"activating" with no listener — infra issue, not terminal-jail's.

## Findings filed (board rows)

- TJ-DF-027 P1 unshare orphan-teardown fails on Debian 13/6.12; bwrap OK;
  dev-host kernel OK.
- TJ-DF-028 P2 fresh-machine CI reality vs dev-host-only green evidence.
- TJ-DF-029 P2 probe RestrictNamespaces judge lacks host-baseline control.
- TJ-DF-030 P3 deploy doc Step 3 "PID = 1" wrong for bwrap/auto backend.
- TJ-DF-031 P3 shim empty-cmd banner path execs unwrapped bash, silently.
- TJ-DF-032 P3 version 1.2.0 identity has no release channel behind it.
