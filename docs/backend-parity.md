# Backend parity: bwrap vs unshare — measured evidence (TJ-GAP-056)

This document records what the parity battery (`scripts/backend-parity-battery.py`)
actually **measured** on the host below. It is evidence, not a plan. The battery is
a classifier in the house style of `scripts/pidns-capability-probe.py` and
`scripts/fs-isolation-probe.py`: it always exits 0 and never gates anything.

**Method note (TJ-GAP-088): an auto-backend run is NOT evidence about the
unshare path.** `TERMINAL_JAIL_JAIL_BACKEND=auto` (the default) prefers bwrap
whenever it is installed and its probe passes, so on this host an unqualified
`./standalone/terminal-jail …` run exercises **bwrap** — a pass proves nothing
about what the `unshare` backend would have done. Claims about the unshare
path require a **forced** run (`TERMINAL_JAIL_JAIL_BACKEND=unshare`); the
earlier "bare mode" probe that motivated this note was in fact the auto
backend. Every launch now names the view it delivered on stderr
(`proc_view=private|host|platform-owned|none`), so a run's /proc evidence is
read off its own output instead of inferred from the absence of a flag.

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
`test_live_unshare_user_exposes_host_proc` pins it. **Nothing stops a
deployment that assumes containment from silently getting the host view by
default** — which is exactly why the demand exists (below) and every launch
now attributes its view (`proc_view=host` on this path, read off stderr).

