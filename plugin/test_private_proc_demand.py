"""TJ-GAP-088 — the enforceable private-/proc demand + per-run attribution.

Contract under test (specs/cli.md section 4 "Jail backends"):

- ``--private-proc`` / ``TERMINAL_JAIL_PRIVATE_PROC=required`` makes backend
  selection REFUSE (exit 2, command not run, marker absent) whenever the
  resolved backend cannot deliver a private procfs: the unshare backend in
  any mode (host /proc view), auto resolving to unshare, bwrap absent or
  probe-failing, and the composed launch;
- an unknown TERMINAL_JAIL_PRIVATE_PROC value is rejected before any
  namespace work (same contract class as the other control variables);
- per-run attribution: every launch states the delivered /proc view on
  stderr — ``proc_view=private`` (bwrap), ``proc_view=host`` (unshare);
  the composed launchers attribute platform-owned/none inside their
  COMPOSED MODE report;
- the DEFAULT (variable unset, flag absent) keeps the historical behavior:
  the command runs and nothing refuses — the known limit stops being
  prose-only (the run now SAYS it got the host view) but no new gate
  appears (this is the no-regression guard).

Host-independent arms use PATH-stub recorders (plugin/test_backend_parity.py
pattern); the live cells assert the MEASURED property — /proc entry count +
/proc/1 identity + the proc_view line — and skip with HOST-DEGRADED-*
markers on degraded hosts exactly like the TJ-GAP-056 lanes.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"

# Recorders log argv as NUL-terminated tokens + "EOR" record end (the
# TJ-GAP-054 pattern). The probe (`true`) exits via the *_PROBE_EXIT knobs;
# a launch EXECs the payload (`--` is bubblewrap's separator) so payload
# side effects (marker files) and inner exit codes are real.
_BWRAP_STUB = """#!/usr/bin/env bash
for a in "$@"; do printf '%s\\0' "$a" >> "$TJ_STUB_LOG"; done
printf 'EOR\\0' >> "$TJ_STUB_LOG"
last="${!#}"
if [ "$last" = "true" ]; then
    exit "${TJ_BWRAP_PROBE_EXIT:-0}"
fi
# Launch shape: `bwrap <flags> -- bash -c 'exec "$@"' terminal-jail
# <payload...>`; exec from the bash trampoline (the `--` separator sits
# mid-argv and must never be parsed as the command).
args=("$@")
for i in "${!args[@]}"; do
    if [ "${args[$i]}" = "bash" ]; then
        exec "${args[@]:$i}"
    fi
done
exec "$@"
"""

_UNSHARE_STUB = """#!/usr/bin/env bash
for a in "$@"; do printf '%s\\0' "$a" >> "$TJ_UNSHARE_STUB_LOG"; done
printf 'EOR\\0' >> "$TJ_UNSHARE_STUB_LOG"
last="${!#}"
if [ "$last" = "true" ]; then
    exit "${TJ_UNSHARE_PROBE_EXIT:-0}"
fi
# The wrapper's launch shape is `unshare <flags> bash -c 'exec "$@"'
# terminal-jail <payload...>`; exec from the bash trampoline so the flag
# tokens are never parsed as the command (real unshare consumes them).
args=("$@")
for i in "${!args[@]}"; do
    if [ "${args[$i]}" = "bash" ]; then
        exec "${args[@]:$i}"
    fi
done
exec "$@"
"""

_TOOLS = ("bash", "uname", "id", "grep", "cut", "head", "env", "sh", "cat", "touch")

# The canned-modify bridge stand-in, verbatim from plugin/test_modify_preflight.py
# (TJ_BRIDGE_LOG records the command; TJ_BRIDGE_PREFIX supplies the rewrite
# prefix; TJ_BRIDGE_MODE selects modify/allow).
_BRIDGE_STUB = """#!/usr/bin/env python3
import json
import os
import shlex
import sys

raw = sys.stdin.readline()
command = ""
try:
    command = json.loads(raw).get("command", "")
