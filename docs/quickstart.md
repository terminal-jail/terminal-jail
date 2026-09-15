# Terminal Jail Quick Start

## 1. Problem statement

Hermes Agent (and any LLM agent) runs terminal commands with the privileges
of its host account. A single destructive command — `rm -rf /`, `dd
of=/dev/sda`, `mkfs.*`, a fork bomb, `curl | sh` — can destroy the host or
its data. **Terminal Jail** is a defense-in-depth toolkit that contains
terminal commands: it puts them in a PID namespace, filters dangerous
patterns before execution, drops privileges, and applies a seccomp filter.

It is *defense in depth*, not a full sandbox: each layer contributes a
specific property, and no single layer is a complete security boundary (see
[docs/threat-model.md](threat-model.md) for what is and is not guaranteed).

## 2. Which component is for you?

| You want to... | Use | How |
|---|---|---|
| Contain a single command in a PID namespace, manually | **Standalone CLI** (`standalone/terminal-jail`) | `terminal-jail <command> [args...]` |
| Block dangerous patterns before they run (firewall) | **Interruptor** (built into the CLI, on by default) | `terminal-jail rm -rf /` → blocked, exit 126 |
| Add privilege dropping + syscall filtering | **CLI flags** | `terminal-jail --user --seccomp <command>` |
| Observe + log Hermes terminal commands (byte budget reserved — not implemented) | **Hermes plugin** (`plugin/terminal_jail/`) | See §4 |
| Harden the Hermes gateway service itself | **systemd drop-in** (`systemd/90-terminal-jail-hardening.conf`) | See §5 — lightweight (4 directives), NOT a PID namespace boundary |
| Replace the Hermes gateway shell with a jailed shell | **Deploy shim** (`standalone/terminal-jail-sh` + `docs/deploy-to-karahermes.md`) | Host-specific; hardcoded paths must be adjusted |

**TL;DR:** individual commands → standalone CLI. Firewall → interruptor
(default on). The gateway service → systemd drop-in + plugin. Full
PID-namespace containment for everything Hermes runs → deploy shim
(see the deploy guide).

## 3. Install and verify

### 3a. Standalone CLI

```bash
# From source (recommended until release assets are published)
git clone https://github.com/totalwindupflightsystems/terminal-jail.git
cd terminal-jail
./install.sh        # installs to ~/.local/bin/terminal-jail (no root needed)
```

Release-mode downloads (wrapper + SHA-256 from a published release) are
**opt-in only**: set `TERMINAL_JAIL_USE_RELEASE=1` (with
`TERMINAL_JAIL_BASE_URL` if you host assets yourself). Without the flag the
installer refuses rather than hitting the dead default release URL — release
assets are not published yet.

**Step 1 — classify the host** (the probe always exits 0):

```bash
~/.local/bin/terminal-jail --version   # → terminal-jail 1.1.0
python3 scripts/pidns-capability-probe.py
# FULL     → the host can create unprivileged PID namespaces — bare mode works
# DEGRADED → it cannot (bare mode exits 2, fail-closed) — use --user
# UNKNOWN  → read the probe's message before trusting either branch
```

**Step 2 — run the branch your host reported.** Containment is proven only by
the jailed process landing in a **different PID-namespace inode** than the
host; `rc=0` on its own proves nothing about isolation.

`FULL` — bare mode is contained; prove the PID namespace:

```bash
readlink /proc/self/ns/pid                         # host: pid:[4026531836]
~/.local/bin/terminal-jail echo "in jail"          # runs in a PID namespace
~/.local/bin/terminal-jail sh -c 'readlink /proc/self/ns/pid'
# → a DIFFERENT inode than the host line above = PID-namespace containment
~/.local/bin/terminal-jail rm -rf /                # → COMMAND BLOCKED, exit 126
```

`DEGRADED` — bare mode refuses and does **not** fall back (fail-closed by
design, TJ-GAP-034); `--user` is the supported path:

```bash
~/.local/bin/terminal-jail echo "in jail"
# terminal-jail: namespace creation failed (unshare exit 1); command not run
#   — on unprivileged hosts try --user                             (exit 2)
~/.local/bin/terminal-jail --user sh -c 'readlink /proc/self/ns/pid'
# host: pid:[4026531836] → jail: pid:[4026538825]  (different inode)
~/.local/bin/terminal-jail --user sh -c 'echo "$USER $LOGNAME $HOME"'
# → nobody nobody /nonexistent                      (identity env scrubbed)
~/.local/bin/terminal-jail rm -rf /                # → COMMAND BLOCKED, exit 126
```

