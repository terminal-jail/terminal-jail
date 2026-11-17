# Dependency Audit — terminal-jail

**Date:** 2026-11-17 (source recheck)

**Auditor:** coding-hermes worker

**Version:** v1.3.4 (`pyproject.toml`)

**Task:** T9.3, corrected by DOC-32

**Scope:** Source review at `7b6e561`, covering the observability hooks,
shipped interruptor engine/bridge/loaders, standalone CLI, and installer.
Conditional probe paths below describe shipped behavior; this review does not
certify every containment tier on the audit host or scan resolved dependencies
for vulnerabilities. Command receipts in section 6 distinguish the small
observability module from the complete runtime.

---

## 1. Plugin Core (`plugin/terminal_jail/plugin.py`)

### Direct Dependencies

| Import | Source | Risk |
|--------|--------|------|
| `logging` | stdlib | Interpreter/host trust |
| `os` | stdlib | Interpreter/host trust |
| `shutil` | stdlib | Interpreter/host trust |
| `sys` (inside `_adopt_shared_metrics`) | stdlib | Interpreter/host trust |
| `dataclasses.dataclass` | stdlib | Interpreter/host trust |
| `typing.Final` | stdlib | Interpreter/host trust |

The imports in this file are stdlib (`__future__.annotations` additionally
controls annotation evaluation; receipt E2). These stdlib entries inherit
interpreter/host trust; the table is an import inventory, not an assertion
that interpreter or host compromise is harmless.

**Package dependency:** `pyproject.toml:15` declares `PyYAML>=6.0`.
The shipped engine imports `yaml` inside `RuleLoader._parse_file()`
(`interruptor/rules.py:514`) and `_rule_ids_in_file()`
(`interruptor/decider.py:578`), using `CSafeLoader` or `safe_load` (E1).
Those indented imports are missed by a column-zero import grep. The lower-bound
constraint permits later releases; safe YAML parsing limits object construction
but still relies on the installed PyYAML implementation and its provenance.

### Transitive Risk from Hermes SDK

The source import scan matched **no direct `hermes` / `hermes_tools` imports**
(E2). Registration is through `register(ctx)` and
`ctx.register_hook("pre_tool_call", ...)` / `"transform_terminal_output"`
(`plugin/__init__.py:97-100`), rather than calls to the former wrapping hooks.

**Transitive risk: inherited host trust.** Hermes controls the process, module
loading, hook context, and tool execution. Absence of a direct SDK import does
not isolate this plugin from a compromised host or SDK. The hooks observe;
command wrapping belongs to the CLI/interruptor (`plugin/__init__.py:4-16`).

### Subprocess / Code Execution Surface

| Risk | Finding |
|------|---------|
| Probe subprocesses | `interruptor/userns.py:_run_launch()` calls `subprocess.run()` at line 139 (E4) |
| Payload execution | `cli.py:91` execs bash; shipped loaders exec the payload (E6) |
| Dynamic module loading | Bundled Landlock loader uses `spec_from_file_location()` and `exec_module()` (E6) |
| Native code | seccomp and Landlock `_libc()` load host libc through `ctypes.CDLL()` (E6) |
| Shell injection | CLI quotes arguments (`standalone/terminal-jail:527-531`); rewritten commands also reach shell evaluation (`:1651-1654`). Quoting is a mitigation, not a general injection-safety proof |

### Network Surface

| Risk | Finding |
|------|---------|
| Local IPC | Optional resident bridge `serve()` binds an `AF_UNIX` socket, then chmods it to `0600` before listening (`interruptor_resident.py:233-326`, E5) |
| TCP probes | Landlock-net `_reserve_loopback_listener()` binds `127.0.0.1` on a kernel-selected port; `kernel_denies_connect()` attempts connections (`interruptor/landlock_net.py:303-374`, E5) |
| Payload egress | The optional Landlock-net tier governs TCP connect; actual coverage depends on configuration and kernel support (see `specs/integration.md`, Landlock-net tier). These local probes are not evidence of remote telemetry |

### Filesystem Surface

The core module looks up executables with `shutil.which()` (`plugin.py:145`);
its small import list must not be generalized to the shipped engine.

