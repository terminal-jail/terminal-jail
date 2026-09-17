# Terminal Jail

Defense-in-depth terminal command containment for Hermes Agent. Three layers: a systemd drop-in with lightweight hardening (process-visibility, privilege, and cgroup bounds — the full PID-namespace profile is staged, not active), Hermes plugin observability (metrics + logging), and a standalone CLI wrapper (portable PID namespace containment).

> **New here?** Start with the [Quick Start guide](docs/quickstart.md) — it covers which component fits your use case, install + verify steps for every path, and a FAQ.

## Architecture

| Layer | Role | Mechanism |
|---|---|---|
| **systemd drop-in** | LIGHTWEIGHT — process-visibility, privilege, cgroup bounds (4 active directives: `ProtectProc=invisible`, `NoNewPrivileges=true`, `ProtectControlGroups=true`, `TasksMax=256`) | Does NOT create a PID namespace. The full profile (`PrivateUsers`, `RestrictNamespaces`, network/fs hardening) is commented out pending per-host verification |
| **Hermes Plugin** | Observability only | `pre_tool_call` (command visibility), `transform_terminal_output` (output annotation stub), command-length logging, metrics export |
| **Standalone CLI** | Portable PID namespace wrapper | `unshare --pid --fork --mount-proc --kill-child=SIGKILL` for manual use outside Hermes or without systemd |

## How It Works

**The plugin does NOT wrap commands.** Hermes core has no pre-execution command-transform hook — `pre_tool_call` only supports block/allow decisions. The plugin observes terminal commands and exports metrics, but PID namespace isolation comes from the systemd layer.

```bash
# CLI only — the sole component that wraps commands:
./standalone/terminal-jail echo "I'm in a PID namespace"
# → unshare --pid --fork --mount-proc --kill-child=SIGKILL bash -c 'echo "I'"'"'m in a PID namespace"'
# On hosts that deny unprivileged PID namespaces (unshare: Operation not
# permitted, EPERM), bare mode exits 2 with a message naming the fallback
# (see Graceful Degradation); use the --user fallback instead (PID-namespace
# lifecycle containment + identity env scrub):
./standalone/terminal-jail --user echo "I'm in a PID namespace"
# --user also scrubs inherited identity env (USER=nobody, LOGNAME=nobody,
# HOME=/nonexistent). Filesystem isolation requires a uid MAPPING
# (--map-users/--map-groups + -S/-G); it is active ONLY when the host permits
# it — otherwise the wrapper warns loudly on stderr:
#   "no filesystem isolation — could not create a uid mapping ...".
# Check your host: python3 scripts/fs-isolation-probe.py
```

The `--kill-child=SIGKILL` flag ensures that when the namespace init exits, every descendant is immediately killed — even processes that double-fork or change session leaders.

## Components

| Component | Path | Purpose |
|---|---|---|
| systemd Drop-in | `systemd/90-terminal-jail-hardening.conf` | LIGHTWEIGHT hardening — 4 active directives (process visibility, no-new-privileges, cgroup protection, task bound). NOT a PID namespace boundary; the full isolation profile is staged/commented. |
| Hermes Plugin | `plugin/terminal_jail/` | Observability: `pre_tool_call` and `transform_terminal_output` hooks. Metrics, logging (command length). Does NOT wrap commands. |
| Standalone CLI | `standalone/terminal-jail` | Portable `unshare` wrapper for use outside Hermes or without systemd |
| Deploy Shim | `standalone/terminal-jail-sh` | SHELL replacement for the Hermes gateway: wraps every shell invocation with `setpriv --no-new-privs` + `--user --seccomp` + the interruptor. Deploy-specific — paths configurable via `TERMINAL_JAIL_HOME` / `TERMINAL_JAIL_BRIDGE` / `TERMINAL_JAIL_CLI` (defaults target `/usr/local/lib/terminal-jail`). See `docs/deploy-to-karahermes.md` |
| Interruptor Engine | `plugin/terminal_jail/interruptor/` | Bash command firewall — parser, matcher, decider, 30 built-in rules, JSON bridge for CLI integration |

## Interruptor Bash Command Firewall (v1.1.0)

The Interruptor is a bash command firewall that sits between the LLM and shell execution. It intercepts every command, parses it, evaluates it against a rule set, and decides: **allow**, **block**, or **modify** (auto-sandbox).

