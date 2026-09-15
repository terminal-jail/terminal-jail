# `terminal-jail` standalone CLI specification

## 1. Purpose and security boundary

`terminal-jail` is the distributable command-line entry point for the Terminal Jail PID-namespace wrapper. It runs one program in a new PID namespace and mounts a namespace-local `/proc`.

The required containment command is:

```text
unshare --pid --fork --mount-proc --kill-child=SIGKILL bash -c 'exec "$@"' terminal-jail <command> [args...]
```

The literal `bash -c` program above is deliberately an argv-preserving trampoline. It is not a shell-concatenated representation of the user command. The first word following the `terminal-jail` placeholder is passed as `$1`; the remaining words are passed as `$2...`; `exec "$@"` then executes them without an additional parse, glob expansion, word splitting, or evaluation.

### Security claims that are valid

With a kernel and `unshare` configuration that permits the requested namespaces:

- The payload has a new PID namespace and sees itself as PID 1.
- The payload sees a `/proc` mounted for that PID namespace.
- Signals addressed through namespace-visible PIDs cannot target host processes outside that PID namespace.
- When the `unshare` parent exits, `--kill-child=SIGKILL` requests SIGKILL for the child process tree created by `--fork`.

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
                 Controlled by TERMINAL_JAIL_SECCOMP env var (default off).
  --interruptor  Enable the Bash command firewall (default). Evaluates
                 commands against a rule engine before execution.
  --no-interruptor  Disable the Bash command firewall.
```

## 4. Launcher implementation contract

The wrapper must begin with:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

`set -e` is mandatory: setup/preflight operations must fail at their first unexpected error. Places where a nonzero status is intentionally inspected must use an `if`/`case` construct so that Bash does not abort before the wrapper prints its diagnostic.

### Required launch form

After parsing and preflight, execute exactly this shape, with no command string construction:

```bash
exec unshare \
  --pid \
  --fork \
  --mount-proc \
  --kill-child=SIGKILL \
  bash -c 'exec "$@"' terminal-jail "$@"
