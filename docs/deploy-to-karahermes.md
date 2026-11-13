## Prompt: Install Terminal-Jail on karaHermes

Run the following on karaHermes-mde-7840hs (Ubuntu 26.04, kernel 7.0.0-27).
You have sudo. Do NOT restart the gateway until all steps are verified.

---

### Measured host state before you start (ops tick 2026-11-10)

There are **three** ways terminal-jail can be installed on this host. Check which one you are
actually touching before you believe any `--version` output:

| surface | path | measured 2026-11-10 |
| --- | --- | --- |
| current user install | `~/.local/bin/terminal-jail` | `terminal-jail 1.3.3`, landlock-loader sha256 `1eb4a20d4ecd72e79aff1cb3321362041e50a776e3293b836b7cda798f5d416b` = repo at v1.3.3 |
| legacy host install (this doc, steps 1-2) | `/usr/local/bin/terminal-jail-sh`, `/usr/local/bin/terminal-jail-bash` | `terminal-jail 1.0.0`, bytes dated 2026-07-24 — stale, and the Step 4 unit is **not installed** (`systemctl list-units --all | grep -c terminal-jail` = 0, no live process, gateway `SHELL=/bin/bash`), so nothing runs it |
| test residue | `/tmp/tj-test-pack2/terminal-jail` | `terminal-jail 1.2.0`, dated 2026-10-01, **first on PATH** |

That third row is the trap: `~/.profile` still carries five PATH exports appended by earlier
verification runs (`/tmp/tj-stranger-bin`, `/tmp/tj-test-pack`, `/tmp/tj-test-pack2`,
`/tmp/tjtest/bin`, `/var/tmp/hermes-scratch/tmp.MYYkb9cBrh/prefix`), so `which terminal-jail` and
`terminal-jail --version` report a `/tmp` build, not the host install. Three of those targets no
longer exist after `/tmp` cleanup, so the entries are dead weight as well as a shadow.

When you verify an install, always probe the absolute path (`/home/kara/.local/bin/terminal-jail
--version`) and hash the file — never the bare command name. And when a step needs a temporary
PATH, scope it to the command (`env PATH="/tmp/x/bin:$PATH" cmd`) or export it inside the worktree
wrapper: never append `export PATH=…` lines to `~/.profile`, because they outlive the run and
silently re-point every future shell (including agent tool shells) at throwaway binaries.

---

## Steps 1–2 are RETIRED (ops tick 2026-11-13)

The `/usr/local` host install is retired. Do **not** install it. Measured on karaHermes 2026-11-13:

| path | `--version` | bytes | sha256 vs tag v1.3.3 |
| --- | --- | --- | --- |
| `/usr/local/bin/terminal-jail-sh` | `1.0.0` | 2094 B, 2026-07-24 | `9a29ecd396d1…` ≠ tag `35e6855e46e5…` |
| `/usr/local/bin/terminal-jail-bash` | `1.0.0` | 8068 B, 2026-07-24 | `35b816a23d3b…` ≠ tag `5afe5e52dbdf…` |
| `~/.local/bin/terminal-jail` (supported) | `1.3.3` | 86885 B, 2026-11-10 | `VERSION_DEFAULT` baked `1.3.3` at install time |

Those shims are dormant: `/etc/systemd/system/hermes-gateway.service.d/` holds
`90-terminal-jail-hardening.conf`, `99-tasks-max.conf` and `signal-dependency.conf` but **no**
`95-terminal-jail-shell.conf`, `systemctl show hermes-gateway -p Environment` is empty, and
`hermes-gateway.service` is `ActiveState=inactive`, `MainPID=0` (no unit file present). Tool shells
run as transient `hermes-worker-proc_*.scope` units invoking `/bin/bash -lic` directly, so no shell
ever passes through the retired shims — their staleness is a supply-of-record defect, not an outage.
The supported install is the user install, which needs no root:

```bash
./install.sh          # installs ~/.local/bin/terminal-jail (currently 1.3.3)
```

If you ever deliberately re-install the shim, install it **from tag v1.3.3** and record the per-file
sha256 — never from a working tree that may be mid-edit.

---

### Step 1 — Install the shell wrapper — RETIRED, do not run

