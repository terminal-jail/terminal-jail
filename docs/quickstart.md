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

# Optional: opt in to a curated rule pack (repeat --rule-pack for more)
./install.sh --rule-pack db         # optional; see the README *Rule packs* section
./install.sh --list-rule-packs      # what this checkout ships
```

Rule packs are validated before anything is written. Installing a YAML pack
needs `python3` with **PyYAML** — on a bare host install the distro package
(`apt install python3-yaml`, `dnf install python3-yaml`) or run
`pip install pyyaml` first. A pack that cannot be validated (missing python3 or
PyYAML, malformed/invalid pack, or an id collision) is a **skip, not a
failure**: the wrapper and default rules still install, the skip is printed
with its reason, and the installer exits `2` at the end with a summary
(`--unrule-pack` needs no Python at all).

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

**Exception — auto-sandboxed (`modify`) commands DO run on a `DEGRADED` host**
(DF-TERMINAL-JAIL-11). The interruptor bridge supplies the rewrite's own `--user`
prefix, and the wrapper probes **that** prefix instead of its own bare-mode
launch, so:

```bash
~/.local/bin/terminal-jail bash script.sh   # auto-sandboxed: runs, exits with the script's status
~/.local/bin/terminal-jail go test ./...    # same for make/pytest/pip/cargo/gcc/npm test
```

A rewrite whose own prefix this host cannot create exits 2 with an
`auto-sandbox modify unavailable` verdict that names the flags probed — never a
generic namespace-creation message. (The bare-mode verdict above still applies to
every command the firewall did **not** rewrite.)

If `~/.local/bin` is not on your PATH, run the export the installer printed,
or use the full path above.

**Backend selection (v1.2 — optional bubblewrap).** Alongside `unshare` the CLI
has an optional `bubblewrap` (`bwrap`) backend. Selection is an **environment
variable** — no new flags:

```bash
TERMINAL_JAIL_JAIL_BACKEND=auto      # default: bwrap when installed + probing green, else unshare
TERMINAL_JAIL_JAIL_BACKEND=bwrap     # demand bwrap: exit 2 (command not run) if missing/unusable
TERMINAL_JAIL_JAIL_BACKEND=unshare   # pin the pre-v1.2 behavior exactly
```

Install the optional dependency the normal way and verify it, then watch the
backend actually being used:

```bash
sudo apt install bubblewrap          # or: sudo dnf install bubblewrap  (external distro package — never vendored here)
bwrap --version                      # → bubblewrap 0.11.1 (verified version)

# PRIVATE /proc: the count inside the jail must be far below the host's count,
# and /proc/1 inside must NOT be the host init.
ls /proc | grep -c '^[0-9]'                                   # host: e.g. 1682
~/.local/bin/terminal-jail sh -c 'ls /proc | grep -c "^[0-9]"; cat /proc/1/comm'
# → e.g. 5 and "bwrap"     (host shows "systemd")

