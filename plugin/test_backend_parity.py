"""TJ-GAP-056 — backend parity: bwrap vs unshare containment contracts.

The measured evidence lives in scripts/backend-parity-battery.py and
docs/backend-parity.md; this module pins the DURABLE contracts as regression
tests, host-independent where possible:

- fail-closed for BOTH backends when the namespace probe fails (PATH-stub +
  marker file): exit 2, the command does not run, the marker the payload
  would have created stays ABSENT;
- the parity-relevant bwrap argv invariants that the TJ-GAP-054 argv test
  does not already pin are repeated here only as the parity contract:
  ``--proc /proc`` present, ``--die-with-parent`` present, ``--as-pid-1``
  absent (the full flag list and the trampoline shape stay owned by
  test_backend_selection.py — deliberately not duplicated);
- the battery itself, executed as a subprocess: a classifier must never
  gate, so it must exit 0 and emit its table (the JSON cells must use the
  documented verdict vocabulary only);
- live containment cells (private /proc, orphan teardown) skip with a
  grep-able HOST-DEGRADED-* marker exactly like the TJ-GAP-054 lanes.
"""

from __future__ import annotations

import functools
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
BATTERY = PROJECT_ROOT / "scripts" / "backend-parity-battery.py"
PIDNS_PROBE = PROJECT_ROOT / "scripts" / "pidns-capability-probe.py"

VOCABULARY = ("SAME", "DIFFERS", "KNOWN-LIMIT", "FAIL-CLOSED-PROVEN")

# Always-failing stub: its `true` probe (the exact launch flags) exits 1, so
# the wrapper must hit the documented fail-closed contract, never launch.
_FAILING_STUB = """#!/usr/bin/env bash
exit 1
"""

# Recording stub (TJ-GAP-054 pattern): NUL-delimited argv + EOR record end;
# the probe (`true`) exits via TJ_BWRAP_PROBE_EXIT, the launch exits 0.
_BWRAP_STUB = """#!/usr/bin/env bash
for a in "$@"; do printf '%s\\0' "$a" >> "$TJ_STUB_LOG"; done
printf 'EOR\\0' >> "$TJ_STUB_LOG"
last="${!#}"
if [ "$last" = "true" ]; then
    exit "${TJ_BWRAP_PROBE_EXIT:-0}"
fi
exit 0
"""


