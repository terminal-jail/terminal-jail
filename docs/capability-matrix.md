# Per-host capability matrix

What containment terminal-jail actually delivers, per enforcement layer and per
launch shape / host class. Every cell states a state — **enforced**,
**degraded**, or **unavailable** — with the reason. Cells nobody measured on the
worked-example host say **unknown (not measured on this host)** explicitly:
nothing on this page is a guess, and nothing is claimed from intent.

**Reproduce the read on your own host** with the two classifier probes (§1).
They classify any host, always exit 0, and print a verdict — they are
classifiers, not gates. The worked example (§3) is Ubuntu 26.04.1 LTS, kernel
7.0.0-31, measured 2026-10-03 from a repo checkout on this host.

---

## 1. The probes that produce this matrix

| Probe | Command | What it classifies |
|---|---|---|
| PID-namespace capability | `python3 scripts/pidns-capability-probe.py` | Whether a bare-mode containment launch works here. Verdicts: `FULL` (the launch succeeds), `DEGRADED` (the host refuses namespace creation; the wrapper fails closed, exit 2, naming `--user`), `UNKNOWN` (missing wrapper / timeout / unexpected output), `JAIL-AWARE` (the probe is itself running inside a terminal-jail launch — run it directly on the outer host). |
| Filesystem-isolation tier | `python3 scripts/fs-isolation-probe.py` | Whether `--user` gets a REAL uid-mapped namespace. It exercises the mapped launch in a throwaway namespace and runs two acceptance checks inside it (read a caller-owned mode-600 file, create a file in the caller's HOME): both must fail for `FULL`, any success is `DEGRADED`. Degradations carry the diagnosed cause: missing `newuidmap`/`newgidmap`, missing `/etc/subuid`/`/etc/subgid` entries, or the AppArmor denial (named explicitly, with the `kernel.apparmor_restrict_unprivileged_userns` value). |

Both probes are also the battery's host gate (TJ-GAP-042): a DEGRADED host
skips bare-mode containment tests instead of silently passing.

Real output on the worked-example host (2026-10-03), quoted verbatim:

```text
$ python3 scripts/pidns-capability-probe.py
FULL
$ python3 scripts/fs-isolation-probe.py
DEGRADED: mapped launch failed (rc=1, stderr='unshare: setgroups failed: Operation not permitted'); causes: uid-mapping denied: mapped launch failed while the legacy one succeeded (kernel denies setgid/setgroups inside unprivileged user namespaces — AppArmor profile 'unprivileged_userns') [kernel.apparmor_restrict_unprivileged_userns=1]. remediation: as root, `sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` or add an AppArmor exception for the launcher, or install newuidmap/newgidmap plus /etc/subuid|/etc/subgid ranges for the calling user
```

---

## 2. The matrix

Columns are the launch shapes. `bwrap` and `unshare` are the two backends,
selected by `TERMINAL_JAIL_JAIL_BACKEND=auto|bwrap|unshare` (default `auto`:
bwrap when installed and its probe passes, otherwise unshare — on the worked
example `auto` lands on bwrap). `unshare --user` is the `--user` identity tier
(backend selected the same way; both backends were measured under `--user`).
"composed" is the tool inside a platform container (`TERMINAL_JAIL_COMPOSED`,
TJ-GAP-089; measured with `python:3.11-slim` as the platform stand-in).
Platform-alone (a container with no tool) gives the platform rows below but NO
per-command verdict — see [docs/composed-deployment.md](composed-deployment.md)
§1.

| Enforcement layer | bwrap backend | unshare (bare) | unshare --user | composed (in container) |
|---|---|---|---|---|
| **PID namespace** | **enforced** — `bwrap --unshare-user --unshare-pid`; the jailed process lands in a new PID namespace (measured: fresh numbering, `/proc/1 = bwrap`) | **enforced where the host permits it** (`unshare --pid --fork --mount-proc --kill-child=SIGKILL`; measured PASS on Debian 13 / kernel 6.12, `docs/backend-parity.md` kernel matrix); **unavailable on the worked-example host** — the bare launch is refused, exit 2: `namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user` | **enforced** — user namespace + new PID namespace (measured `NSpid: 3962131 2` — two namespace levels in `/proc/self/status`) | **not from the tool** — composed mode creates NO inner namespace; the platform's PID namespace is the layer (`jail_layer=platform`; measured container `pid:[4026538482]` = the container init's own namespace) |
| **Identity / env scrub** (`USER`/`LOGNAME`/`HOME`) | **unavailable in plain mode by design** — the scrub is a `--user` property; measured plain bwrap: `uid=1000`, `USER=kara`, `HOME=/home/kara` preserved. The scrub composes with the bwrap backend when `--user` is also passed (measured: `USER=nobody`, `HOME=/nonexistent`) | **unavailable by design** — plain mode scrubs nothing (not separately measurable on this host: the bare launch is refused) | **enforced** — `USER=nobody LOGNAME=nobody HOME=/nonexistent`; `id -u` → `65534`. Without a working uid mapping the underlying kuid is unchanged (TJ-DF-015): an identity rename, not a permissions boundary | **not from the tool** — no `--user` shape exists in composed mode (no inner namespace); measured: the run keeps the container's identity (`uid=0`) |
| **Private `/proc`** | **enforced** — fresh procfs via `--proc /proc`; measured `proc_view=private`, `/proc/1 = bwrap`, **5** numeric PID entries (2026-10-01 board snapshot: **5** entries). Demand it with `--private-proc` (TJ-GAP-088) and selection fails closed instead of silently downgrading | **enforced where bare works** (`--mount-proc` mounts a fresh procfs in the new namespace); **unavailable on the worked-example host** — the bare launch itself is refused | **unavailable** — an unprivileged user namespace cannot mount procfs; the HOST view stays exposed (measured: `proc_view=host`, `/proc/1 = systemd`, **1175** entries vs host 1173; 2026-10-01 board snapshot: **1084**). The mapped-root route is closed on AppArmor hosts (uid_map EPERM). `--private-proc` under this backend refuses — exit 2, measured | **not from the tool** — `proc_view=platform-owned`; the container's own procfs is the view (measured: **4** entries, `/proc/1 = sh`; the shared matrix in [docs/composed-deployment.md](composed-deployment.md) §3 pins **4** `(measured 2026-10-01)`) |
| **Filesystem isolation** (uid mapping) | **unavailable** — bubblewrap has no unprivileged uid-mapping equivalent (`bwrap --uid` only re-labels; DAC still evaluates with the caller's kuid); measured: uid stays 1000, `/` bound in. A kernel-side filesystem tier is a planned Landlock addition (TJ-GAP-082) | **unavailable by design** — bare mode creates no user namespace and maps nothing (not measurable here: the bare launch is refused) | **degraded — effectively unavailable on Ubuntu 24.04+ by default**: the AppArmor `unprivileged_userns` profile denies setuid/setgroups inside the namespace, so the launch falls back mapping-less with the loud `no filesystem isolation` warning; `id` shows 65534 but mode-600 caller files stay readable (TJ-DF-015; probe verdict DEGRADED with exactly that cause). Remediation in §4 | **not from the tool** — the launch states `filesystem: NOT isolated by this tool`; the platform's image and policy govern |
| **seccomp** (`--seccomp`) | **enforced** — measured inside the jail: `Seccomp: 2`, `Seccomp_filters: 1` | **unknown (not measured on this host)** — the bare launch is refused here; where bare works the loader runs with the namespace (contract), unverified on this host | **enforced** — measured: `Seccomp: 2`, `Seccomp_filters: 1` (the filter applies without the uid mapping) | **not from the tool** — `--seccomp` prints a loud warning and applies nothing; the container's own profile is the active seccomp state (measured inside the container: `Seccomp: 2`) |
| **egress** (network) | **enforced, verdict-only** — the interruptor firewall evaluates before execution in every backend (measured: `unshare -r …` → block box, exit 126, `rule_id builtin-ns-escape`). Network-layer containment: **unavailable today in every shape** — the namespace wrap does not restrict network; a Landlock TCP tier is planned (TJ-GAP-083) | **enforced, verdict-only** (same engine, evaluated before the wrap); network-layer containment: **unavailable today** (same reason) | **enforced, verdict-only** (same engine); network-layer containment: **unavailable today** (same reason) | **enforced, verdict-only** — the same verdict inside the container (measured 2026-10-03: `builtin-ns-escape`, exit 126; the live transcript in [docs/composed-deployment.md](composed-deployment.md) records `builtin-rm-rf-root`, exit 126) |

Reading the table: `enforced` = measured working on the worked-example host (or
explicitly scoped "where the host permits"); `degraded` = delivered in a
reduced form with a loud warning; `unavailable` = not delivered, with the
reason; `not from the tool` = that layer belongs to the platform in this shape,
and the tool's own stderr says so (`jail_layer=platform`, `proc_view=…`,
`filesystem: NOT isolated by this tool`).