### Quick Start

```bash
# Test the JSON bridge directly
echo '{"command": "echo hello"}' | python3 plugin/terminal_jail/interruptor_bridge.py
# → {"action":"allow","command":"echo hello",...}

echo '{"command": "rm -rf /"}' | python3 plugin/terminal_jail/interruptor_bridge.py
# → {"action":"block","command":"rm -rf /","rule_id":"builtin-rm-rf-root",...}

# Via standalone CLI with interruptor
USE_INTERRUPTOR=1 ./standalone/terminal-jail echo "hello"
TERMINAL_JAIL_INTERRUPTOR_MODE=warn ./standalone/terminal-jail rm -rf /
TERMINAL_JAIL_INTERRUPTOR_MODE=disabled ./standalone/terminal-jail --no-interruptor echo "test"
```

**Malformed input fails OPEN.** The bridge is a single-command JSON endpoint. Invalid JSON,
empty stdin, or a non-string `command` field make it answer
`{"action":"allow","command":"","rule_id":null,"reason":"[bridge-error] … — fail-open: allowing command"}`
and exit 0 — no rule can be applied, so the command proceeds unguarded. This is the same
fail-open contract the plugin follows (`specs/plugin.md`): a firewall that cannot parse its
input must not wedge the caller. Fail-*closed* applies only to a **missing bridge**, where
enforce mode exits 126 with a `COMMAND BLOCKED` box. If you need malformed input to be denied,
validate the payload yourself and treat any `reason` beginning `[bridge-error]` as a denial.

### Architecture

| Layer | Role | Mechanism |
|-------|------|-----------|
| **Parser** | Tokenize shell commands | Handles pipes, redirects, cmd substitution, heredocs, quoting, variable expansion |
| **Rule Loader** | Load YAML rules | `/etc/terminal-jail/rules.d/` (system) → `~/.config/terminal-jail/rules.d/` (user) in lexical order |
| **Pattern Matcher** | 9 match types | pattern, command, pipeline, subcommand, path, composite, syscall, network, heredoc |
| **Decider** | Evaluate priority | Blocklist (first) → allowlist → auto-sandbox → user rules. First match wins |

### Built-in Rules (30 total)

Counts verified from the engine (`BUILTIN_BLOCKLIST` / `BUILTIN_SANDBOX` / `BUILTIN_ALLOWLIST` in
`plugin/terminal_jail/interruptor/`): **12 critical blocklist, 8 auto-sandbox, 10 always-allow**.
Rule IDs are stable — tests assert behavior by ID.

- **12 Critical Blocklist** (priority 1000, evaluated first, cannot be removed — only overridden to `warn` by a same-ID user rule):
  - `builtin-kill-all` — mass process kill (`kill -9 -1`)
  - `builtin-killpg-pid1` — process-group kill targeting PID 1 or own process group (`os.killpg(0/1, …)`, `kill(-1/0, …)`)
  - `builtin-fork-bomb` — fork bomb pattern (`:(){ :|:& };:`)
  - `builtin-rm-rf-root` — recursive root removal (`rm -rf /`; order-independent recursive + force flags, TJ-DF-001)
  - `builtin-dd-root` — raw device write (`dd of=/dev/sd*`)
  - `builtin-mkfs` — filesystem creation (`mkfs.*`)
  - `builtin-fdisk` — partition manipulation (`fdisk`)
  - `builtin-chmod-777-root` — world-writable root (`chmod 777 /`; `chmod 000 /` is NOT blocked — scope is the world-writable variant)
  - `builtin-echo-to-system` — redirect output to system paths (`echo … > /etc/…` etc.)
  - `builtin-curl-pipe-shell` — `curl|sh` / `wget|sh` pipe-to-shell
  - `builtin-sudo` — privilege escalation (`sudo`)
  - `builtin-code-injection` — code-injection vectors in interpreter arguments (`os.system(`, `subprocess.run(`, `eval(`, `exec(`, `__import__(` — scanned in quoted interpreter code too, TJ-GAP-042)
