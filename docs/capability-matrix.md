# Per-host capability matrix

What containment terminal-jail actually delivers, per enforcement layer and per
host class / backend. Every cell states a state — **enforced**, **degraded**, or
**unavailable** — with the reason. Cells nobody measured on the worked-example
host say **unknown (not measured on this host)** explicitly: nothing on this
page is a guess.

**Reproduce the read on your own host** with the two classifier probes (§1):
they always exit 0 and print a verdict — they are classifiers, not gates.

---

## 1. The probes that produce this matrix

| Probe | Command | What it classifies |
|---|---|---|
| PID-namespace capability | `python3 scripts/pidns-capability-probe.py` | Whether a bare-mode containment launch works here. Verdicts: `FULL` (the launch succeeds), `DEGRADED` (the host refuses namespace creation; the wrapper fails closed, exit 2, naming `--user`), `UNKNOWN` (missing wrapper / timeout / unexpected output), `JAIL-AWARE` (the probe is itself running inside a terminal-jail launch — run it directly on the outer host). |
| Filesystem-isolation tier | `python3 scripts/fs-isolation-probe.py` | Whether `--user` gets a REAL uid-mapped namespace. It exercises the mapped launch in a throwaway namespace and runs two acceptance checks inside it (read a caller-owned mode-600 file, create a file in the caller's HOME): both must fail for `FULL`, any success is `DEGRADED`. Degradations carry the diagnosed cause: missing `newuidmap`/`newgidmap`, missing `/etc/subuid`/`/etc/subgid` entries, or the AppArmor denial (named explicitly, with the `kernel.apparmor_restrict_unprivileged_userns` value). |

Both are classifiers for humans and batteries (TJ-GAP-042): always exit 0, an
honest `UNKNOWN` instead of a hang.

Real output on the worked-example host (2026-10-03, Ubuntu 26.04.1 LTS, kernel
7.0.0-31), quoted verbatim:

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
bwrap when installed and its probe passes, otherwise unshare). "composed" is
the tool inside a platform container (`TERMINAL_JAIL_COMPOSED`, TJ-GAP-089).

| Enforcement layer | bwrap backend | unshare (bare) | unshare --user | composed (in container) |
|---|---|---|---|---|
| **PID namespace** | **enforced** — `bwrap --unshare-pid`; on AppArmor hosts this is typically the only backend that launches (see §3: bare unshare is refused here) | **enforced where the host permits it** (`unshare --pid --fork --kill-child=SIGKILL`); **unavailable** on hosts whose policy denies unprivileged namespace creation — the wrapper fails closed, exit 2, naming `--user` (measured on this host: bare launch refused) | **enforced** — user namespace + PID namespace; measured multi-value `NSpid` in `/proc/self/status` (2026-10-03) | **unavailable from the tool** — composed mode creates NO inner namespace; the platform's PID namespace is the layer (`jail_layer=platform`) |
| **Identity / env scrub** (`USER`/`LOGNAME`/`HOME`) | **unavailable in plain mode by design** — measured 2026-10-03: `uid=1000`, `USER=kara`, `HOME=/home/kara` preserved. The scrub is a `--user` property and composes with either backend (measured under `--user` with bwrap pinned: `USER=nobody`, `HOME=/nonexistent`) | **unavailable by design** — plain mode scrubs nothing | **enforced** — `USER=nobody`, `LOGNAME=nobody`, `HOME=/nonexistent`; uid displays 65534 (2026-10-03) | **unknown (not measured on this host)** — no container runtime here; the composed contract grants the tool only the firewall verdict |
| **Private `/proc`** | **enforced** — fresh procfs via `--proc /proc`; measured 2026-10-03: `/proc/1 = bwrap`, **4** numeric PID entries (2026-10-01 board snapshot: **5** entries). Demand it explicitly with `--private-proc` (TJ-GAP-088) — backend selection then fails closed rather than silently downgrading | **enforced where bare mode works** (`--mount-proc` mounts a fresh procfs); **unavailable on this host** — the bare launch itself is refused by AppArmor policy, so no private procfs is reachable this way | **unavailable** — an unprivileged user namespace cannot mount procfs; the HOST view stays exposed (2026-10-03: `/proc/1 = systemd`, **1175** entries vs host 1173; 2026-10-01 board snapshot: **1084** entries). The mapped-root route to a private procfs is closed on AppArmor hosts (uid_map EPERM) | **unavailable from the tool** — `proc_view=platform-owned`: the outer container's `/proc` is the view (TJ-GAP-088) |
| **Filesystem isolation** (uid mapping) | **unavailable in the wrapper's bwrap launch on this host** — measured 2026-10-03: uid stays 1000, `/` is bound in. Whether bwrap alone could map ids here is **unknown (not measured on this host)** | **unavailable by design** — bare mode creates no user namespace and changes no identity (not separately measurable here: the bare launch is refused) | **degraded — effectively unavailable — on Ubuntu 24.04+ by default**: the AppArmor `unprivileged_userns` profile denies setuid/setgroups inside the namespace, so the launch falls back to a mapping-less namespace with a loud `no filesystem isolation` warning; `id` shows 65534 but the underlying kuid is unchanged, so mode-600 caller files stay readable (TJ-DF-015). Remediation in §4 | **unavailable from the tool** — `filesystem: NOT isolated by this tool`; the platform's filesystem policy governs |
| **seccomp** (`--seccomp`) | **enforced** — measured 2026-10-03: `Seccomp: 2`, `Seccomp_filters: 1` | **unknown on this host** — the bare launch is refused here; where it works the filter loads with the namespace (unverified on this host) | **enforced** — measured 2026-10-03: `Seccomp: 2`, `Seccomp_filters: 1` (the filter applies without the uid mapping) | **unavailable from the tool** — `--seccomp` prints a warning and is a no-op; the container's own profile is the active seccomp state |
| **egress** | **enforced, verdict-only** — the interruptor firewall applies in every launch shape (rule-class block → exit 126 + `rule_id` provenance). Network-layer egress control: **unknown (not measured on this host)** — the Landlock tier is tracked separately as TJ-GAP-083 | **enforced, verdict-only** (same firewall); network-layer **unknown** | **enforced, verdict-only** (same firewall); network-layer **unknown** | **enforced, verdict-only** — identical verdict inside the container (live Docker run 2026-10-03: block = exit 126, `rule_id builtin-rm-rf-root`); network-layer **unknown** |

