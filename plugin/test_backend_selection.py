"""TJ-GAP-054 — runtime-detected bubblewrap (bwrap) backend for the CLI.

Design under test (specs/cli.md section 4 "Jail backends"):

- ``TERMINAL_JAIL_JAIL_BACKEND`` = ``auto`` (default) | ``bwrap`` | ``unshare``.
- ``auto`` prefers bwrap when it is installed AND its probe passes, but keeps
  the unshare mapped launch for ``--user`` on hosts where the uid-mapping
  probe passed (bubblewrap has no unprivileged equivalent, and a mapping is
  real filesystem isolation).
- ``bwrap`` is a demand: missing binary or failed probe => exit 2 and the
  command does NOT run (no silent downgrade).
- ``unshare`` pins the pre-existing backend byte-for-byte.

Most cases run against PATH-stub recorders (length/NUL-delimited argv logs), so
they are host-independent and need no privileges; the live assertions skip with
a HOST-DEGRADED-BWRAP marker on hosts without a usable bubblewrap, exactly like
the existing HOST-DEGRADED-PIDNS / HOST-DEGRADED-FSISO lanes.

The orphan-teardown property of ``--die-with-parent`` is measured by the
project's own probe recipes rather than asserted here (TJ-GAP-056 owns the
parity battery).
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"

# Recorders log argv as NUL-terminated tokens followed by an "EOR" marker, which
# distinguishes an empty argument from a record boundary.
_BWRAP_STUB = """#!/usr/bin/env bash
for a in "$@"; do printf '%s\\0' "$a" >> "$TJ_STUB_LOG"; done
printf 'EOR\\0' >> "$TJ_STUB_LOG"
last="${!#}"
if [ "$last" = "true" ]; then
    exit "${TJ_BWRAP_PROBE_EXIT:-0}"
fi
exit "${TJ_SANDBOX_EXIT:-0}"
"""

_UNSHARE_STUB = """#!/usr/bin/env bash
for a in "$@"; do printf '%s\\0' "$a" >> "$TJ_UNSHARE_STUB_LOG"; done
printf 'EOR\\0' >> "$TJ_UNSHARE_STUB_LOG"
last="${!#}"
if [ "$last" = "true" ]; then
    exit "${TJ_UNSHARE_PROBE_EXIT:-0}"
fi
exit "${TJ_SANDBOX_EXIT:-0}"
"""


def _link_real(bindir: Path, *names: str) -> None:
    for name in names:
        real = shutil.which(name)
        if real:
            (bindir / name).symlink_to(real)


def _make_stub_path(
    tmp_path: Path, *, bwrap: bool = True, unshare: bool = True
) -> str:
    """Curated PATH: bash/uname/id/grep/cut/env plus argv-recording stubs.

    A real /usr/bin/bwrap is deliberately NOT on this PATH, so "bwrap absent"
    is deterministic on hosts that have bubblewrap installed.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    _link_real(
        bindir, "bash", "uname", "id", "grep", "cut", "head", "env", "sh", "cat"
    )
    for name, body, enabled in (
        ("bwrap", _BWRAP_STUB, bwrap),
        ("unshare", _UNSHARE_STUB, unshare),
    ):
        stub = bindir / name
        if enabled:
            stub.write_text(body, encoding="utf-8")
            stub.chmod(0o755)
        elif stub.exists():
            stub.unlink()
    return str(bindir)


def _env(tmp_path: Path, path: str, **overrides: str) -> dict[str, str]:
    env = {
        "PATH": path,
        "HOME": str(tmp_path / "home"),
        "TERMINAL_JAIL_INTERRUPTOR_MODE": "disabled",
        "TERMINAL_JAIL_BRIDGE": str(tmp_path / "no-bridge-here"),
        "TJ_STUB_LOG": str(tmp_path / "bwrap.log"),
        "TJ_UNSHARE_STUB_LOG": str(tmp_path / "unshare.log"),
    }
    Path(env["HOME"]).mkdir(exist_ok=True)
    env.update(overrides)
    return env


def _run_cli(
    *args: str, env: dict[str, str], timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI_SCRIPT), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _records(log: Path) -> list[list[str]]:
    """Parse the stub's argv log: NUL-terminated args, "EOR" ends a record."""
    if not log.exists():
        return []
    records: list[list[str]] = []
    current: list[bytes] = []
    for token in log.read_bytes().split(b"\0"):
        if token == b"EOR":
            records.append([t.decode("utf-8", "replace") for t in current])
            current = []
        else:
            current.append(token)
    return records


def _payload_argv(record: list[str]) -> list[str]:
    """The argv the trampoline receives: `bash -c 'exec "$@"' terminal-jail ...`.

    Indexed from the trampoline itself so the helper works for both backends
    (bubblewrap separates options from the payload with `--`, unshare does not).
    """
    return record[record.index("bash") :]