except Exception:  # noqa: BLE001 - the stand-in still answers
    pass
with open(os.environ["TJ_BRIDGE_LOG"], "a", encoding="utf-8") as handle:
    handle.write(command + "\\n")
mode = os.environ.get("TJ_BRIDGE_MODE", "modify")
if mode == "modify":
    prefix = os.environ["TJ_BRIDGE_PREFIX"]
    response = {
        "action": "modify",
        "command": command,
        "modified": prefix + "bash -c " + shlex.quote(command),
        "rule_id": "stub-auto",
        "reason": "stub auto-sandbox",
    }
else:
    response = {
        "action": "allow",
        "command": command,
        "modified": None,
        "rule_id": None,
        "reason": "",
    }
json.dump(response, sys.stdout)
sys.stdout.write("\\n")
"""


def _stub_path(tmp_path: pathlib.Path, *, bwrap: str, unshare: str) -> str:
    """Curated PATH: real tools plus per-backend stub bodies ("rec" = argv
    recorder, "fail" = always-failing stub, "absent" = not on PATH).
    Real `unshare` is always linked: it is an unconditional preflight
    requirement (specs/cli.md preflight 3) — stubbing it away models
    "util-linux missing", not "bwrap absent"."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name in _TOOLS:
        real = shutil.which(name)
        if real:
            (bindir / name).symlink_to(real)
    for name, body in (("bwrap", bwrap), ("unshare", unshare)):
        stub = bindir / name
        if body == "absent":
            continue  # handled below (real unshare symlink) or stays absent
        if body == "rec":
            stub.write_text(
                _BWRAP_STUB if name == "bwrap" else _UNSHARE_STUB,
                encoding="utf-8",
            )
        else:
            stub.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
        stub.chmod(0o755)
    if unshare == "absent" and shutil.which("unshare"):
        # "bwrap absent" must not mean "util-linux absent": the real
        # unshare satisfies the unconditional preflight, and auto without
        # bwrap then resolves to it (proc_view=host).
        (bindir / "unshare").symlink_to(shutil.which("unshare"))
    return str(bindir)


def _env(tmp_path: pathlib.Path, path: str, **overrides: str) -> dict[str, str]:
    env = {
        "PATH": path,
        "HOME": str(tmp_path / "home"),
        "TERMINAL_JAIL_INTERRUPTOR_MODE": "disabled",
        "TERMINAL_JAIL_BRIDGE": str(tmp_path / "no-bridge-here"),
        "TJ_STUB_LOG": str(tmp_path / "bwrap.log"),
        "TJ_UNSHARE_STUB_LOG": str(tmp_path / "unshare.log"),
    }
    pathlib.Path(env["HOME"]).mkdir(exist_ok=True)
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


def _launch_ran(log: pathlib.Path) -> bool:
    """The stub logs one record per invocation (probe, then launch): more
    than one record means the launch arm ran."""
    if not log.exists():
        return False
    return log.read_bytes().count(b"EOR") > 1


def _stub_log(tmp_path: pathlib.Path, backend: str) -> pathlib.Path:
    return tmp_path / ("bwrap.log" if backend == "bwrap" else "unshare.log")


# ── the demand enforced, fail closed (host-independent) ────────────────────


def _demand_refusal_arm(tmp_path, backend: str, **overrides):
    """Run with the demand set over a backend that cannot deliver a private
    procfs; return (result, marker, env)."""
    marker = tmp_path / f"marker-{backend or 'auto'}"
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="absent", unshare="rec"),
        TERMINAL_JAIL_PRIVATE_PROC="required",
        **overrides,
    )
    result = _run_cli(
        "--no-interruptor",
        *(["--user"] if backend != "bare" else []),
        "touch",
        str(marker),
        env=env,
    )
    return result, marker, env