def _stub_path(tmp_path: pathlib.Path, *, failing: str | None = None) -> str:
    """Curated PATH (bash/uname/... plus stubs). ``failing`` names a backend
    whose stub always exits 1; the others get the recording bwrap stub."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name in ("bash", "uname", "id", "grep", "cut", "head", "env", "sh", "cat"):
        real = shutil.which(name)
        if real:
            (bindir / name).symlink_to(real)
    bwrap = bindir / "bwrap"
    if failing == "bwrap":
        bwrap.write_text(_FAILING_STUB, encoding="utf-8")
    else:
        bwrap.write_text(_BWRAP_STUB, encoding="utf-8")
    bwrap.chmod(0o755)
    unshare = bindir / "unshare"
    if failing == "unshare":
        unshare.write_text(_FAILING_STUB, encoding="utf-8")
    elif shutil.which("unshare"):
        unshare.symlink_to(shutil.which("unshare"))
    return str(bindir)


def _env(tmp_path: pathlib.Path, path: str, **overrides: str) -> dict[str, str]:
    env = {
        "PATH": path,
        "HOME": str(tmp_path / "home"),
        "TERMINAL_JAIL_INTERRUPTOR_MODE": "disabled",
        "TERMINAL_JAIL_BRIDGE": str(tmp_path / "no-bridge-here"),
        "TJ_STUB_LOG": str(tmp_path / "bwrap.log"),
    }
    home = pathlib.Path(env["HOME"])
    home.mkdir(exist_ok=True)
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


def _records(log: pathlib.Path) -> list[list[str]]:
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


# ── fail-closed contract (host-independent) ────────────────────────────────


def _fail_closed_run(backend: str, tmp_path: pathlib.Path):
    marker = tmp_path / f"marker-{backend}"
    overrides = {"TERMINAL_JAIL_JAIL_BACKEND": backend}
    failing = backend
    if backend == "bwrap":
        # The recording stub logs every invocation and fails only the probe
        # (TJ-GAP-054 pattern), so the test can prove the launch never ran.
        failing = ""
        overrides["TJ_BWRAP_PROBE_EXIT"] = "1"
    env = _env(tmp_path, _stub_path(tmp_path, failing=failing), **overrides)
    result = _run_cli("--no-interruptor", "touch", str(marker), env=env)
    return result, marker, env


@pytest.mark.standalone_cli
def test_fail_closed_bwrap_probe_fails_leaves_marker_absent(tmp_path) -> None:
    """A failed bwrap probe: exit 2, command never ran, no marker side effect."""
    result, marker, env = _fail_closed_run("bwrap", tmp_path)
    assert result.returncode == 2, result.stderr
    assert "bwrap namespace creation failed" in result.stderr
    assert "command not run" in result.stderr
    assert result.stdout == ""
    assert not marker.exists(), "the payload RAN despite the failed probe"
    # probe only — the launch never happened
    records = _records(pathlib.Path(env["TJ_STUB_LOG"]))
    assert len(records) == 1 and records[0][-1] == "true", records


@pytest.mark.standalone_cli
def test_fail_closed_unshare_probe_fails_leaves_marker_absent(tmp_path) -> None:
    """Same contract for the unshare backend (an always-failing unshare stub)."""
    result, marker, _env_ = _fail_closed_run("unshare", tmp_path)
    assert result.returncode == 2, result.stderr
    assert "namespace creation failed" in result.stderr
    assert "command not run" in result.stderr
    assert result.stdout == ""
    assert not marker.exists(), "the payload RAN despite the failed probe"


# ── parity-relevant argv invariants (host-independent) ─────────────────────


@pytest.mark.standalone_cli
def test_bwrap_parity_argv_invariants(tmp_path) -> None:
    """The three parity-relevant invariants: fresh procfs mounted, teardown
    armed, and NO --as-pid-1 (it would nullify --die-with-parent). The full
    flag contract stays in test_backend_selection.py."""
    env = _env(tmp_path, _stub_path(tmp_path))
    result = _run_cli("--no-interruptor", "true", env=env)
    assert result.returncode == 0, result.stderr
    launch = _records(pathlib.Path(env["TJ_STUB_LOG"]))[1]
    flags = launch[: launch.index("--")]
    assert "--proc" in flags and flags[flags.index("--proc") + 1] == "/proc"
    assert "--die-with-parent" in flags
    assert "--as-pid-1" not in flags
    assert "--unshare-pid" in flags  # private /proc pairs with a new PID ns


# ── the battery itself: a classifier must never gate ───────────────────────


def _run_battery(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BATTERY), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


@pytest.mark.integration
def test_battery_json_exits_zero_and_uses_the_verdict_vocabulary() -> None:
    result = _run_battery("--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["cells"], "battery produced no cells"
    for cell in payload["cells"]:
        assert cell["verdict"] in VOCABULARY, cell


@pytest.mark.integration
def test_battery_table_mode_exits_zero_and_prints_header() -> None:
    result = _run_battery()
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert any("backend parity battery" in line for line in lines[:2])
    header = next(line for line in lines if line.startswith("cell"))
    for column in ("backend", "measured", "expected", "verdict"):
        assert column in header, header


# ── live containment cells (host-conditional) ──────────────────────────────


@functools.lru_cache(maxsize=1)
def _bwrap_usable() -> bool:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return False
    probe = subprocess.run(
        [bwrap, "--unshare-user", "--unshare-pid", "--die-with-parent",
         "--bind", "/", "/", "--dev-bind", "/dev", "/dev",
         "--proc", "/proc", "true"],
        capture_output=True, check=False, timeout=30,
    )
    return probe.returncode == 0


@functools.lru_cache(maxsize=1)
def _pidns_full() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, str(PIDNS_PROBE)],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.stdout.strip().startswith("FULL")


def _host_proc_count() -> int:
    return len([p for p in pathlib.Path("/proc").iterdir() if p.name.isdigit()])


def _jail_proc_count(backend: str) -> int:
    env = dict(os.environ)
    env["TERMINAL_JAIL_JAIL_BACKEND"] = backend
    env["TERMINAL_JAIL_INTERRUPTOR_MODE"] = "disabled"
    result = subprocess.run(
        [str(CLI_SCRIPT), "--no-interruptor", "--user",
         "sh", "-c", 'ls /proc | grep -c "^[0-9]\\+$"'],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
        check=False, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip().splitlines()[-1])


@pytest.mark.integration
def test_live_bwrap_user_proc_is_private() -> None:
    if not _bwrap_usable() or not _pidns_full():
        pytest.skip(
            "HOST-DEGRADED-BWRAP: bubblewrap is absent or cannot create "
            "namespaces on this host — bwrap private-/proc parity not verified"
        )
    host_count = _host_proc_count()
    jail_count = _jail_proc_count("bwrap")
    assert jail_count < 100 and jail_count < host_count, (
        f"bwrap jail sees {jail_count} /proc entries vs {host_count} on the "
        "host — /proc is not private"
    )


@pytest.mark.integration
def test_live_unshare_user_exposes_host_proc() -> None:
    """The documented known limit, pinned honestly: --user cannot mount /proc
    unprivileged, so the host PID view stays visible (specs/cli.md)."""
    if not _pidns_full():
        pytest.skip(
            "HOST-DEGRADED-PIDNS: this host cannot create unprivileged PID "
            "namespaces — unshare --user /proc parity not verified"
        )
    host_count = _host_proc_count()
    jail_count = _jail_proc_count("unshare")
    assert jail_count >= host_count * 0.5, (
        f"unshare --user jail sees {jail_count} /proc entries vs {host_count} "
        "on the host — unexpectedly private; re-document the limit"
    )


def _sleep300_pids() -> set[int]:
    out = set()
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if argv[:2] == [b"sleep", b"300"]:
            out.add(int(proc.name))
    return out


def _orphan_teardown(backend: str) -> float:
    """SIGKILL the wrapper; return payload teardown latency in seconds."""
    before = _sleep300_pids()
    env = dict(os.environ)
    env["TERMINAL_JAIL_JAIL_BACKEND"] = backend
    env["TERMINAL_JAIL_INTERRUPTOR_MODE"] = "disabled"
    launcher = subprocess.Popen(
        [str(CLI_SCRIPT), "--no-interruptor", "--user", "sleep", "300"],
        cwd=str(PROJECT_ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    payload = None
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < 10:
            new = _sleep300_pids() - before
            if new:
                payload = min(new)
                break
            time.sleep(0.05)
        if payload is None:
            pytest.fail("no sleep payload appeared within 10s")
        try:
            os.kill(launcher.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        tk = time.monotonic()
        while time.monotonic() - tk < 15:
            if not pathlib.Path(f"/proc/{payload}").exists():
                return time.monotonic() - tk
            time.sleep(0.02)
        # cleanup (not the contract): do not leave an orphan behind
        try:
            os.kill(payload, signal.SIGKILL)
        except ProcessLookupError:
            pass
        pytest.fail(
            f"orphan: {backend} payload {payload} survived the wrapper's "
            "death for 15s"
        )
    finally:
        launcher.wait()


@pytest.mark.integration
def test_live_bwrap_orphan_teardown() -> None:
    if not _bwrap_usable() or not _pidns_full():
        pytest.skip(
            "HOST-DEGRADED-BWRAP: bubblewrap is absent or cannot create "
            "namespaces on this host — --die-with-parent teardown not verified"
        )
    latency = _orphan_teardown("bwrap")
    assert latency < 15


@pytest.mark.integration
def test_live_unshare_orphan_teardown() -> None:
    if not _pidns_full():
        pytest.skip(
            "HOST-DEGRADED-PIDNS: this host cannot create unprivileged PID "
            "namespaces — --kill-child teardown not verified"
        )
    latency = _orphan_teardown("unshare")
    assert latency < 15
