# Incumbent parity sweep — 2026-10-12

First execution of the recurring incumbent-parity sweep defined by board row
**PARITY-TJ-001** (the row IS the cadence: re-check terminal-jail against
bubblewrap / firejail / nsjail / Docker+gVisor / Anthropic sandbox-runtime /
OpenAI Codex **each release cut + quarterly**). Source row: `PARITY-TJ-001`.

Everything below was re-derived from primary sources on 2026-10-12, not from
memory:

- incumbent **versions were read live from the GitHub releases API**
  (`api.github.com/repos/<org>/<repo>/releases/latest`) on 2026-10-12;
- capability facts come from each project's own README / man page / official
  docs at the URLs cited per fact;
- terminal-jail cells were **measured on this host today** (Ubuntu 26.04.1,
  kernel 7.0.0-31; host toolchain: bwrap 0.11.1, util-linux unshare 2.41.3,
  Landlock ABI 8) with the exact commands quoted in the cells.

Any fact that could not be verified from a primary source is labeled
**unverified** — nothing is glossed. This page is a snapshot: facts rot, the
cadence re-runs.

---

## 1. Incumbent state (primary-source versions, 2026-10-12)

| Incumbent | Latest release (live API read 2026-10-12) | Primary sources |
|---|---|---|
| bubblewrap | v0.13.0 (2026-09-22); NEWS: setuid build support REMOVED — user namespaces are the only mode | <https://github.com/containers/bubblewrap/releases> · <https://github.com/containers/bubblewrap/blob/main/NEWS.md> · README: "bubblewrap is not a complete, ready-made sandbox with a specific security policy… the level of protection… is entirely determined by the arguments passed" |
| firejail | 0.9.80 (2026-03-14) | <https://github.com/netblue30/firejail/releases> · README: "SUID sandbox program… Linux namespaces, seccomp-bpf and Linux capabilities" · man page <https://man.archlinux.org/man/firejail.1.en> (netfilter, `--protocol=`, whitelist) |
| nsjail | 3.6 (2026-03-18) | <https://github.com/google/nsjail/releases> · README (features list: UTS/MOUNT/PID/IPC/NET/USER/CGROUPS/TIME namespaces, chroot/pivot_root, custom /proc, rlimits, Kafel seccomp-bpf, MACVLAN/pasta networking, cgroups) |
| Docker + gVisor | moby `docker-v29.9.0` (2026-10-08); gVisor `release-20261005.0` (2026-10-08) | <https://github.com/moby/moby/releases> · <https://docs.docker.com/engine/security/seccomp/> ("Docker's default seccomp profile is an allowlist…") · <https://docs.docker.com/engine/network/> (network namespace model) · <https://github.com/google/gvisor/releases> + README ("gVisor is NOT a syscall filter… not a VM… an application kernel in userspace (Go)") |
| Anthropic sandbox-runtime (srt) | v0.0.79 (2026-10-07) — beta research preview | <https://github.com/anthropics/sandbox-runtime/releases> · README: "native OS sandboxing primitives (sandbox-exec on macOS, bubblewrap on Linux) and proxy-based network filtering"; config keys `denyRead`/`allowWrite`/`denyWrite`, `allowedDomains`/`deniedDomains`; "violation monitoring" (macOS) |
| OpenAI Codex (CLI) | 0.162.1 (`rust-v0.162.1`, 2026-10-09) | <https://github.com/openai/codex/releases> · sandbox modes doc <https://developers.openai.com/codex/concepts/sandboxing.md> (`read-only` / `workspace-write` / `danger-full-access`; Linux enforcement via bwrap from PATH with a bundled helper fallback; `bwrap-userns-restrict` AppArmor profile remedy for Ubuntu 24.04/25.04) · security doc <https://developers.openai.com/codex/agent-approvals-security.md> (network OFF by default in `workspace-write`; `[features.network_proxy]` domain allow/deny; command `rules` = allow/prompt/forbid prefixes) |

---

## 2. Delta table