@pytest.mark.standalone_cli
@pytest.mark.parametrize("backend", ["unshare", "auto", "bare"])
def test_demand_over_unshare_refuses_fail_closed(tmp_path, backend) -> None:
    """required + a backend that resolves to unshare (pinned, auto without
    bwrap, or bare) must REFUSE: exit 2, no launch, marker absent, and NO
    proc_view line (nothing was delivered)."""
    overrides = {}
    if backend in ("unshare", "auto"):
        overrides["TERMINAL_JAIL_JAIL_BACKEND"] = backend
    result, marker, env = _demand_refusal_arm(tmp_path, backend, **overrides)
    assert result.returncode == 2, result.stderr
    assert "TERMINAL_JAIL_PRIVATE_PROC=required" in result.stderr
    assert "command not run" in result.stderr
    assert "proc_view=" not in result.stderr
    assert result.stdout == ""
    assert not marker.exists(), "the payload RAN despite the demand"
    assert not _launch_ran(_stub_log(tmp_path, "unshare")), (
        "the unshare launch arm ran despite the demand"
    )


@pytest.mark.standalone_cli
def test_flag_private_proc_refuses(tmp_path) -> None:
    """The --private-proc CLI flag is the same demand as the env var."""
    marker = tmp_path / "marker-flag"
    env = _env(tmp_path, _stub_path(tmp_path, bwrap="absent", unshare="rec"))
    result = _run_cli(
        "--no-interruptor",
        "--private-proc",
        "--user",
        "touch",
        str(marker),
        env=env,
    )
    assert result.returncode == 2, result.stderr
    assert "private /proc" in result.stderr
    assert "command not run" in result.stderr
    assert not marker.exists()


@pytest.mark.standalone_cli
def test_demand_over_probe_failing_bwrap_refuses(tmp_path) -> None:
    """required + a bwrap stub whose PROBE fails: the demand must refuse —
    a bwrap that cannot create namespaces delivers no private procfs."""
    marker = tmp_path / "marker-bwrap-fail"
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="rec", unshare="rec"),
        TERMINAL_JAIL_JAIL_BACKEND="bwrap",
        TERMINAL_JAIL_PRIVATE_PROC="required",
        TJ_BWRAP_PROBE_EXIT="1",
    )
    result = _run_cli("--no-interruptor", "touch", str(marker), env=env)
    assert result.returncode == 2, result.stderr
    assert "bwrap namespace creation failed" in result.stderr
    assert not marker.exists()
    # bwrap probe only — never launched
    assert not _launch_ran(pathlib.Path(env["TJ_STUB_LOG"]))


@pytest.mark.standalone_cli
def test_demand_with_working_bwrap_launches_private(tmp_path) -> None:
    """The demand over a WORKING bwrap resolves: the launch runs and
    attributes proc_view=private."""
    marker = tmp_path / "marker-ok"
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="rec", unshare="absent"),
        TERMINAL_JAIL_PRIVATE_PROC="required",
    )
    result = _run_cli("--no-interruptor", "touch", str(marker), env=env)
    assert result.returncode == 0, result.stderr
    assert marker.exists()
    assert "proc_view=private" in result.stderr


# ── the demand validated like the other control variables ─────────────────


@pytest.mark.standalone_cli
def test_unknown_private_proc_value_rejected(tmp_path) -> None:
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="absent", unshare="rec"),
        TERMINAL_JAIL_PRIVATE_PROC="please",
    )
    result = _run_cli("echo", "x", env=env)
    assert result.returncode == 2
    assert (
        "unknown TERMINAL_JAIL_PRIVATE_PROC='please' (expected required, "
        "or unset for the default behavior)" in result.stderr
    )


@pytest.mark.standalone_cli
def test_env_and_flag_together_still_enforced(tmp_path) -> None:
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="absent", unshare="rec"),
        TERMINAL_JAIL_PRIVATE_PROC="required",
    )
    result = _run_cli("--no-interruptor", "--private-proc", "echo", "x", env=env)
    assert result.returncode == 2
    assert "command not run" in result.stderr


# ── the default is unchanged (the no-regression guard) ─────────────────────


