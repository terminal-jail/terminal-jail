# Terminal-jail dogfood 2026-09-23 — the plugin + seccomp + fresh-install angle

Run 8 in `dogfood-log.md`. Angle (per the skill's re-run rule — change the surface, not the
depth): every prior run (08-10 → 09-19 evening) exercised the **standalone CLI wrapper**, the
**interruptor rule engine**, and the **install leg**. This run took the surfaces those runs did
NOT touch: the **Hermes plugin as it actually deploys and fires in a live Hermes process**, the
**seccomp filter's real enforcement** (not just its installation), and a fresh-machine
install whose smoke actually probes the filter.

## Promise statement (null hypothesis)

"A Hermes operator can contain, observe, and firewall terminal commands via: (a) the Hermes
plugin (installed + enabled, hooks firing), (b) the interruptor firewall, (c) the seccomp
filter via `--user --seccomp`, (d) the systemd drop-in."

## What was done for real (not the test suite)

1. **Live gateway, real process.** `~/.hermes/plugins/terminal-jail/` is enabled in this
   fleet's live Hermes gateway. Its `pre_tool_call` hook fired on EVERY terminal command of
   this session (agent.log: `observed terminal command (N bytes); pre-execution wrapping is
   unavailable` — dozens of entries, 2026-09-23 06:32). Its spin veto was exercised for real:
   a `while :; do :; done` probe command was **blocked pre-execution** by the deployed
   plugin's spin_policy with the loadavg-220 doctrine message. The plugin is not dead code —
   it is actively guarding this very session.
2. **Interruptor as a firewall consumer** (bridge JSON, real decisions): ls→allow(rule
   allow-ls), `rm -rf /`→block(builtin-rm-rf-root), curl file-upload→block, curl -F→block,
   interpreter socket exfil→block, plain `cat /etc/shadow`→allow(rule_id=null =
   default-allow, documented). Evasion reparse: 11/12 nested-payload probes blocked
   (subshell/backtick/heredoc/base64-pipe/xargs/env/find -exec/awk system/nested-jail/sudo);
   `ssh evil 'cat /etc/shadow'` allow rides the known DF-29/30 remote-host class (reconfirmed
   live, not re-filed).
3. **Seccomp, proven numerically.** `--user --seccomp` → `Seccomp: 2, Seccomp_filters: 1` in
   /proc/self/status inside the jail. In-process probe: 10/11 deny-NR syscalls return EPERM
   under the filter (pivot_root, mount, acct, settimeofday, swapon, swapoff, create_module,
   kexec_load, add_key, keyctl, clock_settime). BPF program byte-verified (23 instructions,
   deny-block jump layout correct). The one miss — libc `adjtimex()` succeeds — is a REAL
   finding: glibc routes it to clock_adjtime(305), which the deny list does not cover
   (TJ-DF-020). The earlier "filter not applied" scare was re-measured and retracted: the
   first probe omitted `--seccomp`.
4. **Perf (Step 2b).** `hyperfine --warmup 3 --runs 20`: jail wrap
   `./standalone/terminal-jail echo` **185.5ms ± 10.4** warm / 215.5ms ± 4.6 cold;
   `--user` adds ~20ms (204.3ms ± 10.7); bridge verdict **27.7ms ± 2.1** (≈22ms of that is
   bare python startup — the engine itself is ~6ms). Nothing here is slow enough that a user
   would notice; per the skill no PERF row is filed (a win nobody can feel is not a finding).
5. **Fresh-machine install leg (ephemeral bunker-las-03, agent 3c18196b, destroyed after):**
   documented `git clone https://github.com/...` (public origin) **5s**, `./install.sh`
   **<1s** (PATH + rules + plugin bridge tree + seccomp loader all installed cleanly), bare
   `terminal-jail echo` **smoke PASS in 0s**, firewall live on the fresh box, bare
   `--seccomp` PASS (Seccomp: 2/1, mount denied mount-rc=32). **FAIL:** the quickstart §3c
   form `--user --seccomp` → `Permission denied` opening seccomp-loader.py → **TJ-DF-019**
   (root-caused: 0700 home × mapped-launch subordinate uid 231072 DAC traversal).
   `fs-isolation-probe.py` on the agent: FULL (correct — the mapping exists; the doc gap is
   that FULL ≠ "the loader path is traversable by the mapped payload").

## Verdict: PROMISING-BUT-ROUGH

- **Does it work?** Yes, for every surface exercised: live plugin guard (real block),
  firewall decisions with provenance, PID namespace real (5 procs inside vs 1001 host),
  seccomp filter denies 10/11 deny-NRs, fresh install works end-to-end in <1s install.
- **Is it useful?** Yes — it blocked a real busy-wait probe in the live fleet session this
  run ran in, which is the product working exactly as designed (the 09-18 loadavg-220
  doctrine, enforced by the deployed plugin).
- **Usable?** Time-to-first-success ~5min (clone+install+smoke). Friction count 3: the §3d
  HERMES_PLUGINS docs path does not exist in current Hermes core (TJ-DF-021); the §3c
  `--user --seccomp` form fails on 0700-home hosts (TJ-DF-019); the §3c verify example
  (echo payload) cannot detect a silently-skipped filter (TJ-DF-023).
- **Trustworthy?** Fail-closed paths verified (unknown backend → exit 2 command-not-run;
  bwrap-requested-but-missing → exit 2). One new trust gap: the deny list misses glibc-routed
  variant syscalls (TJ-DF-020) — the filter is real but its coverage claim (threat-model §9.2)
  is narrower than the wrapper-level syscall surface glibc actually uses.

## Findings filed (board, this run)

- **TJ-DF-019 [P1]** fresh-machine `--user --seccomp` fails on 0700-home hosts (install leg)
- **TJ-DF-020 [P2]** seccomp deny list misses clock_adjtime(305) variant (adjtimex EPERM miss)
- **TJ-DF-021 [P2]** quickstart §3d HERMES_PLUGINS env-var loading does not exist in current core
- **TJ-DF-022 [P2]** deployed plugin (v0.2.0) ≠ repo plugin (v1.2.0); no update path documented
- **TJ-DF-023 [P3]** §3c verify example cannot prove the filter; fails-open behavior undocumented

Prior findings re-verified live and NOT re-filed: DF-29/30 (ssh/scp exfil allow — unchanged),
DF-15 family (uid-mapped DAC tradeoff — now visible as TJ-DF-019's mechanism), default-allow
provenance (rule_id null semantics documented, working as documented).

## Honest limitations

- The systemd drop-in and deploy-shim surfaces were NOT exercised this run (host has no
  hermes-gateway.service eligible for the drop-in test without touching the live gateway;
  the deploy shim path was covered by the 09-17/09-18 runs).
- request_key probe returned ENOKEY(126) not EPERM — harness artifact (keyring state), not
  evidence about the filter; raw keyctl(250) denied EPERM in the same process.
- The `grep Seccomp /proc/self/status` proof must be run INSIDE the jail; a naive
  `terminal-jail --user sh -c 'grep Seccomp ...'` (no --seccomp) correctly shows 0 — the
  filter is opt-in per invocation, which is documented but easy to misread (folded into
  TJ-DF-023).