Verdicts are terminal-jail (v1.3.0, this tree) **vs that incumbent on that
capability row**: `ahead` / `parity` / `behind` / `n-a` (n-a = not comparable,
e.g. licensing). "measured 2026-10-12" cells carry the command that produced
them. A cell with no primary source says so.

### Capability 1 — Pre-exec command judging (the firewall)

| Capability | Incumbent | Incumbent position (source) | terminal-jail | Verdict |
|---|---|---|---|---|
| Pre-exec command judging | bubblewrap | None. README: the caller owns the security model; bwrap executes whatever argv it is handed | Per-command firewall BEFORE execution, every backend: parser → matcher → 4-layer precedence (engine builtin / shipped YAML / operator / rule pack) → block / modify(auto-sandbox) / allow. Measured 2026-10-12: `./standalone/terminal-jail unshare -r echo x` → `COMMAND BLOCKED — builtin-ns-escape`, exit 126; JSON bridge verdict carries `rule_id` + `layer` (`{"action": "block", …, "layer": "yaml"}`) | **ahead** |
| Pre-exec command judging | firejail | None for commands: profiles are static per-program policy files; no per-command judgment, no verdict record (README + man page) | (same as above) | **ahead** |
| Pre-exec command judging | nsjail | None: policy is flags/config applied to the jail itself, not to the command string (README) | (same as above) | **ahead** |
| Pre-exec command judging | Docker + gVisor | None at command level: admission is image/config based; runtime logs, no per-command security verdict (Docker docs; gVisor README) | (same as above) | **ahead** |
| Pre-exec command judging | srt | Partial: pre-exec allow/deny by config domains and paths (README config keys); whether any per-command rule verdict record is emitted is **unverified** (none documented in the README) | Per-command verdict with rule id + provenance layer, scriptable line protocol (`plugin/terminal_jail/interruptor_bridge.py`), resident AF_UNIX daemon (TJ-GAP-084), arg-size ceiling (TJ-GAP-086) | **ahead** |
| Pre-exec command judging | Codex | Comparable: `rules` allow/prompt/forbid COMMAND PREFIXES pre-exec, plus `auto_review` agent reviewing escalations (security doc). Prefix matching, not parsed-command semantics; decisions surface in the approval UI, no documented standalone machine-readable verdict stream | Regex/matcher engine over parsed segments, 4-layer precedence, recorded verdict incl. provenance layer; no interactive approval loop (different trust model: unattended default-deny) | **parity** |

### Capability 2 — PID / user namespace isolation

| Capability | Incumbent | Incumbent position (source) | terminal-jail | Verdict |
|---|---|---|---|---|
| PID / user namespace | bubblewrap | Unprivileged user+PID namespaces (`--unshare-user --unshare-pid`); setuid mode removed in 0.13 (NEWS) | Delivered via the bwrap backend + the unshare backend (`--user --pid --fork`); measured 2026-10-12: `proc_view=private`, `/proc/1 = bwrap`, 5 PID entries; adds fail-closed tier demands (`TERMINAL_JAIL_REQUIRE_TIER`, TJ-GAP-087) | **parity** (consumes bwrap; adds selection, demands, attribution) |
| PID / user namespace | firejail | Full namespace suite incl. PID+NET+IPC via an SUID launcher (README) | No NET/IPC namespace in any shape; firejail's SUID launcher is an attack-surface trade bwrap explicitly abandoned (bwrap NEWS) | **behind** (no NET/IPC ns) |
| PID / user namespace | nsjail | UTS/MOUNT/PID/IPC/NET/USER/CGROUPS/TIME namespaces + cgroups + rlimits (README features) | Same scope limit as firejail (no NET/IPC/cgroup/rlimit layer) | **behind** |
| PID / user namespace | Docker + gVisor | Container namespace suite; gVisor replaces the syscall surface with a userspace application kernel (gVisor README: "not a syscall filter… an application kernel") | Different weight class; TJ's composed mode (TJ-GAP-089) deliberately CONSUMES this layer as the outer containment | **behind** (by design — TJ is the inner layer, see composed mode) |
| PID / user namespace | srt | bwrap on Linux → unprivileged user namespace, same primitive (srt README) | Same primitive + unshare fallback + tier demands | **parity** |
| PID / user namespace | Codex | bwrap from PATH on Linux/WSL2 (bundled helper fallback needing unprivileged userns) (sandboxing doc) | Same primitive | **parity** |

