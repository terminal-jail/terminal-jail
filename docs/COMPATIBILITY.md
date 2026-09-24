# terminal-jail Compatibility Matrix

## Kernel Compatibility

| Kernel Version | User Namespaces | PID Namespaces | --mount-proc | Status |
|---------------|-----------------|----------------|--------------|--------|
| 5.4 LTS | ✅ | ✅ | ✅ | Supported |
| 5.10 LTS | ✅ | ✅ | ✅ | Supported |
| 5.15 LTS | ✅ | ✅ | ✅ | Supported |
| 6.1 LTS | ✅ | ✅ | ✅ | Supported |
| 6.6 LTS | ✅ | ✅ | ✅ | Supported |
| 7.0+ | ✅ | ✅ | ⚠️ Varies by distro | Conditional |

**Key:** ✅ = Works, ⚠️ = May require configuration, ❌ = Not supported

### Kernel Configuration Requirements

For PID namespace isolation to work, the following kernel parameters may need to be enabled:

```bash
# Required on some distributions (Debian, Ubuntu ≥ 23.10)
kernel.unprivileged_userns_clone=1

# May be restricted by LSM (AppArmor/SELinux)
# Check with: sysctl kernel.unprivileged_userns_clone
```

### Known Host Limitations

- **Ubuntu 26.04 (kernel 7.0.0-27):** `unshare --mount-proc` requires privileges unavailable in unprivileged user namespaces: the standalone CLI's unshare backend fails at the OS level there. The standalone CLI is the component that wraps commands; the Hermes plugin is **observability-only and cannot wrap commands** (see README and specs/integration.md) — the plugin runs, but the unshare-wrapped isolation is unavailable. The CLI's `bwrap` backend and the systemd drop-in remain viable alternatives (see the jail-backend table below).
- **Debian 12 (kernel 6.1):** Works with `kernel.unprivileged_userns_clone=1`.
- **Arch Linux (kernel 6.x+):** User namespaces enabled by default. Full functionality.

## Hermes Agent Compatibility