| Risk | Finding |
|------|---------|
| Rule reads | `RuleLoader._parse_file()` opens rule files; `_rule_ids_in_file()` reads them for provenance (`interruptor/rules.py:499-500`, `decider.py:572-573`, E3) |
| UID-map probes | `_property_observation()` creates `tj-fsaccess-*/caller-600` and attempts `.tj-fsaccess-probe-<pid>` in the current workdir; its `finally` removes probe state (`interruptor/userns.py:251-295`, E4) |
| Landlock proof files | `_make_enforcement_probe()` writes `.tj-landlock-eacces-probe-<pid>` in a caller-writable, ungranted candidate directory, with `tj-ll-proof-*` temporary candidates; probe mode is `0600` (`interruptor/landlock.py:443-510`, E4) |
| Resident socket inode | `serve()` creates the socket parent directory, binds `~/.local/run/terminal-jail/interruptor.sock` by default, chmods it, and unlinks it on handled cleanup; the socket path is configurable (`interruptor_resident.py:63-83,233-333`, E5) |
| Egress diagnostics mark | CLI creates `terminal-jail-net-mark.XXXXXXXX` under its TMPDIR/HOME fallback when the egress tier is enabled; `_note_engine_degradation()` appends a cause to the configured mark path (`standalone/terminal-jail:538-549`, `interruptor/landlock_net.py:605-635`, E5) |

Cleanup paths reduce residue; they do not make these operations read-only or
prove cleanup after every abrupt termination.

### Privilege Escalation

| Risk | Finding |
|------|---------|
| Namespace and identity behavior | Probe launches use `unshare`; subordinate-ID configuration is read from `/etc/subuid` and `/etc/subgid` (`interruptor/userns.py:159-191,273-280`) |
| Kernel restriction setup | Landlock calls `prctl(PR_SET_NO_NEW_PRIVS)` before restriction (`interruptor/landlock.py:280-297`); seccomp also relies on native kernel interfaces |
| Boundary | Effective privileges and containment depend on the host, launch path, and enabled tiers; import counts alone cannot establish privilege safety |

---

## 2. Plugin Init (`plugin/__init__.py`)

| Import | Source | Risk |
|--------|--------|------|
| `logging` | stdlib | Interpreter/host trust |
| `typing.Any` | stdlib | Interpreter/host trust |
| `.terminal_jail.plugin.*` | local | Inherits core and host trust |

The init hook imports are stdlib plus the local observability module (E2).
This is a narrower profile than the installed package's interruptor runtime.

---

## 3. Standalone CLI (`standalone/terminal-jail`)

Bash wrapper (1,760 lines at the reviewed revision; E7). Runtime dependencies
include:

| Dependency | Type | Risk |
|-----------|------|------|
| `bash` | System shell | Executes the wrapper and shell payload paths |
| `unshare` (util-linux) | PID namespace | Host tool and kernel namespace support |
| `bwrap` (bubblewrap) | Optional PID-namespace backend with a private `/proc` | External distro package resolved from `PATH` (LGPL-2.1-or-later); availability and explicit backend demands affect selection |
| Python 3 and the shipped bridge/loaders | Interruptor and kernel-tier support | Python package, PyYAML, libc and kernel behavior are part of the runtime trust surface |
| `uname`, `mktemp`, other shell utilities | Host tooling | OS detection and temporary mark-file creation, among other operations |

The wrapper invokes the Python bridge, reads process/environment and support
files, can create an egress diagnostics mark (E5), and executes payloads through
the selected backend/loaders (E6). Payload filesystem/network behavior is
additional to these wrapper/probe operations and depends on applied containment.

---

## 4. Install Script (`install.sh`)

POSIX sh script (1,690 lines at the reviewed revision; E7). Dependencies include:

| Dependency | Type | Risk |
|-----------|------|------|
| `curl` or `wget` | Downloader | Release mode downloads a wheel and checksum manifest from the configured base URL (GitHub Releases by default) |
| `sha256sum` or `shasum` | Checksum verifier | Verifies the downloaded wheel before extraction |
| Python 3 or `unzip` | Wheel extraction | Release mode needs an available extractor |
| Python 3 / PyYAML | Rule-pack validation | YAML pack validation requires PyYAML; plain JSON has a fallback |
| `awk` and other shell utilities | Text processing / file deployment | Checksum extraction, copying, permissions, and profile updates |

**Install script security properties (source review, E8):**
- Downloads go to temporary files; release mode checks SHA256 against the
  downloaded manifest before extraction. The extracted wrapper is checked for
  the expected shebang and non-empty content.