### Capability 3 — Filesystem isolation (incl. Landlock)

| Capability | Incumbent | Incumbent position (source) | terminal-jail | Verdict |
|---|---|---|---|---|
| FS isolation | bubblewrap | Mount-tree construction (`--ro-bind`, `--tmpfs`…); no unprivileged uid mapping; no kernel LSM deny layer | Namespace mounts via backends PLUS the Landlock FS tier (TJ-GAP-082, shipped 1.3.0): kernel-enforced read-denials on credential surfaces + write confinement, survives exec. Measured 2026-10-12: default launch → `head ~/.ssh/id_rsa` denied (rc 1), `/tmp` write OK | **ahead** (kernel LSM layer bwrap lacks) |
| FS isolation | firejail | Mature per-app profiles: whitelist/blacklist trees, read-only, private dirs (man page), via mounts, SUID | Landlock deny-layer scope is narrower than firejail's profile breadth (TJ grants read to system/toolchain trees, denies credential surfaces + confines writes; no per-app profile library) | **behind** (breadth; firejail has years of profile curation) |
| FS isolation | nsjail | chroot / pivot_root / read-only mounts / custom /proc (README) | Comparable mount story via backends + Landlock deny layer on top | **parity** |
| FS isolation | Docker + gVisor | Image FS + gVisor's gofer-mediated filesystem (application kernel intercepts FS syscalls) (gVisor README/docs) | Same weight-class note as capability 2 | **behind** (platform layer; consumed by composed mode) |
| FS isolation | srt | `denyRead`/`allowWrite`/`denyWrite` config → enforced by sandbox-exec (macOS) / bubblewrap mounts (Linux) (README) | Comparable policy surface; TJ's Landlock enforcement is kernel-side and survives exec; srt's Linux path is mounts. Whether srt adds a kernel LSM on Linux is **unverified** (none documented) | **parity** |
| FS isolation | Codex | `workspace-write` writable roots + protected paths (.git, .codex) inside bwrap (sandboxing + config docs) | Comparable shape (workspace-write-equivalent confinement via Landlock + tmpfs writes) | **parity** |

### Capability 4 — Network egress control

| Capability | Incumbent | Incumbent position (source) | terminal-jail | Verdict |
|---|---|---|---|---|
| Network egress | bubblewrap | None granular: shared host network by default; `--unshare-net` cuts ALL networking (README/flags) | Landlock TCP tier (TJ-GAP-083, shipped 1.3.0): `connect(2)` to any port outside the allowlist fails EPERM at the kernel, payload + descendants. Measured 2026-10-12: `TERMINAL_JAIL_LANDLOCK_NET=1` loader → port 9151 → `EPERM`; without the tier → `ECONNREFUSED` | **ahead** (per-port allow inside a shared netns; bwrap is all-or-nothing) |
| Network egress | firejail | `--net=none`/new netns + `--netfilter` (iptables) + `--protocol=` family filter (man page) | Firejail's netfilter is richer (iptables: hosts/networks); TJ's tier is port-granular only (Landlock v4 has no host selector) and off by default | **parity** (different granularities; both kernel-enforced) |
| Network egress | nsjail | NET namespace isolation + MACVLAN/pasta userland networking (README) | nsjail isolates or moves the whole netns; TJ filters per-port inside the caller's netns | **ahead** (in-place per-port deny vs all-or-nothing) |
| Network egress | Docker + gVisor | Publish/port-declare model + Docker network policies; gVisor implements the network stack in its userspace kernel (Docker network docs, gVisor README) | Platform-plane policy vs TJ's in-jail kernel tier; TJ composes UNDER this layer (composed mode) | **parity** (different planes; neither subsumes the other) |
| Network egress | srt | HTTP(S) **domain** allow/deny via a local filtering proxy (README `allowedDomains`) | TJ has NO domain-level control (Landlock v4 is port-granular, no host selector); TJ's tier is kernel-side (raw `connect()`), srt's proxy governs proxied traffic. Raw-socket bypass posture of srt is **unverified** | **behind** (no domain-level egress) |
| Network egress | Codex | Network OFF by default in `workspace-write`; optional `[features.network_proxy]` with per-domain allow/deny (security doc) | Same domain-granularity gap as srt; TJ's default posture is "firewall verdict + open netns" rather than "network off by default" | **behind** (no domain-level egress; no default-off network) |