- **8 Auto-Sandbox** (wrapped in `unshare --user --pid --fork --kill-child=SIGKILL`):
  - `auto-pytest` — `pytest|tox|nose`
  - `auto-npm-test` — `npm test` / `npx vitest|jest`
  - `auto-go-test` — `go test`
  - `auto-make` — `make`
  - `auto-pip` — `pip install` / `pip3 install`
  - `auto-cargo` — `cargo build|test`
  - `auto-gcc` — `gcc|g++|clang++` compilation
  - `auto-script` — script execution (`./foo.sh`, `bash foo.py`, etc.)
- **10 Always-Allow** (skip further evaluation when matched):
  - `allow-echo` — `echo`
  - `allow-ls` — `ls`
  - `allow-pwd` — `pwd`
  - `allow-cat-safe` — `cat` on non-sensitive paths (not `/etc`, `/boot`, `/proc`, `/sys`)
  - `allow-grep` — `grep`
  - `allow-find-safe` — `find` without `-exec`/`-delete`
  - `allow-git-read` — `git status|log|diff`
  - `allow-python-version` — `python … --version`
  - `allow-which` — `which` / `command -v`
  - `allow-cd` — `cd`

### Modes

| Mode | Behavior |
|------|----------|
| `enforce` (default) | Blocked commands exit 126 with formatted block output |
| `warn` | Print warning message but allow command through |
| `disabled` | Bypass the interruptor entirely |

Set via `TERMINAL_JAIL_INTERRUPTOR_MODE` env var or `--no-interruptor` flag on the CLI.

## Quick Start

### CLI

```bash
./standalone/terminal-jail echo "I'm in a PID namespace"
./standalone/terminal-jail --help
./standalone/terminal-jail --version
```