**The enforceable demand and per-run attribution (TJ-GAP-088).** A deployment
that NEEDS private procfs says so explicitly: `--private-proc` (CLI flag) or
`TERMINAL_JAIL_PRIVATE_PROC=required` (env, same effect). With the demand set,
backend selection **fails closed** — exit 2, command not run — unless the
resolved backend can deliver a private procfs: bwrap absent, a failing bwrap
probe, any `unshare` launch, and the composed launch (no inner procfs) all
refuse. Without the demand, behavior is unchanged (the limit above stays
prose-only). Independently of the demand, **every launch states the delivered
view on stderr**: `proc_view=private` (bwrap), `proc_view=host` (unshare),
`proc_view=platform-owned` (composed; the outer layer's procfs), or
`proc_view=none` (composed forced with no outer layer). Standing probe:
battery cells 1–2 (entry count + `/proc/1` identity per backend), cell 8
(the demand enforced, fail-closed, host-independent), cell 9 (the
attribution, host-independent).

**(b) The payload is namespace PID 2 under bwrap, not PID 1.**
bubblewrap's reaper occupies PID 1 of the jail; the payload runs as PID 2
(`--as-pid-1` is deliberately unused because it makes the payload PID 1 and
nullifies `--die-with-parent` — measured orphan on bubblewrap 0.11.1; see the
flag rationale at `standalone/terminal-jail`, `BWRAP_FLAGS` block). Under the
unshare backend `--fork` makes the payload namespace PID 1. Practical consequence:
`/proc/1` inside a bwrap jail is the reaper, not the payload. (The signal-reach
consequences of that shape are measured in their own section below.)

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

**(e) TJ-DF-043 — the uid-mapped unshare launch loses its parent-death
signal to its own credential change (FIXED with a setpriv re-arm tail).**

Root cause, named: util-linux arms `--kill-child=SIGKILL`'s
`prctl(PR_SET_PDEATHSIG)` in the forked child **before** the
`setgroups`/`setgid`/`setuid` that `-S`/`-G` request (observed order on the
failing host with an LD_PRELOAD syscall-order shim: `prctl(PR_SET_PDEATHSIG)
→ setgroups(0) → setgid(65534) → setuid(65534) → exec payload`). The kernel
**clears** the parent-death setting on any thread-credential change (man 2
prctl, PR_SET_PDEATHSIG: "cleared upon changes to any of the following
thread credentials: effective user ID, effective group ID, filesystem user
ID, or filesystem group ID"; `kernel/cred.c` `commit_creds()`:
`task->pdeath_signal = 0`). After the `-S/-G` change the payload therefore
runs with NO parent-death linkage, and as namespace PID 1 the kernel's
namespace-exit reaping does not apply to it either: when the wrapper is
SIGKILLed the payload survives as a real orphan. Fix: the mapped launch ends
with a `setpriv --pdeathsig=SIGKILL` exec tail that re-arms the signal AFTER
the credential changes; the probe flags are identical to the launch flags,
so a host without a capable `setpriv` fails the probe and falls back
mapping-less loudly (never silently). Measured on Debian 13.7 /
`6.12.107+deb13-amd64` (bunker-las-03): mapped launch orphaned (survived the
5 s budget on every repetition); with the re-arm tail the payload was gone
in 20 ms. The mapping-less `--user` launch never had the defect — its
payload keeps the caller's kuid, so the dying parent's kernel-side
permission check (`kill_ok_by_cred`, kernel/signal.c) passes by uid
equality.

Why the dev host never saw it: this host's AppArmor policy
(`unprivileged_userns`) denies `setuid`/`setgroups` inside unprivileged
user namespaces, so the mapped launch **cannot be created here at all** —
the probe fails, the wrapper falls back mapping-less, and every green
dev-host teardown run exercised only the mapping-less shape. "Passes on the
dev host" was structurally blind to the failing shape; only hosts where the
mapped launch is creatable (Debian 13) could reach the bug. This is a
launch-shape defect, not a kernel-version divergence: the kernel code at
both sites (`kernel/cred.c` clear, `kernel/exit.c`
`forget_original_parent` delivery, `kernel/signal.c` permission check) is
byte-identical between v6.12 and v7.0 (diffed against the raw sources).

No cell was left unmeasured on this host; there are no intent markers in this
document. On hosts where bubblewrap is absent or namespaces are denied, the
battery reports the affected cells as `KNOWN-LIMIT ... UNMEASURED` instead of
guessing, and `plugin/test_backend_parity.py` skips the live cells with
`HOST-DEGRADED-*` markers.

**(f) TJ-GAP-089 — composed mode: inside a container the backends are
unreachable by design, and the tool composes instead of refusing.**
Measured in `docker run --rm python:3.11-slim` (the bunker-agent stand-in,
bunker GAP-179): no `CAP_SYS_ADMIN` (CapEff `00000000a80425fb`, bit 21 clear)
and the container seccomp profile (host Seccomp state 2) deny inner namespace
creation — BOTH backends' launch (`unshare --pid --fork …` and the mapped
`--user` shape) fail with EPERM in ~1–2 ms, so neither backend can run there
and the plain-host contract would refuse every command. Composed mode
(`TERMINAL_JAIL_COMPOSED=auto|on|off`, default `auto`) detects the outer
layer and runs the command with firewall (tool) + platform namespace
containment, stating per layer what is enforced (`jail_layer=platform`;
seccomp explicitly NOT applied by the tool). The launcher-level parity table
above describes what each backend provides; composed mode is the documented
alternative when NEITHER backend can run. Three-cell battery:
`scripts/composed-mode-battery.py` (host / platform / both, per-layer
properties); live transcript: `docs/dogfood/2026-10-03-composed-mode.md`.
Launch-probe budgets are 3s (was 15s): inside a container the failed mapped
launch's forked child can survive as a zombie holding the capture pipe, so
probes answer by timeout — a capable host answers in milliseconds.

## Signal reach boundary (bwrap private /proc) — REVIEW-TJ-009

A premise reached the board claiming that inside a `--unshare-pid` bwrap jail
with a private `/proc`, "the payload CAN still signal host processes via their
host PIDs" (kill -0 1 succeeding as the evidence). **The premise output
reproduces exactly; the host-reach interpretation attached to it is DISPROVEN
by measurement.** This section states what is actually true, so neither
containment nor its absence is over-claimed.

The measured boundary on the evidence host (bubblewrap 0.11.1, kernel
`7.0.0-31-generic`, 2026-10-06):