---

## 3. Worked example: Ubuntu 26.04.1 LTS, kernel 7.0.0-31 (this host)

Host policy facts (2026-10-03): `kernel.apparmor_restrict_unprivileged_userns = 1`;
`/usr/bin/newuidmap` and `/usr/bin/newgidmap` ARE installed and `/etc/subuid`
has entries for the caller (`kara:100000:65536`) — the blocker is the AppArmor
policy, not missing helpers. `scripts/pidns-capability-probe.py` → `FULL`;
`scripts/fs-isolation-probe.py` → `DEGRADED` (§1).

Measured per launch shape (every line below was run 2026-10-03 from a repo
checkout on this host; `…` stands for a payload such as `sh -c '<checks>'`):

| Launch | Result on this host |
|---|---|
| `TERMINAL_JAIL_JAIL_BACKEND=unshare ./standalone/terminal-jail echo x` | exit 2 — `namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user` |
| `./standalone/terminal-jail sh -c '…'` (auto → bwrap) | launches; `proc_view=private`; `/proc/1 = bwrap`; **5** numeric PID entries; identity preserved (`uid=1000`, `USER=kara`, `HOME=/home/kara`) |
| `TERMINAL_JAIL_JAIL_BACKEND=bwrap ./standalone/terminal-jail --user sh -c '…'` | launches; `proc_view=private`; `USER=nobody`, `HOME=/nonexistent`; uid stays 1000 (no mapping) + `no filesystem isolation` warning |
| `TERMINAL_JAIL_JAIL_BACKEND=unshare ./standalone/terminal-jail --user sh -c '…'` | launches; `proc_view=host`; `NSpid: 3962131 2`; `uid=65534`; `USER=nobody`, `HOME=/nonexistent`; `/proc/1 = systemd`, **1175** entries (host view: 1173); `no filesystem isolation` warning |
| any of the above + `--seccomp` | launches; `Seccomp: 2`, `Seccomp_filters: 1` |
| `TERMINAL_JAIL_JAIL_BACKEND=unshare ./standalone/terminal-jail --user --private-proc echo x` | exit 2 — the demand is enforced: `… 'unshare' cannot provide a private /proc; command not run …` |
| `./standalone/terminal-jail unshare -r echo ns-escape-attempt` | `COMMAND BLOCKED — builtin-ns-escape`, exit **126** |
| `docker run --rm -v "$PWD:/tj" -w /tj python:3.11-slim ./standalone/terminal-jail sh -c '…'` | composed report: `jail_layer=platform`, `proc_view=platform-owned`; container `/proc/1 = sh`, **4** entries, `Seccomp: 2`, `CapEff 00000000a80425fb` (bit 21 clear) |
| same + payload `unshare -r echo ns-escape-attempt` | `COMMAND BLOCKED — builtin-ns-escape`, exit **126** — the firewall works inside the container |