- Checksum and wheel share the configured release source; checksum agreement
  alone does not authenticate an independently trusted publisher.
- Default deployment includes `$HOME/.local/bin`, the sibling `lib/terminal-jail`
  runtime tree, and user rules. Overrides select other destinations;
  `--hermes-plugin` deploys the plugin tree. The old bin-only write claim was
  narrower than the actual operations.
- PATH setup may modify an existing user shell profile or create `.profile`
  for a default install; explicit and environment-based skip conditions apply.
- Bubblewrap handling is advisory (`install.sh:763-772`); it names a separately
  installed distro dependency.
- Installation fetches release artifacts in opted-in release mode; subsequent
  CLI execution loads the installed bridge/loaders and runs the caller's payload.

---

## 5. Test Dependencies

| Dependency | Source | Risk |
|-----------|--------|------|
| `pytest>=8` | PyPI | Declared dev group |
| `pytest-cov>=6` | PyPI | Declared dev group; coverage tooling |
| `ruff==0.16.8` | PyPI | Declared dev group; lint/format tooling |
| `unittest.mock` | stdlib | Test tooling |

The manifest separates the dev group from the runtime `PyYAML>=6.0`
dependency (E1). This declaration distinguishes intended installation roles;
it is not a provenance or vulnerability assessment of a resolved environment.

---

## 6. Supply Chain Summary

| Vector | Status |
|--------|--------|
| pip dependencies | One declared runtime requirement: `PyYAML>=6.0`; dev requirements listed separately (E1) |
| Bundled code | Repository CLI and tier-loader copies ship in `terminal_jail/_bundled/`; this review is not a full provenance inventory |
| Network access at runtime | Local Unix IPC and TCP loopback enforcement probes (E5); payload egress is a separate containment concern |
| Subprocess execution at runtime | Probe launches, bash entry point, and payload exec paths (E4, E6) |
| File access at runtime | Rule reads, caller-owned probe files, diagnostics marks, socket directory/inode (E3–E5) |
| Dynamic code loading | Local module loading and native libc loading (E6) |
| Hermes SDK transitive risk | Direct SDK import scan is empty (E2); runtime still inherits trust in the host |

### Per-claim reconciliation

Historical claims below are rejected or narrowed, rather than retained as
current security guarantees. Paths under `interruptor/` refer to
`plugin/terminal_jail/interruptor/`.

| Original claim | Ground truth | Evidence command / file:line |
|----------------|--------------|------------------------------|
| “zero third-party packages”; pip dependencies `0` | Runtime declares PyYAML; engine imports it lazily for rules/provenance | E1; `pyproject.toml:15,37`, `rules.py:514`, `decider.py:578` |
| “seven stdlib imports” | Core's list differs from the old table; the full package has a broader import surface | E2; `plugin.py:1-7,66` |
| “zero ... filesystem access”; file reads/writes/temp files absent | Rule reads plus UID-map, Landlock and diagnostics writes; resident socket inode | E3–E5; `rules.py:499`, `userns.py:266-279`, `landlock.py:477-490`, `landlock_net.py:632`, `interruptor_resident.py:267` |
| “zero network ... access”; socket/TCP absent | Optional resident Unix IPC and Landlock-net loopback listeners/connect probes | E5; `interruptor_resident.py:265-267`, `landlock_net.py:303-374` |
| Subprocess execution and dynamic loading absent | `subprocess.run`, `os.execvp`, local module loading and libc loading are shipped | E4, E6; `userns.py:139`, `cli.py:91`, `_bundled/landlock-loader.py:62-71`, `seccomp.py:408-409` |
| SDK transitive risk “NONE”; plugin wraps commands | Import scan is empty, but Hermes still owns execution; registered hooks observe | E2; `plugin/__init__.py:4-16,97-100` |
| CLI 56 lines; installer 159 lines; only pre-existing shell tools | Reviewed files have 1,760 / 1,690 lines; Python/PyYAML and native interfaces participate | E1, E6, E7 |
| Installer writes only to bin; profiles require existence; downloaded “binary” checked | Runtime/plugin/rules deployment and profile creation; release wheel verified before extraction | E8; `install.sh:695,1221-1247,1337,1377-1394,1472-1506` |
| Footprint at “theoretical minimum”; MINIMAL risk | Small core, but third-party parser plus conditional filesystem, IPC, subprocess and native-code surfaces | E1–E8; revised verdict below |