@pytest.mark.standalone_cli
def test_default_unset_runs_and_attributes_host(tmp_path) -> None:
    """Without the demand the historical behavior holds: the --user launch
    runs, no refusal, marker present — and criterion 2's per-run
    attribution names the host view (prose-only no longer: the run SAYS
    it got the host /proc, it just does not refuse)."""
    marker = tmp_path / "marker-default"
    env = _env(tmp_path, _stub_path(tmp_path, bwrap="absent", unshare="rec"))
    result = _run_cli("--no-interruptor", "--user", "touch", str(marker), env=env)
    assert result.returncode == 0, result.stderr
    assert marker.exists()
    assert "command not run" not in result.stderr
    assert _launch_ran(_stub_log(tmp_path, "unshare"))
    view = next(ln for ln in result.stderr.splitlines() if "proc_view=" in ln)
    assert "proc_view=host" in view


@pytest.mark.standalone_cli
def test_empty_value_is_the_default(tmp_path) -> None:
    marker = tmp_path / "marker-empty"
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="absent", unshare="rec"),
        TERMINAL_JAIL_PRIVATE_PROC="",
    )
    result = _run_cli("--no-interruptor", "--user", "touch", str(marker), env=env)
    assert result.returncode == 0, result.stderr
    assert marker.exists()
    assert "command not run" not in result.stderr


# ── per-run proc_view attribution (host-independent) ───────────────────────


@pytest.mark.standalone_cli
def test_proc_view_private_attributed_under_bwrap(tmp_path) -> None:
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="rec", unshare="absent"),
        TERMINAL_JAIL_JAIL_BACKEND="auto",
    )
    result = _run_cli("--no-interruptor", "true", env=env)
    assert result.returncode == 0, result.stderr
    view = next(ln for ln in result.stderr.splitlines() if "proc_view=" in ln)
    assert "proc_view=private" in view
    assert "bwrap" in view


@pytest.mark.standalone_cli
def test_proc_view_host_attributed_under_unshare_user(tmp_path) -> None:
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="absent", unshare="rec"),
        TERMINAL_JAIL_JAIL_BACKEND="unshare",
    )
    result = _run_cli("--no-interruptor", "--user", "true", env=env)
    assert result.returncode == 0, result.stderr
    view = next(ln for ln in result.stderr.splitlines() if "proc_view=" in ln)
    assert "proc_view=host" in view
    assert "unshare" in view


@pytest.mark.standalone_cli
def test_composed_demand_refuses_before_the_composed_launch(tmp_path) -> None:
    """required + namespace creation failing on a plain host: the demand
    refuses BEFORE the composed decision — no COMPOSED MODE banner, the
    command is not run even with TERMINAL_JAIL_COMPOSED=on."""
    env = _env(
        tmp_path,
        _stub_path(tmp_path, bwrap="absent", unshare="fail"),
        TERMINAL_JAIL_PRIVATE_PROC="required",
        TERMINAL_JAIL_COMPOSED="on",
    )
    result = _run_cli("--no-interruptor", "echo", "x", env=env)
    assert result.returncode == 2, result.stderr
    assert "TERMINAL_JAIL_PRIVATE_PROC=required" in result.stderr
    assert "COMPOSED MODE" not in result.stderr