```bash
# RETIRED 2026-11-13: this installed /usr/local/bin/terminal-jail-bash, now stale at 1.0.0.
# Use ./install.sh (user install -> ~/.local/bin/terminal-jail) instead.
# sudo cp /home/kara/terminal-jail/standalone/terminal-jail /usr/local/bin/terminal-jail-bash
# sudo chmod 755 /usr/local/bin/terminal-jail-bash
```

### Step 2 — Install the SHELL shim (handles -lic invocation) — RETIRED, do not run

The Hermes terminal tool invokes the shell as: `bash -lic "set +m; {command}"`. We need a thin
wrapper that extracts the command, runs it through the interruptor, wraps it in the CLI's jail
(`--user --seccomp`; the backend — `unshare`, or the optional bubblewrap one with a private
`/proc` — is chosen by the CLI at runtime, see `specs/cli.md` §4 "Jail backends"), and execs.
The canonical wrapper lives in this repo at `standalone/terminal-jail-sh`. The `/usr/local`
destination is **retired** (see the retirement note above) — do not install it there:

```bash
# RETIRED 2026-11-13: lands a dormant, unversioned copy in /usr/local. Do not run.
# sudo install -m 755 /home/kara/terminal-jail/standalone/terminal-jail-sh /usr/local/bin/terminal-jail-sh
```

The wrapper resolves its base directory relative to the repo checkout when present, and falls back
to `/usr/local/lib/terminal-jail` (override with `TERMINAL_JAIL_HOME` / `TERMINAL_JAIL_BRIDGE` /
`TERMINAL_JAIL_CLI`). On hosts without `setpriv` it degrades gracefully.

Empty-command invocation (`-lic` with no command string, the interactive/login form — e.g. the
command text arrives on stdin) has nothing to evaluate: the shim prints a one-line stderr notice
(`terminal-jail: no command string — running unwrapped (no firewall, no namespace)`) and execs an
UNWRAPPED `/bin/bash` — no interruptor firewall, no namespace, no seccomp (TJ-DF-031). Only the
`-c "command"` form is jailed; a gateway that must jail every command must always invoke the shim
with `-c`.

### Step 3 — Verify the shim works

> The `/usr/local/bin/terminal-jail-sh` paths below assume the **retired** legacy install. If you did
> not reinstall the shim from tag v1.3.3 (see the retirement note), run the repo copy instead:
> `standalone/terminal-jail-sh -c "..."` from the checkout — that is the same file, at the current tag.

```bash
# Test: simple command
/usr/local/bin/terminal-jail-sh -c "echo hello"
# Expected: "hello"

# Test: blocked command
/usr/local/bin/terminal-jail-sh -c "rm -rf /"
# Expected: error box, exit 126

# Test: sandboxed command — the jail must run in its OWN PID namespace.
# The shell's PID inside the jail depends on the backend chosen at runtime
# (specs/cli.md §4 "Jail backends"): unshare → 1; bwrap / auto (host has
# bwrap) → 2, because PID 1 inside the jail is bwrap itself. So do NOT
# assert a specific PID — compare namespace inodes instead (same check as
# the README smoke test):
readlink /proc/self/ns/pid
# host pid-ns inode, e.g. pid:[4026531836]
/usr/local/bin/terminal-jail-sh -c "readlink /proc/self/ns/pid"
# Expected: a DIFFERENT pid:[...] inode than the host's — that is the proof
# the jail has its own PID namespace, whichever backend was chosen.
```

Measured on this host (2026-10-07): the wrapper needs installing first, so the
probes ran the repo checkout copy `standalone/terminal-jail-sh` directly — the
exact file Steps 1–2 install. Backend `auto` → bwrap here:

```text
$ standalone/terminal-jail-sh -c "echo pid inside jail: \$\$"
terminal-jail: WARNING: no filesystem isolation — could not create a uid mapping under the user namespace (no filesystem isolation: this host denies setuid inside unprivileged user namespaces, e.g. Ubuntu AppArmor profile 'unprivileged_userns'; see scripts/fs-isolation-probe.py)
terminal-jail: proc_view=private (bwrap backend: fresh procfs via --proc /proc)
pid inside jail: 2
$ readlink /proc/self/ns/pid
pid:[4026531836]
$ standalone/terminal-jail-sh -c "readlink /proc/self/ns/pid"
terminal-jail: WARNING: no filesystem isolation — could not create a uid mapping under the user namespace (no filesystem isolation: this host denies setuid inside unprivileged user namespaces, e.g. Ubuntu AppArmor profile 'unprivileged_userns'; see scripts/fs-isolation-probe.py)
terminal-jail: proc_view=private (bwrap backend: fresh procfs via --proc /proc)
pid:[4026536180]
```

The jail inode (`pid:[4026536180]`) differs from the host inode
(`pid:[4026531836]`) — that is the isolation proof. The shell prints PID 2
because PID 1 inside the jail is bwrap itself; under the `unshare` backend it
would print 1. The invariant to check is the differing inode, not the number.

### Step 4 — Deploy systemd hardening (Phase 5)

First, verify what THIS host's systemd actually accepts and enforces (TJ-GAP-052).
The probe launches throwaway transient units only — it never touches the gateway
unit, never writes under `/etc`, and never reloads the manager:

```bash
python3 /home/kara/terminal-jail/scripts/systemd-directive-probe.py --json
```

Read the verdicts before copying anything: `ENFORCED` = accepted and observed
enforced; `NOT_ENFORCED` = accepted but the effect was not observed (expected in
the USER scope for ProtectHome/ProtectSystem/ProtectProc/ProtectControlGroups —
the user manager under-enforces mount-namespace directives; the system scope
enforces them); `UNSUPPORTED` = rejected at load (the `CloseOnExec=true`
negative control must classify UNSUPPORTED); `UNKNOWN` = probe could not tell.
See the "Per-host verification" section of `specs/systemd.md` for the verdict
model. Only proceed when the directives you are about to activate are ENFORCED
under the manager scope that will run the gateway service (the system scope,
since the gateway runs as a system service).

Then copy the drop-in:

```bash
sudo mkdir -p /etc/systemd/system/hermes-gateway.service.d
sudo cp /home/kara/terminal-jail/systemd/90-terminal-jail-hardening.conf \
    /etc/systemd/system/hermes-gateway.service.d/
```

### Step 5 — Update gateway unit to use the jail SHELL

> **Blocked by the retirement (2026-11-13).** `SHELL=/usr/local/bin/terminal-jail-sh` points at the
> retired path, which is stale (1.0.0) and will not be reinstalled by default. Do not run this step
> until the shim has been reinstalled **from tag v1.3.3** at a stable path and Steps 1–3 pass against
> it. Measured state: `/etc/systemd/system/hermes-gateway.service.d/` has no
> `95-terminal-jail-shell.conf`, `systemctl show hermes-gateway -p Environment` is empty, and
> `hermes-gateway.service` reports `ActiveState=inactive`, `MainPID=0` — this host runs the gateway
> outside systemd (tool shells are transient `hermes-worker-proc_*.scope` units), so there is no unit
> to add this override to until that is resolved.

```bash
sudo mkdir -p /etc/systemd/system/hermes-gateway.service.d
sudo tee /etc/systemd/system/hermes-gateway.service.d/95-terminal-jail-shell.conf << 'UNIT'
[Service]
Environment="SHELL=/usr/local/bin/terminal-jail-sh"
UNIT
```

### Step 6 — Reload and restart

```bash
sudo systemctl daemon-reload
sudo systemctl restart hermes-gateway
sleep 5
systemctl status hermes-gateway --no-pager -l | head -20
```

### Step 7 — Verify isolation

```bash
# Check that SHELL is set
systemctl show hermes-gateway -p Environment | grep SHELL

# Check that systemd hardening is active
systemd-analyze security hermes-gateway --no-pager 2>/dev/null | tail -5
```

### Rollback (if anything breaks)

```bash
sudo rm /etc/systemd/system/hermes-gateway.service.d/95-terminal-jail-shell.conf
sudo systemctl daemon-reload
sudo systemctl restart hermes-gateway
```

---

**Post-install:** Tell me the output of Step 3 and Step 7 so I can verify.
