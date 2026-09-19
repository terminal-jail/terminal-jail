# `terminal-jail` standalone CLI specification

## 1. Purpose and security boundary

`terminal-jail` is the distributable command-line entry point for the Terminal Jail PID-namespace wrapper. It runs one program in a new PID namespace and mounts a namespace-local `/proc`.

The required containment command is:

```text
unshare --pid --fork --mount-proc --kill-child=SIGKILL bash -c 'exec "$@"' terminal-jail <command> [args...]
```

The literal `bash -c` program above is deliberately an argv-preserving trampoline. It is not a shell-concatenated representation of the user command. The first word following the `terminal-jail` placeholder is passed as `$1`; the remaining words are passed as `$2...`; `exec "$@"` then executes them without an additional parse, glob expansion, word splitting, or evaluation.

The command above is the **unshare backend's** launch form. v1.2 adds a second, optional backend — bubblewrap — selected at runtime by `TERMINAL_JAIL_JAIL_BACKEND` (section 4, *Jail backends*), and emits an equivalent argv-preserving command:

```text
bwrap --unshare-user --unshare-pid --die-with-parent --bind / / --dev-bind /dev /dev --proc /proc -- bash -c 'exec "$@"' terminal-jail <command> [args...]
```

`TERMINAL_JAIL_JAIL_BACKEND=unshare` restores the v1.1 behavior byte-for-byte; `auto` (the default) selects bubblewrap only when it is installed *and* its namespace probe passes, so a host without bubblewrap behaves exactly as before.

### Security claims that are valid

With a kernel and `unshare` configuration that permits the requested namespaces:

- The payload has a new PID namespace. Under the unshare backend the payload is namespace PID 1; under the bubblewrap backend it is PID 2, with bubblewrap's minimal reaper as PID 1 (see section 4 — bubblewrap's `--as-pid-1` is deliberately not used because it nullifies `--die-with-parent`).
- The payload sees a `/proc` mounted for that PID namespace. **This is
  backend-conditional (v1.2):** the bubblewrap backend always mounts a fresh
  procfs (the jail's `/proc` lists only the sandbox's own processes); the
  unshare backend mounts one in bare mode (`--mount-proc`) but exposes the
  **host** `/proc` under `--user`, because an unprivileged user namespace
  cannot mount `/proc`. A private `/proc` must therefore never be claimed for
  the unshare `--user` path.
- Signals addressed through namespace-visible PIDs cannot target host processes outside that PID namespace.
- When the `unshare` parent exits, `--kill-child=SIGKILL` requests SIGKILL for the child process tree created by `--fork`; when the bubblewrap process dies, `--die-with-parent` (PR_SET_PDEATHSIG) kills the sandbox tree — including on a SIGKILL of the wrapper, where no userspace cleanup handler can run.

### Explicit non-goals and limitations

The exact required flags are **not** a general-purpose security sandbox. They do not by themselves provide a filesystem root, read-only filesystem, network isolation, seccomp filtering, Linux capability dropping, cgroup resource limits, disk quotas, or a PID-count limit. Existing host files that the invoking user can access remain accessible. Network access remains available. A process may still consume CPU, memory, disk, and host-wide per-user process capacity subject to normal host limits.

Therefore, the CLI must not claim that it prevents a fork bomb from causing host OOM, nor that untrusted `pip` packages cannot modify files or make network requests available to the invoking user. Those requirements need an additional hardening profile (for example: cgroup v2 `pids.max`/`memory.max`, a quota-backed writable filesystem, mount/user/network namespaces, dropped capabilities, and seccomp) and are outside this standalone CLI's fixed flag contract.

The test matrix below includes these cases specifically so CI documents and enforces this boundary rather than silently making a false security claim.

## 2. Deliverable and language recommendation

Install one executable file named `terminal-jail` under `~/.local/bin/terminal-jail`.

### Recommendation: Bash

Implement the standalone CLI as a Bash script with this shebang:

```bash
#!/usr/bin/env bash
```

Rationale:

- The required launcher is already a Bash/`unshare` composition.
- It has no runtime dependency beyond Bash, util-linux `unshare`, and Linux kernel namespace support.
- It is transparent for users installing with `curl | sh`, small enough to audit, and can preserve argv and file descriptors directly with `exec`.
- A Bash implementation can use `set -euo pipefail` and perform clear preflight diagnostics before replacing itself with `unshare`.

Do **not** use Python for the installed wrapper: Python adds interpreter/version availability concerns, and a subprocess-based implementation can accidentally change signal handling or stdio. Do **not** use Go for this v1 wrapper: it would require architecture-specific release binaries, checksum/release distribution, and additional installer logic without improving namespace semantics. Go becomes reasonable only if the project later needs a cross-platform binary manager, cgroup setup, quota provisioning, or structured diagnostics that cannot be reliably implemented in shell.

The installer is a separate POSIX `sh` script because it is invoked as `curl URL | sh`; it must not require Bash before installing the Bash payload.

## 3. Exact command-line interface

### Synopsis

```text
terminal-jail [--help] [--version]
terminal-jail [--user] [--seccomp] [--interruptor | --no-interruptor] <command> [args...]
```

`<command>` is required unless `--help` or `--version` is the sole argument.

### Arguments

| Item | Meaning | Required | Notes |
|---|---|---:|---|
| `<command>` | Executable name or path to execute in the jail. | Yes | Passed as one argv element; it is never interpolated into shell source. |
| `[args...]` | Every argument for `<command>`. | No | Passed byte-for-byte as argv elements, except that Unix argv cannot represent NUL. Empty strings, whitespace, quotes, glob characters, and leading dashes are supported. |

### Options

