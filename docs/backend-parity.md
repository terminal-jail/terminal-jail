# Backend parity: bwrap vs unshare — measured evidence (TJ-GAP-056)

This document records what the parity battery (`scripts/backend-parity-battery.py`)
actually **measured** on the host below. It is evidence, not a plan. The battery is
a classifier in the house style of `scripts/pidns-capability-probe.py` and
`scripts/fs-isolation-probe.py`: it always exits 0 and never gates anything.

## Measured on

| | |
|---|---|
| Host | karaHermes-mde-7840hs |
| Kernel | `7.0.0-30-generic` |
| bubblewrap | 0.11.1 (`/usr/bin/bwrap`) |
| terminal-jail | 1.1.0 (`./standalone/terminal-jail --version`, rc=0) |
| Date of run | 2026-09-21 |

Host classification at run time (cell 7): PID-namespace creation **FULL**
(`scripts/pidns-capability-probe.py`); uid mapping / FS isolation **DEGRADED**
(`scripts/fs-isolation-probe.py`: `unshare: setgroups failed: Operation not
permitted` — AppArmor profile `unprivileged_userns`, `kernel.apparmor_restrict_unprivileged_userns=1`).

## The parity table (battery output, verbatim)

Verdict vocabulary: `SAME` / `DIFFERS` / `KNOWN-LIMIT` / `FAIL-CLOSED-PROVEN`.
Every value below was observed on this host; no cell is an intent marker.

```text
cell                                                        backend  measured                                                                                                                       expected                                                    verdict
----------------------------------------------------------  -------  -----------------------------------------------------------------------------------------------------------------------------  ----------------------------------------------------------  ------------------
1 private /proc — bwrap backend                             bwrap    4 entries (host: 1340)                                                                                                         a handful of entries, far below the host count              SAME
2 private /proc — unshare backend                           unshare  1344 entries (host: 1340)                                                                                                      ≈ host count (documented known limit)                       KNOWN-LIMIT
3 orphan teardown — bwrap (--die-with-parent)               bwrap    payload gone in 20 ms; host-side pid 567741, identified by exact cmdline 'sleep 300' diffed against the pre-launch /proc scan  payload gone shortly after the wrapper dies                 SAME
4 orphan comparison — unshare (--kill-child=SIGKILL)        unshare  payload gone in 20 ms; host-side pid 567867, identified by exact cmdline 'sleep 300' diffed against the pre-launch /proc scan  payload gone shortly after the wrapper dies                 SAME
5 escape-wave replay under the bwrap backend                bwrap    rc=0, tail: 221 passed in 0.95s                                                                                                all escape vectors stay green under the bwrap backend       SAME
5b escape replay live slice (wrapper, argv+exit semantics)  bwrap    argv round-trip rc=0 stdout='[a b][$(id)][*][]'; exit 42 -> rc=42                                                              argv preserved, payload exit propagated                     SAME
6 fail-closed when the namespace probe fails                bwrap    rc=2, stdout='', marker=ABSENT                                                                                                 exit 2, command not run, marker file ABSENT                 FAIL-CLOSED-PROVEN
6 fail-closed when the namespace probe fails                unshare  rc=2, stdout='', marker=ABSENT                                                                                                 exit 2, command not run, marker file ABSENT                 FAIL-CLOSED-PROVEN
7 host classification: PID-namespace creation               both     FULL                                                                                                                           FULL on a containment-capable host                          SAME
7 host classification: uid mapping (FS isolation)           both     DEGRADED                                                                                                                       mapped keeps real FS isolation; degraded runs mapping-less  KNOWN-LIMIT
```

**Zero unexplained divergences.** The two `KNOWN-LIMIT` cells are the documented
limits (a) and (c) below; no cell says `DIFFERS` on this host.

## Cell notes (how each number was produced)

1. **Private /proc — bwrap.** The jail ran via the real wrapper
   (`TERMINAL_JAIL_JAIL_BACKEND=bwrap ... --user`); the payload counted numeric
   `/proc` entries and the host count was sampled just before the launch (it
   jitters run to run: 1333–1382 observed on this box). Measured: bwrap **4**
   vs host **1340**. A measurement caution learned while producing these
   numbers: raw `bwrap --bind / / --unshare-pid ...` **without** `--proc /proc`
   still shows the *host* procfs (measured **1348** entries) — the wrapper's
   argv includes `--proc /proc` (fresh procfs), and that flag is exactly what
   makes the jail's `/proc` private. Any hand-rolled probe that omits it
   measures the wrong thing.

