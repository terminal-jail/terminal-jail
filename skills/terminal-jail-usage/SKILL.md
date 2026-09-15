---
name: terminal-jail-usage
description: >-
  How to USE the terminal-jail project for real: what it does, entry points,
  run commands, common pitfalls, and the right-way patterns. Load this skill
  before integrating with or extending terminal-jail. Written from the
  2026-08-10 dogfood run, refreshed 2026-08-19 (all TJ-DF-001..010 fixes
  verified live; new findings TJ-DF-011..014), refreshed 2026-08-22
  (TJ-DF-011/012/014 closed — pitfalls below updated to fixed reality),
  refreshed 2026-09-15 (TJ-DF-017 — verify flow branches on FULL/DEGRADED).
version: 1.2.0
category: software-development
---

# Terminal Jail — Usage Skill

Defense-in-depth terminal containment for Hermes/LLM agents. The interruptor
(bash command firewall) is the layer that actually does something; the plugin
is observability-only; the systemd drop-in is lightweight hardening (4
directives) — NOT a PID namespace boundary as shipped.

> **Before trusting any "known gap" list (including this file):** check the
> board (`.coding-hermes/board/tasks.jsonl`) for open tasks first. This
> project's knowledge artifacts went stale once already (TJ-DF-013) — the
> board is the source of truth, the skill is the quickstart.

## Entry points

| Component | Path | What it does |
|---|---|---|
| Standalone CLI | `standalone/terminal-jail` (install → `~/.local/bin/terminal-jail`) | `unshare` PID-namespace wrapper + interruptor firewall. THE main tool. |
| Interruptor engine | `plugin/terminal_jail/interruptor/` | Pure-python rule engine: `intercept(cmd)` → allow/block/modify. |
| JSON bridge | `plugin/terminal_jail/interruptor_bridge.py` | stdin/stdout JSON wrapper over the engine — safe to script, never executes. THE oracle for rule probes. |
| Hermes plugin | `plugin/__init__.py` | Observability hooks only (pre_tool_call logs, transform returns None). |
| Deploy shim | `standalone/terminal-jail-sh` | SHELL replacement for the Hermes gateway (setpriv + seccomp + interruptor). Host-specific. |
| systemd drop-in | `systemd/90-terminal-jail-hardening.conf` | 4 active directives; full profile commented out. |

## Quick start (real commands, verified on Ubuntu 26.04 / kernel 7.0.0-30)

```bash
./install.sh                                     # from a checkout — the supported path
TJ=~/.local/bin/terminal-jail
$TJ --version                                    # terminal-jail 1.1.0
python3 scripts/pidns-capability-probe.py        # FULL | DEGRADED | UNKNOWN, exit 0
readlink /proc/self/ns/pid                       # host pid-ns inode (here 4026531836)
$TJ --user sh -c 'readlink /proc/self/ns/pid'    # DIFFERENT inode → containment
$TJ --user echo hi                               # exec + rc=0 only — NOT containment proof
$TJ --user bash -c 'exit 7'; echo $?             # exit codes pass through → 7
echo hi | $TJ --user cat                         # stdin passes through
$TJ --user fdisk /dev/sda                        # COMMAND BLOCKED box, rc=126
TERMINAL_JAIL_INTERRUPTOR_MODE=warn $TJ --user fdisk /dev/sda   # WARN + allow
TERMINAL_JAIL_INTERRUPTOR_MODE=disabled $TJ --user fdisk /dev/sda
$TJ --no-interruptor --user fdisk /dev/sda       # per-invocation firewall off
```

**Branch on the probe — `rc=0` is never evidence of containment; a different
pid-ns inode is.** `FULL` → bare mode (`$TJ echo hi`) creates the namespace;
prove it by comparing the jailed `readlink /proc/self/ns/pid` with the host's
(they must differ). `DEGRADED` (this host) → bare mode exits 2, fail-closed,
with **no automatic `--user` fallback** (TJ-GAP-034), so `--user` is the
supported path.