# Fail-closed proof for an explicitly requested backend: no output, exit 2.
TERMINAL_JAIL_JAIL_BACKEND=bwrap ~/.local/bin/terminal-jail --version   # still prints (help/version never launch)
TERMINAL_JAIL_JAIL_BACKEND=typo ~/.local/bin/terminal-jail echo hi      # exit 2, names the accepted values
```

bubblewrap is an optional external runtime dependency: install it from your
distribution as above and the CLI resolves the externally installed `bwrap`
executable from `PATH` at run time. This MIT project does not vendor or
redistribute it — no vendored source tree, no git submodule, no binary blob,
and `install.sh` neither downloads nor installs packages (it only prints an
advisory note when `bwrap` is missing, and the install still succeeds).
bubblewrap is LGPL-2.1-or-later under its own authors' terms and is
redistributed by your distribution, not by this project; this is project
packaging guidance, not legal advice. Skipping it is fully supported: `auto`
then uses the `unshare` backend, and only an explicitly demanded
`TERMINAL_JAIL_JAIL_BACKEND=bwrap` fails closed (exit 2, command not run).

What each backend guarantees (do not conflate them):

| | `unshare` backend | `bwrap` backend |
|---|---|---|
| New PID namespace | yes | yes |
| Private `/proc` (host PIDs invisible) | bare mode only — **`--user` exposes the host `/proc`** | **yes, always** |
| Payload is namespace PID 1 | yes | no (bubblewrap's reaper is PID 1; the payload is PID 2) |
| Sandbox dies with the wrapper | `--kill-child=SIGKILL` | `--die-with-parent` (survives a SIGKILL of the wrapper) |
| Filesystem isolation (uid mapping) | `--user` where the host allows a mapping | not available (reports `TERMINAL_JAIL_FS_ISOLATION=degraded`) |
| Filesystem view | host's | host's (`--bind / /` + `--dev-bind /dev /dev`) — no added isolation |

Honest limits: bubblewrap needs the **same** unprivileged user-namespace
permission as `unshare`, so a host that forbids user namespaces fails closed
under both backends. Where user namespaces are allowed but bare-mode `unshare`
is denied, `auto` still gets you a contained, private-`/proc` jail — that is
the measured situation on this project's host. And because bubblewrap has no
unprivileged equivalent of `--map-users`, `auto` deliberately keeps the
`unshare` backend for `--user` on hosts where the uid mapping works (real
filesystem isolation), rather than silently trading it away.

### 3b. Interruptor modes

```bash
TERMINAL_JAIL_INTERRUPTOR_MODE=warn terminal-jail rm -rf /    # warns, allows (firewall layer only)
TERMINAL_JAIL_INTERRUPTOR_MODE=disabled terminal-jail rm -rf / # bypasses firewall
terminal-jail --no-interruptor echo "bypass"                   # same, per-invocation
```

**Default-allow posture.** The firewall is a deny-list: a command that matches no rule is
**allowed**, and `"rule_id": null` on an allow verdict means no rule matched at all — default-allow,
not an approved decision (a matched allow rule names itself, e.g. `"rule_id":"allow-ls"` for `ls`).
For deny-by-default, add your own rules under `~/.config/terminal-jail/rules.d/`: a catch-all
`block` rule with a new id denies everything the built-in allow rules do not already match.

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
commands matching the 54 built-in rules are blocked — the interruptor is a
pattern firewall, not a policy sandbox (see `specs/interruptor.md`).

**What happens if the bridge receives malformed input (bad JSON, empty stdin)?**
It fails **open**: the bridge expects one JSON object with a string `command` key
(`{"command": "..."}`). Bad JSON, empty stdin, a payload that is not a JSON
object (`null`, array, number, boolean, quoted string), a missing or misnamed
`command` key (`{}`, `{"Command": ...}`), or a non-string `command` value all
make it answer
`{"action":"allow","command":"","rule_id":null,"reason":"[bridge-error] invalid JSON on stdin — fail-open: allowing command"}`
and exit 0, so the command proceeds unguarded — the error is **reported** in
`reason` (which schema problem it was), not enforced as a block. A *missing*
bridge is different — enforce mode fails **closed** (exit 126,
`COMMAND BLOCKED`). Validate the payload yourself and treat any `reason`
starting with `[bridge-error]` as a denial if you need malformed input to block
(README "Malformed input fails OPEN"). An explicit empty command
(`{"command": ""}`) is valid input, not a schema error.

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
containment. The **bubblewrap backend does not have to make that trade**: with
the `bubblewrap` package installed, `TERMINAL_JAIL_JAIL_BACKEND=auto` (the
default) gives the `--user` containment *and* a private `/proc` on hosts where
the bwrap probe passes — verify with the PID-count check in §3a.

**Which backend is running, and how do I pin one?**
The CLI never says so on a successful launch (wrapper diagnostics would break
the stdout/stderr contract), so check the property instead of trusting a label:
`ls /proc | grep -c "^[0-9]"` inside the jail is a handful on the bwrap backend
and the host count on the unshare backend. To force a choice use
`TERMINAL_JAIL_JAIL_BACKEND=unshare` (exact pre-v1.2 behavior) or
`=bwrap` (demands bubblewrap: a missing binary or a failed namespace probe
exits **2 with the command not run** — the requested backend is never silently
downgraded). A present-but-unusable bubblewrap under `auto` prints a warning
naming the private-`/proc` loss, then continues with `unshare`. An unknown
value exits 2 before anything runs. Backends are documented in `specs/cli.md`
§4 ("Jail backends").

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
54 built-in rules in the engine (35 blocklist + 9 auto-sandbox + 10 allow); user rules load from
`/etc/terminal-jail/rules.d/` and `~/.config/terminal-jail/rules.d/`
(lexical order, user overrides system). `./install.sh` ships the default rules file to
`~/.config/terminal-jail/rules.d/00-builtins.yaml` for a default install; with a custom
`TERMINAL_JAIL_INSTALL_DIR` prefix it lands under `<prefix>/config/terminal-jail/rules.d/`
instead (the engine won't read it there — the installer prints a WARNING). Set
`TERMINAL_JAIL_RULES_DIR` to override the target (e.g. to the live directory) — it always wins —
or export `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=<dir>` and the installer resolves its rules
directory to exactly that value (the engine reads the same variable at run time, so prefix
installs load their rules). Note for prefix installs: opt-in rule packs (`--rule-pack`) are
SKIPPED in the prefix-local scope instead of being installed inert — the skip message names the
remediation.
See `specs/interruptor.md`.

## 5. Next steps

- [specs/integration.md](specs/integration.md) — architecture & defense-in-depth layers
- [docs/threat-model.md](threat-model.md) — what Terminal Jail does and does not prevent
- [docs/supply-chain.md](supply-chain.md) — release & supply-chain integrity
- [docs/pentest-plan.md](pentest-plan.md) — adversarial verification plan
- [docs/COMPATIBILITY.md](COMPATIBILITY.md) — host/kernel compatibility matrix