Count method: the entry counts above are **numeric PID directories** in `/proc`
(the `proc_entry_count` convention of `scripts/composed-mode-battery.py`) —
re-measured 2026-10-03. The 2026-10-01 board snapshot (bwrap **5**, `unshare
--user` **1084**, container **4**, as pinned in
[docs/composed-deployment.md](composed-deployment.md) §3) counted `/proc`
entries the same way; absolute counts track what is running at the instant of
measurement, so the qualitative property — a handful of entries for a private
procfs vs a four-digit host view — is what the matrix asserts.

One-line read of this host class: `auto` lands on bwrap, which delivers the PID
namespace and the private `/proc`; `--user` delivers the identity scrub;
filesystem isolation stays degraded until the AppArmor policy is remediated
(§4); the firewall verdict is unconditional; composed-in-container keeps the
verdict and inherits the platform's namespace.

---

## 4. The Ubuntu AppArmor case (adoption guidance)

Filesystem isolation is **unavailable on Ubuntu 24.04+ by default** (the probe
classifies it DEGRADED): stock Ubuntu ships the `unprivileged_userns` AppArmor
profile, which denies setuid/setgroups inside unprivileged user namespaces, so
the uid-mapped `--user` launch cannot come up. The wrapper fails LOUD, not
silent: it prints `no filesystem isolation — could not create a uid mapping …`
on stderr and proceeds with the mapping-less namespace. This is a host policy
restriction, not a code defect — the same policy also refuses the bare `unshare`
launch on these hosts, which is why `auto` selects bubblewrap where it is
installed.

Remediation (pick one, as root):

1. `sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` — host-wide; persist it under `/etc/sysctl.d/` if you accept the trade;
2. add an AppArmor exception for the launcher in the `unprivileged_userns` profile;
3. install `newuidmap`/`newgidmap` plus `/etc/subuid`/`/etc/subgid` ranges for the calling user — helps only where the policy permits the mapping (on the worked-example host the helpers were already present and the policy was the blocker).

Classify any host before adopting: run the two probes in §1. If
`fs-isolation-probe.py` says DEGRADED, decide whether the identity scrub
without filesystem isolation is acceptable for your threat model — make that
decision against `docs/threat-model.md`, not against this page. A
kernel-side filesystem tier that does not need the mapping (Landlock) is
tracked as TJ-GAP-082 and a network-egress tier as TJ-GAP-083; until they land,
this page marks those cells accordingly rather than optimistically.

---

## 5. Cross-links

- `TJ-GAP-082` — the Landlock filesystem tier (planned; the fs-isolation cells above say what is true today).
- `TJ-GAP-083` — the Landlock TCP egress tier (planned; network-layer egress is unmeasured until it lands).
- `TJ-GAP-088` — private `/proc` ownership, the `--private-proc` fail-closed demand, and `proc_view` attribution on every launch.
- `TJ-GAP-089` — composed mode (`TERMINAL_JAIL_COMPOSED=auto|on|off`); the shared per-layer guarantee matrix lives in [docs/composed-deployment.md](composed-deployment.md) (platform copy: bunker `DOC-043`).
- `TJ-DF-015` / [docs/backend-parity.md](backend-parity.md) — raw per-backend measurement cells, including the host-`/proc` known limit (a).
- `tests/test_capability_matrix_doc.py` — pins this page's probe names, layer rows, and measured numbers so they cannot drift silently.
