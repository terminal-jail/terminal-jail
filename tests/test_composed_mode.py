"""TJ-GAP-089 — composed-mode regression suite.

Pins the composed deployment contract end to end:

- the env knob (TERMINAL_JAIL_COMPOSED=auto|on|off) is validated before any
  namespace work and documented in --help;
- on a PLAIN host (no outer layer) nothing changes: the forced-fail refusal
  keeps its first sentence verbatim, now followed by one-line cause and
  options; an explicitly pinned backend stays byte-identical (never a silent
  downgrade); auto never composes where detection finds no outer layer;
- TERMINAL_JAIL_COMPOSED=on is the operator override: the command RUNS, and
  when detection found no outer layer the per-layer line says so instead of
  over-claiming platform enforcement;
- composed mode never weakens the firewall: the block arm still exits 126;
- the seccomp filter is NOT applied in composed mode and the wrapper says so;
- the host-capability probes fail fast (3s budget, was 15s) — pinned as
  constants, and live inside a container only (skip marker elsewhere);
- scripts/composed-mode-battery.py: validation semantics (offline) and, on a
  container host, the live three-cell run (skip when docker is absent).

Patterns follow plugin/test_standalone_cli.py (forced-fail PATH without
bwrap = the real container shape) and tests/test_kernel_matrix_teardown.py
(import-and-pin the battery's validator).
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys
import time

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
BATTERY = PROJECT_ROOT / "scripts" / "composed-mode-battery.py"
PIDNS_PROBE = PROJECT_ROOT / "scripts" / "pidns-capability-probe.py"

_ORIG_REFUSAL = (
    "terminal-jail: namespace creation failed (unshare exit 1); "
    "command not run — on unprivileged hosts try --user"
)

_TESTBIN_TOOLS = (
    "bash",
    "uname",
    "python3",
    "grep",
    "cat",
    "cut",
    "timeout",
    "unshare",
    "id",
    "env",
    "echo",
    "awk",
    "readlink",
)


def _make_testbin(tmp_path: pathlib.Path) -> str:
    """A PATH WITHOUT bwrap: auto resolves to the unshare backend, whose
    probe fails on a plain AppArmor host — the forced-fail shape, and the
    exact shape of a slim container (no bubblewrap installed)."""
    testbin = tmp_path / "testbin-nobwrap"
    testbin.mkdir(exist_ok=True)
    for tool in _TESTBIN_TOOLS:
        (testbin / tool).symlink_to(f"/usr/bin/{tool}")
    return str(testbin)


def _run_cli(
    *args: str,
    extra_env: dict[str, str] | None = None,
    path_override: str | None = None,
    timeout: float = 40,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if path_override:
        env["PATH"] = path_override
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(CLI_SCRIPT), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _load_battery():
    spec = importlib.util.spec_from_file_location("tj_composed_battery", BATTERY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── Env knob contract ─────────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_help_documents_composed_env() -> None:
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "TERMINAL_JAIL_COMPOSED=auto|on|off" in result.stdout
    assert "Composed deployment" in result.stdout


@pytest.mark.standalone_cli
def test_unknown_composed_value_rejected_before_namespace_work(
    tmp_path: pathlib.Path,
) -> None:
    result = _run_cli(
        "echo",
        "x",
        extra_env={"TERMINAL_JAIL_COMPOSED": "maybe"},
        path_override=_make_testbin(tmp_path),
    )
    assert result.returncode == 2
    assert (
        "unknown TERMINAL_JAIL_COMPOSED='maybe' (expected auto, on, or off)"
        in result.stderr
    )


# ── Plain-host regression guards (forced-fail PATH, no bwrap) ─────────────


@pytest.mark.standalone_cli
def test_composed_off_refusal_names_cause_and_options(
    tmp_path: pathlib.Path,
) -> None:
    result = _run_cli(
        "--no-interruptor",
        "echo",
        "x",
        extra_env={"TERMINAL_JAIL_COMPOSED": "off"},
        path_override=_make_testbin(tmp_path),
    )
    assert result.returncode == 2
    lines = result.stderr.splitlines()
    assert lines[0] == _ORIG_REFUSAL
    assert any("cause:" in ln and "CAP_SYS_ADMIN" in ln for ln in lines)
    assert any("options:" in ln and "TERMINAL_JAIL_COMPOSED=on" in ln for ln in lines)


@pytest.mark.standalone_cli
def test_explicit_unshare_pin_refusal_byte_identical(
    tmp_path: pathlib.Path,
) -> None:
    result = _run_cli(
        "echo",
        "x",
        extra_env={"TERMINAL_JAIL_JAIL_BACKEND": "unshare"},
        path_override=_make_testbin(tmp_path),
    )
    assert result.returncode == 2
    assert result.stderr == _ORIG_REFUSAL + "\n"


@pytest.mark.standalone_cli
def test_plain_host_auto_never_composes(tmp_path: pathlib.Path) -> None:
    result = _run_cli(
        "--no-interruptor", "echo", "x", path_override=_make_testbin(tmp_path)
    )
    assert result.returncode == 2
    assert result.stderr.splitlines()[0] == _ORIG_REFUSAL
    assert "COMPOSED MODE" not in result.stderr


@pytest.mark.standalone_cli
def test_composed_on_forced_runs_and_reports_no_outer_layer(
    tmp_path: pathlib.Path,
) -> None:
    result = _run_cli(
        "--no-interruptor",
        "echo",
        "tj089-on-arm",
        extra_env={"TERMINAL_JAIL_COMPOSED": "on"},
        path_override=_make_testbin(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "tj089-on-arm" in result.stdout
    assert "COMPOSED MODE" in result.stderr
    assert "NO outer layer detected" in result.stderr
    assert "NOT enforced by any layer" in result.stderr
    assert "provided by the platform/container" not in result.stderr


@pytest.mark.standalone_cli
def test_composed_on_seccomp_not_applied_and_said(
    tmp_path: pathlib.Path,
) -> None:
    result = _run_cli(
        "--seccomp",
        "bash",
        "-c",
        'echo "TJ_SECCOMP_ENV=${TERMINAL_JAIL_SECCOMP:-unset}"',
        extra_env={"TERMINAL_JAIL_COMPOSED": "on"},
        path_override=_make_testbin(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "seccomp filter is NOT applied in composed mode" in result.stderr
    assert "TJ_SECCOMP_ENV=unset" in result.stdout


@pytest.mark.standalone_cli
def test_composed_never_weakens_the_firewall() -> None:
    result = _run_cli("rm", "-rf", "/", extra_env={"TERMINAL_JAIL_COMPOSED": "on"})
    assert result.returncode == 126
    assert "builtin-rm-rf-root" in result.stderr


@pytest.mark.standalone_cli
def test_composed_detection_budget_below_two_seconds(
    tmp_path: pathlib.Path,
) -> None:
    """The composed refusal path (detection + report) answers well under the
    2s probe budget on a plain host."""
    t0 = time.time()
    result = _run_cli(
        "--no-interruptor",
        "echo",
        "x",
        extra_env={"TERMINAL_JAIL_COMPOSED": "off"},
        path_override=_make_testbin(tmp_path),
    )
    elapsed = time.time() - t0
    assert result.returncode == 2
    assert elapsed < 2.0, f"refusal path took {elapsed:.2f}s"


# ── Inside-container behavior (skip cleanly elsewhere) ────────────────────

_IN_CONTAINER = pathlib.Path("/.dockerenv").exists()


@pytest.mark.skipif(
    not _IN_CONTAINER, reason="composed live behavior needs a container"
)
class TestInsideContainer:
    def test_composed_echo_runs_with_layer_report(self) -> None:
        result = _run_cli("echo", "TJ089-INNER-OK")
        assert result.returncode == 0, result.stderr
        assert "TJ089-INNER-OK" in result.stdout
        if "COMPOSED MODE" in result.stderr:
            # Composed path taken: the per-layer report must be honest.
            assert "jail_layer=platform" in result.stderr
            assert "firewall: enforced by terminal-jail" in result.stderr
        # else: this container CAN create inner namespaces (CAP_SYS_ADMIN +
        # userns allowed) — the plain jail ran, which is also contract-green.

    def test_firewall_block_inside_container(self) -> None:
        result = _run_cli("rm", "-rf", "/")
        assert result.returncode == 126
        assert "builtin-rm-rf-root" in result.stderr

    def test_probes_fail_fast_inside_container(self) -> None:
        t0 = time.time()
        result = subprocess.run(
            [sys.executable, str(PIDNS_PROBE)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        elapsed = time.time() - t0
        assert result.returncode == 0, result.stderr
        assert elapsed < 10, f"probe took {elapsed:.1f}s inside the container"
        assert "timed out after 15s" not in result.stdout


# ── Probe budgets pinned as text (offline) ────────────────────────────────


def test_probe_budgets_are_three_seconds() -> None:
    userns = (
        PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor" / "userns.py"
    ).read_text(encoding="utf-8")
    assert "_PROBE_TIMEOUT = 3" in userns
    assert "_PROPERTY_TIMEOUT = 3" in userns
    assert "_PROBE_TIMEOUT = 15" not in userns
    pidns = PIDNS_PROBE.read_text(encoding="utf-8")
    assert "timeout=3" in pidns
    assert "timed out after 3s" in pidns
    fs_probe = (PROJECT_ROOT / "scripts" / "fs-isolation-probe.py").read_text(
        encoding="utf-8"
    )
    assert "timeout: int = 3" in fs_probe


# ── Battery pins (offline + container-conditional live) ───────────────────


def shutil_which_docker() -> bool:
    import shutil

    return shutil.which("docker") is not None


class TestCompositionBattery:
    @classmethod
    def setup_class(cls) -> None:
        cls.battery = _load_battery()

    def test_valid_row_accepted(self) -> None:
        row = {
            "cell": "both",
            "verdict": "PASS",
            "properties": {"pid_ns": "pid:[1]"},
            "failures": [],
            "note": "n",
        }
        assert self.battery._validate_row(row) == []

    def test_malformed_rows_rejected(self) -> None:
        good = {
            "cell": "both",
            "verdict": "PASS",
            "properties": {"pid_ns": "pid:[1]"},
            "failures": [],
            "note": "n",
        }
        bad = [
            {**good, "verdict": "GREEN"},
            {**good, "cell": "everywhere"},
            {**good, "verdict": "UNAVAILABLE", "failures": []},
            {**good, "verdict": "PASS", "failures": ["x"]},
            {**good, "verdict": "PASS", "properties": None},
        ]
        for row in bad:
            assert self.battery._validate_row(row), f"accepted malformed: {row}"

    def test_selftest_nonvacuous(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BATTERY), "--selftest"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "SELFTEST PASS" in result.stdout
        assert "5 malformed rows rejected" in result.stdout

    @pytest.mark.skipif(
        not shutil_which_docker(), reason="docker not available on this host"
    )
    def test_live_three_cell_run(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BATTERY)],
            capture_output=True,
            text=True,
            timeout=400,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "summary: 3/3 PASS" in result.stdout