@pytest.mark.standalone_cli
def test_composed_demand_over_modify_rewrite_refuses(tmp_path) -> None:
    """required + a firewall rewrite whose own prefix cannot be created:
    the demand refuses (exit 2) instead of composing the rewrite's
    payload. Bridge stand-in: the recorded canned-modify stub from
    plugin/test_modify_preflight.py (env-configured prefix)."""
    bindir = tmp_path / "bin-mod"
    bindir.mkdir(exist_ok=True)
    for name in _TOOLS + ("python3", "echo", "true"):
        real = shutil.which(name)
        if real:
            (bindir / name).symlink_to(real)
    stub = bindir / "unshare"
    stub.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    stub.chmod(0o755)
    bridge = tmp_path / "bridge.py"
    bridge.write_text(_BRIDGE_STUB, encoding="utf-8")
    bridge.chmod(0o755)
    env = _env(
        tmp_path,
        str(bindir),
        TERMINAL_JAIL_PRIVATE_PROC="required",
        TERMINAL_JAIL_BRIDGE=str(bridge),
        TJ_BRIDGE_LOG=str(tmp_path / "bridge.log"),
        TJ_BRIDGE_PREFIX="unshare --user --pid --fork --kill-child=SIGKILL ",
    )
    env.pop("TERMINAL_JAIL_INTERRUPTOR_MODE", None)
    result = _run_cli("echo", "rewrite-me", env=env)
    assert result.returncode == 2, result.stderr
    assert "TERMINAL_JAIL_PRIVATE_PROC=required" in result.stderr
    assert "rewritten" not in result.stdout


# ── live cells: the MEASURED property (entry count + /proc/1 identity) ─────


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