```

Requirements:

- `exec` is mandatory. It avoids an extra parent wrapper, preserves the caller's file descriptors, and makes the `unshare` exit status the CLI exit status.
- The `unshare` flags must be exactly `--pid`, `--fork`, `--mount-proc`, and `--kill-child=SIGKILL`. Do not substitute short forms or omit `--fork`.
- `bash -c 'exec "$@"' terminal-jail "$@"` is mandatory. The word `terminal-jail` supplies Bash's `$0`; the user command begins at `$1`. It prevents a user argument from becoming shell syntax.
- Do not use `eval`, `bash -c "$*"`, `"$@"` as shell source, a temporary command file, a pipeline, command substitution, or `xargs`.
- Do not modify `PATH`, current directory, environment variables, `umask`, resource limits, standard file descriptors, or terminal mode.
- The CLI performs no automatic shell fallback. If a user wants shell syntax, they must explicitly request it: `terminal-jail bash -c 'echo "$HOME"; command | other'`.

### Extended launch forms (v1.1)

The four extended options change the launch shape as follows:

- `--user`: the `--mount-proc` flag is replaced by `--user`. Default launch: `unshare --user --map-users=65534:<subuid_start>:1 --map-groups=65534:<subgid_start>:1 -S 65534 -G 65534 --pid --fork --kill-child=SIGKILL` (subuid/subgid start read from `/etc/subuid`|`/etc/subgid` for the calling user, fallback `100000`) — this uid mapping is what makes filesystem isolation REAL. The exact mapped flags are preflighted first (`unshare <mapped flags> true`); on failure the launch degrades to the legacy mapping-less `unshare --user --pid --fork --kill-child=SIGKILL` with a loud `no filesystem isolation` warning on stderr (e.g. hosts whose AppArmor profile denies setuid/setgid inside unprivileged user namespaces), and `TERMINAL_JAIL_FS_ISOLATION` is exported as `mapped` or `degraded` accordingly (`TERMINAL_JAIL_UID_MAP=0|off|false` forces the legacy mode). Because user namespaces cannot mount `/proc` unprivileged, the host PID view remains exposed — this is documented behavior, not a regression. Hosts are classified by `scripts/fs-isolation-probe.py`.
- `--seccomp`: the launch becomes `unshare <flags> bash -c 'exec python3 "$@"' terminal-jail <seccomp-loader.py> <command> [args...]`. The loader applies the BPF filter inside the PID namespace, then `exec`s the payload. `TERMINAL_JAIL_SECCOMP` (values `1`/`true`/`yes`/`on`) enables the same path without the flag. The loader path is resolved relative to the wrapper (`standalone/seccomp-loader.py`); a missing loader is a preflight error (exit `2`).
- Interruptor evaluation (`--interruptor`, default on): before preflight/launch, the reconstructed command string is piped to `plugin/terminal_jail/interruptor_bridge.py` (located next to the wrapper, or via the Python module path). The bridge returns JSON: `{"action":"block",...}` → the wrapper prints a formatted block box to stderr and exits `126` (in `warn` mode it prints `[terminal-jail] WARN: ...` to stderr and allows execution); `{"action":"modify","modified":"<unshare-prefixed rewrite>"}` → the rewrite already contains its own `unshare` prefix and is executed as-is via `bash -c` (no second wrapping — double `unshare` fails with EPERM); `{"action":"allow"}` → normal launch. If the bridge is unavailable the wrapper fails open with a warning to stderr. `--no-interruptor` and `TERMINAL_JAIL_INTERRUPTOR_MODE=disabled` skip evaluation entirely.
- When the interruptor rewrites a command (`modify`), `--seccomp` is not applied (the rewrite's own namespace wrapper governs).

`TERMINAL_JAIL_VERSION` overrides the reported version string (used by the release process to bake the version).

### Preflight checks

Preflight occurs before the final `exec`:

1. Confirm the host is Linux (`uname -s` exactly `Linux`). Otherwise print a concise diagnostic to stderr and exit `2`.
2. Resolve `unshare` using `command -v unshare`. If absent or not executable, print `terminal-jail: unshare is required (install util-linux)` to stderr and exit `2`.
3. Do not pre-resolve `<command>` on the host. Resolution must happen inside the launch environment, using the inherited `PATH`; pre-resolving would produce incorrect behavior for commands whose PATH, mounts, or executable availability differ at runtime.
4. Do not perform a speculative `unshare` capability probe. Such a probe is not equivalent to the real launch and can have policy-dependent side effects. Let the actual `unshare` invocation report kernel permission/capability failures unchanged on stderr.

The wrapper must use `command -v` only for its own dependency (`unshare`), not to validate the payload command.

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
  unshare --pid --fork (execs Bash trampoline)
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

The wrapper must preserve the status returned by the launched `unshare`/payload path exactly. Because the wrapper `exec`s `unshare`, there is no wrapper post-processing that can lose a Bash, Make, test, or application exit code.

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
| `2` | Wrapper preflight/usage jail error: unsupported host, missing `unshare`, missing command, or missing seccomp loader. | Wrapper only. |
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
| Kernel denies namespace creation (`EPERM`, disabled user namespaces, missing capabilities, container policy) | Actual `unshare` invocation | Preserve `unshare` stderr and returned status exactly. Do not hide it or retry with weaker flags. | Pass-through |
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
| `TERMINAL_JAIL_BASE_URL` | Canonical release base URL | Release endpoint used to download the Bash wrapper and its checksum. |

The script must reject an empty/unset `HOME` with a diagnostic; it must not fall back to `/` or a system location.

### Platform detection

1. Run `uname -s`; accept only `Linux`. For every other OS (macOS, BSD, Windows environments without Linux namespaces), print that Terminal Jail requires Linux and exit nonzero.
2. Run `uname -m`; accept the architectures for which the release has been tested. Because the payload is a Bash script, architecture does not change its bytes, but the installer must still print the detected architecture for diagnostics and may reject explicitly unsupported platforms under release policy.
3. Check for `bash` and `unshare` with `command -v`. The installation may complete without `unshare` only if the installer prominently warns that the CLI cannot run until util-linux is installed. It must never try to install packages, invoke `sudo`, or mutate the system package database.
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
6. Its installer is POSIX `sh`, installs verified content atomically to `~/.local/bin/` by default, and handles PATH idempotently without privilege escalation.
7. Tests cover every row in section 9, including the intentionally negative resource and package-containment tests. No documentation or test report may claim security properties that the fixed PID-only flag set does not provide.