# ── Selector surface ───────────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_help_documents_the_backend_selector(tmp_path: Path) -> None:
    env = _env(tmp_path, _make_stub_path(tmp_path))
    result = _run_cli("--help", env=env)
    assert result.returncode == 0
    assert "TERMINAL_JAIL_JAIL_BACKEND" in result.stdout
    assert "bwrap" in result.stdout


@pytest.mark.standalone_cli
def test_unknown_backend_value_fails_closed(tmp_path: Path) -> None:
    """A typo must not silently run with a default backend."""
    path = _make_stub_path(tmp_path)
    env = _env(tmp_path, path, TERMINAL_JAIL_JAIL_BACKEND="bwrap-typo")
    result = _run_cli("--no-interruptor", "echo", "nope", env=env)
    assert result.returncode == 2
    assert "bwrap-typo" in result.stderr
    assert "auto, bwrap, or unshare" in result.stderr
    assert "nope" not in result.stdout
    # nothing was launched with either backend
    assert _records(Path(env["TJ_STUB_LOG"])) == []
    assert _records(Path(env["TJ_UNSHARE_STUB_LOG"])) == []


# ── auto: selection, flags, argv ───────────────────────────────────────────


@pytest.mark.standalone_cli
def test_auto_prefers_bwrap_when_present(tmp_path: Path) -> None:
    path = _make_stub_path(tmp_path)
    env = _env(tmp_path, path)
    result = _run_cli("--no-interruptor", "printf", "%s", "hi", env=env)
    assert result.returncode == 0, result.stderr
    bwrap_calls = _records(Path(env["TJ_STUB_LOG"]))
    # exactly the probe (flags + `true`) and the launch (flags + `--` + payload)
    assert len(bwrap_calls) == 2, bwrap_calls
    assert bwrap_calls[0][-1] == "true"
    assert bwrap_calls[0][:-1] == bwrap_calls[1][: len(bwrap_calls[0]) - 1]
    # unshare is never touched when bwrap is selected
    assert _records(Path(env["TJ_UNSHARE_STUB_LOG"])) == []
    # the normal (non-degraded) selection is silent
    assert "WARNING" not in result.stderr


@pytest.mark.standalone_cli
def test_bwrap_launch_flags_are_the_documented_contract(tmp_path: Path) -> None:
    """Every documented flag, and the deliberately-omitted one.

    --as-pid-1 is pinned ABSENT: it makes the payload namespace PID 1 and
    nullifies --die-with-parent (measured orphan on bubblewrap 0.11.1), so the
    contract is bwrap's default reaper + --die-with-parent.
    """
    path = _make_stub_path(tmp_path)
    env = _env(tmp_path, path)
    _run_cli("--no-interruptor", "true", env=env)
    launch = _records(Path(env["TJ_STUB_LOG"]))[1]
    flags = launch[: launch.index("--")]
    assert flags[:2] == ["--unshare-user", "--unshare-pid"]
    assert "--die-with-parent" in flags
    assert "--proc" in flags and flags[flags.index("--proc") + 1] == "/proc"
    assert "--bind" in flags and flags[flags.index("--bind") + 1 :][:2] == ["/", "/"]
    assert "--dev-bind" in flags
    assert flags[flags.index("--dev-bind") + 1 :][:2] == ["/dev", "/dev"]
    assert "--as-pid-1" not in flags
    assert "--mount-proc" not in flags
    # argv-preserving trampoline, not a shell-concatenated command string
    assert launch[launch.index("--") + 1 :] == [
        "bash",
        "-c",
        'exec "$@"',
        "terminal-jail",
        "true",
    ]


@pytest.mark.standalone_cli
def test_bwrap_preserves_argv_boundaries(tmp_path: Path) -> None:
    """Malformed/multiword/metacharacter arguments arrive as separate argv."""
    path = _make_stub_path(tmp_path)
    env = _env(tmp_path, path)
    payload = [
        "a b",
        "$(id)",
        "`id`",
        "quote'q",
        'say "hi"',
        "-dash",
        "*",
        "semi;colon",
        "pipe|d",
        "back\\slash",
        "",
        "  padded  ",
    ]
    result = _run_cli("--no-interruptor", "cmd", *payload, env=env)
    assert result.returncode == 0, result.stderr
    launch = _records(Path(env["TJ_STUB_LOG"]))[1]
    assert _payload_argv(launch) == ["bash", "-c", 'exec "$@"', "terminal-jail", "cmd", *payload]