### Capability 5 — seccomp filter

| Capability | Incumbent | Incumbent position (source) | terminal-jail | Verdict |
|---|---|---|---|---|
| seccomp | bubblewrap | None (no seccomp flags; NNP only) (README/flags) | `--seccomp` applies a BPF filter inside the jail (capability matrix, measured cells: `Seccomp: 2`, `Seccomp_filters: 1`); opt-in | **ahead** |
| seccomp | firejail | seccomp-bpf ON by default with curated profiles (README) | TJ's filter is opt-in (`--seccomp`), one shipped deny-list; firejail defaults ON with per-app profiles | **parity** (firejail ahead on default-on + profile breadth; proposed row TJ-GAP-091) |
| seccomp | nsjail | Kafel seccomp-bpf policies (README) | Comparable mechanism (BPF deny-list); Kafel is a policy language, TJ's is a shipped filter | **parity** |
| seccomp | Docker + gVisor | Docker: default seccomp ALLOWLIST profile on by default ("an allowlist which specifies the calls that are allowed", docs.docker.com/engine/security/seccomp); gVisor: NOT a seccomp filter — userspace application kernel (README) | TJ ships a deny-list, opt-in; incumbents ship default-on allowlisting + a much smaller syscall surface under gVisor | **behind** (default-off deny-list vs default-on allowlist) |
| seccomp | srt | None documented on the Linux path (bubblewrap + NNP); **unverified** whether srt adds seccomp anywhere (README silent) | TJ's opt-in BPF filter applies in every backend | **ahead** |
| seccomp | Codex | No user-configurable seccomp documented; enforcement is bwrap + platform sandboxes (sandboxing doc) | TJ adds an explicit opt-in filter layer | **ahead** |

### Capability 6 — Private /proc

| Capability | Incumbent | Incumbent position (source) | terminal-jail | Verdict |
|---|---|---|---|---|
| Private /proc | bubblewrap | Fresh procfs via `--proc /proc` (flags) | Same, via the bwrap backend + `proc_view` attribution per launch + fail-closed `--private-proc` demand (TJ-GAP-088). Measured 2026-10-12: `./standalone/terminal-jail --private-proc bash -c '…'` → `proc_view=private`, `/proc/1 = bwrap`, 5 PID entries, NSpid 2 | **parity** (+ attribution/demand layer) |
| Private /proc | firejail | PID namespace ⇒ private process table (README) | Same class of guarantee where the backend provides it | **parity** |
| Private /proc | nsjail | Custom /proc mounts documented as a feature (README) | Same class | **parity** |
| Private /proc | Docker + gVisor | Container PID namespace procfs; gVisor implements /proc in its kernel (README/docs) | Same class in the composed shape (platform-owned view, attributed `proc_view=platform-owned`) | **parity** |
| Private /proc | srt | Via bwrap on Linux; whether `--proc` isolation is passed is **unverified** (README silent) | Demand + attribution make the delivered view explicit on every launch | **parity** |
| Private /proc | Codex | Via bwrap on Linux (sandboxing doc) | Same primitive + attribution | **parity** |

### Capability 7 — Telemetry / provenance of verdicts