| Option | Behavior | Exit status |
|---|---|---:|
| `--help`, `-h` | Print the usage text to stdout and do not launch `unshare`. | 0 |
| `--version`, `-V` | Print one machine-readable line: `terminal-jail <VERSION>`. The version is baked into the installed script by the release process. | 0 |
| `--user` | Add user namespace isolation: launch with `unshare --user ...` for PID-namespace lifecycle containment + identity env scrub. Filesystem isolation requires a uid mapping (`--map-users`/`--map-groups` with `-S`/`-G`); it is active ONLY when the exact-flags preflight passes (`TERMINAL_JAIL_FS_ISOLATION=mapped`), otherwise the launch degrades to the mapping-less namespace with a loud `no filesystem isolation` warning (`=degraded`). Incompatible with `--mount-proc`, so the host PID view is exposed. Classify hosts with `scripts/fs-isolation-probe.py`. | Payload |
| `--seccomp` | Apply a seccomp BPF filter inside the jail (denies mount, pivot_root, kexec_load, and other dangerous syscalls) via `standalone/seccomp-loader.py`. Equivalent to `TERMINAL_JAIL_SECCOMP=1`; the env var controls the default (default off). | Payload |
| `--interruptor` | Enable the Bash command firewall (default). The command is evaluated by the interruptor engine (JSON bridge to `plugin/terminal_jail/interruptor_bridge.py`) before execution: block → formatted block box on stderr + exit `126`; modify → the sandboxed rewrite is executed; allow → pass through. | 126 on block; payload otherwise |
| `--no-interruptor` | Disable the Bash command firewall for this invocation. `TERMINAL_JAIL_INTERRUPTOR_MODE=disabled` has the same effect. | Payload |

Flags may appear in any order but must precede `<command>`. There are no
hidden `--`, `--shell`, resource-limit, mount, or networking flags: v1.1
extends the v1 contract only with the four options above plus the
`TERMINAL_JAIL_SECCOMP` and `TERMINAL_JAIL_INTERRUPTOR_MODE` environment
variables. A bare `--` is not a flag terminator — a command literally named
`--` is executed as the payload command.

### Parsing rules

1. With no arguments, print an error and usage to stderr and return jail error `2`.
2. If the sole argument is `--help` or `-h`, print help to stdout and exit `0`.
3. If the sole argument is `--version` or `-V`, print version to stdout and exit `0`.
4. Otherwise, consume any leading flags from the known set (`--user`, `--seccomp`, `--interruptor`, `--no-interruptor`) in any order via a `while`/`case` loop. The first non-flag argument is always `<command>`, even if it begins with `-`; all remaining arguments belong to that command. This makes commands such as `terminal-jail -program arg` representable if such a program path exists.
5. `terminal-jail --help extra` and `terminal-jail --version extra` are treated as attempts to execute commands named `--help` and `--version`, respectively (the flag-consumption loop only recognizes the four extended flags; `--help`/`--version` are honored solely as a single-argument form). The wrapper must not silently discard `extra` arguments.
6. Option parsing must not use `getopts` (a `while`/`case` loop is used instead), because the flag set is fixed and all multi-argument forms after the flags are payload argv, not wrapper options.

### Required usage text

The installed script must print this semantic content (minor whitespace wrapping is allowed):

```text
Usage: terminal-jail <command> [args...]
       terminal-jail --user <command> [args...]
       terminal-jail --seccomp <command> [args...]
       terminal-jail --user --seccomp <command> [args...]
       terminal-jail --interruptor <command> [args...]
       terminal-jail --no-interruptor <command> [args...]
       terminal-jail --help
       terminal-jail --version

Run COMMAND in a new Linux PID namespace. Arguments are passed without
shell re-parsing.

Options:
  --user         Add user namespace isolation: PID namespace lifecycle
                 containment (namespace-exit kills children) + identity env
                 scrub. The host PID view is exposed (no private /proc
                 mount). Filesystem isolation is active ONLY when a uid
                 mapping can be created (TERMINAL_JAIL_FS_ISOLATION=mapped);
                 otherwise it degrades loudly to the mapping-less namespace
                 (see README and scripts/fs-isolation-probe.py).
  --seccomp      Apply a seccomp BPF filter that denies dangerous syscalls
                 (mount, pivot_root, kexec_load, etc.) inside the jail.
                 Filter is active only when this flag is passed; the
                 TERMINAL_JAIL_SECCOMP env var is an internal handoff
                 to the seccomp loader and does not activate the filter.
  --interruptor  Enable the Bash command firewall (default). Evaluates
                 commands against a rule engine before execution.
  --no-interruptor  Disable the Bash command firewall.

Environment:
  TERMINAL_JAIL_JAIL_BACKEND=auto|bwrap|unshare
                 Select the jail backend (default: auto). auto uses
                 bubblewrap when it is installed and its namespace probe
                 passes, otherwise util-linux unshare. Only the bwrap
                 backend provides a PRIVATE /proc; unshare is the
                 documented fallback. A requested backend that cannot run
                 fails closed (exit 2) — isolation is never silently
                 downgraded. See specs/cli.md section 4 "Jail backends".
```

## 4. Launcher implementation contract

The wrapper must begin with:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

`set -e` is mandatory: setup/preflight operations must fail at their first unexpected error. Places where a nonzero status is intentionally inspected must use an `if`/`case` construct so that Bash does not abort before the wrapper prints its diagnostic.

### Required launch forms

The **unshare backend** (the v1.1 contract, unchanged) executes exactly this shape, with no command string construction:

```bash
exec unshare \
  --pid \
  --fork \
  --mount-proc \
  --kill-child=SIGKILL \
  bash -c 'exec "$@"' terminal-jail "$@"
```

The **bubblewrap backend** (v1.2, section *Jail backends*) executes exactly this shape:

```bash
exec bwrap \
  --unshare-user \
  --unshare-pid \
  --die-with-parent \
  --bind / / \
  --dev-bind /dev /dev \
  --proc /proc \
  -- bash -c 'exec "$@"' terminal-jail "$@"
```

Requirements:

- `exec` is mandatory. It avoids an extra parent wrapper, preserves the caller's file descriptors, and makes the backend's exit status the CLI exit status.
- **unshare backend:** the flags must be exactly `--pid`, `--fork`, `--mount-proc`, and `--kill-child=SIGKILL`. Do not substitute short forms or omit `--fork`.
- **bubblewrap backend:** the flags must be exactly `--unshare-user`, `--unshare-pid`, `--die-with-parent`, `--bind / /`, `--dev-bind /dev /dev`, `--proc /proc`, then `--`. Do not add `--as-pid-1` (it makes the payload namespace PID 1 and nullifies `--die-with-parent`), do not omit `--die-with-parent`, and do not replace `--proc /proc` with the host `/proc`. The `--dev-bind /dev /dev` is required: with only `--bind / /` the sandbox's device nodes are present but unusable (`/dev/null`, `/dev/zero`, `/dev/urandom` all return `EACCES`), which breaks payloads such as a Python interpreter.
- `bash -c 'exec "$@"' terminal-jail "$@"` is mandatory for **both** backends. The word `terminal-jail` supplies Bash's `$0`; the user command begins at `$1`. It prevents a user argument from becoming shell syntax.
- Do not use `eval`, `bash -c "$*"`, `"$@"` as shell source, a temporary command file, a pipeline, command substitution, or `xargs`.
- Do not modify `PATH`, current directory, environment variables, `umask`, resource limits, standard file descriptors, or terminal mode.
- The CLI performs no automatic shell fallback. If a user wants shell syntax, they must explicitly request it: `terminal-jail bash -c 'echo "$HOME"; command | other'`.

### Extended launch forms (v1.1)

The four extended options change the launch shape as follows:

- `--user`: the `--mount-proc` flag is replaced by `--user`. Default launch: `unshare --user --map-users=65534:<subuid_start>:1 --map-groups=65534:<subgid_start>:1 -S 65534 -G 65534 --pid --fork --kill-child=SIGKILL` (subuid/subgid start read from `/etc/subuid`|`/etc/subgid` for the calling user, fallback `100000`) — this uid mapping is what makes filesystem isolation REAL. The exact mapped flags are preflighted first (`unshare <mapped flags> true`); on failure the launch degrades to the legacy mapping-less `unshare --user --pid --fork --kill-child=SIGKILL` with a loud `no filesystem isolation` warning on stderr (e.g. hosts whose AppArmor profile denies setuid/setgid inside unprivileged user namespaces), and `TERMINAL_JAIL_FS_ISOLATION` is exported as `mapped` or `degraded` accordingly (`TERMINAL_JAIL_UID_MAP=0|off|false` forces the legacy mode). Because user namespaces cannot mount `/proc` unprivileged, the host PID view remains exposed — this is documented behavior, not a regression. Hosts are classified by `scripts/fs-isolation-probe.py`.
- `--seccomp`: the launch becomes `unshare <flags> bash -c 'exec python3 "$@"' terminal-jail <seccomp-loader.py> <command> [args...]`. The loader applies the BPF filter inside the PID namespace, then `exec`s the payload. `TERMINAL_JAIL_SECCOMP` (values `1`/`true`/`yes`/`on`) enables the same path without the flag. The loader path is resolved relative to the wrapper (`standalone/seccomp-loader.py`); a missing loader is a preflight error (exit `2`).
- Interruptor evaluation (`--interruptor`, default on): before preflight/launch, the reconstructed command string is piped to `plugin/terminal_jail/interruptor_bridge.py` (located next to the wrapper, or via the Python module path). The bridge returns JSON: `{"action":"block",...}` → the wrapper prints a formatted block box to stderr and exits `126` (in `warn` mode it prints `[terminal-jail] WARN: ...` to stderr and allows execution); `{"action":"modify","modified":"<unshare-prefixed rewrite>"}` → the rewrite already contains its own `unshare` prefix and is executed as-is via `bash -c` (no second wrapping — double `unshare` fails with EPERM); the wrapper's namespace preflight describes its **own** launch and never the rewrite, so when a rewrite is present the probe runs with the **rewrite's own** flags (`unshare <flags> true`, taken from the rewrite's `<prefix> bash -c <payload>` shape) — a host that denies bare-mode namespaces while permitting `unshare --user` therefore still runs the rewrite, and only a rewrite whose own prefix cannot be created exits `2` with an `auto-sandbox modify unavailable` verdict (never the generic namespace-creation message, DF-TERMINAL-JAIL-11); a rewrite that carries no `unshare` prefix adds no namespace at this layer and is executed as-is; `{"action":"allow"}` → normal launch. If the bridge is unavailable the wrapper fails open with a warning to stderr. `--no-interruptor` and `TERMINAL_JAIL_INTERRUPTOR_MODE=disabled` skip evaluation entirely.
- When the interruptor rewrites a command (`modify`), `--seccomp` is not applied (the rewrite's own namespace wrapper governs).
- **Transparent auto-sandbox / `modify` wrap selection** (`plugin/terminal_jail/interruptor/userns.py`, TJ-DF-015 + DF-TERMINAL-JAIL-15): the rewrite's `unshare` prefix is selected on a **proven property, never on namespace creation alone**. The uid-mapped launch is used for a rewrite only when this host can create it **and** a payload launched through it can still read a caller-owned mode-600 probe file it just created **and** write a probe file in the caller's current working directory (both checked inside the candidate launch, bounded by an explicit timeout that counts as failure). Otherwise the mapping-less `unshare --user --pid --fork --kill-child=SIGKILL` prefix is used; when the mapped launch is creatable but breaks that property — the payload's host uid is the caller's subuid, so DAC denies the caller's repository and HOME — the engine prints **one** loud `no filesystem isolation` warning on stderr naming the cause and `TERMINAL_JAIL_UID_MAP=0`, and stdout stays pure JSON. The auto-sandbox therefore makes no filesystem-isolation claim; the mapped launch remains the **explicit hard-isolation path** (`terminal-jail --user`, whose own preflight above is unchanged).

`TERMINAL_JAIL_VERSION` overrides the reported version string (used by the release process to bake the version).

### Jail backends (v1.2)

The wrapper has two jail backends. Selection is **runtime-detected** from the environment variable `TERMINAL_JAIL_JAIL_BACKEND`; there are no new CLI flags (the flag contract in section 3 is unchanged, and a bare `--bwrap` is still just a payload command name).

| Value | Behavior | Exit status when the backend cannot run |
|---|---|---|
| `auto` (default) | Use `bwrap` when it resolves on `PATH` **and** the bwrap probe passes (and the invocation does not need the unshare uid mapping, below). Otherwise use `unshare`. | n/a — falls back; a *present but unusable* bwrap warns loudly on stderr and continues with `unshare` |
| `bwrap` | Demand bubblewrap. | `2` — bwrap missing, or the bwrap probe failed; the command does not run and isolation is **never** silently downgraded to `unshare` |
| `unshare` | Pin the v1.1 backend byte-for-byte; bwrap is not probed or invoked. | `2` on namespace-creation failure (unchanged v1.1 message) |
| anything else | Rejected before any namespace work. | `2` — message names the value and the accepted set |

Selection rules and the reasons they exist:

1. **bwrap is never assumed.** Presence is resolved with `command -v bwrap` at runtime; a host without bubblewrap behaves exactly as v1.1 (silently, no warning — that is the documented normal path).
2. **`auto` keeps `unshare` for `--user` on hosts where the uid-mapping probe passes.** A uid mapping (`--map-users`/`--map-groups` + `-S`/`-G`) is real filesystem isolation, and bubblewrap has no unprivileged equivalent: its `--uid`/`--gid` only re-label the sandbox uid while DAC still evaluates with the caller's kuid (measured on bubblewrap 0.11.1: a caller-owned mode-600 file remains readable with `--uid 65534`). `auto` therefore never trades away isolation it can have; where the mapping is unavailable (degraded), `auto` uses bwrap and keeps the loud `no filesystem isolation` warning and `TERMINAL_JAIL_FS_ISOLATION=degraded`.
3. **An explicitly requested `bwrap` always states the isolation loss** on a mapped host: it prints a `no filesystem isolation under the bwrap backend` warning and exports `TERMINAL_JAIL_FS_ISOLATION=degraded`, because that backend cannot apply the mapping this host supports.
4. **A present-but-unusable bwrap is loud.** When `command -v bwrap` succeeds but the probe fails, `auto` prints a warning naming the loss (`this fallback does NOT provide a private /proc`) before continuing with `unshare`.
5. **The unshare fallback stays fully available.** `util-linux unshare` remains a hard preflight requirement (`unshare is required (install util-linux)`, exit `2`) because it is both the fallback backend and the uid-mapping classifier; bubblewrap is optional on top of it.

Backend differences that must never be overstated:

| Property | `unshare` backend | `bwrap` backend |
|---|---|---|
| New PID namespace | yes | yes (`--unshare-pid`) |
| New user namespace | `--user` only | always (`--unshare-user`) |
| Private `/proc` (jail sees only its own PIDs) | bare mode only (`--mount-proc`); **`--user` exposes the host `/proc`** | yes, always (`--proc /proc` mounts a fresh procfs) |
| Payload is namespace PID 1 | yes (`--fork`) | no — bubblewrap's reaper is PID 1, the payload is PID 2 |
| Teardown when the wrapper dies | `--kill-child=SIGKILL` (util-linux installs a parent-death signal on the child) | `--die-with-parent` (PR_SET_PDEATHSIG on the sandbox) |
| Filesystem view | host mount namespace (inherited) | host root and host `/dev` bound in (`--bind / /`, `--dev-bind /dev /dev`) — same visibility and permissions, **no added filesystem isolation** |
| Filesystem isolation via uid mapping | `--user` on a mapping-capable host (`TERMINAL_JAIL_FS_ISOLATION=mapped`) | not available unprivileged (`TERMINAL_JAIL_FS_ISOLATION=degraded`) |
| `--seccomp`, interruptor, exit-status and stdio semantics | unchanged | unchanged (same trampoline, same loader path) |

Both backends are subject to the same host policy: both need unprivileged user namespaces, so on a host that denies them (e.g. Ubuntu's `kernel.apparmor_restrict_unprivileged_userns=1` with the `unprivileged_userns` AppArmor profile) **both** fail closed with exit `2` and the command does not run. Bubblewrap is not a workaround for a host that forbids user namespaces; where bare-mode `unshare` is denied but user namespaces are allowed (a common configuration), the bwrap backend can run in bare mode while the unshare backend cannot — an improvement, not a guarantee.

Prerequisites: the `bubblewrap` system package (`apt install bubblewrap` / `dnf install bubblewrap`), invoked as an external binary resolved from `PATH` at run time; it is an optional runtime dependency like `util-linux` and is never vendored, bundled, or redistributed by this MIT-licensed repository — no vendored source tree, no git submodule, no binary blob, and no download or build step in `install.sh`, which prints an advisory note only when `bwrap` is absent and still installs successfully (TJ-GAP-055). bubblewrap is LGPL-2.1-or-later under its own authors' terms: installing it and meeting its license obligations are between the operator and their distribution (this is project packaging guidance, not legal advice). The CLI falls back to the `unshare` backend when bubblewrap is absent, and an explicitly demanded `TERMINAL_JAIL_JAIL_BACKEND=bwrap` fails closed (exit `2`, command not run) when it is missing or unusable. Verified against bubblewrap 0.11.1. Host classification helpers: `scripts/pidns-capability-probe.py` (bare-mode namespace creation) and `scripts/fs-isolation-probe.py` (uid mapping); a bwrap-specific containment battery is TJ-GAP-056.

### Preflight checks

Preflight occurs before the final `exec`:

1. Confirm the host is Linux (`uname -s` exactly `Linux`). Otherwise print a concise diagnostic to stderr and exit `2`.
2. Reject an unknown `TERMINAL_JAIL_JAIL_BACKEND` value before any namespace work (exit `2`, message names the value and the accepted set).
3. Resolve `unshare` using `command -v unshare`. If absent or not executable, print `terminal-jail: unshare is required (install util-linux)` to stderr and exit `2`. This check is unconditional in v1.2: `unshare` is both the fallback backend and the uid-mapping classifier.
4. Resolve the backend: `command -v bwrap` (skipped entirely when the value is `unshare`), then probe the selected backend's exact launch flags with a throwaway `true` payload. A failed probe on an explicitly requested backend is a hard error (exit `2`, command not run). This probe is deliberate and backend-specific — it is what makes the documented degradation contract (exit `2` + a message) reachable instead of leaking a raw backend error after `exec`.
5. Do not pre-resolve `<command>` on the host. Resolution must happen inside the launch environment, using the inherited `PATH`; pre-resolving would produce incorrect behavior for commands whose PATH, mounts, or executable availability differ at runtime.

The wrapper must use `command -v` only for its own dependencies (`unshare`, optionally `bwrap`), not to validate the payload command.

## 5. Standard stream and terminal preservation

### File-descriptor contract

The wrapper must preserve the caller's descriptor bindings exactly:

```text
caller stdin  (fd 0) ──┐
caller stdout (fd 1) ─┼─> terminal-jail Bash ─> exec unshare ─> Bash trampoline ─> payload
caller stderr (fd 2) ─┘
```

No stage may redirect, capture, close, duplicate, serialize, buffer, pipe, tee, or merge fd 0, 1, or 2. The final `exec` retains those descriptors. Consequently:

- stdin supports pipes, redirected files, heredocs, and a terminal.
- stdout remains raw payload stdout; binary data, ANSI escape sequences, and output ordering are not transformed by the wrapper.
- stderr remains raw payload stderr; it is never merged into stdout.
- A noninteractive pipeline such as `printf x | terminal-jail cat > out` preserves the byte stream.

Wrapper diagnostics (usage and preflight errors) go to stderr. Help/version output goes to stdout. The implementation must never emit wrapper log lines during a successful command launch.

### Interactive/PTY behavior

The wrapper must not allocate a PTY, invoke `script`, change job control, call `stty`, or attempt to proxy keystrokes. It inherits the existing controlling terminal and its process group exactly as `exec` normally does:

```text
terminal emulator / SSH PTY
          │ fd 0, fd 1, fd 2; controlling TTY
          ▼
  invoking interactive shell
          ▼
  terminal-jail (exec)
          ▼
  <backend> --pid ... (execs Bash trampoline)
          ▼
  interactive payload, e.g. bash or python
```

Interactive usage is therefore supported as:

```text
terminal-jail bash
tty | terminal-jail cat
terminal-jail python3
```

TTY-dependent programs must observe `isatty(0)`, `isatty(1)`, and `isatty(2)` exactly as they do outside the wrapper. The PID namespace changes process visibility; it does not create a separate terminal session or PTY. Terminal-generated signals such as Ctrl-C follow the inherited foreground process group rules. This behavior is intentional and must be documented, rather than simulated with an unsafe hand-rolled signal proxy.

## 6. Exit-status contract

The wrapper must preserve the status returned by the launched backend/payload path exactly. Because the wrapper `exec`s the backend, there is no wrapper post-processing that can lose a Bash, Make, test, or application exit code. Both backends use the same `bash -c 'exec "$@"'` trampoline, so `command not found` (normally `127`) and permission errors (normally `126`) keep their native diagnostics and statuses under either backend (verified live for the bubblewrap backend).

Examples:

```text
terminal-jail true                 -> 0
terminal-jail false                -> 1
terminal-jail bash -c 'exit 42'    -> 42
terminal-jail make target          -> exactly make's status
```

For a signal-terminated payload, the invoking shell reports the platform's normal encoded status (commonly `128 + signal`, e.g. `137` for SIGKILL). The CLI must not translate it.

### Status table

| Status | Meaning | Source |
|---:|---|---|
| `0` | Successful wrapper action or payload success. | Help/version, or payload. |
| `1` | Conventional payload command failure. | Payload/unshare execution path; passed through unchanged. |
| `2` | Wrapper preflight/usage jail error: unsupported host, missing `unshare`, missing command, missing seccomp loader, unknown `TERMINAL_JAIL_JAIL_BACKEND` value, or a requested backend that cannot run (bwrap missing / bwrap probe failed). | Wrapper only. |
| `126` | Command blocked by the interruptor (enforce mode). | Interruptor block box on stderr; also the payload's own `126` (permission denied) passes through unchanged. |
| `3` | Reserved for a future explicit jail setup/configuration error. v1 does not intentionally emit it. | Wrapper only. |
| `4` | Reserved for a future explicit resource/quota setup error. v1 does not intentionally emit it. | Wrapper only. |
| `5`–`255` | Payload status, signal-derived status, or an `unshare`/kernel runtime failure; preserved exactly. | Launch path. |

Important compatibility rule: Unix exit statuses are only 8 bits, and arbitrary payloads legitimately return values `2+`. It is impossible to both reserve every value `2+` exclusively for jail errors and preserve arbitrary payload exit codes exactly. This specification resolves that conflict by reserving `2` only for failures detected by the wrapper before `exec`; all statuses from the actual launch path are pass-through. Documentation may describe `2+` as possible jail/runtime errors, but must never infer that every `2+` came from the jail.

## 7. Required error behavior

| Condition | Detection point | Required user-visible behavior | Required status |
|---|---|---|---:|
| No command | Wrapper argument parser | Error plus usage on stderr. | 2 |
| Non-Linux host | Wrapper preflight | Explain that this CLI requires Linux PID namespaces. | 2 |
| `unshare` unavailable | Wrapper preflight | Explain that util-linux `unshare` is required. | 2 |
| `TERMINAL_JAIL_JAIL_BACKEND` unknown value | Wrapper preflight (before any namespace work) | Name the value and the accepted set (`auto`, `bwrap`, `unshare`); the command is not run. | 2 |
| `TERMINAL_JAIL_JAIL_BACKEND=bwrap` but bubblewrap is not installed | Wrapper preflight | Say bubblewrap is not installed, name the system package, and state that the command was not run — never fall back silently. | 2 |
| `TERMINAL_JAIL_JAIL_BACKEND=bwrap` but the bwrap probe fails | Wrapper preflight | Say bwrap namespace creation failed and that the requested backend is never silently downgraded; the command is not run. | 2 |
| `TERMINAL_JAIL_JAIL_BACKEND=auto`, bubblewrap present but its probe fails | Wrapper preflight | Warn on stderr that the fallback does **not** provide a private `/proc`, then continue with the `unshare` backend. | Payload (or `2` if `unshare` also fails) |
| Bridge-supplied `modify` rewrite whose own `unshare` prefix cannot be created | Wrapper preflight, probe of the rewrite's own flags | Say the auto-sandbox rewrite is unavailable, name the flags probed and their status, and state that the command was not run. Never the generic bare-mode namespace-creation message — a rewrite is executed by its own prefix, not by the wrapper's launch (DF-TERMINAL-JAIL-11). | 2 |
| Kernel denies namespace creation (`EPERM`, disabled user namespaces, missing capabilities, container policy) | Selected backend's probe | Preserve the backend's stderr and returned status exactly. Do not hide it or retry with weaker flags. | Pass-through (probe failure on an explicitly requested backend: `2`) |
| Payload command not found | Bash trampoline `exec` | Preserve Bash's normal `command not found` stderr, including the command name. | Normally 127; pass-through |
| Payload executable not permitted | Bash trampoline/kernel | Preserve native `Permission denied` diagnostic and status. | Normally 126; pass-through |
| Disk full / quota (`ENOSPC`/`EDQUOT`) | Payload filesystem operation | Preserve payload stderr and exact returned status. | Pass-through |

Disk quota note: v1 does not create or enforce a quota. `ENOSPC` and `EDQUOT` can occur only if the underlying host filesystem or external sandbox already enforces them. Adding a quota option later is a breaking expansion and must be specified separately.

## 8. Installer specification (`install.sh`)

The published install URL is expected to be used as:

```sh
curl -fsSL https://<project-host>/install.sh | sh
```

Release documentation must replace `<project-host>` with the canonical HTTPS host. The installer itself must be usable by POSIX `sh` and must not assume Bash, Python, package managers, root, `sudo`, or a writable system prefix.

**Local-checkout mode:** when `install.sh` is executed from a repository clone (`standalone/terminal-jail` present next to the script), it installs the local wrapper directly instead of downloading release assets, and skips the downloader/checksum requirements (the wrapper comes from the trusted checkout; the shebang/content sanity checks still run). This keeps the documented install path working before any release assets are published. Release mode remains the default for `curl | sh` invocations.

### Installer inputs and defaults

| Variable | Default | Meaning |
|---|---|---|
| `TERMINAL_JAIL_VERSION` | Current stable release version | Optional pinned release version. `latest` is allowed only if project policy explicitly supports it. |
| `TERMINAL_JAIL_INSTALL_DIR` | `$HOME/.local/bin` | Installation directory. |
| `TERMINAL_JAIL_RULES_DIR` | Derived from the install scope (see below) | Target directory for the shipped default rules file (`00-builtins.yaml`). A non-empty value is used verbatim and wins over any derivation, even outside the install prefix. |
| `TERMINAL_JAIL_BASE_URL` | Canonical release base URL | Release endpoint used to download the Bash wrapper and its checksum. |

Scope rule (DF-TERMINAL-JAIL-8): the installer must not write user config outside the scope the caller selected. The default install (`$HOME/.local/bin`) targets the live user rules directory `$HOME/.config/terminal-jail/rules.d` unchanged. Any custom `TERMINAL_JAIL_INSTALL_DIR` prefix receives its default rules under `<prefix>/config/terminal-jail/rules.d` — the engine does not scan prefix-local config (it loads only `/etc/terminal-jail/rules.d` and `~/.config/terminal-jail/rules.d`), so the installer prints a WARNING naming the target and the override for prefix installs. An explicit `TERMINAL_JAIL_RULES_DIR` always wins.

The script must reject an empty/unset `HOME` with a diagnostic; it must not fall back to `/` or a system location.

### Platform detection

1. Run `uname -s`; accept only `Linux`. For every other OS (macOS, BSD, Windows environments without Linux namespaces), print that Terminal Jail requires Linux and exit nonzero.
2. Run `uname -m`; accept the architectures for which the release has been tested. Because the payload is a Bash script, architecture does not change its bytes, but the installer must still print the detected architecture for diagnostics and may reject explicitly unsupported platforms under release policy.
3. Check for `bash`, `unshare`, and (optionally) `bwrap` with `command -v`. The installation may complete without `unshare` only if the installer prominently warns that the CLI cannot run until util-linux is installed. It must never try to install packages, invoke `sudo`, or mutate the system package database. `bwrap` (bubblewrap) is OPTIONAL and is never a preflight error: when it is absent the installer prints an advisory NOTE naming the distro system package (`apt install bubblewrap` / `dnf install bubblewrap`), the `unshare` fallback backend, and the fact that the installer neither downloads, builds, nor vendors bubblewrap — the installation still succeeds. An explicitly demanded `TERMINAL_JAIL_JAIL_BACKEND=bwrap` still fails closed at run time (sections 4 and 7).
4. Require one HTTPS-capable downloader: prefer `curl -fsSL`; otherwise use `wget -qO-`. If neither is available, fail with a concise error.
5. Require checksum verification tooling if release policy publishes checksums: prefer `sha256sum`, then `shasum -a 256`. If no verifier is available, fail closed rather than installing unverified executable content.

### Download, verification, and atomic installation

1. Create the target directory with `mkdir -p "$TERMINAL_JAIL_INSTALL_DIR"`; failures are fatal.
2. Create a temporary file in that same directory using `mktemp` so the final rename is atomic on the same filesystem. Arrange a POSIX `trap` to remove temporary files on exit, interruption, and termination.
3. Download the versioned `terminal-jail` payload and its published SHA-256 checksum over HTTPS.
4. Verify that the downloaded payload's SHA-256 exactly matches the published release checksum before marking it executable or replacing an existing installation.
5. Validate the payload's first line is exactly `#!/usr/bin/env bash` and that it is nonempty. This is an integrity sanity check, not a substitute for the checksum.
6. Set mode `0755` on the verified temporary file.
7. Atomically rename it to `$TERMINAL_JAIL_INSTALL_DIR/terminal-jail`. Existing installation replacement is allowed only after successful download and verification.
8. Print the installed absolute path and `terminal-jail --version` output. Do not launch a jailed test command from the installer; namespace permissions may differ from the install environment and failure must not leave installation ambiguous.

### PATH setup

The desired install location is `~/.local/bin/`, not `/usr/local/bin`, so installation is unprivileged.

1. If `$TERMINAL_JAIL_INSTALL_DIR` is already present as a full path element in `$PATH`, state that no PATH change is needed.
2. Otherwise detect a shell startup file conservatively, in this order: `$HOME/.profile`, `$HOME/.bash_profile`, `$HOME/.bashrc`, `$HOME/.zshrc`.
3. Append exactly one idempotent, clearly delimited POSIX-compatible block to the first appropriate existing startup file, or create `$HOME/.profile` if none exists and the user has not chosen a custom install directory:

   ```sh
   # terminal-jail
   export PATH="$HOME/.local/bin:$PATH"
   ```

4. Before appending, search the file for the `# terminal-jail` marker and for an equivalent PATH entry. Never append duplicates.
5. If the shell cannot be identified or no startup file is safe to change, do not guess. Print the exact export command the user must add manually.
6. Do not source startup files from the installer. Tell the user to open a new shell or run the displayed `export` command in the current one.

## 9. Test matrix

All tests must execute the installed or repository wrapper, not an inlined copy of the `unshare` command. Tests requiring namespaces must be skipped with an explicit reason only when the CI environment demonstrably denies `unshare`; they must not be silently marked successful.

| ID | Scenario | Setup / command shape | Expected outcome | What it proves / does not prove |
|---|---|---|---|---|
| CLI-01 | Help | `terminal-jail --help` | Usage on stdout; status 0; no `unshare` launch. | Stable discoverability. |
| CLI-02 | Version | `terminal-jail --version` | Exactly one version line on stdout; status 0. | Release identity. |
| CLI-03 | Missing command | `terminal-jail` | Error/usage on stderr; status 2. | Argument validation. |
| CLI-04 | Argv preservation | Execute a helper that writes each argv element as an unambiguous length-prefixed record; pass empty, spaces, quotes, glob characters, newline, and leading-dash args. | Received argv exactly equals supplied argv. | No shell injection or quoting corruption. |
| CLI-05 | Stdio bytes | Pipe binary fixture bytes through `terminal-jail cat`, redirect stdout to a file, and compare SHA-256; separately write distinct sentinels to stdout and stderr. | Byte-identical stdout; stderr sentinel only on stderr; stdin reaches payload. | All three standard streams are preserved. |
| CLI-06 | PTY | Run `terminal-jail bash -c 'test -t 0; test -t 1; test -t 2'` from a test-created PTY. | Status 0; no nested PTY; terminal settings unchanged before/after. | Interactive descriptor inheritance. |
| CLI-07 | Exit passthrough | Run `terminal-jail bash -c 'exit 42'` and `terminal-jail make <known-failing-target>`. | Caller observes 42 and exactly Make's known status. | No wrapper status translation. |
| CLI-08 | Command missing in jail | `terminal-jail definitely-not-a-real-command` | Native Bash not-found diagnostic on stderr; normally 127. | Resolution occurs in the trampoline and status is preserved. |
| CLI-09 | Permission denied | Execute a non-executable fixture through the CLI. | Native permission diagnostic; normally 126. | Kernel/Bash errors are not masked. |
| CLI-10 | `killpg(1)` containment | Use a dedicated helper executed as namespace PID 1. The helper calls `setpgid(0, 0)`, confirms its namespace PID/PGID are both 1, spawns a descendant in that group, then calls `killpg(1, SIGKILL)`. Host harness checks the descendant has terminated and checks an independently created host sentinel process is still alive. | Jailed process group dies (caller normally sees SIGKILL-derived 137); host sentinel remains alive. | Namespace PID/process-group targeting cannot kill the host sentinel. |
| CLI-11 | `killall` host protection | Start a uniquely named host sentinel process; in jail run `killall -9 <sentinel-name>` if `killall` is installed, then verify host sentinel is alive. Also record `/proc/1` inside the jail and outside it. | `killall` finds no host sentinel through namespace `/proc`; host sentinel survives. | PID namespace `/proc` visibility. It does not prove filesystem/network isolation. |
| CLI-12 | Fork bomb / resource boundary | In a disposable VM or cgroup-limited CI worker only, run a bounded fork stress helper under the exact v1 wrapper and monitor host cgroup memory/PID usage. | Test documents that PID namespace alone does **not** impose `pids.max`, memory, or OOM protection. It must fail the claim “PID namespace prevents OOM” unless an external cgroup limit is deliberately applied. | Prevents a false security regression claim. Never run an unbounded fork bomb on developer hosts or shared CI. |
| CLI-13 | `pip install malware` boundary | In a disposable test account, use a harmless test package whose install hook attempts an allowed-user write and an outbound connection to a test endpoint; run it through the CLI. | With only v1 flags, the write/network attempt may succeed. The test must record this as an expected limitation, not a pass for sandbox escape prevention. | Demonstrates that PID isolation is not package/malware containment. A future hardened profile must reverse this expectation. |
| CLI-14 | Disk full/quota | Run a payload that writes to a filesystem mounted with a deliberately small external quota or tmpfs size. | Payload gets `ENOSPC`/`EDQUOT` diagnostic and nonzero status; wrapper does not alter either. | Error propagation; not quota enforcement by v1. |
| CLI-15 | Unshare unavailable | Execute wrapper with a PATH containing no `unshare` (while retaining required shell utilities). | Clear stderr diagnostic; status 2. | Dependency error path. |
| CLI-16 | Namespace permission denied | Run in a known restricted container/user configuration where the real `unshare` call returns EPERM. | Native `unshare` diagnostic and exact status pass through. | Permission error is not hidden or weakened. |
| CLI-17 | bwrap selected by `auto` | `TERMINAL_JAIL_JAIL_BACKEND=auto` with PATH-stub recorders for `bwrap` and `unshare`; run a simple payload. | The recorded bwrap argv is exactly the documented flag set, then `--`, then the `bash -c 'exec "$@"' terminal-jail …` trampoline; `unshare` is never invoked; no warning on stderr. | Runtime detection and the documented flag contract, without needing a real namespace. A stub proves argv shape, not containment. |
| CLI-18 | Private `/proc` under the bwrap backend | On a bubblewrap-capable host run `readlink /proc/self/ns/pid`, `ls /proc`, `cat /proc/1/comm` inside the jail and on the host. | The namespace inode differs, the jail's PID count is far below the host's, and `/proc/1/comm` is not the host init. | The private-`/proc` property is real for this backend. Host-conditional: skip with a `HOST-DEGRADED-BWRAP` marker where bwrap is absent or cannot create namespaces. |
| CLI-19 | bwrap absent falls back to unshare | `auto` with a PATH that has no `bwrap` (stub `unshare` recorder). | The recorded `unshare` argv is the v1.1 shape; no warning is printed. | The documented normal path is silence-preserving; bubblewrap is never assumed. |
| CLI-20 | Explicit `bwrap`, binary missing | `TERMINAL_JAIL_JAIL_BACKEND=bwrap`, PATH without `bwrap`. | Exit `2`; stderr names bubblewrap and the system package; the command does not run; `unshare` is not invoked. | Fail closed: an explicitly requested backend is never silently downgraded. |
| CLI-21 | Explicit `bwrap`, probe fails | `TERMINAL_JAIL_JAIL_BACKEND=bwrap` with a `bwrap` stub whose probe exits nonzero. | Exit `2`; the stub records the probe only (no launch); `unshare` is not invoked. | Same fail-closed contract for a host that has bwrap but denies its namespaces. |
| CLI-22 | `auto` with a present-but-unusable bwrap | `auto` with a failing `bwrap` probe stub and a working `unshare` stub. | A warning naming the private-`/proc` loss is printed, then the `unshare` launch proceeds. | Degradation stays loud; no silent loss of a publicized property. |
| CLI-23 | Argv preservation per backend | Run the wrapper with empty, whitespace, quote, glob, `$(…)`, semicolon and leading-dash arguments through each backend's recorder; then live through bwrap with `printf '[%s]'`. | The recorded trampoline argv equals the supplied argv element-for-element, and the live output is byte-exact. | No shell re-parsing, no reconstruction of the user command under either backend. |
| CLI-24 | Unknown backend value | `TERMINAL_JAIL_JAIL_BACKEND=<typo>`. | Exit `2`; the message names the value and the accepted set; nothing is launched and no namespace is created. | A configuration typo cannot silently select a weaker backend. |
| CLI-25 | v1.1 backend pinned | `TERMINAL_JAIL_JAIL_BACKEND=unshare` with `bwrap` present on PATH. | The `unshare` launch shape is used and `bwrap` is neither probed nor invoked. | The pre-v1.2 behavior is exactly recoverable, byte-for-byte. |
| CLI-26 | Optional bubblewrap absent at install time | Run `install.sh` from a checkout with a curated PATH holding real coreutils but no `bwrap` (and, in the counter-case, a `bwrap` stub). | Exit `0` in both cases; with `bwrap` absent an advisory NOTE names the distro package (`apt install bubblewrap` / `dnf install bubblewrap`), the `unshare` fallback, and the no-vendoring boundary, the binary is installed, and no `bwrap`/bubblewrap artifact or vendored package appears under the install scope; with `bwrap` present the NOTE is not printed. | The optional dependency never fails an install, and the installer advises rather than acting. |
| CLI-27 | No vendored bubblewrap in the tracked tree | `git ls-files` over the repository plus the packaging claims in `README.md` / `specs/cli.md`. | No `vendor/`-style path, no git submodule, no bubblewrap C source file, and the docs keep the optional/distro-package/external/no-vendoring/not-legal-advice boundary while an explicit `TERMINAL_JAIL_JAIL_BACKEND=bwrap` stays documented as fail-closed. | The MIT repository distributes no bubblewrap code: the distro package is the only install path (TJ-GAP-055). |

### Safety requirements for destructive-looking tests

- Never execute a literal unbounded fork bomb.
- Never use a real malicious package or a package that attempts host persistence, credential access, privilege escalation, destructive writes, or external exfiltration.
- Run process-signal and resource tests inside an ephemeral VM/container with an externally imposed cgroup limit and a timeout.
- Every test that creates a background process must use a cleanup trap and verify cleanup before returning.

## 10. Acceptance criteria

A v1 implementation is complete only when all of the following are true:

1. The executable implements the exact interface and parser rules in section 3.
2. Its launcher uses the exact required `unshare` flags and an argv-preserving `bash -c 'exec "$@"'` trampoline.
3. It begins with Bash plus `set -euo pipefail` and avoids shell-string evaluation of payload arguments.
4. It preserves fd 0/1/2 and PTY behavior with no intermediary pipes or output rewriting.
5. It preserves payload/unshare exit statuses exactly and returns wrapper usage/preflight errors as documented.
6. Its installer is POSIX `sh`, installs verified content atomically to `~/.local/bin/` by default, and handles PATH idempotently without privilege escalation; it treats the optional bubblewrap dependency as advisory only — a distro system package it never downloads, builds, installs, or vendors.
7. Tests cover every row in section 9, including the intentionally negative resource and package-containment tests. No documentation or test report may claim security properties that the fixed PID-only flag set does not provide.
8. (v1.2) The backend is selected by `TERMINAL_JAIL_JAIL_BACKEND` only, runtime-detected, with no new CLI flags; the unshare backend's launch form and exit semantics are unchanged; an explicitly requested backend that cannot run fails closed (exit `2`, command not run, no silent downgrade); the bubblewrap backend's command carries `--unshare-user`, `--unshare-pid`, `--die-with-parent`, `--bind / /`, `--dev-bind /dev /dev`, `--proc /proc` and the identical argv-preserving trampoline; a private `/proc` is claimed **only** for the bubblewrap backend and only where a live check on the host proves it; and `--seccomp`, interruptor, stdio and exit-status behavior are identical under both backends. bubblewrap itself stays an optional external distro package resolved from `PATH`: this MIT-licensed repository vendors, bundles, and redistributes none of it (section 4).