1. **`kill -0 1` succeeds — but it is a namespace-internal signal, not host
   reach.** Direct launch (bypassing the wrapper's preflight, which on this
   host refuses unprivileged namespaces for the wrapper while direct bwrap
   works):

   ```console
   $ bwrap --proc /proc --dev /dev --unshare-pid \
       --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib \
       --ro-bind /lib64 /lib64 --ro-bind /etc /etc \
       bash -c 'kill -0 1 && echo CAN-SIGNAL-PID1; ps -p 1 -o comm='
   CAN-SIGNAL-PID1
   bwrap
   ```

   The `kill -0` succeeds because **pid 1 in that jail is bwrap's own reaper**
   (see known limit (b): the payload is namespace PID 2) — the same-namespace
   permission check passes trivially. Even `kill -TERM 1` reports success while
   the reaper ignores it (uncaught non-fatal signals to PID 1 are dropped by
   the kernel). This says nothing about signaling the host.

2. **The PID namespace is NOT shared with the host.** Measured directly, not
   inferred:

   ```console
   $ readlink /proc/self/ns/pid                 # host
   pid:[4026531836]
   $ bwrap --proc /proc --dev /dev --unshare-pid ... bash -c \
       'readlink /proc/self/ns/pid'             # jail
   pid:[4026536176]
   ```

   `--unshare-pid` does what it says. Because the namespaces differ, host PIDs
   are not even addressable from inside the jail.

3. **A live host process is unreachable from inside — the sharpest test.** A
   plain `sleep` was started on the host (host pid 184986, alive, same uid as
   the jail), and the jail payload was pointed at that pid:

   ```text
   kill -0 <host-pid>   -> bash: kill: (184986) - No such process   (ESRCH)
   kill -TERM <host-pid>-> same ESRCH; the host process SURVIVED
   ls /proc | grep -c '^[0-9]'  ->  4 (the private view; the host process is
                                   not in it)
   ```

   The signal returned ESRCH — there is no process with that number in the
   jail's namespace — and the host `sleep` was still alive afterwards. So the
   truthful statement is the inverse of the premise: **the bwrap jail cannot
   signal host processes by host PID; what it CAN do is signal namespace-local
   pids (the reaper at pid 1, the payload at pid 2), which is what the
   succeeding `kill -0 1` actually measured.**

Honest attribution: this is one host's measurement (dev host, mapping-less
shape per known limit (c)); battery cell 10 re-measures the boundary on
whatever host it runs on and flags any divergence as `DIFFERS`. It is a
signal-reach boundary of the *direct* bwrap shape — the same shape and
`--proc /proc` caution as cell 1 apply. The pdeathsig/credential discussion
(known limit (e)) covers the parent-death linkage direction; the composed-mode
known limit (f) covers what happens when no backend can run at all. Nothing
here changes TJ-GAP-088's unshare proc leak — that limit is about the *view*
(`--user` exposing the host procfs), this section is about *signals*. The two
must not be conflated, and the unshare arm was measured too so the contrast
is exact: under `unshare --user --pid --fork` the host `/proc` IS visible
(1117 entries; `/proc/<host-pid>/comm` of the live marker READS as `sleep`)
yet signaling that same live host pid still returns ESRCH and the process
survives — the view leaks, the signal path does not, because `--pid` creates
a new PID namespace and signal delivery follows the namespace translation,
not the procfs view. Visibility is not reachability: NEITHER backend can
signal host processes from inside its jail on this host; the backends differ
only in what they let the payload SEE.

## Kernel-matrix teardown status (TJ-DF-037)

The dev-host table above is **one kernel's measurement, not a multi-kernel
proof**. The committed runner for the orphan-teardown kernel matrix is
`scripts/kernel-matrix-teardown.py` (verdict vocabulary `PASS` / `FAIL` /
`UNMEASURED` / `UNAVAILABLE`; an unavailable kernel or backend is never
converted into a pass). Current, honest status of that matrix (post
TJ-DF-043 fix — the fix's per-cell raw evidence is in the repo at
`docs/dogfood/tjdf043-kernel-cells/`, importable via the documented
`--import` path):