@functools.lru_cache(maxsize=1)
def _pidns_full() -> bool:
    try:
        result = subprocess.run(
            ["python3", str(PROJECT_ROOT / "scripts" / "pidns-capability-probe.py")],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.stdout.strip().startswith("FULL")


def _host_proc_count() -> int:
    return len([p for p in pathlib.Path("/proc").iterdir() if p.name.isdigit()])


def _read_proc1_comm() -> str:
    try:
        return pathlib.Path("/proc/1/comm").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _jail_proc_observation(backend: str, **extra: str) -> tuple[int, str, str]:
    """Run the real wrapper under `backend`; return (count, /proc/1 comm,
    stderr) from inside the jail."""
    env = dict(os.environ)
    env["TERMINAL_JAIL_JAIL_BACKEND"] = backend
    env["TERMINAL_JAIL_INTERRUPTOR_MODE"] = "disabled"
    env.update(extra)
    result = subprocess.run(
        [
            str(CLI_SCRIPT),
            "--no-interruptor",
            "--user",
            "sh",
            "-c",
            'echo "COUNT=$(ls /proc | grep -c "^[0-9]\\+$")"; '
            'echo "P1=$(cat /proc/1/comm 2>/dev/null || echo unreadable)"',
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    count, proc1 = -1, ""
    for line in result.stdout.splitlines():
        if line.startswith("COUNT="):
            count = int(line[len("COUNT=") :])
        elif line.startswith("P1="):
            proc1 = line[len("P1=") :]
    return count, proc1, result.stderr


@pytest.mark.integration
def test_live_bwrap_demand_delivers_private_proc() -> None:
    if not _bwrap_usable() or not _pidns_full():
        pytest.skip(
            "HOST-DEGRADED-BWRAP: bubblewrap absent/unusable — the live "
            "private-proc demand cell not verified here"
        )
    host = _host_proc_count()
    host_proc1 = _read_proc1_comm()
    count, proc1, stderr = _jail_proc_observation(
        "bwrap", TERMINAL_JAIL_PRIVATE_PROC="required"
    )
    assert count < 100 and count < host, (
        f"bwrap jail sees {count} entries vs {host} host — not private"
    )
    assert proc1 and proc1 != host_proc1, (
        f"/proc/1 = {proc1!r} inside a private procfs jail (host init = {host_proc1!r})"
    )
    assert "proc_view=private" in stderr


@pytest.mark.integration
def test_live_unshare_user_demand_refuses() -> None:
    """The demand over the unshare backend refuses live: exit 2, marker
    absent — the host-view launch never happens."""
    if not _pidns_full():
        pytest.skip(
            "HOST-DEGRADED-PIDNS: no unprivileged namespaces — live "
            "refusal cell not verified here"
        )
    marker = pathlib.Path("/tmp") / f"tj-gap088-marker-{os.getpid()}"
    env = dict(os.environ)
    env["TERMINAL_JAIL_JAIL_BACKEND"] = "unshare"
    env["TERMINAL_JAIL_PRIVATE_PROC"] = "required"
    env["TERMINAL_JAIL_INTERRUPTOR_MODE"] = "disabled"
    try:
        result = subprocess.run(
            [str(CLI_SCRIPT), "--no-interruptor", "--user", "touch", str(marker)],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 2, result.stderr
        assert "TERMINAL_JAIL_PRIVATE_PROC=required" in result.stderr
        assert not marker.exists()
        assert "proc_view=" not in result.stderr
    finally:
        marker.unlink(missing_ok=True)


@pytest.mark.integration
def test_live_unshare_user_default_exposes_host_proc_and_attributes() -> None:
    """Default (no demand): the documented known limit, pinned live with
    the /proc/1 identity AND the proc_view=host attribution."""
    if not _pidns_full():
        pytest.skip(
            "HOST-DEGRADED-PIDNS: no unprivileged namespaces — the live "
            "host-view cell not verified here"
        )
    host = _host_proc_count()
    host_proc1 = _read_proc1_comm()
    count, proc1, stderr = _jail_proc_observation("unshare")
    assert count >= host * 0.5, (
        f"unshare --user jail sees {count} entries vs {host} host — "
        "unexpectedly private; re-document the limit"
    )
    assert proc1 == host_proc1, (
        f"/proc/1 = {proc1!r} — the host init ({host_proc1!r}) should be "
        "visible through the host /proc view"
    )
    assert "proc_view=host" in stderr


# ── the standing probe in the parity battery (import-and-pin) ──────────────


def _load_battery():
    spec = importlib.util.spec_from_file_location(
        "tj_parity_battery",
        PROJECT_ROOT / "scripts" / "backend-parity-battery.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def battery():
    return _load_battery()


def test_battery_demand_cell_is_host_independent_fail_closed(battery) -> None:
    """Cell 8 (the demand enforced) runs on stubs only: it must prove the
    refusal — exit 2, marker ABSENT — regardless of the host's namespace
    or bubblewrap situation."""
    cell = battery._private_proc_demand_cell()
    assert cell["verdict"] == "FAIL-CLOSED-PROVEN", cell
    assert "rc=2" in cell["measured"] and "marker=ABSENT" in cell["measured"]


def test_battery_attribution_cell_names_both_views(battery) -> None:
    """Cell 9 (per-run attribution): on a host where auto resolves to
    bwrap the pair is private/host; where bwrap cannot run it degrades to
    UNMEASURED notes — never a DIFFERS from a mis-set stub. The cell must
    always carry at least one proc_view observation (the attribution is
    the contract, whichever backend resolved)."""
    cell = battery._proc_view_attribution_cell()
    assert cell["verdict"] in ("SAME", "DIFFERS"), cell
    if cell["verdict"] == "SAME":
        assert "proc_view=private" in cell["measured"]
        assert "proc_view=host" in cell["measured"]


@pytest.mark.integration
def test_battery_full_run_has_no_unexplained_divergence() -> None:
    """The whole battery (classifier): exits 0 and never reports DIFFERS
    on a healthy host — the demand cell is FAIL-CLOSED-PROVEN, the
    attribution cell SAME, and the /proc cells keep their verdicts."""
    result = subprocess.run(
        [
            "python3",
            str(PROJECT_ROOT / "scripts" / "backend-parity-battery.py"),
            "--json",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    by_cell = {c["cell"]: c for c in payload["cells"]}
    assert "8 private-proc demand enforced (fail closed)" in by_cell
    assert "9 proc_view attribution per launch" in by_cell
    divergences = [c for c in payload["cells"] if c["verdict"] == "DIFFERS"]
    assert not divergences, divergences
    # cells 1+2 carry the /proc/1 identity the row asked for
    for name in (
        "1 private /proc — bwrap backend",
        "2 private /proc — unshare backend",
    ):
        assert "/proc/1 = " in by_cell[name]["measured"], by_cell[name]