2. **Private /proc — unshare.** Same experiment under
   `TERMINAL_JAIL_JAIL_BACKEND=unshare`: **1344** entries vs host **1340** —
   the host `/proc` is visible, which is the documented known limit (a), not a
   failure. The battery records it honestly as `KNOWN-LIMIT`.

3. **Orphan teardown — bwrap.** A jail was started whose payload is
   `sleep 300`; the payload was identified on the host by its exact cmdline
   (`sleep 300`) diffed against a pre-launch `/proc` scan (host-side pid, since
   the host's view shares the PID numbering). The **wrapper** process was
   `SIGKILL`ed; the payload disappeared within the 20 ms poll granularity — no
   orphan, no leftover `sleep 300` processes. `--die-with-parent` arms
   PR_SET_PDEATHSIG on the sandbox and the teardown survives the wrapper's death.

4. **Orphan comparison — unshare.** Same experiment (`--kill-child=SIGKILL`
   semantics): the payload was also gone in 20 ms — **no orphan either**. On
   this host the teardown property is therefore *equivalent* between the
   backends; the mechanisms differ (PDEATHSIG on bwrap's sandbox vs util-linux's
   kill-on-death child), not the observable outcome.

5. **Escape-wave replay.** Method (a), stated explicitly: the shipped engine
   corpus `plugin/test_escape_waves.py` (221 collected) was run via the repo
   venv with `TERMINAL_JAIL_JAIL_BACKEND=bwrap` in the environment. Raw tail
   line: `221 passed in 0.95s`. Note for re-runners: the corpus pins
   auto-sandbox (modify) verdicts, which require the **default** interruptor
   mode — setting `TERMINAL_JAIL_INTERRUPTOR_MODE=disabled` flips 105 of the
   221 verdicts to allow (measured). Cell 5b adds a live-wrapper slice through
   the bwrap backend: argv boundaries survive (including metacharacter-looking
   arguments, which the verdict engine would have blocked had the interruptor
   been active — hence it is disabled for that cell only) and payload exit
   status propagates (`bash -c 'exit 42'` → rc 42).

6. **Fail-closed contract.** Host-independent by construction: a curated `PATH`
   provides stub `bwrap`/`unshare` binaries whose probe (`... true`) exits 1.
   For each backend the wrapper was invoked as
   `terminal-jail --no-interruptor touch <marker>`: both runs exited **2**,
   printed the documented `command not run` degradation message, produced empty
   stdout, and the marker file the payload would have created is **ABSENT**.
   The command provably never ran.

## Known limits

**(a) unshare `--user` exposes the host `/proc`; bwrap does not.**
Measured: 1344 host-visible entries under the unshare `--user` jail vs 4 under
bwrap (host ≈ 1340). A user namespace cannot mount `/proc` unprivileged, so the
`--user` launch leaves the host procfs visible; bwrap's `--proc /proc` mounts a
fresh procfs and the jail sees only its own PIDs. This is the one containment
property where the backends genuinely differ; specs/cli.md documents it and
`test_live_unshare_user_exposes_host_proc` pins it.

**(b) The payload is namespace PID 2 under bwrap, not PID 1.**
bubblewrap's reaper occupies PID 1 of the jail; the payload runs as PID 2
(`--as-pid-1` is deliberately unused because it makes the payload PID 1 and
nullifies `--die-with-parent` — measured orphan on bubblewrap 0.11.1; see the
flag rationale at `standalone/terminal-jail`, `BWRAP_FLAGS` block). Under the
unshare backend `--fork` makes the payload namespace PID 1. Practical consequence:
`/proc/1` inside a bwrap jail is the reaper, not the payload.

**(c) FS isolation is DEGRADED on this host (AppArmor) — both backends run
mapping-less here.**
`scripts/fs-isolation-probe.py`: the mapped launch fails (`unshare: setgroups
failed: Operation not permitted`); both backends therefore print the loud
`no filesystem isolation` warning and provide PID-namespace containment +
identity-env scrub only. This is a host condition, not a backend difference.
Host-level remediation (requires root): `sysctl -w
kernel.apparmor_restrict_unprivileged_userns=0`, or add an AppArmor exception
for the launcher, or install `newuidmap`/`newgidmap` plus `/etc/subuid`/
`/etc/subgid` ranges for the calling user.

**(d) Teardown equivalence is host-measured, not a theorem.**
Both backends tore the payload down within the 20 ms poll granularity on this
host. The mechanisms differ (PR_SET_PDEATHSIG on bwrap's sandbox vs
`--kill-child=SIGKILL`); if either backend's parent-death linkage ever fails,
the battery's orphan cells (3–4) are the tripwire — an orphan reports
`DIFFERS` with the surviving pid named.

No cell was left unmeasured on this host; there are no intent markers in this
document. On hosts where bubblewrap is absent or namespaces are denied, the
battery reports the affected cells as `KNOWN-LIMIT ... UNMEASURED` instead of
guessing, and `plugin/test_backend_parity.py` skips the live cells with
`HOST-DEGRADED-*` markers.

## Kernel-matrix teardown status (TJ-DF-037)

The dev-host table above is **one kernel's measurement, not a multi-kernel
proof**. The committed runner for the orphan-teardown kernel matrix is
`scripts/kernel-matrix-teardown.py` (verdict vocabulary `PASS` / `FAIL` /
`UNMEASURED` / `UNAVAILABLE`; an unavailable kernel or backend is never
converted into a pass). Current, honest status of that matrix:

| Kernel | bwrap orphan teardown | unshare orphan teardown | Cell status |
|---|---|---|---|
| `7.0.0-31-generic` (this dev host) | PASS (battery cell 3, 20 ms) | PASS (battery cell 4, 20 ms) | MEASURED here — one host only |
| Debian 13.7 / `6.12.107` | observed PASS on the external host | observed FAIL (orphan) on the external host | **UNVERIFIED external cell** — raw output was produced on an ephemeral agent (see `docs/dogfood/2026-09-25-deploy-shim-systemd-probe.md`) and was **not attached to this repo**; the row stays unresolved until that raw output is imported |
| any third kernel | — | — | UNMEASURED — no measurement exists in this repo |

Matrix verdict: **NOT GREEN.** One host is measured here, one external kernel
awaits attached raw output, and no third kernel has any measurement. Release
claims must not describe the kernel matrix as green or as verified from this
repository.

### The live cell (current host, executable)

```console
$ cd /home/kara/terminal-jail
$ .venv/bin/python scripts/kernel-matrix-teardown.py            # human table
$ .venv/bin/python scripts/kernel-matrix-teardown.py --json     # machine rows
$ .venv/bin/python scripts/kernel-matrix-teardown.py --raw      # + evidence blocks
$ .venv/bin/python scripts/kernel-matrix-teardown.py --selftest # offline validator selftest
```

Each row carries `uname -r` (kernel), backend, verdict, post-wrapper-death
survival seconds, exit code, and raw evidence; launches are bounded (10 s
launch wait, 15 s teardown budget). The script executes only on the host it
runs on and never pretends to execute a remote kernel.

### Attaching an external kernel's raw output

Capture on the external kernel host (exact commands):

```console
$ git clone https://github.com/terminal-jail/terminal-jail && cd terminal-jail
$ uname -r                                                # record the kernel string
$ python3 scripts/kernel-matrix-teardown.py --json > cell-$(uname -r).json
$ # keep the raw console output of that run too (the evidence text)
```

Then import on any host (pure parsing + classification — no remote execution,
no network):

```console
$ .venv/bin/python scripts/kernel-matrix-teardown.py --import cell-6.12.107.json
```

Imported-file schema (v1): `{"rows": [row, ...]}` where each row is
`{"kernel": str, "backend": "bwrap"|"unshare", "verdict":
"PASS"|"FAIL"|"UNMEASURED"|"UNAVAILABLE", "survival_seconds": number|null,
"exit_code": int|null, "captured": str, "evidence": str}`. PASS/FAIL rows
must carry the observed numbers; UNMEASURED/UNAVAILABLE rows must carry
nulls; malformed rows are rejected (reported on stderr), never repaired.
The matrix counts as green only when **three or more distinct kernels** have
a complete, measured bwrap+unshare pair and every cell is PASS — a
single-host run can never satisfy this, by construction.

## How to re-run

```console
$ cd /home/kara/terminal-jail
$ .venv/bin/python scripts/backend-parity-battery.py          # human table
$ .venv/bin/python scripts/backend-parity-battery.py --json   # structured cells
$ .venv/bin/python scripts/kernel-matrix-teardown.py --json   # TJ-DF-037 matrix cell (this host)
$ .venv/bin/python -m pytest plugin/test_backend_parity.py -v # contracts + live cells
$ .venv/bin/python scripts/pidns-capability-probe.py          # host layer 1
$ .venv/bin/python scripts/fs-isolation-probe.py              # host layer 2
```

All commands run unprivileged. The battery always exits 0; read the verdicts,
not the exit status.