@pytest.mark.standalone_cli
def test_unshare_backend_preserves_argv_boundaries(tmp_path: Path) -> None:
    """Existing backend, same argv guarantee."""
    path = _make_stub_path(tmp_path, bwrap=False)
    env = _env(tmp_path, path)
    payload = ["a b", "$(id)", "-dash", "*", ""]
    result = _run_cli("--no-interruptor", "cmd", *payload, env=env)
    assert result.returncode == 0, result.stderr
    launch = _records(Path(env["TJ_UNSHARE_STUB_LOG"]))[1]
    assert _payload_argv(launch) == ["bash", "-c", 'exec "$@"', "terminal-jail", "cmd", *payload]


# ── auto: absence / failure paths ──────────────────────────────────────────


@pytest.mark.standalone_cli
def test_auto_falls_back_to_unshare_when_bwrap_absent(tmp_path: Path) -> None:
    """bwrap absent is the documented normal path: unshare, silently."""
    path = _make_stub_path(tmp_path, bwrap=False)
    env = _env(tmp_path, path)
    result = _run_cli("--no-interruptor", "cmd", "arg", env=env)
    assert result.returncode == 0, result.stderr
    unshare_calls = _records(Path(env["TJ_UNSHARE_STUB_LOG"]))
    assert len(unshare_calls) == 2, unshare_calls
    assert unshare_calls[0][-1] == "true"
    assert "WARNING" not in result.stderr
    assert not Path(env["TJ_STUB_LOG"]).exists()


@pytest.mark.standalone_cli
def test_auto_warns_and_falls_back_when_bwrap_probe_fails(tmp_path: Path) -> None:
    """A present-but-unusable bwrap is loud: the private-/proc loss is stated."""
    path = _make_stub_path(tmp_path)
    env = _env(tmp_path, path, TJ_BWRAP_PROBE_EXIT="1")
    result = _run_cli("--no-interruptor", "cmd", env=env)
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "does NOT provide a private /proc" in result.stderr
    # probe only — bwrap was never launched
    assert len(_records(Path(env["TJ_STUB_LOG"]))) == 1
    assert len(_records(Path(env["TJ_UNSHARE_STUB_LOG"]))) == 2


@pytest.mark.standalone_cli
def test_explicit_bwrap_fails_closed_when_binary_missing(tmp_path: Path) -> None:
    path = _make_stub_path(tmp_path, bwrap=False)
    env = _env(tmp_path, path, TERMINAL_JAIL_JAIL_BACKEND="bwrap")
    result = _run_cli("--no-interruptor", "cmd", env=env)
    assert result.returncode == 2
    assert "bubblewrap (bwrap) is not installed" in result.stderr
    assert "command not run" in result.stderr
    # NO silent downgrade to the unshare backend
    assert _records(Path(env["TJ_UNSHARE_STUB_LOG"])) == []


@pytest.mark.standalone_cli
def test_explicit_bwrap_fails_closed_when_probe_fails(tmp_path: Path) -> None:
    path = _make_stub_path(tmp_path)
    env = _env(tmp_path, path, TERMINAL_JAIL_JAIL_BACKEND="bwrap", TJ_BWRAP_PROBE_EXIT="1")
    result = _run_cli("--no-interruptor", "cmd", env=env)
    assert result.returncode == 2
    assert "bwrap namespace creation failed" in result.stderr
    assert len(_records(Path(env["TJ_STUB_LOG"]))) == 1  # probe only
    assert _records(Path(env["TJ_UNSHARE_STUB_LOG"])) == []


@pytest.mark.standalone_cli
def test_pinned_unshare_ignores_a_present_bwrap(tmp_path: Path) -> None:
    path = _make_stub_path(tmp_path)
    env = _env(tmp_path, path, TERMINAL_JAIL_JAIL_BACKEND="unshare")
    result = _run_cli("--no-interruptor", "cmd", env=env)
    assert result.returncode == 0, result.stderr
    assert not Path(env["TJ_STUB_LOG"]).exists()
    launch = _records(Path(env["TJ_UNSHARE_STUB_LOG"]))[1]
    assert _payload_argv(launch) == ["bash", "-c", 'exec "$@"', "terminal-jail", "cmd"]


# ── --user: mapped isolation is never traded away ──────────────────────────


@pytest.mark.standalone_cli
def test_auto_keeps_unshare_mapped_launch_for_user(tmp_path: Path) -> None:
    """A passing uid-mapping probe wins: bubblewrap cannot map a subuid, and a
    mapping is real filesystem isolation (measured: bwrap --uid alone leaves a
    caller-owned mode-600 file readable)."""
    path = _make_stub_path(tmp_path)  # unshare stub passes every probe
    env = _env(tmp_path, path)
    result = _run_cli("--no-interruptor", "--user", "cmd", env=env)
    assert result.returncode == 0, result.stderr
    assert not Path(env["TJ_STUB_LOG"]).exists()  # bwrap never probed/launched
    launch = _records(Path(env["TJ_UNSHARE_STUB_LOG"]))[-1]
    assert any(a.startswith("--map-users=65534:") for a in launch), launch
    assert "--user" in launch