| Hermes Version | Plugin Discovery | pre_tool_call Hook | --sandbox Flag | Status |
|---------------|------------------|-------------------|----------------|--------|
| < 1.0 | ❌ | ❌ | not shipped (never existed) | Not supported |
| 1.0 - current | ✅ | ✅ (observe only) | not shipped (never existed) | Observability only |
| Future (PR #68216) | ✅ | ✅ | not shipped (never existed) | Full isolation |

The `--sandbox` flag named in this table's column **does not exist** — `grep -c -- '--sandbox' standalone/terminal-jail` returns 0 and no Hermes version defines it; the column is kept only to mark the flag as never shipped. The plugin provides **observability** (command logging, metrics) on all supported Hermes versions. Full PID namespace wrapping requires the standalone CLI (see the jail backends below), or:
- The `--sandbox` flag from [PR #68216](https://github.com/NousResearch/hermes-agent/pull/68216) to be merged upstream (never shipped in any release), or
- A `pre_terminal_command` hook in Hermes core

### Fallback: Backend-Layer Wrapping

On the `totalwindupflightsystems/hermes-agent` fork (branch `fix/cron-repeat-int-format`), the terminal backend wraps commands with `unshare --pid --fork --mount-proc --kill-child=SIGKILL` when `HERMES_TERMINAL_JAIL_ENABLED=true`. This bypasses the plugin layer entirely — the plugin itself is observability-only and cannot wrap commands.

## Standalone CLI Jail Backends (v1.2)

The standalone CLI performs all command wrapping and selects its backend at runtime via `TERMINAL_JAIL_JAIL_BACKEND=auto|bwrap|unshare` (default `auto`):

| Backend | Requires | Private /proc | `--kill-child=SIGKILL` teardown | Selection | Missing prerequisite |
|---------|----------|---------------|--------------------------------|-----------|----------------------|
| `unshare` | util-linux ≥ 2.38 (≥ 2.34 without `--kill-child`) | ❌ (shared host procfs) | ✅ | `TERMINAL_JAIL_JAIL_BACKEND=unshare` | exits 2 naming the fallback |
| `bwrap` (optional) | bubblewrap ≥ 0.11.1 (verified against 0.11.1; adds a private `/proc` and `--die-with-parent` teardown) | ✅ | ✅ | `TERMINAL_JAIL_JAIL_BACKEND=bwrap` | **fails closed: exit 2, command not run** |
| `auto` (default) | either | ✅ when bwrap passes its probe | ✅ | unset / `auto` | falls back to `unshare` |

Consistent with the README backend table: bubblewrap is an optional runtime dependency resolved from `PATH` (never vendored or installed by this project); an explicit `TERMINAL_JAIL_JAIL_BACKEND=bwrap` on a host without it fails closed (exit 2) — isolation is never silently downgraded.

## util-linux (unshare) Compatibility

| util-linux Version | --pid | --fork | --mount-proc | --kill-child |
|-------------------|-------|--------|-------------|-------------|
| 2.34+ | ✅ | ✅ | ✅ | ❌ |
| 2.38+ | ✅ | ✅ | ✅ | ✅ |
| 2.40+ | ✅ | ✅ | ✅ | ✅ |

`--kill-child=SIGKILL` requires util-linux ≥ 2.38. Earlier versions will still create the PID namespace but cannot guarantee child process cleanup on jail exit.

## Distribution Compatibility

| Distribution | Plugin | CLI | systemd Drop-in | Notes |
|-------------|--------|-----|----------------|-------|
| Ubuntu 24.04 LTS | ✅ | ✅ | ✅ | May need `kernel.unprivileged_userns_clone=1` |
| Ubuntu 26.04 LTS | ⚠️ | ✅ | ✅ | CLI PID-namespace isolation blocked (see host limitations) |
| Debian 12 | ✅ | ✅ | ✅ | Works with userns enabled |
| Debian 13 | ✅ | ✅ | ✅ | Expected to work |
| Arch Linux | ✅ | ✅ | ✅ | Full support |
| Fedora 40+ | ✅ | ✅ | ✅ | User namespaces enabled |
| RHEL 9+ | ⚠️ | ✅ | ✅ | Check SELinux policies |
| Alpine 3.19+ | ✅ | ✅ | ✅ | Uses BusyBox unshare (subset of flags) |
| macOS | ❌ | ❌ | ❌ | No Linux namespaces |
| WSL2 | ⚠️ | ⚠️ | ❌ | Kernel namespaces may be restricted |

## Python Compatibility

| Python Version | Plugin | Tests |
|---------------|--------|-------|
| 3.9 | ✅ | ✅ (CI) |
| 3.10 | ✅ | ✅ (CI) |
| 3.11 | ✅ | ✅ (CI, primary dev) |
| 3.12 | ✅ | Planned |
| 3.13 | ✅ | Planned |
| 3.14 | ✅ | Planned |

## Test Compatibility Notes

- 108 unit/functional tests run on any system with Python ≥ 3.9
- 25 integration tests require `unshare --user --pid --fork --mount-proc` support and will skip otherwise
- Fork bomb containment test (`test_t32_fork_bomb_containment`) requires `ulimit -u` support
- Performance benchmark test requires ≥ 100 iterations for statistical significance

## Reporting Compatibility Issues

If terminal-jail doesn't work on your system:
1. Check the compatibility matrix above
2. Try the standalone CLI as a fallback: `standalone/terminal-jail your-command`
3. Verify kernel config: `sysctl kernel.unprivileged_userns_clone`
4. File a bug report with the template in `.github/ISSUE_TEMPLATE/bug_report.md`

---

Last verified: 2026-09-24 against v1.2.0. This document predates the v1.2 backend split and is stale for pre-1.2 releases: earlier versions had no `TERMINAL_JAIL_JAIL_BACKEND` selection, no bwrap backend, and no Interruptor firewall.