---

## 3. Worked example: Ubuntu 26.04, kernel 7.0.0-31 (this host)

Host policy: `kernel.apparmor_restrict_unprivileged_userns = 1`.
`/usr/bin/newuidmap` and `/usr/bin/newgidmap` ARE installed and `/etc/subuid`
has entries for the caller — the blocker is the AppArmor policy, not missing
helpers.

Measured per launch shape (every line below was run 2026-10-03 from a repo
checkout on this host):

| Launch | Result on this host |
|---|---|
| bare unshare (`TERMINAL_JAIL_JAIL_BACKEND=unshare`) | `namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user` — exit 2, command not run |
| bwrap plain | launches; `proc_view=private`; `/proc/1 = bwrap`; **4** numeric PID entries; identity preserved (`uid=1000`, `USER=kara`, `HOME=/home/kara`) |
| bwrap + `--seccomp` | launches; `Seccomp: 2`, `Seccomp_filters: 1` |
| `--user` (unshare) | launches; multi-value `NSpid` (inside a new PID namespace); `uid=65534`; `USER=nobody`, `HOME=/nonexistent`; `proc_view=host` — host `/proc` visible (`/proc/1 = systemd`, **1175** entries vs host 1173); loud `no filesystem isolation` warning (AppArmor setgroups denial) |
| `--user` + `--seccomp` | launches; `Seccomp: 2`, `Seccomp_filters: 1` |
| `--user` with bwrap pinned | launches; `proc_view=private`; `USER=nobody`, `HOME=/nonexistent` — the scrub composes with the bwrap backend too |

Board snapshot (2026-10-01): bwrap **5** entries with `/proc/1 = bwrap`;
`unshare --user` **1084** entries with `/proc/1 = systemd`. The 2026-10-03
numbers above count **numeric PID directories** (the `proc_entry_count`
convention of `scripts/composed-mode-battery.py`); the 2026-10-01 snapshot
counted all `/proc` entries. Absolute counts track what is running at the
instant of measurement — the qualitative property (a handful of entries vs a
four-digit host view) is what the matrix asserts, exactly as
`docs/composed-deployment.md` §3 states for its own copy of the numbers.

One-line read of this host class: `auto` backend selection lands on bwrap,
which delivers the PID namespace and the private `/proc`; `--user` delivers the
identity scrub; filesystem isolation stays degraded until the AppArmor policy
is remediated (§4); the firewall verdict is unconditional.

---

## 4. The Ubuntu AppArmor case (adoption guidance)

Filesystem isolation is **unavailable on Ubuntu 24.04+ by default** (the probe
classifies it DEGRADED): stock Ubuntu ships the `unprivileged_userns` AppArmor
profile, which denies setuid/setgroups inside unprivileged user namespaces, so
the uid-mapped `--user` launch cannot come up. The wrapper fails LOUD, not
silent: it prints `no filesystem isolation — could not create a uid mapping …`
on stderr and proceeds with the mapping-less namespace. This is a host policy
restriction, not a code defect.

Remediation (pick one, as root):

1. `sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` — host-wide; persist it under `/etc/sysctl.d/` if you accept the trade;
2. add an AppArmor exception for the launcher in the `unprivileged_userns` profile;
3. install `newuidmap`/`newgidmap` plus `/etc/subuid`/`/etc/subgid` ranges for the calling user — helps only where the policy permits the mapping (on this host the helpers were already present and the policy was the blocker).

Classify any host before adopting: run the two probes in §1. If
`fs-isolation-probe.py` says DEGRADED, decide whether the identity scrub
without filesystem isolation is acceptable for your threat model — make that
decision against `docs/threat-model.md`, not against this page.

---

## 5. Cross-links

- `TJ-GAP-083` — the Landlock egress tier (separate, optional; network-layer egress is unmeasured until it lands).
- `TJ-GAP-088` — private `/proc` ownership, the `--private-proc` fail-closed demand, and `proc_view` attribution on every launch.
- `TJ-GAP-089` — composed mode (`TERMINAL_JAIL_COMPOSED=auto|on|off`); the shared per-layer guarantee matrix lives in [docs/composed-deployment.md](composed-deployment.md) (platform copy: bunker `DOC-043`).
- `TJ-DF-015` / [docs/backend-parity.md](backend-parity.md) — raw per-backend measurement cells, including the host-`/proc` known limit.
- `tests/test_capability_matrix_doc.py` — pins this page's probe names, layer rows, and measured numbers so they cannot drift silently.
