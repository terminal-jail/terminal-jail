from __future__ import annotations

import functools
import os
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"


@pytest.fixture(scope="module")
def cli_path() -> Path:
    assert CLI_SCRIPT.exists(), f"CLI script not found: {CLI_SCRIPT}"
    return CLI_SCRIPT


def _run_cli(
    cli: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
    unset_env: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    for key in unset_env:
        env.pop(key, None)
    return subprocess.run(
        [str(cli), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=False,
        check=False,
        timeout=10,
    )


def _make_test_bin(tmp_path: Path, *, include_unshare: bool = False) -> str:
    """Build a minimal PATH with bash and uname, optionally unshare."""
    test_bin = tmp_path / "testbin"
    test_bin.mkdir(exist_ok=True)
    (test_bin / "bash").symlink_to("/usr/bin/bash")
    (test_bin / "uname").symlink_to("/usr/bin/uname")
    if include_unshare:
        (test_bin / "unshare").symlink_to("/usr/bin/unshare")
    return str(test_bin)


def _host_denied_namespaces(stderr: str) -> bool:
    """True when the host refused namespace creation: either the raw EPERM
    leak from unshare itself, or the wrapper's mapped degradation message
    (TJ-GAP-034 — the CLI now exits 2 with a clean message instead of
    leaking the raw error)."""
    return (
        "Permission denied" in stderr
        or "Operation not permitted" in stderr
        or "namespace creation failed" in stderr
    )


@functools.lru_cache(maxsize=1)
def _host_denies_bare_mode(cli_path: Path) -> bool:
    """True when this host refuses bare-mode PID namespace creation.

    Probes once per test process: bare mode either works (rc==0) or fires
    the fail-closed degradation path (rc==2 + degradation message,
    TJ-GAP-034). The result drives honest skips on degraded hosts — a
    bare-mode test that cannot run must SKIP with the HOST-DEGRADED-PIDNS
    marker, never silently pass (TJ-GAP-042)."""
    result = _run_cli(cli_path, "true")
    if result.returncode == 0:
        return False
    stderr = result.stderr.decode("utf-8", errors="replace")
    return result.returncode == 2 and _host_denied_namespaces(stderr)


# ── Flag parsing ──────────────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_help_flag(cli_path: Path) -> None:
    result = _run_cli(cli_path, "--help", unset_env=("TERMINAL_JAIL_VERSION",))
    assert result.returncode == 0
    stdout = result.stdout.decode("utf-8")
    assert "Usage:" in stdout


@pytest.mark.standalone_cli
def test_short_help_flag(cli_path: Path) -> None:
    result = _run_cli(cli_path, "-h", unset_env=("TERMINAL_JAIL_VERSION",))
    assert result.returncode == 0
    assert "Usage:" in result.stdout.decode("utf-8")


@pytest.mark.standalone_cli
def test_version_flag(cli_path: Path) -> None:
    result = _run_cli(cli_path, "--version", unset_env=("TERMINAL_JAIL_VERSION",))
    assert result.returncode == 0
    stdout = result.stdout.decode("utf-8")
    assert "terminal-jail" in stdout


@pytest.mark.standalone_cli
def test_short_version_flag(cli_path: Path) -> None:
    result = _run_cli(cli_path, "-V", unset_env=("TERMINAL_JAIL_VERSION",))
    assert result.returncode == 0
    assert "terminal-jail" in result.stdout.decode("utf-8")


@pytest.mark.standalone_cli
def test_version_from_env(cli_path: Path) -> None:
    result = _run_cli(
        cli_path, "--version", extra_env={"TERMINAL_JAIL_VERSION": "9.9.9-test"}
    )
    assert result.returncode == 0
    assert "9.9.9-test" in result.stdout.decode("utf-8")


# ── Error paths ────────────────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_no_args(cli_path: Path) -> None:
    result = _run_cli(cli_path)
    assert result.returncode == 2
    assert result.stdout == b""
    stderr = result.stderr.decode("utf-8")
    assert "Usage:" in stderr


@pytest.mark.standalone_cli
def test_non_linux_os(cli_path: Path, tmp_path: Path) -> None:
    """Simulate non-Linux OS by overriding uname with a fake Darwin."""
    test_bin = tmp_path / "testbin"
    test_bin.mkdir(exist_ok=True)
    (test_bin / "bash").symlink_to("/usr/bin/bash")
    (test_bin / "python3").symlink_to("/usr/bin/python3")

    fake_uname = test_bin / "uname"
    fake_uname.write_text("#!/bin/bash\necho Darwin\n")
    fake_uname.chmod(
        fake_uname.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    )

    result = _run_cli(cli_path, "echo", "hello", extra_env={"PATH": str(test_bin)})
    assert result.returncode == 2
    stderr = result.stderr.decode("utf-8")
    assert "requires Linux PID namespaces" in stderr


@pytest.mark.standalone_cli
def test_missing_unshare(cli_path: Path, tmp_path: Path) -> None:
    """PATH lacks unshare — script exits 2 with error message."""
    path = _make_test_bin(tmp_path, include_unshare=False)
    # python3 is required by the interruptor bridge (fail-closed without it);
    # include it so this test exercises the unshare preflight, not the bridge.
    (tmp_path / "testbin" / "python3").symlink_to("/usr/bin/python3")
    result = _run_cli(cli_path, "echo", "hello", extra_env={"PATH": path})
    assert result.returncode == 2
    assert "unshare is required" in result.stderr.decode("utf-8")


# ── Command execution (host-constrained: unshare --mount-proc may fail) ─────


@pytest.mark.standalone_cli
def test_simple_command(cli_path: Path) -> None:
    """A trivial command through the jail."""
    result = _run_cli(cli_path, "echo", "hello-world-42")
    if result.returncode == 0:
        assert "hello-world-42" in result.stdout.decode("utf-8")
    else:
        assert _host_denies_bare_mode(cli_path), (
            "HOST-DEGRADED-PIDNS: bare-mode command failed without the "
            "host-degradation path"
        )
        pytest.skip(
            "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
            "bare-mode containment not verified"
        )


@pytest.mark.standalone_cli
def test_command_with_args(cli_path: Path) -> None:
    result = _run_cli(cli_path, "printf", "%s:%s:%s", "a", "b", "c")
    if result.returncode == 0:
        assert "a:b:c" in result.stdout.decode("utf-8")
    else:
        assert _host_denies_bare_mode(cli_path), (
            "HOST-DEGRADED-PIDNS: bare command failed without the host-degradation path"
        )
        pytest.skip(
            "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
            "bare-mode containment not verified"
        )


@pytest.mark.standalone_cli
def test_command_with_special_chars(cli_path: Path) -> None:
    result = _run_cli(cli_path, "echo", "path/to/file with spaces")
    if result.returncode == 0:
        assert "path/to/file with spaces" in result.stdout.decode("utf-8")
    else:
        assert _host_denies_bare_mode(cli_path), (
            "HOST-DEGRADED-PIDNS: bare command failed without the host-degradation path"
        )
        pytest.skip(
            "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
            "bare-mode containment not verified"
        )


# ── Exit code propagation ──────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_exit_code_zero(cli_path: Path) -> None:
    result = _run_cli(cli_path, "true")
    if _host_denies_bare_mode(cli_path):
        pytest.skip(
            "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
            "bare-mode containment not verified"
        )
    assert result.returncode == 0


@pytest.mark.standalone_cli
def test_exit_code_nonzero(cli_path: Path) -> None:
    result = _run_cli(cli_path, "bash", "-c", "exit 42")
    if _host_denies_bare_mode(cli_path):
        pytest.skip(
            "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
            "bare-mode containment not verified"
        )
    assert result.returncode == 42


# ── Stdin/stderr passthrough ───────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_stdin_passthrough(cli_path: Path) -> None:
    env = os.environ.copy()
    proc = subprocess.run(
        [str(cli_path), "cat", "-"],
        input=b"hello-from-stdin\n",
        capture_output=True,
        check=False,
        timeout=10,
        env=env,
    )
    if proc.returncode == 0:
        assert b"hello-from-stdin" in proc.stdout
    else:
        assert _host_denies_bare_mode(cli_path), (
            "HOST-DEGRADED-PIDNS: bare command failed without the host-degradation path"
        )
        pytest.skip(
            "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
            "bare-mode containment not verified"
        )


@pytest.mark.standalone_cli
def test_stderr_passthrough(cli_path: Path) -> None:
    result = _run_cli(cli_path, "bash", "-c", "echo 'to-stderr' >&2")
    if result.returncode == 0:
        assert b"to-stderr" in result.stderr
    else:
        assert _host_denies_bare_mode(cli_path), (
            "HOST-DEGRADED-PIDNS: bare command failed without the host-degradation path"
        )
        pytest.skip(
            "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
            "bare-mode containment not verified"
        )


@pytest.mark.standalone_cli
def test_combined_user_seccomp(cli_path: Path) -> None:
    result = _run_cli(cli_path, "--user", "--seccomp", "echo", "combined-test")
    if result.returncode == 0:
        assert "combined-test" in result.stdout.decode("utf-8")
    else:
        stderr = result.stderr.decode("utf-8", errors="replace")
        assert _host_denied_namespaces(stderr) or result.returncode in (159, -31)


# ── Identity env scrubbing (--user jail, TJ-DF-014) ────────────────────────


@pytest.mark.standalone_cli
def test_user_jail_scrubs_identity_env(cli_path: Path) -> None:
    """--user jail must not leak the caller's USER/LOGNAME/HOME into the
    nobody (65534) namespace: git/ssh/dotfile tooling would misread or write
    the caller's home as nobody."""
    result = _run_cli(cli_path, "--user", "env")
    if result.returncode == 0:
        stdout = result.stdout.decode("utf-8")
        assert "USER=nobody" in stdout
        assert "LOGNAME=nobody" in stdout
        assert "HOME=/nonexistent" in stdout
    else:
        stderr = result.stderr.decode("utf-8", errors="replace")
        assert _host_denied_namespaces(stderr), stderr


@pytest.mark.standalone_cli
def test_bare_mode_keeps_identity_env(cli_path: Path) -> None:
    """Bare mode (no --user) must NOT scrub: identity env passes through
    untouched — the scrub is --user-only."""
    result = _run_cli(
        cli_path,
        "env",
        extra_env={"USER": "tester", "HOME": "/home/tester"},
    )
    if result.returncode == 0:
        stdout = result.stdout.decode("utf-8")
        assert "USER=tester" in stdout
        assert "HOME=/home/tester" in stdout
    else:
        assert _host_denies_bare_mode(cli_path), (
            "HOST-DEGRADED-PIDNS: bare command failed without the host-degradation path"
        )
        pytest.skip(
            "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
            "bare-mode containment not verified"
        )


@pytest.mark.standalone_cli
def test_bare_mode_pid_namespace_containment(cli_path: Path) -> None:
    """The REAL containment assertion: bare mode must land the command in a
    NEW PID namespace (TJ-GAP-042).

    Runs ``readlink /proc/self/ns/pid`` inside the jail and compares the
    inode against the caller's own PID namespace inode. Equal inodes mean
    bare mode gave NO isolation — a hard failure, not a skip. On hosts
    that refuse PID namespace creation the jail exits 2 with the
    degradation message and the test skips (host limitation, not a
    regression)."""
    outside = Path("/proc/self/ns/pid").resolve()
    result = _run_cli(cli_path, "readlink", "/proc/self/ns/pid")
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        if _host_denied_namespaces(stderr):
            pytest.skip(
                "HOST-DEGRADED-PIDNS: host refused PID namespace creation — "
                "bare-mode containment not verified"
            )
        pytest.fail(
            f"bare readlink failed without the host-degradation path: "
            f"rc={result.returncode}, stderr={stderr!r}"
        )
    inside = result.stdout.decode("utf-8", errors="replace").strip()
    assert inside.startswith("pid:[") and inside.endswith("]"), (
        f"unexpected readlink output: {inside!r}"
    )
    assert inside != str(outside), (
        f"bare mode did not create a new PID namespace: inside={inside}, "
        f"outside={outside}"
    )


# ── seccomp loader readability under the uid-mapped launch (TJ-DF-019) ─────

_NEW_READ_WARNING = "seccomp loader not readable under the uid-mapped launch"
_OLD_MAPPING_WARNING = "could not create a uid mapping"


@pytest.mark.standalone_cli
def test_user_seccomp_unreadable_loader_degrades_and_runs(cli_path: Path) -> None:
    """TJ-DF-019: when the subordinate uid of the mapped launch cannot READ
    the seccomp loader (e.g. a 0700/750 agent home it cannot traverse), the
    wrapper must NOT die with Errno 13 before the wrapped command runs. It
    must print its own loud warning naming the exact loader path, fall back
    to the mapping-less --user launch, and still RUN the command with the
    seccomp filter applied (Seccomp: 2).

    The unreadable-loader outcome is driven through the documented test seam
    TERMINAL_JAIL_SECCOMP_READ_PROBE (a failing probe command), because this
    host cannot create a uid-mapped launch at all (Ubuntu AppArmor profile
    'unprivileged_userns') — the real mapped launch is not creatable here."""
    result = _run_cli(
        cli_path,
        "--user",
        "--seccomp",
        "sh",
        "-c",
        "echo TJDF019-RAN; grep Seccomp /proc/self/status",
        extra_env={
            "TERMINAL_JAIL_SECCOMP_READ_PROBE": "test -r /nonexistent/tj-df-019-seccomp-loader",
        },
        unset_env=("TERMINAL_JAIL_SECCOMP_LOADER",),
    )
    stderr = result.stderr.decode("utf-8", errors="replace")
    stdout = result.stdout.decode("utf-8", errors="replace")
    assert result.returncode == 0, (
        f"wrapped command must RUN, not die on the loader: "
        f"rc={result.returncode}, stderr={stderr!r}"
    )
    assert "TJDF019-RAN" in stdout, "wrapped command did not actually run"
    assert "Seccomp:\t2" in stdout, (
        f"seccomp filter not applied inside the fallback jail: stdout={stdout!r}"
    )
    assert _NEW_READ_WARNING in stderr, f"new warning missing: stderr={stderr!r}"
    assert str(PROJECT_ROOT / "standalone" / "seccomp-loader.py") in stderr, (
        f"warning must name the exact unreadable loader path: stderr={stderr!r}"
    )
    assert _OLD_MAPPING_WARNING not in stderr, (
        f"read-failure warning must be distinguishable from the "
        f"creation-failure warning: stderr={stderr!r}"
    )


@pytest.mark.standalone_cli
def test_user_seccomp_read_probe_success_no_degradation(cli_path: Path) -> None:
    """TJ-DF-019: when the readability probe reports the mapped launch can
    read the loader, the wrapper promotes it silently — neither the new
    read-failure warning nor the legacy mapping-degradation warning may
    appear."""
    result = _run_cli(
        cli_path,
        "--user",
        "--seccomp",
        "echo",
        "TJDF019-OK",
        extra_env={"TERMINAL_JAIL_SECCOMP_READ_PROBE": "true"},
        unset_env=("TERMINAL_JAIL_SECCOMP_LOADER",),
    )
    stderr = result.stderr.decode("utf-8", errors="replace")
    assert _NEW_READ_WARNING not in stderr, f"stderr={stderr!r}"
    assert _OLD_MAPPING_WARNING not in stderr, f"stderr={stderr!r}"
    if result.returncode == 0:
        assert "TJDF019-OK" in result.stdout.decode("utf-8")
    else:
        # This host cannot create the mapped launch the seam-forced
        # promotion selects (Ubuntu AppArmor 'unprivileged_userns'); the
        # failure must land on the host-denial path at exec, never on a
        # silent non-zero exit.
        assert _host_denied_namespaces(stderr), (
            f"HOST-DEGRADED-USERNS: mapped exec failed without a host-"
            f"denial error: rc={result.returncode}, stderr={stderr!r}"
        )
