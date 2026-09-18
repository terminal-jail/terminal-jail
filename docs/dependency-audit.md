# Dependency Audit — terminal-jail

**Date:** 2026-07-20  
**Auditor:** coding-hermes foreman tick  
**Version:** v1.0.0  
**Task:** T9.3

---

## 1. Plugin Core (`plugin/terminal_jail/plugin.py`)

### Direct Dependencies

| Import | Source | Risk |
|--------|--------|------|
| `logging` | stdlib | None |
| `os` | stdlib | None |
| `shlex` | stdlib | None |
| `shutil` | stdlib | None |
| `time` | stdlib | None |
| `dataclasses.dataclass` | stdlib | None |
| `typing.Final` | stdlib | None |

**Zero third-party imports.** The plugin has no pip dependencies, no vendored libraries, no external packages.

### Transitive Risk from Hermes SDK

The plugin imports nothing from Hermes' Python SDK. Hook registration occurs via `plugin.yaml` manifest — Hermes discovers the module and calls `on_pre_tool_call` / `on_transform_terminal_output` by name. The plugin does not import `hermes`, `hermes_tools`, or any Hermes internals.

**Transitive risk: NONE.** In the worst case of a compromised Hermes SDK, the plugin would still only execute its own code paths — logging, string transformation, and shutil.which().

### Subprocess / Code Execution Surface

| Risk | Finding |
|------|---------|
| `subprocess.Popen` | NOT used |
| `os.system` / `os.popen` | NOT used |
| `exec()` / `eval()` | NOT used |
| Dynamic imports (`__import__`) | NOT used |
| Shell injection via `shlex` | Mitigated — `shlex.quote()` used for all command wrapping |

### Network Surface

| Risk | Finding |
|------|---------|
| `socket` | NOT imported |
| `urllib` / `requests` | NOT imported |
| HTTP / FTP / TCP | NOT used |
| DNS resolution | NOT used |

### Filesystem Surface

| Risk | Finding |
|------|---------|
| File writes (`open`, `write`) | NOT used — plugin only reads env vars via `os.environ.get()` |
| File reads | NOT used |
| Temporary files | NOT used |

### Privilege Escalation

| Risk | Finding |
|------|---------|
| `sudo` / `su` | NOT used |
| `os.setuid` / `os.seteuid` | NOT used |
| `os.setgid` / `os.setegid` | NOT used |
| `capabilities` | NOT modified |

---

## 2. Plugin Init (`plugin/__init__.py`)

| Import | Source | Risk |
|--------|--------|------|
| `logging` | stdlib | None |
| `typing.Any` | stdlib | None |
| `.terminal_jail.plugin.*` | local | None (same repo) |

Same profile as core — pure stdlib, no external risk.

---

## 3. Standalone CLI (`standalone/terminal-jail`)

56-line POSIX bash script. Dependencies:

| Dependency | Type | Risk |
|-----------|------|------|
| `bash` | System shell | Pre-existing; required by Hermes already |
| `unshare` (util-linux) | PID namespace | Required for functionality; system-installed |
| `bwrap` (bubblewrap) | Optional PID-namespace backend with a private `/proc` | External distro package invoked from `PATH`; **never vendored or redistributed** by this repo (LGPL-2.1-or-later). Absent ⇒ `unshare` fallback; an explicitly demanded `bwrap` fails closed |
| `uname` | System info | Coreutils, always present on Linux |

No network calls. No file writes beyond stdout/stderr. No dynamic code loading.

---

## 4. Install Script (`install.sh`)

159-line POSIX sh script. Dependencies:

| Dependency | Type | Risk |
|-----------|------|------|
| `curl` or `wget` | Downloader | Downloads from GitHub Releases over HTTPS |
| `sha256sum` or `shasum` | Checksum verifier | Validates downloaded binary before execution |
| `awk` | Text processing | Extracts checksum |

**Install script security properties verified:**
- Does NOT pipe `curl` directly to `sh` (avoids the classic `curl | sh` attack)
- Uses temp file + SHA256 verification + shebang sanity check + empty file check
- Only writes to `$HOME/.local/bin` — no system directories, no `sudo`
- Modifies user shell profile (`.profile`, `.bashrc`, `.zshrc`) — gated by existence checks
- Does not download or execute arbitrary code at runtime
- Never downloads, builds, installs as a package, or vendors bubblewrap: the optional `bwrap` dependency is advisory only — a host without bubblewrap installs successfully and the CLI keeps the `unshare` backend (TJ-GAP-055)

---

## 5. Test Dependencies

| Dependency | Source | Risk |
|-----------|--------|------|
| `pytest` | PyPI | Test-only; not shipped with plugin |
| `unittest.mock` | stdlib | Test-only |

Tests are not installed or executed by the plugin at runtime.

---

## 6. Supply Chain Summary

| Vector | Status |
|--------|--------|
| pip dependencies | 0 |
| Vendored code | None |
| Network access at runtime | None |
| Subprocess execution at runtime | None (plugin wraps — doesn't execute) |
| File writes at runtime | None |
| Dynamic code loading | None |
| Hermes SDK transitive risk | None |

---

## 7. Verdict

**Risk level: MINIMAL.** The plugin has the smallest possible dependency footprint — seven stdlib imports, zero third-party packages, zero network or filesystem access at runtime, and zero Hermes SDK imports. The standalone CLI and installer depend only on pre-existing system tools (bash, unshare, curl/wget, sha256sum).

**Recommendation:** GPG-sign releases (T9.4) for defense-in-depth, but the dependency surface is already at its theoretical minimum.