| Capability | Incumbent | Incumbent position (source) | terminal-jail | Verdict |
|---|---|---|---|---|
| Verdict telemetry | bubblewrap | None (no verdict concept; stderr only) | Every verdict carries `rule_id` + provenance `layer` (engine/yaml/operator/rule pack, TJ-GAP-085) + `proc_view` attribution; JSON line protocol + resident AF_UNIX daemon (TJ-GAP-084) + metrics counters (TJ-DF-033). Measured 2026-10-12: bridge JSON `{"action": "block", "rule_id": "builtin-ns-escape", "layer": "yaml"}` | **ahead** |
| Verdict telemetry | firejail | `--trace`/`--audit` logs to files; no structured per-command verdict record (man page) | (same as above) | **ahead** |
| Verdict telemetry | nsjail | Jail logs; no verdict records (README) | (same as above) | **ahead** |
| Verdict telemetry | Docker + gVisor | Container/runtime logs; gVisor can log syscalls — platform observability, not per-command security verdicts with rule provenance (docs) | (same as above) | **ahead** |
| Verdict telemetry | srt | Violation monitoring (macOS sandbox violation log tap, real-time alerts) (README); Linux-path logging **unverified** | TJ records allow/block/modify verdicts with provenance on every launch, host-independent | **ahead** |
| Verdict telemetry | Codex | Approval/review decisions recorded in the product session (approvals + auto_review, security doc); no documented standalone machine-readable verdict stream | TJ's stream is offline, scriptable, and rule-provenance-bearing; Codex's lives in the product | **ahead** (narrow: standalone verdict protocol) |

### Capability 8 — Licensing

| Capability | Incumbent | Incumbent position (source) | terminal-jail | Verdict |
|---|---|---|---|---|
| Licensing | bubblewrap | LGPL-2.1-or-later (COPYING in repo) | MIT (LICENSE); bwrap is an OPTIONAL external dependency, never vendored (TJ-GAP-055, README packaging boundary) | **n-a** (compatible as external dep) |
| Licensing | firejail | GPL-2.0 (GitHub API license field) | MIT; firejail is not used, referenced only as an incumbent | **n-a** |
| Licensing | nsjail | Apache-2.0 (GitHub API) | MIT | **n-a** |
| Licensing | Docker + gVisor | moby Apache-2.0, gVisor Apache-2.0 (GitHub API + pkg.go.dev) | MIT | **n-a** |
| Licensing | srt | Apache-2.0 (GitHub API) | MIT | **n-a** |
| Licensing | Codex | Apache-2.0 (GitHub API) | MIT | **n-a** |

---

## 3. Board rows this sweep consumed

All landed in the 1.3.0 release (CHANGELOG `[1.3.0] — 2026-10-08`; commit
shas from `git log`):

| Row | What it delivered (verified in CHANGELOG / git) | Parity effect |
|---|---|---|
| TJ-GAP-082 | Landlock kernel-enforced FS-isolation tier (`bd39236`; coverage `b2f5b40`) | Capability 3: bwrap/no-uid-map cells move from "planned" to a shipped kernel deny layer |
| TJ-GAP-083 | Landlock TCP-connect (network egress) tier (`376dab2`) | Capability 4: network-layer containment no longer "unavailable in every shape"; measured EPERM today |
| TJ-GAP-084 | Resident AF_UNIX verdict daemon + one-shot cost guard (`c2e7023`) | Capability 7: transport for verdict telemetry |
| TJ-GAP-085 | Rule resolution provenance in the verdict (`93ecf3b`) | Capability 7: per-verdict provenance layer — observed live today (`"layer": "yaml"`) |
| TJ-GAP-086 | Enforced 256 KiB argument-size ceiling + benchmark (`80deb8e`) | Capability 1: firewall robustness (O(len) refusal before parse) |
| TJ-GAP-087 | install.sh tier report + `TERMINAL_JAIL_REQUIRE_TIER` fail-closed (`933ffe0`, rework `b7da134`) | Capability 2: deployment can demand the PID-namespace tier |
| TJ-DF-038 | Preflight names a missing `uname` instead of claiming non-Linux (`cd31f7b`) | Diagnostics honesty (supports every capability row's classify-first doctrine) |
| JSONL-NORM-002 | Board JSONL schema guard + migration (`a7ecbf4`) | Harness-side: keeps the cadence's own bookkeeping (this row's board) schema-checked |

