# Composed deployment — terminal-jail inside a platform container

Terminal-jail is a building block, not a whole fortress. The strongest
deployment composes it with an outer containment layer: the tool running
**inside** a platform container (a bunker-agent container, or any OCI
container). The platform owns the ambient namespace and lifecycle primitives;
the tool owns per-command judgment. This page states the three configurations,
gives a runnable composed quickstart, and carries the **shared per-layer
guarantee matrix** — the same numbers must appear in the bunker repository's
copy of the matrix (bunker `DOC-043`).

The composed leg of this page was **live-verified with Docker** (Docker 28.5.2,
image `python:3.11-slim`) on host Ubuntu 26.04 / kernel 7.0.0-31; the plain-host
legs were verified with the repo's own CLI. Every command below was executed as
written and its output is quoted from the run.

---

## 1. The three configurations

| Configuration | Who owns the PID namespace / `/proc` / lifecycle | Who owns per-command judgment | Use it when |
|---|---|---|---|
| **Tool alone** (`terminal-jail` on a plain host) | **The tool** — it creates a private PID namespace per command (and a private `/proc` under the `bwrap` backend) | The tool (interruptor firewall + seccomp + identity scrub) | You already trust the host and want per-command verdicts, provenance, and a namespace boundary around each command |
| **Platform alone** (a bunker agent / OCI container, no tool) | **The platform** — its own PID namespace, its own procfs, its own lifecycle | Nobody (no per-command verdict; whatever the platform's own policy is) | You want a long-lived contained environment with lifecycle management, and no per-command firewall |
| **BOTH composed** (the tool inside the platform) | **The platform** — the tool does **not** add a namespace layer (`jail_layer=platform`) | The tool (firewall verdict + exit codes) | You want the platform's containment **plus** a per-command firewall inside it. This is the recommended production shape |

Additive, not exclusive: the composed stack is the platform's layer **plus** the
tool's firewall. Nothing about the tool replaces the platform, and nothing about
the platform replaces the tool.

---

## 2. Composed quickstart

### Platform requirement

Composed mode needs **no extra container capability**: the platform's own PID
namespace and procfs *are* the namespace layer, and the tool adds only its
firewall. This is the post-`TJ-GAP-089` behavior.

If instead you want the tool to create its **own** inner namespace layer inside
the container (private `/proc`, seccomp filter, mapped filesystem), the
container must permit inner namespace creation. Measured on this host with
`docker run --rm python:3.11-slim unshare --pid --fork --mount-proc true`:

| Container launch | Inner `unshare` | Why |
|---|---|---|
| plain | **rc=1** `unshare failed: Operation not permitted` | no `CAP_SYS_ADMIN` and the default seccomp profile denies the user namespace |
| `--cap-add SYS_ADMIN` | **rc=1** `cannot change root filesystem propagation: Permission denied` | user namespace created, but the container rootfs cannot be made a mount-proc parent |
| `--security-opt seccomp=unconfined` | **rc=1** `unshare failed: Operation not permitted` | seccomp alone does not grant `CAP_SYS_ADMIN` |
| `--privileged` | **rc=0** | inner namespaces permitted; the tool then runs its **own** jail (no composed report) |

So: **leave the container restrictive and let the platform own the namespace**
(the default below). Reach for `--privileged` only when you specifically want the
tool's own inner namespace, and understand that you have then widened the
container.

The jail backend is selected by the `TERMINAL_JAIL_JAIL_BACKEND`
(`auto|bwrap|unshare`) environment variable — there is **no `--backend` CLI
flag**. In composed mode the backend is irrelevant (no inner namespace is
created); an explicitly pinned backend still fails closed rather than silently
downgrading.

### The commands

Everything runs from the repository root. The repo is bind-mounted read-write so
the tool and its rules are visible inside the container.

A normal command — this runs, and prints the per-layer composed report on
stderr:

```bash
docker run --rm -v "$PWD:/tj" -w /tj python:3.11-slim \
  ./standalone/terminal-jail echo composed-ok
```

Expected stderr (quoted from the live run; the pid inode varies per container):

```text
sentinel: /.dockerenv present
namespace: /proc/self/ns/pid == /proc/1/ns/pid (pid:[4026538479]): this process already sits in the same PID namespace as the init above it
filesystem: root mount is overlayfs (/proc/self/mountinfo)
cgroup: /proc/self/cgroup path is / (cgroup v2 container root)
terminal-jail: COMPOSED MODE — running without an inner namespace
terminal-jail: composed layers — jail_layer=platform (outer containment: PID namespace/proc provided by the platform/container, NOT by this tool); firewall: enforced by terminal-jail (interruptor verdict applied); seccomp: NOT applied by this tool (the outer layer's own profile, if any, is the active seccomp state); filesystem: NOT isolated by this tool
```

A dangerous command — the firewall still blocks inside the container:

```bash
docker run --rm -v "$PWD:/tj" -w /tj python:3.11-slim \
  ./standalone/terminal-jail rm -rf /
```

Expected: **exit 126**, with the block provenance naming the rule:

```text
+--------------------------------------------------------------+
|  COMMAND BLOCKED — builtin-rm-rf-root
+--------------------------------------------------------------+
|  Recursive root directory removal (rm -rf /) is blocked.
|
|  Command: 'rm' '-rf' '/'
|  Rule: builtin-rm-rf-root
+--------------------------------------------------------------+
```

The **exit code is 126** and the verdict carries **`rule_id builtin-rm-rf-root`**
— this is the tool's contribution to the composed stack, and it is identical to
the plain-host verdict.

### Detection finds nothing (`auto`) vs the override

Composed mode is entered when namespace creation fails **and** an outer layer is
detected (`/.dockerenv`, `/run/.containerenv`, PID-ns identity, overlay root,
cgroup root). Two boundary behaviors, both measured:

- **`auto` + nothing detected** → the tool keeps the plain-host contract and
  **refuses**, exit 2, naming the cause and the options:

  ```text
  terminal-jail: namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user
  terminal-jail: cause: namespace creation needs privileges this context does not grant — a missing CAP_SYS_ADMIN (bit 21, e.g. inside a container: grep CapEff /proc/self/status) or a container seccomp/AppArmor profile denying unshare/unprivileged user namespaces …
  terminal-jail: options: … or set TERMINAL_JAIL_COMPOSED=on to run with the firewall plus the outer layer's containment (composed mode, see README "Composed deployment")
  ```

- **Override** `TERMINAL_JAIL_COMPOSED=on` → the command runs even where
  detection finds nothing, and the tool says loudly that no layer provides
  namespace isolation:

  ```bash
  docker run --rm -e TERMINAL_JAIL_COMPOSED=on -v "$PWD:/tj" -w /tj python:3.11-slim \
    ./standalone/terminal-jail echo override-ok
  ```

  ```text
  terminal-jail: WARNING: TERMINAL_JAIL_COMPOSED=on forced composed mode but no outer containment layer was detected — NO layer of this launch provides namespace isolation (operator decision)
  terminal-jail: COMPOSED MODE — running without an inner namespace
  terminal-jail: composed layers — jail_layer=platform claimed by operator override but NO outer layer detected: pid-namespace/proc NOT enforced by any layer in this launch; firewall: enforced by terminal-jail (interruptor verdict applied); seccomp: NOT applied by this tool; filesystem: NOT isolated by this tool
  ```

- **`off`** → plain-host behavior exactly: the refusal above, even inside a
  container:

  ```bash
  docker run --rm -e TERMINAL_JAIL_COMPOSED=off -v "$PWD:/tj" -w /tj python:3.11-slim \
    ./standalone/terminal-jail --no-interruptor echo x    # exit 2, refusal
  ```

- **A pinned backend is never silently downgraded.** Inside the container:

  ```bash
  docker run --rm -e TERMINAL_JAIL_JAIL_BACKEND=unshare -v "$PWD:/tj" -w /tj python:3.11-slim \
    ./standalone/terminal-jail --no-interruptor echo x    # exit 2, refusal
  ```

  ```text
  terminal-jail: namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user
  ```

  and with `TERMINAL_JAIL_JAIL_BACKEND=bwrap` in a slim container:
  `terminal-jail: TERMINAL_JAIL_JAIL_BACKEND=bwrap was requested but bubblewrap (bwrap) is not installed; command not run` (exit 2).

**Contracts that do not move in composed mode:** the firewall always applies; the
exit code is the command's own (a block is 126); `--seccomp` prints a loud
warning and does **not** apply the filter (the loader needs the inner namespace);
an explicitly requested backend still fails closed.

---

## 3. Shared per-layer guarantee matrix

The **same numbers** must appear in the platform repository's copy of this matrix
(bunker `DOC-043`). A change to one copy is a change to both.

Counts of `/proc` entries are the `proc_entry_count` property reported by
`scripts/composed-mode-battery.py`: **numeric PID directories** visible in
`/proc`, i.e. a live process-visibility count. It tracks what is running at the
instant of measurement, so the frozen 2026-10-01 snapshot values are annotated
`(measured 2026-10-01)`; the qualitative property — a handful of entries for a
private procfs vs a four-digit host view — is what the matrix asserts. Values
re-verified live on 2026-10-03 carry no annotation.

| Layer | Who enforces | Measured evidence | What the other layer does NOT give you |
|---|---|---|---|
| **LAYER 1 — platform / container** (bunker agent or any OCI container) | The platform: its own PID namespace, procfs, and lifecycle | own PID namespace — container `pid:[4026538479]` ≠ host `pid:[4026531836]`; private procfs — `/proc` entry count **4** `(measured 2026-10-01)`, `/proc/1 = bash`; lifecycle owned by the platform; uid 0 inside with the container capability set — `CapEff 00000000a80425fb` (`CAP_SYS_ADMIN`, bit 21, clear); outer seccomp profile present — `Seccomp: 2` | **No per-command verdict and no provenance.** The platform does not decide per command; it does not emit a `rule_id`, it does not firewall the command, and it does not tell you *why* something was refused |
| **LAYER 2 — tool on a plain host** | The tool: a per-command firewall verdict with provenance, an optional seccomp filter, an identity scrub, and (via `bwrap` only) a private procfs | per-command verdict with provenance — block **exit 126** + **`rule_id builtin-rm-rf-root`**; seccomp filter with `--seccomp` — `Seccomp: 2`, `CapEff 0000000000000000`; identity scrub with `--user` — `HOME=/nonexistent`, `USER=nobody`; private `/proc` **only** via the `bwrap` backend — `/proc` entry count **5** `(measured 2026-10-01)`, **`/proc/1 = bwrap`**; the `unshare --user` path exposes the **HOST** view — `/proc` entry count **1084** `(measured 2026-10-01)`, `/proc/1 = systemd`; on this host class the mapped-root route to a private procfs is closed (`uid_map` EPERM — Ubuntu AppArmor `unprivileged_userns`) | **No ambient lifecycle and no container-grade PID namespace of its own.** The tool creates a PID namespace per command; without `bwrap` it does **not** give a private `/proc`, and it never provides the platform's long-lived contained environment |
| **LAYER 3 — composed** (the tool inside the platform) | The platform owns the PID namespace, `/proc`, and lifecycle; the tool owns the firewall | the tool adds **no** inner namespace layer — stderr states `jail_layer=platform`; the firewall half works inside the container — `rm -rf /` → blocked, **`rule_id builtin-rm-rf-root`**, **exit 126**; inner seccomp **not** applied (`--seccomp` warns); filesystem **not** isolated by the tool | **Nothing extra from the tool on the namespace axis.** In composed mode the tool provides *only* per-command judgment — it does **not** provide a PID namespace, a private `/proc`, lifecycle containment, an inner seccomp filter, or filesystem isolation |

---

## 4. Per-layer attribution warnings

The composed configuration is exactly where over-claiming happens, so the
attribution is stated plainly:

- In composed mode terminal-jail **does not provide a PID namespace** and **does
  not provide a private `/proc`**. Those are the platform's; the tool's own
  stderr says so: `jail_layer=platform`.
- In composed mode terminal-jail **does not apply a seccomp filter** and **does
  not isolate the filesystem**. The active seccomp state, if any, is the
  container's own profile; `--seccomp` prints a warning and is a no-op.
- What terminal-jail **does** provide in composed mode is the per-command
  firewall: a verdict, a `rule_id`, and exit 126 on a block. Never describe the
  composed stack as "terminal-jail gives you PID-namespace containment inside a
  container" — that property belongs to the platform.
- Conversely, the platform alone gives you **no per-command verdict and no
  provenance**. Never describe a bunker agent as providing a firewall.
- On a **plain host** without `bwrap`, the tool provides per-command containment
  and a namespace lifecycle, but **not** a private `/proc` — the `unshare --user`
  path exposes the host's `/proc` (see LAYER 2 above). Only the `bwrap` backend
  gives a private `/proc` on a plain host.

---

## 5. Cross-links and pinning

**Local (terminal-jail) rows**

- `TJ-GAP-089` — composed mode (the fix that makes the composed stack work
  instead of refusing everything).
- `TJ-GAP-088` — private `/proc` ownership (which layer owns `/proc`).
- `TJ-GAP-082` — the Landlock tier (a separate, optional hardening tier).
- `TJ-GAP-090` — onboarding proven end-to-end (the reader's path into the jail).

**Platform (bunker) rows**

- `GAP-179` — private `/proc` ownership on the platform side (what the
  bunker-agent container must permit and expose for the inner layer to add
  value).
- `DOC-043` — the platform-side copy of this composed-stack documentation. It
  **must carry the identical per-layer guarantee matrix** (the same numbers as
  §3 above); the two copies are one source of truth and each names the other. A
  change to one is a change to both.

**Pinning.** `tests/test_composed_doc.py` reads this file and asserts the pinned
strings (the matrix numbers, the layer rows, `/proc/1 = bwrap`, **exit 126**,
`rule_id builtin-rm-rf-root`, `GAP-179`, `DOC-043`) so the numbers cannot drift
silently. The live measurement behind the matrix is
`scripts/composed-mode-battery.py` (tool alone / platform alone / BOTH); the
2026-10-03 Docker transcript is in
[`docs/dogfood/2026-10-03-composed-mode.md`](dogfood/2026-10-03-composed-mode.md).