**Always use `--user` on hosts that deny unprivileged PID namespaces**
(plain `unshare --pid` → EPERM — this host, documented). On such a host
`--user` gives PID-namespace lifecycle containment + env scrub on every host
(host PIDs visible in /proc — PID 1 is still the host's `systemd`), and NO
filesystem isolation unless a uid mapping can be created: the CLI prints
`no filesystem isolation` on stderr and continues. That separate layer is
classified by `python3 scripts/fs-isolation-probe.py` (`FULL`/`DEGRADED`,
exit 0) — do not conflate the two probes. NOTE: `--user`
scrubs identity env (USER=nobody, LOGNAME=nobody, HOME=/nonexistent —
TJ-DF-014 fixed, verified live 2026-08-19).

## Firewall probing (no execution — the safe way to test rules)

```bash
echo '{"command": "rm -rf /"}' | python3 plugin/terminal_jail/interruptor_bridge.py
# → {"action":"block","rule_id":"builtin-rm-rf-root",...}
echo '{"command": "echo hi"}' | python3 plugin/terminal_jail/interruptor_bridge.py
# → {"action":"allow",...}
```

Engine-level (fast, no subprocess):
```python
import sys; sys.path.insert(0, "plugin")
from terminal_jail.interruptor import intercept
r = intercept("sudo apt install cowsay")   # → block (builtin-sudo, priority 1000)
```

## User rules (WORKING since TJ-DF-004 — verified live 2026-08-19)

```bash
mkdir -p ~/.config/terminal-jail/rules.d
cat > ~/.config/terminal-jail/rules.d/99-mine.yaml <<'EOF'
rules:
  - id: my-block-touch
    priority: 900
    action: block
    match: {type: command, command: touch}
EOF
$TJ --user touch /tmp/x   # → COMMAND BLOCKED, rc=126
```

- Same-ID rules REPLACE builtins in their layer (builtin-rm-rf-root can be
  overridden). An `action: warn` same-ID override now ALLOWS with a
  would-have-blocked reason surfaced on stderr by the CLI (TJ-DF-012
  fixed — previously silent); `TERMINAL_JAIL_INTERRUPTOR_MODE=warn` env
  also surfaces warnings correctly.
- Rules load from `/etc/terminal-jail/rules.d/` (system) and
  `~/.config/terminal-jail/rules.d/` (user); install.sh ships
  `00-builtins.yaml` to the user dir (TJ-GAP-033).

## Common pitfalls (current as of 2026-08-22)

1. **`chmod -R 777 /` is now BLOCKED** (TJ-DF-011 fixed, verified live
   2026-08-22): the world-writable-root rule is token-aware/order-
   independent — `chmod -R 777 /`, `chmod --recursive 777 /`,
   `chmod a+rwx /`, `chmod 7777 /`, `chmod -R 777 /etc` ALL block with
   `builtin-chmod-777-root`; benign `chmod 755 /` still allows.
2. **Same-ID `action: warn` override surfaces a warning** (TJ-DF-012
   fixed): command runs (allow) but the CLI prints a WARN line with the
   would-have-blocked reason on stderr. Use it for downgraded-rule
   visibility; `TERMINAL_JAIL_INTERRUPTOR_MODE=warn` env works too.
3. **`--user` scrubs `$USER`/`$HOME`** (TJ-DF-014 fixed): process runs
   with USER=nobody, LOGNAME=nobody, HOME=/nonexistent — no caller
   identity via env.
   **⚠️ `--user` filesystem isolation is CONDITIONAL (TJ-DF-015, fixed
   2026-09-15):** the CLI now builds a uid-MAPPED namespace
   (`--map-users=65534:<subuid>:1 --map-groups=... -S 65534 -G 65534`,
   subuid/subgid from /etc/subuid|/etc/subgid) whenever the exact-flags
   preflight passes — that mapping makes file permissions REAL (a jailed
   process cannot read caller-owned mode-600 files or write the caller's
   home), exported as `TERMINAL_JAIL_FS_ISOLATION=mapped`. When the host
   denies the mapping (this one: AppArmor `unprivileged_userns` denies
   setuid/setgid/setgroups inside unprivileged user namespaces), it falls
   back to the legacy MAPPING-LESS namespace (`=degraded`) and prints a
   loud `no filesystem isolation` warning: `id` shows 65534 (unmapped-
   display overflow) but the process keeps the caller's underlying kuid
   and file permissions evaluate as the OWNER of the caller's files
   (verified: a jailed process read a mode-600 file under the caller's
   home and created files there as owner; a REAL `sudo -u nobody` on the
   same file is denied, errno 13). Escape hatch:
   `TERMINAL_JAIL_UID_MAP=0|off|false` forces the mapping-less mode.
   Classify any host before trusting `--user` for filesystem isolation:
   `python3 scripts/fs-isolation-probe.py` (FULL/DEGRADED + cause, rc=0).
   Bare mode is unchanged: no automatic `--user` fallback ever
   (TJ-GAP-034).
4. **seccomp works now** (TJ-DF-002/003 fixed, verified): filter installs
   unprivileged; denies via `SECCOMP_RET_ERRNO|EPERM` (NOT SIGSYS — a
   denied syscall returns EPERM, it doesn't kill). Verify with
   `grep Seccomp /proc/self/status` → `2`, or a ctypes `mount()` probe
   returning errno 1. `TERMINAL_JAIL_SECCOMP=1` alone still does nothing;
   the `--seccomp` flag is required.
5. **Enforce mode fails closed** when the bridge is missing/crashes
   (rc=126 + box) — correct behavior; fix the bridge path, don't switch to
   warn mode.
6. **install.sh local-checkout detection**: must be invoked as
   `./install.sh` (or `install.sh`); `bash /abs/path/install.sh` refuses
   (release mode is opt-in). Intentional, just don't be surprised.
7. **Auto-sandbox (modify)**: pytest/make/go test/pip/script runs get
   wrapped in a nested `unshare --user --pid` — the CLI prints
   `[terminal-jail] Modified: ... → sandboxed` and runs the wrapped
   command; the nested namespace works on this host (PID 1 inside).

## Right-way patterns

- **Blocking test battery**: engine (`intercept`) → bridge (stdin JSON) →
  CLI (only for block box/exit codes). Never run the dangerous commands
  themselves — the bridge is the safe oracle.
- **Installed-binary testing**: always test BOTH repo layout and
  `TERMINAL_JAIL_INSTALL_DIR=/tmp/x ./install.sh` layout — they diverged
  twice (TJ-GAP-021, TJ-DF-002) and are verified converged now.
- **Seccomp verification**: `$TJ --user --seccomp grep Seccomp /proc/self/status`
  must show `Seccomp: 2`; a ctypes mount probe must return errno 1 (EPERM).
- **Host constraint**: this host can't run plain `unshare --pid`; every
  execution test needs `--user`. CI/test suites know this (integration
  tests skip on hosts blocking --mount-proc).
- **Gateway interaction**: the Hermes gateway hardline may block probe
  commands containing literal dangerous tokens (`mkfs`, `dd of=/dev/...`)
  even as bridge DATA — build those strings at runtime in scratch files.

## Board & history

- Board: `.coding-hermes/board/tasks.jsonl` (JSONL v2.1 — append rows in
  that schema; there is no tasks.md anymore).
- Dogfood runs: 2026-08-10 (TJ-DF-001..010 — all complete, verified),
  2026-08-19 (TJ-DF-011..014 — 011/012 security, 013 docs, 014 hygiene;
  all complete). Refreshed 2026-08-22 (TJ-GAP-040) — pitfalls reflect
  fixed reality; verify against the board before trusting lists.
  E2E-001 is the recurring full-battery tick; NEVER-DONE the audit tick.
- Commits must carry `Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>`
  and pass `gitreins guard` (see AGENTS.md).