### Source command receipts

Commands ran from the worktree root against `7b6e561` source. Outputs below are
quoted excerpts unless marked complete; scans establish source presence or
absence within their named scope, not the behavior of arbitrary payloads.

**E1 — declarations and nested runtime YAML imports:**

```sh
grep -n '^dependencies\|^dev =' pyproject.toml
grep -nE '^[[:space:]]*import yaml|yaml\.(load|safe_load)' plugin/terminal_jail/interruptor/{rules,decider}.py
```

> `15:dependencies = ["PyYAML>=6.0"]`
> `37:dev = ["pytest>=8", "pytest-cov>=6", "ruff==0.16.8"]`
> `rules.py:514:            import yaml`
> `rules.py:522:                    data = yaml.load(content, Loader=yaml.CSafeLoader)`
> `rules.py:524:                    data = yaml.safe_load(content)`
> `decider.py:578:        import yaml`

**E2 — core/init import scope and hook wiring:**

```sh
grep -nE '^[[:space:]]*(import|from) ' plugin/terminal_jail/plugin.py plugin/__init__.py
if grep -rnE '^[[:space:]]*(from|import)[[:space:]]+hermes([_.[:space:]]|$)' plugin/terminal_jail/ plugin/__init__.py; then printf 'Hermes import matches found\n'; else printf 'Hermes import scan: no matches\n'; fi
grep -nE 'register_hook|pre-execution wrapping is unavailable' plugin/__init__.py
```

Core module list from the import scan: `__future__`, `logging`, `os`,
`shutil`, `dataclasses`, `typing`, `sys` (the last at line 66). Init module
list: `__future__`, `logging`, `typing`, `.terminal_jail.plugin`.

> `Hermes import scan: no matches` (complete SDK scan output)
> `58:            "pre-execution wrapping is unavailable",`
> `99:    ctx.register_hook("pre_tool_call", _on_pre_tool_call)`
> `100:    ctx.register_hook("transform_terminal_output", _on_transform_terminal_output)`

**E3 — rule reads:**

```sh
grep -nE 'open\(file_path\)|content = f.read' plugin/terminal_jail/interruptor/{rules,decider}.py
```

> `rules.py:499:            with open(file_path) as f:`
> `rules.py:500:                content = f.read()`
> `decider.py:572:        with open(file_path) as f:`
> `decider.py:573:            content = f.read()`

**E4 — probe artifacts and subprocess:**

```sh
grep -nE 'mkdtemp|caller-600|\.tj-fsaccess|open\(secret|unlink\(target|def _property_observation|subprocess.run' plugin/terminal_jail/interruptor/userns.py
grep -nE 'def _make_enforcement_probe|tj-ll-proof|\.tj-landlock-eacces|open\(probe,|os.chmod\(probe' plugin/terminal_jail/interruptor/landlock.py
```

> `139:        return subprocess.run(`
> `266:    probe_dir = tempfile.mkdtemp(prefix="tj-fsaccess-")`
> `267:    secret = os.path.join(probe_dir, "caller-600")`
> `268:    target = os.path.join(workdir, f".tj-fsaccess-probe-{os.getpid()}")`
> `270:        with open(secret, "w", encoding="utf-8") as handle:`
> `293:            os.unlink(target)`
> `477:            created = tempfile.mkdtemp(prefix="tj-ll-proof-", dir=temp)`
> `486:            probe = os.path.join(root, f".tj-landlock-eacces-probe-{os.getpid()}")`
> `488:                with open(probe, "w", encoding="utf-8") as handle:`
> `490:                os.chmod(probe, 0o600)`

**E5 — socket and diagnostics artifacts:**

```sh
grep -nE 'DEFAULT_SOCK|def serve|server.bind|os.chmod\(sock_path|sock_path.unlink' plugin/terminal_jail/interruptor_resident.py
grep -nE 'def _reserve_loopback|sock.bind|def kernel_denies_connect|sock.connect|open\(mark_path' plugin/terminal_jail/interruptor/landlock_net.py
grep -nE 'mktemp|\.tj-fsaccess|caller-600|>>|_TJ_NET_MARK_FILE=' standalone/terminal-jail
```