> **Host limitation:** the first example requires an unprivileged PID
> namespace (`unshare --pid`). On hosts that deny it (e.g. this one —
> `unshare: unshare failed: Operation not permitted`, EPERM), use the `--user`
> fallback instead: `./standalone/terminal-jail --user echo "I'm in a PID
> namespace"` (PID-namespace lifecycle containment + identity env scrub; the
> host PID view stays exposed). Filesystem isolation via `--user` is active
> ONLY where a uid mapping can be created — classify your host with
> `python3 scripts/fs-isolation-probe.py`. See
> [Host Limitations](#host-limitations).

### Plugin (Hermes)

The plugin registers two hooks for observability:

- `pre_tool_call` — visibility into terminal commands (can block/allow, cannot modify)
- `transform_terminal_output` — output annotation (stub — returns output unchanged)

**Important:** The plugin is observability-only — Hermes core has no pre-execution command-transform hook, so the plugin cannot wrap commands. Former wrapping functions (`transform_command`/`transform_exec_command`) were removed in v1.1.x as dead code (TJ-GAP-010). See `specs/integration.md` for the full architectural rationale (HOOK-GAP-03).

Configuration via environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `HERMES_TERMINAL_JAIL_ENABLED` | `true` | Enable/disable plugin (`true`/`false`/`1`/`0`) |
| `HERMES_TERMINAL_JAIL_COMMAND` | `unshare` | Path to `unshare` binary |
| `HERMES_TERMINAL_JAIL_MAX_COMMAND_BYTES` | `131072` | Reserved — not yet read by the plugin |
| `HERMES_TERMINAL_JAIL_LOG_LEVEL` | `WARNING` | Python logging level |
| `HERMES_TERMINAL_JAIL_USER_NS` | `false` | Enable user namespace isolation (`true`/`false`/`1`/`0`) |
| `TERMINAL_JAIL_SECCOMP` ⚠️ | `0` | Enable seccomp BPF filter (`1`/`true`/`yes`/`on`) — **only honored when the CLI is also invoked with `--seccomp`; the env var alone does not activate the filter.** **Note:** does not use `HERMES_TERMINAL_JAIL_` prefix — legacy naming from pre-plugin seccomp module. |

### systemd Hardening (LIGHTWEIGHT — 4 active directives)

**Important:** the shipped drop-in is *not* a PID namespace isolation boundary.
It activates only `ProtectProc=invisible`, `NoNewPrivileges=true`,
`ProtectControlGroups=true`, and `TasksMax=256` (process-visibility,
privilege, cgroup, and task-count hardening). The stronger directives
(`PrivateUsers=true`, `RestrictNamespaces=true`, network/fs hardening) are
commented out in the file with rationale — they require per-host verification
before activation. The full profile is specified in `specs/systemd.md` and the
staged activation procedure in `docs/deploy-to-karahermes.md`.

For actual PID namespace containment of terminal commands, use the standalone
CLI (`./standalone/terminal-jail <command>`) or a verified full-profile
deployment. See `docs/quickstart.md` for the decision tree.

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
```

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

## Install

### From source (recommended)

```bash
git clone https://github.com/totalwindupflightsystems/terminal-jail.git
cd terminal-jail
./install.sh
```

The installer detects the repository checkout and installs the local
`standalone/terminal-jail` wrapper to `~/.local/bin/terminal-jail` (override
with `TERMINAL_JAIL_INSTALL_DIR`). It never requires root, and it prints the
exact PATH export to run if `~/.local/bin` is not on your PATH.

Rules follow the install scope: the default install ships the default rules
file to `~/.config/terminal-jail/rules.d/00-builtins.yaml`, while a custom
`TERMINAL_JAIL_INSTALL_DIR` prefix receives it under
`<prefix>/config/terminal-jail/rules.d/` instead (the engine only reads
`/etc/terminal-jail/rules.d` and `~/.config/terminal-jail/rules.d`, so the
installer prints a warning for prefix installs). Set `TERMINAL_JAIL_RULES_DIR`
to target the live rules directory explicitly — it always wins.

Release-mode installs (downloading the wrapper from a published release plus
its SHA-256 checksum, verified and atomically installed) are supported by
`install.sh` via `TERMINAL_JAIL_USE_RELEASE=1` with `TERMINAL_JAIL_BASE_URL`,
but no release assets are published yet and release mode is therefore
**opt-in only** — without the flag the installer refuses instead of hitting a
dead URL. The git-clone path above is the supported install path.

## Graceful Degradation

Every layer degrades independently:

- **systemd drop-in**: optional — gateway runs without it. Provides process-visibility/privilege/cgroup hardening only; it is NOT a PID namespace boundary (the stronger directives are staged).
- **Plugin**: observes and logs. Returns command unchanged if disabled. Does not block execution.
- **CLI**: exits with code 2 and a message if `unshare` not found, not on Linux, or namespace creation fails. There is **no automatic fallback** — on hosts that deny unprivileged PID namespaces you must add `--user` yourself (see the example block above). Bare mode stays fail-closed: it never silently downgrades isolation. `--user` itself has two tiers, chosen by an exact-flags preflight: when the host permits a **uid mapping** the launch is `unshare --user --map-users=65534:<subuid>:1 --map-groups=65534:<subgid>:1 -S 65534 -G 65534 ...` (real filesystem isolation, `TERMINAL_JAIL_FS_ISOLATION=mapped`); otherwise it falls back to the legacy mapping-less namespace (`=degraded`) and prints a loud `no filesystem isolation` warning — the PID-namespace containment, env scrub, and exit codes stay exactly the same. `TERMINAL_JAIL_UID_MAP=0|off|false` forces the mapping-less mode. `scripts/fs-isolation-probe.py` classifies any host (FULL/DEGRADED + cause, always exit 0).
- **E2E battery (PID-NS layer)**: every run is labeled **FULL** or **DEGRADED** by `scripts/pidns-capability-probe.py` (classifies any host by probing bare mode: `FULL` when the namespace works, `DEGRADED` when the host refuses creation, `UNKNOWN` otherwise — the probe always exits 0). When the host is DEGRADED, bare-mode tests **skip** with a `HOST-DEGRADED-PIDNS` marker instead of silently passing, so the battery never reports "ALL GREEN" without actually verifying PID-namespace containment; on FULL hosts the containment test asserts the jailed command lands in a new PID namespace inode.

## Requirements

- Linux (kernel 3.8+ for user namespaces, 4.3+ for `--kill-child`)
- `util-linux` 2.32+ (`unshare` with `--kill-child`)
- `bash`
- systemd (for the primary isolation layer)

## Host Limitations

`unshare --mount-proc` requires privileges unavailable in unprivileged user namespaces on some distributions. On Ubuntu 26.04 (kernel 7.0.0-27), the CLI's bare mode (which appends --mount-proc internally) will fail on some commands. This is a host kernel policy limitation, not a code defect. The systemd layer provides process-visibility and privilege hardening (`ProtectProc=invisible`, `NoNewPrivileges=true`) independently of `unshare`, but it does not create a PID namespace (the shipped drop-in's `PrivateUsers`/`RestrictNamespaces` directives are commented out pending verification).

The same applies to `--user`'s filesystem isolation tier: creating a uid mapping requires setuid/setgid inside the unprivileged user namespace, and stock Ubuntu ships an AppArmor profile (`unprivileged_userns`) that denies exactly those capabilities (`apparmor="DENIED" ... capname="setuid"` in `dmesg`; see also `sysctl kernel.apparmor_restrict_unprivileged_userns`). On such hosts the CLI falls back to the mapping-less namespace and prints a loud `no filesystem isolation` warning — a host restriction, not a code defect. Classify any host with `python3 scripts/fs-isolation-probe.py` (prints FULL or DEGRADED plus the diagnosed cause, always exits 0).

## Repository layout

```
plugin/            Hermes plugin — observability hooks + the Interruptor engine (plugin/terminal_jail/interruptor/)
standalone/        Bash wrapper (terminal-jail), gateway shell shim (terminal-jail-sh), seccomp-loader.py
systemd/           Gateway hardening drop-in snippet
scripts/           Ops/verification helpers (pidns capability probe, benchmarks, metrics export, watchdogs)
specs/             Product specs (cli, plugin, integration, interruptor, systemd)
docs/              User/ops documentation (quickstart, threat model, ADRs, deploy, audits)
skills/            Repo-local agent skill (skills/terminal-jail-usage/SKILL.md)
.github/           CI workflow + issue templates
.vfs/              Hilo code-graph cache — .vfs/graph/edges.jsonl is TRACKED on purpose
.gitreins/         GitReins harness records (tasks.yaml, history/)
.coding-hermes/    Fleet task board (canonical JSONL stores under board/)
.memory-bank/      Long-term project memory
<root files>       LICENSE, README, AGENTS, CHANGELOG, CODEOWNERS, CONTRIBUTING, CODE_OF_CONDUCT,
                   GOVERNANCE, SECURITY, SUPPORT, TRADEMARK_POLICY, install.sh, pyproject.toml,
                   .gitleaks.toml, .gitignore
```

**Intentional exceptions** — these paths look like generated or local state but are
tracked deliberately. Do not move or delete them:

| Path | Why it is tracked |
|---|---|
| `.vfs/` | Hilo code-graph cache. `edges.jsonl` and `manifest.yaml` are committed so the graph survives a clone; the binary cache (`graph.db`) is gitignored. |
| `.gitreins/` | GitReins harness records — task definitions plus per-run history. |
| `.coding-hermes/` | The fleet task board (canonical JSONL stores under `board/`). |
| `.memory-bank/` | Long-term project memory (see `AGENTS.md`). |
| `skills/terminal-jail-usage/` | Repo-local agent skill doc. |

**Retired: `e2e-output/`** (removed 2026-09-10 by CLN-1). It held two stale one-off
E2E battery dumps — `report.md` (tick #167, 2026-08-08) and `tasks.md` (tick #36,
2026-08-01). Neither was referenced by any test, CI workflow, `install.sh`, or doc:
`git grep -n "e2e-output"` matched only the board's own audit history and the GitReins
CLN-1 task record itself, and
`grep -rn "e2e-output" plugin/ .github/workflows/ci.yml install.sh docs/ README.md scripts/ systemd/ specs/`
returned zero matches. The per-tick reports stopped being written there after tick
#167 — battery results now live in the board's `events.jsonl`. Both files were removed
with `git rm`; git history retains their content.

## Development

Run the test suite from a fresh checkout with one command:

```bash
uv sync --dev && uv run pytest plugin -q
```

`uv sync --dev` creates `.venv/` with the runtime dependency (`PyYAML`) plus
the `dev` dependency group (`pytest`); `uv run pytest plugin -q` then runs
the suite (~300 passed on this host — the skips are environment-gated:
SIGHUP reload, seccomp requiring CAP_SYS_ADMIN, and namespace
integration tests). `pyproject.toml` sets `pythonpath = ["."]`, so
`plugin/` imports resolve without extra configuration.

## License

MIT
