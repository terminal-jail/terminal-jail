# Changelog

## [Unreleased]

### License-clean bubblewrap installation/dependency path (TJ-GAP-055)

- **`install.sh`**: a new advisory `NOTE` when `bwrap` is not on `PATH`. bubblewrap is optional, so the note is never a preflight error: a host without bubblewrap installs successfully and the CLI keeps the `unshare` backend. The installer still never downloads, builds, installs as a package, or vendors bubblewrap, and stays POSIX `sh`.
- **Packaging boundary stated**: `README.md` (Requirements + *Bubblewrap backend*), `specs/cli.md` §4 and `docs/quickstart.md` now say plainly that bubblewrap is an optional external distro package invoked from `PATH`, that this MIT-licensed repository does not vendor, bundle, download, build, or redistribute it (bubblewrap is LGPL-2.1-or-later under its own authors' terms — project packaging guidance, not legal advice), and that an explicitly demanded `TERMINAL_JAIL_JAIL_BACKEND=bwrap` still fails closed (exit 2, command not run) while `auto` falls back to `unshare`.
- **Docs**: `docs/dependency-audit.md` lists `bwrap` as an optional external dependency and records the installer's no-vendoring property.
- **Tests**: `plugin/test_install.py` covers the installer contract (advisory when absent with a still-successful install, silent when present, no bubblewrap artifact written into the install tree, and a source invariant that `install.sh` never downloads/builds/installs/vendors bubblewrap). `plugin/test_packaging.py` adds the tracked-tree verdict (no vendor/third-party tree, no submodule, no bubblewrap source file) and the documentation-claim contract over `README.md` / `specs/cli.md`. All cases are offline, host-independent, and need no `bwrap` binary.

### Optional bubblewrap (bwrap) jail backend (TJ-GAP-054)

- **`standalone/terminal-jail`**: runtime-detected backend selection via `TERMINAL_JAIL_JAIL_BACKEND=auto|bwrap|unshare` (default `auto`; no new CLI flags). `auto` uses bubblewrap when it is installed and its namespace probe passes, otherwise the unchanged `unshare` backend; `bwrap` is a demand that fails closed (exit 2, command not run) when bubblewrap is missing or unusable; `unshare` pins the pre-v1.2 behavior byte-for-byte; an unknown value exits 2 before any namespace work.
- **Private `/proc`**: the bwrap backend launches `bwrap --unshare-user --unshare-pid --die-with-parent --bind / / --dev-bind /dev /dev --proc /proc -- bash -c 'exec "$@"' terminal-jail …` — a fresh procfs the jail cannot use to enumerate host PIDs (measured: 5 entries vs 1682 host PIDs), plus `--die-with-parent` teardown that survives a SIGKILL of the wrapper. The unshare backend keeps its documented limitation (`--user` exposes the host `/proc`).
- **No silent downgrade, no traded-away isolation**: a present-but-unusable bubblewrap under `auto` warns that the fallback has no private `/proc` before continuing; `auto` keeps the `unshare` mapped launch for `--user` on mapping-capable hosts because bubblewrap has no unprivileged `--map-users` equivalent (`--uid` alone leaves DAC unchanged — measured), and `bwrap --user` states that loss loudly with `TERMINAL_JAIL_FS_ISOLATION=degraded`.
- **Deliberately not used**: `--as-pid-1` — it makes the payload namespace PID 1 and nullifies `--die-with-parent` (measured orphaned jail on bubblewrap 0.11.1). Consequence documented: under the bwrap backend the payload is PID 2 behind bubblewrap's reaper.
- **Devices**: `--dev-bind /dev /dev` is required next to `--bind / /`; with the bind alone the sandbox's `/dev/null`, `/dev/zero` and `/dev/urandom` return `EACCES`, which breaks payloads such as the `--seccomp` loader's Python interpreter.
- **Tests**: `plugin/test_backend_selection.py` (16 cases) covers selection, the documented flag contract, per-backend argv preservation, absence/failure/degradation paths, the `--user` mapping rule and live private-`/proc` + exit-semantics checks (host-conditional `HOST-DEGRADED-BWRAP` skips). `plugin/test_install.py`'s unshare-failure test now pins `TERMINAL_JAIL_JAIL_BACKEND=unshare` so it keeps asserting the same contract.
- **Docs**: `specs/cli.md` §1/§4 ("Jail backends")/§6/§7/§9/§10, `README.md` (How It Works, Components, Graceful Degradation, Requirements, Host Limitations), `docs/quickstart.md` (backend selection + FAQ), `docs/deploy-to-karahermes.md`.

### Docs & install path (2026-08-05)

- **Quick Start guide** (`docs/quickstart.md`): problem statement, which-component-for-which-user decision tree, install + verify steps for every path (CLI, interruptor modes, plugin, systemd drop-in, deploy shim), FAQ/troubleshooting. Linked from the README.
- **systemd drop-in honesty fix**: the shipped `systemd/90-terminal-jail-hardening.conf` is now explicitly labeled LIGHTWEIGHT (4 active directives) — README and `specs/systemd.md` no longer claim PRIMARY PID-namespace isolation; the full profile (`PrivateUsers`, `RestrictNamespaces`, network/fs) is documented as staged pending per-host verification.
- **Install path fix**: `install.sh` gained local-checkout mode (installs `standalone/terminal-jail` directly from a repo clone when release assets are absent); README Install now leads with the git-clone path and marks the release-URL one-liner as "when published". Scheduler registration `repo_url` corrected to `totalwindupflightsystems/terminal-jail` and pinned in `fleet.toml`.
- **CLI spec alignment** (`specs/cli.md`): documents the real v1.1 interface — `--user`, `--seccomp`, `--interruptor`, `--no-interruptor`, the `while`/`case` parser rules, extended launch forms, exit `126` for blocked commands, and the installer's local-checkout mode.
- **Deploy shim documented** (`standalone/terminal-jail-sh`): now env-configurable (`TERMINAL_JAIL_HOME` / `TERMINAL_JAIL_BRIDGE` / `TERMINAL_JAIL_CLI`) instead of hardcoded machine paths; listed in README Components; `docs/deploy-to-karahermes.md` heredoc updated to match.

## [1.1.0] — 2026-07-24

### Phase 11: Interruptor Bash Command Firewall

- **Parser**: Tokenizes shell commands — pipes, redirects, cmd substitution, heredocs, variable expansion, quoting. Fail-open to passthrough on parse errors.
- **Rule Loader**: YAML-based rules from `/etc/terminal-jail/rules.d/` and `~/.config/terminal-jail/rules.d/`. Lexical ordering, user rules override system.
- **Pattern Matcher**: 9 match types — pattern, command, pipeline, subcommand, path, composite, syscall, network, heredoc. Configurable per-rule.
- **Decider**: Blocklist-first, then allowlist, then auto-sandbox, then user rules. First match wins. 27 built-in rules (10 critical blocklist, 8 auto-sandbox, 9 always-allow).
- **Shell Integration**: JSON bridge (`interruptor_bridge.py`) — stdin/stdout protocol between bash CLI wrapper and Python engine. TERMINAL_JAIL_INTERRUPTOR_MODE: enforce/warn/disabled.
- **Testing**: 56 new Interruptor tests (T-I01 through T-I40), 6 integration tests for CLI compose.
- **Performance**: Cold start 0.08ms, warm start 0.027ms, 1KB parse 0.273ms, 500-rule eval 0.864ms.
- **Documentation**: Updated integration spec with 4-layer defense-in-depth diagram.

### Plugin Core
- PID namespace isolation via `unshare --pid --fork --mount-proc --kill-child=SIGKILL`
- Observability-only plugin architecture (command wrapping lives in Hermes backend/CLI layers)
- Register-based Hermes hook manifest (`pre_tool_call`, `transform_terminal_output`)
- Configurable log levels via `HERMES_TERMINAL_JAIL_LOG_LEVEL`
- Graceful degrade when `unshare` is missing from PATH

### Standalone CLI
- Universal `terminal-jail` bash wrapper (56 lines)
- Works outside Hermes — wraps any command in a PID namespace
- `--help` and `--version` flags
- Byte-exact exit code propagation

### systemd Hardening
- Graduated `90-terminal-jail-hardening.conf` drop-in (14 directives)
- Safe directives active by default, dangerous ones commented
- Rollback procedure documented (<10s downtime)
- Defense-in-depth: `ProtectSystem=strict`, `PrivateUsers=true`, `RestrictNamespaces=~pid`

### Hermes Core Integration
- `--sandbox` CLI flag submitted as upstream PR (#68216)
- Backend-layer command wrapping (`tools/environments/local.py`)
- `terminal.jail_enabled` config key

### Testing
- 108 unit + integration tests (26 skipped — require real `unshare --mount-proc`)
- Real unshare integration tests: fork bomb containment, killall containment, exit code propagation, stdout/stderr integrity, nested jails, signal handling, performance benchmark, env var isolation
- Standalone CLI tests (15 tests)
- install.sh tests (11 tests)
- Metrics export tests (21 tests)
- Edge-case coverage: NUL bytes, non-str input, budget exceptions

### Observability
- Jail metrics counters (wrapped, passed-through, missing-unshare, crashes)
- Byte budget tracking and rejection logging
- Performance regression alerts (p99 > 50ms)
- DuckBrain metrics exporter

### Documentation
- 4 axiom-level specs (plugin, CLI, systemd, integration)
- 5 architecture decision records (ADR-001 through ADR-005)
- Threat-aware: all Phase 5-6 deployment tasks documented as BLOCKED by host limitations
- CONTRIBUTING.md
