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

## How to re-run

```console
$ cd /home/kara/terminal-jail
$ .venv/bin/python scripts/backend-parity-battery.py          # human table
$ .venv/bin/python scripts/backend-parity-battery.py --json   # structured cells
$ .venv/bin/python -m pytest plugin/test_backend_parity.py -v # contracts + live cells
$ .venv/bin/python scripts/pidns-capability-probe.py          # host layer 1
$ .venv/bin/python scripts/fs-isolation-probe.py              # host layer 2
```

All commands run unprivileged. The battery always exits 0; read the verdicts,
not the exit status.