| Kernel | bwrap orphan teardown | unshare orphan teardown | Cell status |
|---|---|---|---|
| `7.0.0-31-generic` (this dev host) | PASS (battery cell 3, 20 ms) | PASS (battery cell 4, 20 ms) | MEASURED here — one host only. NOTE: the dev host cannot create the uid-mapped launch (AppArmor), so this row exercises the mapping-less shape only |
| `6.12.107+deb13-amd64` (bunker-las-03, Debian 13.7) | PASS (0 ms) | **FAIL pre-fix (orphan >5 s, reproduced 3×; PASS 20 ms post-fix)** | MEASURED externally 2026-10-02 — raw cells committed under `docs/dogfood/tjdf043-kernel-cells/`; the pre-fix FAIL cell stays in the matrix as the regression's record |
| `6.12.101+deb13-amd64` (bunker-las-02, Debian 13.7) | PASS (0 ms) | **FAIL pre-fix (orphan >5 s, reproduced 2×; PASS 20 ms post-fix)** | MEASURED externally 2026-10-02 — same raw-cell location |
| any third kernel | — | — | UNMEASURED — no measurement exists in this repo |

Matrix verdict: **NOT GREEN** (2 complete kernels of the required ≥3), but
the TJ-DF-043 orphan signature is now **root-caused and fixed at the launch
shape**, with both reachable 6.12 hosts flipping PASS under the fixed
wrapper. The pre-fix FAIL cells are deliberately retained as evidence.

### TJ-DF-043 release-hold re-evaluation (RELEASE-TJ-008 blocker 1 of 3)

The QA-TERMINAL-JAIL-13 hold — recorded as the first blocker of the P0
release hold RELEASE-TJ-008 ("hold v1.3.0 candidate … blockers unchanged:
QA-TERMINAL-JAIL-13 failed, no artifact channel, no cut authorization") —
is RESOLVED by the fix, not re-scoped:

- Root cause was NAMED with kernel citations (man 2 prctl
  PR_SET_PDEATHSIG credential-clearing rule; `kernel/cred.c`
  `commit_creds()` `task->pdeath_signal = 0`) and demonstrated with a
  minimal reproducer on the failing kernel (LD_PRELOAD syscall-order shim
  showing the arming-before-cred-change order, plus the mapped-vs-mapping-less
  teardown split on the same kernel). It was never a kernel-version
  divergence: the relevant kernel code is byte-identical v6.12 ↔ v7.0.
- The failing kernel cells are now MEASURED in this repo (raw rows above),
  the fix is verified ON those kernels (20 ms teardown 3/3, mapped shape
  confirmed live), and the regression is pinned four ways: the argv-level
  re-arm-tail tests (`plugin/test_tjdf043_pdeathsig_rearm.py`, the
  interruptor launch-contract fixtures rejecting the tail-less shape),
  the live parity cell (`test_live_unshare_orphan_teardown` — meaningful
  only on hosts that can create the shape), the harness gate
  (`scripts/kernel-matrix-teardown.py --gate`, CI cell), and the retained
  prefix FAIL cells as the fixed evidence baseline.
- Remaining honesty constraint: the matrix is 3 kernels ONLY when the two
  Debian cells are imported alongside a dev-host run; the committed cells
  are external measurements (captured by the documented protocol), and a
  future release claim of "matrix green" still requires a THIRD kernel
  with a complete measured pair per the harness's own rule. The orphan
  DEFECT itself — the thing the hold was about — no longer exists at
  HEAD on any kernel we can reach or reason about: the tail-less shape is
  rejected by contract tests, and the shape actually launched re-arms the
  signal after its credential change.
- Verdict for RELEASE-TJ-008: blocker 1 (QA-TERMINAL-JAIL-13) CAN LIFT on
  the strength of this evidence. Blockers 2 and 3 (no artifact channel, no
  cut authorization) are outside this tool's ownership and stay as
  recorded by the releng sweep. The strong lifecycle guarantee — that a
  SIGKILLed launcher can NEVER leave a payload — remains the PLATFORM's
  guarantee (bunker: cgroup/pid-namespace supervision); this tool's
  on-any-host guarantee is the narrowed one, stated here and enforced by
  the contract pins: the launched shape always carries a re-armed
  parent-death signal, and any launch shape that cannot hold it is
  refused at the probe (fail-closed), never silently selected.

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