---

## 4. Proposed rows (gaps that remain)

Filed here ONLY as proposals — the board is written by the foreman.

| Proposed id | One-line evidence |
|---|---|
| `TJ-GAP-090` | Domain-level egress: srt (`allowedDomains`) and Codex (`features.network_proxy` domains) enforce HTTP(S) HOST-granular egress; TJ's Landlock tier is port-granular only (Landlock v4 has no host selector) — an optional local filtering-proxy tier would close the capability-4 "behind" verdicts (sources in §2, capability 4) |
| `TJ-GAP-091` | Default-on seccomp: firejail ships seccomp-bpf ON by default and Docker ships a default ALLOWLIST profile; TJ's `--seccomp` is opt-in and deny-list (docs.docker.com/engine/security/seccomp; firejail README) — evaluate a default-on (opt-out) loader after host-matrix regression |
| `TJ-GAP-092` | systemd service-layer egress directives remain staged-commented in the shipped drop-in (specs/integration.md integration matrix: `RestrictAddressFamilies` listed as "staged — commented out as shipped") — the Landlock tier is per-command and opt-in; the service-level layer is still not shipped |

## 5. Gaps explicitly closed this sweep

| Gap | Closed because |
|---|---|
| "Landlock FS tier is planned" (TJ-GAP-082) | Shipped 1.3.0 (`bd39236`) and measured working on this host 2026-10-12 (`~/.ssh/id_rsa` read denied, `/tmp` write allowed under the default launch). The stale docs statement in `docs/capability-matrix.md` is corrected in this commit |
| "Network-layer containment unavailable today in every shape" (TJ-GAP-083) | Shipped 1.3.0 (`376dab2`); measured today: `TERMINAL_JAIL_LANDLOCK_NET=1` loader → connect to non-allowlisted port 9151 → **EPERM** (kernel), vs `ECONNREFUSED` without the tier. Same docs correction in this commit. Residual: domain granularity ≠ closed — see proposed `TJ-GAP-090` |
| FS isolation vs bubblewrap on AppArmor-restricted hosts (no unprivileged uid mapping) | Mitigated, not by a TJ code gap: the kernel-side Landlock tier now covers the credential-surface denial use case without any uid mapping. The host-wide AppArmor remedy gap is narrowed by the added per-profile `bwrap-userns-restrict` remedy (docs/capability-matrix.md §4, this commit). Full uid-mapped isolation on hosts that deny setuid/setgroups inside userns remains a HOST policy matter, not an open TJ gap |

No silent carry-over: every previously-open parity item is either consumed
(§3), closed (§5), or proposed (§4).

## 6. Implemented in this sweep (same commit)

The sweep's one concrete improvement (cheap + local, chosen after checking that
TJ-GAP-085 already covers verdict provenance): **the per-host capability matrix
had gone stale against 1.3.0** — its Filesystem-isolation and egress rows still
described the Landlock tiers as "planned"/"unavailable today" although
TJ-GAP-082/083 shipped on 2026-10-08. This commit updates
`docs/capability-matrix.md`:

1. FS-isolation row: the Landlock tier is stated as shipped (1.3.0) instead of
   "a planned Landlock addition (TJ-GAP-082)".
2. Egress row: "unavailable today in every shape" replaced by the opt-in
   Landlock TCP tier (TJ-GAP-083), with the 2026-10-12 measured EPERM cell.
3. §4 remediation list: added the per-profile `bwrap-userns-restrict` AppArmor
   remedy (the scoped remedy OpenAI documents for Codex on Ubuntu 24.04/25.04)
   — an alternative to the host-wide sysctl that does not weaken other
   unprivileged-userns denials (worded precisely: it helps bwrap-backed
   launches; it does not lift the setuid/setgroups denial for the uid-mapped
   `unshare --user` launch).
4. §5 cross-links: TJ-GAP-082/083 marked shipped.

## 7. Cadence

Re-run each release cut + quarterly (next: after the next release tag, and
2027-01-05 quarter-start window). Source board row: **PARITY-TJ-001**.
