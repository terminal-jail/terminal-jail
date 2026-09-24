# LKML Monitoring Guide (T10.3)

How to watch the Linux Kernel Mailing List for changes that affect terminal-jail's PID/user namespace isolation, seccomp filters, and AppArmor interactions.

## What to Monitor

### Key subsystems

| Subsystem | LKML prefix / list | Why it matters |
|-----------|-------------------|----------------|
| Namespaces | `linux-kernel`, `containers@` | `CLONE_NEWPID`, `CLONE_NEWUSER`, `CLONE_NEWNS` changes |
| Seccomp | `linux-kernel`, `linux-security-module@` | BPF filter behavior, new syscall audit flags |
| AppArmor | `linux-security-module@`, `apparmor@` | `kernel.apparmor_restrict_unprivileged_userns` policy changes |
| /proc filesystem | `linux-fsdevel@` | `/proc` mount behavior inside PID namespaces |
| User namespaces | `containers@`, `linux-kernel` | `unshare(2)` flag changes, uid_map/gid_map write restrictions |

### Specific kernel interfaces terminal-jail depends on

| Interface | Kernel option / sysctl | Watch for |
|-----------|----------------------|-----------|
| `unshare(CLONE_NEWPID)` | `kernel.unprivileged_userns_clone` | Default changing from 0→1 or 1→0 |
| `unshare(CLONE_NEWUSER)` | `kernel.apparmor_restrict_unprivileged_userns` | Policy tightening/loosening |
| `/proc/self/uid_map` | `user.max_user_namespaces` | Write permission changes |
| `prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER)` | `CONFIG_SECCOMP_FILTER` | BPF verifier changes that reject existing filters |
| `unshare(CLONE_NEWNS)` | `kernel.unprivileged_userns_clone` | Mount namespace behavior inside user NS |

## Monitoring Channels

### 1. LKML via lore.kernel.org

```
# Search for recent namespace-related patches
https://lore.kernel.org/all/?q=CLONE_NEWPID+OR+CLONE_NEWUSER+OR+unshare

# Search for seccomp changes
https://lore.kernel.org/all/?q=seccomp+AND+filter

# Search for AppArmor user namespace restrictions
https://lore.kernel.org/all/?q=apparmor+AND+user+AND+namespace
```

### 2. RSS feeds via public-inbox

```
# LKML RSS (firehose — filter locally)
https://lore.kernel.org/all/new.atom

# Linux Security Module list
https://lore.kernel.org/linux-security-module/new.atom

# Containers list
https://lore.kernel.org/containers/new.atom
```

### 3. Kernel release changelogs

Check each new kernel release (every ~9 weeks) for relevant commits:

```bash
# Example: check what changed between 7.0 and 7.1
git log v7.0..v7.1 --oneline -- kernel/user_namespace.c kernel/seccomp.c security/apparmor/
```

## Automated Monitoring

The `scripts/kernel-watchdog.sh` (T10.1) already monitors the local kernel's current state. To extend with LKML awareness, add:

1. **Weekly RSS check** — script that fetches the RSS feeds above and greps for relevant keywords
2. **New release diff** — script that diffs `kernel/user_namespace.c`, `kernel/seccomp.c`, `security/apparmor/lsm.c` between kernel versions

### Example weekly check script (future work — not shipped)

`scripts/lkml-check.sh` is **not shipped yet** — the block below is a sketch for a future
helper, not a ready-to-run file. Do not point cron at it until it lands in the repo.

```bash
#!/usr/bin/env bash
# scripts/lkml-check.sh — weekly LKML scan for terminal-jail-relevant patches
# (PROPOSED; not in the repo yet — see note above)

FEEDS=(
  "https://lore.kernel.org/all/new.atom"
  "https://lore.kernel.org/linux-security-module/new.atom"
  "https://lore.kernel.org/containers/new.atom"
)

KEYWORDS="CLONE_NEWPID|CLONE_NEWUSER|unshare|seccomp|uid_map|apparmor.*userns|user.max_user_namespaces"

for feed in "${FEEDS[@]}"; do
  curl -s "$feed" | grep -iE "$KEYWORDS" | head -5
done
```

## Response Protocol

| Severity | Trigger | Response time | Action |
|----------|---------|---------------|--------|
| **Critical** | Kernel change that would break terminal-jail on next upgrade | 48h | File issue, assess if workaround exists, notify Hermes team |
| **High** | New restriction on unprivileged user namespaces | 1 week | Update compatibility matrix, document workaround |
| **Medium** | Seccomp BPF verifier change that may reject existing filters | 2 weeks | Test against affected kernel, update BPF filter if needed |
| **Low** | Documentation-only change (sysctl rename, new config option) | Next quarterly review | Update docs |

## Current State (2026-07-21)

- Kernel: 7.0.0-27-generic (Ubuntu 26.04)
- `kernel.unprivileged_userns_clone`: 1 (enabled)
- `kernel.apparmor_restrict_unprivileged_userns`: 1 (restricted — blocks uid_map writes)
- `user.max_user_namespaces`: 63712
- Seccomp BPF: working (dual-arch x86_64 + aarch64)
