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

The package declares `requires-python = ">=3.11"` (`pyproject.toml:14`), so **Python 3.9 and 3.10 are not
supported**: `pip` refuses the install rather than installing and failing later. This is a *Python*
floor only — the kernel, Landlock and `util-linux` requirements in the sections above are independent of
it, so a 3.11+ interpreter on an old kernel still needs the namespace prerequisites listed there, and a
new interpreter does not raise the kernel floor.

The `Tests` column is justified by the job matrix in `.github/workflows/ci.yml` — the authority for what
CI actually executes — and never by the classifier list in `pyproject.toml`:

```bash
grep -n -A 3 'python-version: \[' .github/workflows/ci.yml
```

| Python Version | Plugin | Tests |
|---------------|--------|-------|
| 3.11 | ✅ | ✅ CI — matrix entry `"3.11"` (primary dev interpreter) |
| 3.12 | ✅ | ✅ CI — matrix entry `"3.12"` |
| 3.13 | ✅ | ✅ CI — matrix entry `"3.13"` |
| 3.14 | ⚠️ untested — installable (≥ floor) but no CI job runs it | ⚠️ untested — absent from the CI matrix |

A row only carries a ✅ in `Tests` when the matrix names that interpreter; anything above the newest
matrix entry is installable by metadata alone and has no test verdict. Note that `pyproject.toml`'s
classifier list is publication metadata, not a test record — it currently lists 3.11 and 3.12 while CI
executes 3.13, so this table follows the matrix.

## Test Compatibility Notes

The repository currently declares version 1.3.4 and requires Python ≥ 3.11. The test count below is a collection snapshot, not a permanent promise: run the command from the repository root whenever the test surface changes.

```bash
.venv/bin/python -m pytest plugin tests --collect-only -q
```

Measured on 2026-11-16: `2162 tests collected`; collection duration varies by host.

This command reports the complete collected scope; it does not claim a fixed unit/integration split. Tests that require unavailable host capabilities report their own skip or failure when the full suite is run.

- Fork bomb containment test (`test_t32_fork_bomb_containment`) requires `ulimit -u` support
- Performance benchmark test requires ≥ 100 iterations for statistical significance

## Reporting Compatibility Issues

If terminal-jail doesn't work on your system:
1. Check the compatibility matrix above
2. Try the standalone CLI as a fallback: `standalone/terminal-jail your-command`
3. Verify kernel config: `sysctl kernel.unprivileged_userns_clone`
4. File a bug report with the template in `.github/ISSUE_TEMPLATE/bug_report.md`

---

Last verified: 2026-11-16 against the published v1.3.3 release and repository version 1.3.4. The backend split described above is present in v1.2.0 and later; this document is current for the v1.3.x source tree and does not describe pre-v1.2 behavior.