@pytest.mark.standalone_cli
def test_auto_uses_bwrap_for_user_when_mapping_unavailable(tmp_path: Path) -> None:
    """Degraded uid mapping => the bwrap backend still adds private /proc."""
    path = _make_stub_path(tmp_path)
    env = _env(tmp_path, path, TJ_UNSHARE_PROBE_EXIT="1")
    result = _run_cli("--no-interruptor", "--user", "cmd", env=env)
    assert result.returncode == 0, result.stderr
    assert "no filesystem isolation" in result.stderr  # unchanged warning
    launch = _records(Path(env["TJ_STUB_LOG"]))[1]
    assert _payload_argv(launch) == [
        "bash",
        "-c",
        'exec "$@"',
        "terminal-jail",
        "cmd",
    ]


@pytest.mark.standalone_cli
def test_explicit_bwrap_with_user_states_the_isolation_loss(tmp_path: Path) -> None:
    """Requesting bwrap on a mapped host must say what is given up."""
    path = _make_stub_path(tmp_path)  # mapped probe passes
    env = _env(tmp_path, path, TERMINAL_JAIL_JAIL_BACKEND="bwrap")
    result = _run_cli("--no-interruptor", "--user", "cmd", env=env)
    assert result.returncode == 0, result.stderr
    assert "no filesystem isolation under the bwrap backend" in result.stderr
    assert _records(Path(env["TJ_STUB_LOG"]))  # bwrap really ran


# ── Live checks (host-conditional) ─────────────────────────────────────────


@functools.lru_cache(maxsize=1)
def _bwrap_usable() -> bool:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return False
    probe = subprocess.run(
        [
            bwrap,
            "--unshare-user",
            "--unshare-pid",
            "--die-with-parent",
            "--bind",
            "/",
            "/",
            "--dev-bind",
            "/dev",
            "/dev",
            "--proc",
            "/proc",
            "true",
        ],
        capture_output=True,
        check=False,
        timeout=30,
    )
    return probe.returncode == 0


def _skip_unless_bwrap() -> None:
    if not _bwrap_usable():
        pytest.skip(
            "HOST-DEGRADED-BWRAP: bubblewrap is absent or cannot create "
            "namespaces on this host — bwrap-backend containment not verified"
        )


def _run_live(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TERMINAL_JAIL_INTERRUPTOR_MODE"] = "disabled"
    env["TERMINAL_JAIL_JAIL_BACKEND"] = "bwrap"
    return subprocess.run(
        [str(CLI_SCRIPT), "--no-interruptor", *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


@pytest.mark.integration
def test_live_bwrap_private_proc_and_new_pid_namespace() -> None:
    _skip_unless_bwrap()
    host_ns = Path("/proc/self/ns/pid").resolve()
    host_procs = len([p for p in Path("/proc").iterdir() if p.name.isdigit()])
    host_init = Path("/proc/1/comm").read_text(encoding="utf-8").strip()
    result = _run_live(
        "sh",
        "-c",
        'echo "ns=$(readlink /proc/self/ns/pid)"; echo "procs=$(ls /proc | '
        'grep -c "^[0-9]")"; echo "init=$(cat /proc/1/comm)"',
    )
    assert result.returncode == 0, result.stderr
    lines = dict(
        line.split("=", 1) for line in result.stdout.strip().splitlines() if "=" in line
    )
    assert lines["ns"] != str(host_ns), "bwrap did not create a new PID namespace"
    assert int(lines["procs"]) < host_procs, (
        f"jail sees {lines['procs']} procs vs {host_procs} on the host — "
        f"/proc is not private"
    )
    assert lines["init"] != host_init, (
        f"jail /proc/1/comm={lines['init']!r} matches the host init: /proc is the "
        f"host's"
    )


@pytest.mark.integration
def test_live_bwrap_argv_and_exit_semantics() -> None:
    _skip_unless_bwrap()
    payload = ["a b", "$(id)", "-dash", "*", "", "new\nline"]
    result = _run_live("printf", "[%s]", *payload)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "".join(f"[{arg}]" for arg in payload)
    exit_code = _run_live("bash", "-c", "exit 42")
    assert exit_code.returncode == 42, exit_code.stderr
    missing = _run_live("definitely-not-a-real-command-tj054")
    assert missing.returncode == 127, missing.stderr
    assert "not found" in missing.stderr