> `63:DEFAULT_SOCK_DIR = Path.home() / ".local" / "run" / "terminal-jail"`
> `64:DEFAULT_SOCK_PATH = DEFAULT_SOCK_DIR / "interruptor.sock"`
> `267:        server.bind(str(sock_path))`
> `287:        os.chmod(sock_path, 0o600)`
> `307:            sock_path.unlink()`
> `307:        sock.bind(("127.0.0.1", 0))`
> `363:        sock.connect((host, port))`
> `632:        with open(mark_path, "a", encoding="utf-8") as fh:`
> `547:            mktemp "${TMPDIR:-${HOME:-/tmp}}/terminal-jail-net-mark.XXXXXXXX" 2>/dev/null || true`

**E6 — execution and loading:**

```sh
grep -nE 'spec_from_file_location|exec_module|execvp' plugin/terminal_jail/_bundled/landlock-loader.py
grep -nE 'spec_from_file_location|execvp' plugin/terminal_jail/_bundled/landlock-loader.py plugin/terminal_jail/cli.py
grep -nE 'libc_name =|ctypes.CDLL' plugin/terminal_jail/seccomp.py plugin/terminal_jail/interruptor/landlock.py
```

> `_bundled/landlock-loader.py:62:                spec = importlib.util.spec_from_file_location(`
> `_bundled/landlock-loader.py:71:                    spec.loader.exec_module(module)`
> `_bundled/landlock-loader.py:91:        os.execvp(args[0], args)`
> `cli.py:91:        os.execvp("bash", ["bash", str(_CLI_SCRIPT), *argv])`
> `seccomp.py:409:    return ctypes.CDLL(libc_name, use_errno=True)`
> `interruptor/landlock.py:234:    return ctypes.CDLL(libc_name, use_errno=True)`

**E7 — script sizes (complete output):**

```sh
wc -l standalone/terminal-jail install.sh
```

> `1760 standalone/terminal-jail`
> `1690 install.sh`
> `3450 total`

**E8 — installer scope and integrity-check ordering:**

```sh
grep -nE 'release_asset_url=|release_checksum_url=|check_sha256 "\$tmp_wheel"|zipfile -e|unzip -q|first_line=|\[ ! -s "\$tmp_payload"|LIB_DIR=|cp -R|cp "\$shipped_rules"|startup_file="\$HOME/.profile"|cat >>|printf.*>>' install.sh
```

> `695:    cp -R "$plugin_source_dir"/plugin/. "$HERMES_PLUGIN_TARGET/"`
> `1247:        cp -R "$SCRIPT_DIR/plugin/terminal_jail" "$LIB_DIR/plugin/"`
> `1337:        cp "$shipped_rules" "$installed_rules"`
> `1348:    release_asset_url="${TERMINAL_JAIL_BASE_URL}/${release_asset}"`
> `1349:    release_checksum_url="${TERMINAL_JAIL_BASE_URL}/SHA256SUMS"`
> `1377:    if ! check_sha256 "$tmp_wheel" "$expected"; then`
> `1386:        if python3 -m zipfile -e "$tmp_wheel" "$tmp_extract"; then`
> `1394:        if unzip -q "$tmp_wheel" -d "$tmp_extract"; then`
> `1418:first_line="$(head -n1 "$tmp_payload")"`
> `1423:if [ ! -s "$tmp_payload" ]; then`
> `1472:            startup_file="$HOME/.profile"`
> `1487:                    cat >> "$startup_file" <<'SHELLRC'`

---

## 7. Verdict

**Risk level: MODERATE (revised from MINIMAL).** This is a qualitative
supply-chain/runtime-exposure rating, not the severity of a newly demonstrated
vulnerability. The observability core remains small and stdlib-based (E2), but
the distributed runtime declares a third-party YAML parser (E1), reads policy
files and creates conditional probe/mark/socket artifacts (E3–E5), uses local
IPC and TCP probes (E5), and launches subprocesses and loads local/native code
(E4, E6). Trust extends to Hermes, the interpreter, installed dependencies,
host tools and kernel support. The old “theoretical minimum” conclusion was
based on an obsolete core-only model and is withdrawn.

**Recommendation:** Retain release-signing as defense-in-depth (T9.4); verify
publisher identity as well as checksums, review resolved PyYAML versions and
provenance, protect rule/loader/socket paths, and verify enabled containment
tiers on each deployment. Source review and documentation gates are separate
from a vulnerability scan, provenance audit, or host enforcement certification.