The jailed inode value changes per invocation — the check is the inequality,
not a literal. On a `DEGRADED` host `--user` gives **PID-namespace containment
+ identity env scrub** on every run, but the host PID view stays exposed (no
private `/proc` mount — PID 1 is still the host's `systemd`) and there is **no
filesystem isolation** unless a uid mapping can be created; when the mapping is
denied the CLI prints `no filesystem isolation` on stderr and continues. That
second layer is classified by a different probe —
`python3 scripts/fs-isolation-probe.py` (`FULL` | `DEGRADED` + cause, exit 0) —
do not conflate the two. See §3c and FAQ §4.

If `~/.local/bin` is not on your PATH, run the export the installer printed,
or use the full path above.

### 3b. Interruptor modes

```bash
TERMINAL_JAIL_INTERRUPTOR_MODE=warn terminal-jail rm -rf /    # warns, allows (firewall layer only)
TERMINAL_JAIL_INTERRUPTOR_MODE=disabled terminal-jail rm -rf / # bypasses firewall
terminal-jail --no-interruptor echo "bypass"                   # same, per-invocation
```

### 3c. Privilege + syscall hardening

```bash
terminal-jail --user echo "contained + env-scrubbed"   # user namespace
terminal-jail --user --seccomp echo "seccomp BPF active"   # denies mount/pivot_root/...
# NOTE: on hosts denying unprivileged PID namespaces (unshare: Operation not
# permitted), the bare `--seccomp` form fails — use the --user variant above
# (see FAQ §4) or deploy the systemd drop-in.
# `--user` gives PID-namespace containment + env scrub on EVERY host;
# FILESYSTEM isolation additionally requires a uid mapping. When the host
# denies one (e.g. Ubuntu AppArmor 'unprivileged_userns') the CLI prints
# `no filesystem isolation` on stderr and continues. Classify your host:
python3 scripts/fs-isolation-probe.py    # FULL / DEGRADED + cause, exit 0
```

### 3d. Hermes plugin

```bash
pip install -e .   # from the repo root (installs the plugin/ package tree)
```

**Enable via `HERMES_PLUGINS`.** The value must be an **absolute path** to
the plugin directory — relative paths are not resolved. Copy-paste this and
substitute your checkout path:

```bash
export HERMES_PLUGINS="/absolute/path/to/terminal-jail/plugin"
```

Multiple plugins are comma-separated. To append when `HERMES_PLUGINS` is
already set:

```bash
export HERMES_PLUGINS="$HERMES_PLUGINS,/absolute/path/to/other/plugin"
```

The variable must be in the Hermes gateway process environment: export it in
the shell that launches Hermes, or set it in the gateway's service env file.

**Confirm the plugin loaded at runtime** — one command that launches Hermes
with the plugin and greps its startup log for the registration line emitted
by `register()`:

```bash
HERMES_PLUGINS="/absolute/path/to/terminal-jail/plugin" hermes <launch-cmd> 2>&1 | grep "Observability hooks registered"
```

A silent exit (`grep` returns 1, no match) means the plugin did **not** load —
re-check that the path is absolute and that `HERMES_PLUGINS` reaches the
Hermes process environment.

The plugin hooks `pre_tool_call` (command visibility) and
`transform_terminal_output` (stub — returns output unchanged). It
does **not** wrap or modify commands — Hermes core has no pre-execution
command-transform hook. Verify with the plugin test suite:

```bash
python3 -m pytest plugin/test_plugin.py -q
```

### 3e. systemd drop-in (gateway hardening)

**Host check first.** The drop-in hardens the *gateway's* systemd unit — if
this host has no `hermes-gateway.service`, copying the file does nothing and
the naive verify below prints misleading default values. Check before
installing:

```bash
systemctl is-enabled hermes-gateway.service
# "enabled" (or "static" / "indirect") → continue below
# "not-found" → STOP: no gateway unit on this host — the drop-in is not
#   applied. Deploy the gateway unit first (docs/deploy-to-karahermes.md),
#   or skip this section.
```

```bash
sudo cp systemd/90-terminal-jail-hardening.conf \
  /etc/systemd/system/hermes-gateway.service.d/
sudo systemctl daemon-reload
sudo systemctl restart hermes-gateway
sudo systemd-analyze security hermes-gateway.service   # see the score
```

**Note:** the shipped drop-in activates only 4 directives
(`ProtectProc=invisible`, `NoNewPrivileges=true`,
`ProtectControlGroups=true`, `TasksMax=256`). It is lightweight hardening,
**not** a PID namespace boundary. The stronger directives
(`PrivateUsers=true`, `RestrictNamespaces=true`, network/fs hardening) are
commented out pending per-host verification — follow
[docs/deploy-to-karahermes.md](deploy-to-karahermes.md) to stage them.

Verify the drop-in is loaded (fail-loud: `systemctl show` prints default
values like `ProtectProc=default` for a nonexistent unit, so the unit must be
checked first):

```bash
systemctl is-enabled hermes-gateway.service >/dev/null 2>&1 || {
  echo "ERROR: hermes-gateway.service not found — drop-in not applied."
  echo "See docs/deploy-to-karahermes.md to deploy the gateway unit first."
  exit 1
}
systemctl show hermes-gateway.service -p ProtectProc -p NoNewPrivileges
# Expect: ProtectProc=invisible  /  NoNewPrivileges=yes
```

### 3f. Full gateway containment (advanced)

For actual PID-namespace containment of every command the gateway runs,
follow [docs/deploy-to-karahermes.md](deploy-to-karahermes.md) — it installs
`/usr/local/bin/terminal-jail-sh` as the gateway's `SHELL`, wrapping every
shell invocation with `setpriv --no-new-privs` + the CLI's
`--user --seccomp` flags plus the interruptor firewall.

## 4. FAQ / Troubleshooting

**`unshare` fails with "Operation not permitted"?**
The host kernel or container policy denies namespace creation. The CLI
passes `unshare`'s error through unchanged. Workarounds: use `--user`
(requires user-namespace support), or deploy the systemd drop-in (which does
not need `unshare`). In bare (non `--user`) mode the CLI internally mounts
a private /proc, which fails in unprivileged user namespaces on some
distributions (e.g. Ubuntu 26.04, kernel 7.0.0-27) — see README "Host
Limitations".

**`terminal-jail: unshare is required`?**
Install util-linux (`sudo apt install util-linux` or your distro's package).

**A command I expected to be blocked ran anyway?**
Check the mode: `TERMINAL_JAIL_INTERRUPTOR_MODE` (default `enforce`). In
`warn` mode the firewall prints `WARN: would have blocked` but allows
execution. `warn` relaxes only the **firewall** layer — the namespace layer
still runs, so on hosts that deny `unshare` (see the EPERM item above) a
warned command can still exit 2 unless you also pass `--user`. Also, only
commands matching the 30 built-in rules are blocked — the interruptor is a
pattern firewall, not a policy sandbox (see `specs/interruptor.md`).

**What happens if the bridge receives malformed input (bad JSON, empty stdin)?**
It fails **open**: the bridge answers
`{"action":"allow","command":"","rule_id":null,"reason":"[bridge-error] invalid JSON on stdin — fail-open: allowing command"}`
and exits 0, so the command proceeds unguarded. A *missing* bridge is
different — enforce mode fails **closed** (exit 126, `COMMAND BLOCKED`).
Validate the payload yourself and treat any `reason` starting with
`[bridge-error]` as a denial if you need malformed input to block (README
"Malformed input fails OPEN").

**The interruptor bridge is not available (warning or block on stderr)?**
The CLI resolves `plugin/terminal_jail/interruptor_bridge.py` in this order:
`TERMINAL_JAIL_BRIDGE` (explicit path), `../plugin/` next to the wrapper
(repository checkout), the installed lib layout
(`~/.local/lib/terminal-jail/plugin/` — shipped by `./install.sh`), then the
Python module path (`pip install -e .` from the repo root makes the bridge
importable). If the bridge is genuinely missing, enforce mode FAILS CLOSED
(exits 126 with a `COMMAND BLOCKED` box) instead of running unguarded; use
`TERMINAL_JAIL_INTERRUPTOR_MODE=warn` only if you explicitly accept the risk.

**Why does `--user` show host PIDs in `/proc`?**
User namespaces cannot mount a namespace-local `/proc` unprivileged. This is
documented behavior — `--user` trades `/proc` isolation for user-namespace
containment.

**Does `--user` isolate the filesystem?**
Only when the host allows a **uid mapping** (checked by preflight; marker
`TERMINAL_JAIL_FS_ISOLATION=mapped`). A mapping-less `--user` namespace is
an identity display only: `id` shows 65534, but file permissions still
evaluate as the calling user, so mode-600 files stay readable and home files
writable. When the mapping cannot be created (e.g. Ubuntu AppArmor profile
`unprivileged_userns` denies setuid/setgid inside unprivileged user
namespaces) the CLI prints a loud `no filesystem isolation` warning and
continues with PID-namespace containment + env scrub. Classify your host
and see the remediation options:
`python3 scripts/fs-isolation-probe.py`.

**Does the plugin block commands?**
No. `pre_tool_call` can block/allow at the Hermes level, but the plugin is
observability-first; the interruptor in the CLI/shim is the command
firewall.

**How do I roll back the systemd drop-in?**
```bash
sudo rm /etc/systemd/system/hermes-gateway.service.d/90-terminal-jail-hardening.conf
sudo systemctl daemon-reload && sudo systemctl restart hermes-gateway
```
The file itself contains the full rollback procedure.

**Where are the rules defined?**
30 built-in rules in the engine (12 blocklist + 8 auto-sandbox + 10 allow); user rules load from
`/etc/terminal-jail/rules.d/` and `~/.config/terminal-jail/rules.d/`
(lexical order, user overrides system). `./install.sh` ships the default rules file to
`~/.config/terminal-jail/rules.d/00-builtins.yaml`. See `specs/interruptor.md`.

## 5. Next steps

- [specs/integration.md](specs/integration.md) — architecture & defense-in-depth layers
- [docs/threat-model.md](threat-model.md) — what Terminal Jail does and does not prevent
- [docs/supply-chain.md](supply-chain.md) — release & supply-chain integrity
- [docs/pentest-plan.md](pentest-plan.md) — adversarial verification plan
- [docs/COMPATIBILITY.md](COMPATIBILITY.md) — host/kernel compatibility matrix
