## Prompt: Install Terminal-Jail on karaHermes

Run the following on karaHermes-mde-7840hs (Ubuntu 26.04, kernel 7.0.0-27).
You have sudo. Do NOT restart the gateway until all steps are verified.

---

### Step 1 — Install the shell wrapper

```bash
sudo cp /home/kara/terminal-jail/standalone/terminal-jail /usr/local/bin/terminal-jail-bash
sudo chmod 755 /usr/local/bin/terminal-jail-bash
```

### Step 2 — Install the SHELL shim (handles -lic invocation)

The Hermes terminal tool invokes the shell as: `bash -lic "set +m; {command}"`. We need a thin
wrapper that extracts the command, runs it through the interruptor, wraps it in the CLI's jail
(`--user --seccomp`; the backend — `unshare`, or the optional bubblewrap one with a private
`/proc` — is chosen by the CLI at runtime, see `specs/cli.md` §4 "Jail backends"), and execs.
The canonical wrapper lives in this repo at `standalone/terminal-jail-sh` — install it from there
(do NOT copy a script by hand; the repo copy is the maintained one):

```bash
sudo install -m 755 /home/kara/terminal-jail/standalone/terminal-jail-sh /usr/local/bin/terminal-jail-sh
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
