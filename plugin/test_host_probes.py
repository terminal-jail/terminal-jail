"""Jail-aware host-classification probes (DF-TERMINAL-JAIL-18).

scripts/pidns-capability-probe.py and scripts/fs-isolation-probe.py document
"classifies any host (always exit 0)", but run under a terminal-jail launch
they delivered their own failure as a classification: the pidns probe's
nested bare-mode launch hung inside the jail ("UNKNOWN: probe timed out
after 15s") and the fs probe's mode-600 chmod failed with EINVAL inside the
mapped namespace ("UNKNOWN: probe error: [Errno 22] Invalid argument").

The fix: both probes detect that THEY are jailed (the TERMINAL_JAIL_*
env markers the wrapper exports into a jailed process, or a multi-value
NSpid in /proc/self/status — the auto-sandbox modify path exports no env
markers) and short-circuit to an honest JAIL-AWARE verdict instead of
attempting a nested namespace launch that cannot work.

These tests simulate the jail context offline (monkeypatched env + NSpid
seam) and pin the direct-run classification with fake launches. The real
end-to-end path — both probes through ./standalone/terminal-jail, exactly
as the docs run them — is covered by the host-conditional integration
tests at the bottom (CI runs -m "not integration").
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIDNS_PROBE = PROJECT_ROOT / "scripts" / "pidns-capability-probe.py"
FS_PROBE = PROJECT_ROOT / "scripts" / "fs-isolation-probe.py"
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"


def _load_module(module_name: str, path: Path):
    """Import a dash-named probe script by path."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pidns_probe = _load_module("tj_pidns_capability_probe", PIDNS_PROBE)
fs_probe = _load_module("tj_fs_isolation_probe", FS_PROBE)


class _NoLaunch:
    """Stand-in that fails the test if the probe attempts ANY subprocess."""

    @staticmethod
    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError(
            "probe attempted a subprocess launch while jailed — the guard "
            "must short-circuit BEFORE any nested namespace launch"
        )


# ── pidns-capability-probe.py: jail detection (offline) ────────────────────


class TestPidnsJailDetection:
    def test_env_marker_alone_means_jailed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # --user launches export TERMINAL_JAIL_FS_ISOLATION into the jailed
        # process; NSpid stays single-valued in this simulation to prove the
        # env signal fires on its own.
        monkeypatch.setenv("TERMINAL_JAIL_FS_ISOLATION", "degraded")
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4242"])
        assert pidns_probe._inside_terminal_jail() is True

    def test_multi_value_nspid_alone_means_jailed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The auto-sandbox (modify) path exports NO env markers; a two-value
        # NSpid (outer pid + inner pid 1) is its only fingerprint.
        monkeypatch.delenv("TERMINAL_JAIL_FS_ISOLATION", raising=False)
        monkeypatch.delenv("TERMINAL_JAIL_SECCOMP", raising=False)
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4021", "1"])
        assert pidns_probe._inside_terminal_jail() is True

    def test_empty_marker_value_is_not_a_jail_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_FS_ISOLATION", "")
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4242"])
        assert pidns_probe._inside_terminal_jail() is False

    def test_direct_context_is_not_jailed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TERMINAL_JAIL_FS_ISOLATION", raising=False)
        monkeypatch.delenv("TERMINAL_JAIL_SECCOMP", raising=False)
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4096871"])
        assert pidns_probe._inside_terminal_jail() is False


# ── pidns-capability-probe.py: jailed verdict (offline) ────────────────────


class TestPidnsJailAwareVerdict:
    def test_classify_short_circuits_before_any_launch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4021", "1"])
        monkeypatch.delenv("TERMINAL_JAIL_FS_ISOLATION", raising=False)
        monkeypatch.setattr(pidns_probe.subprocess, "run", _NoLaunch.run)
        verdict = pidns_probe._classify()
        assert verdict.startswith("JAIL-AWARE")
        assert "UNKNOWN" not in verdict

    def test_verdict_names_the_detection_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TERMINAL_JAIL_FS_ISOLATION", raising=False)
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4021", "1"])
        verdict = pidns_probe._jail_aware_verdict()
        assert "multi-value NSpid in /proc/self/status: 4021 1" in verdict

    def test_verdict_carries_direct_run_guidance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4021", "1"])
        verdict = pidns_probe._jail_aware_verdict()
        assert "python3 scripts/pidns-capability-probe.py" in verdict
        assert "outer host" in verdict


# ── pidns-capability-probe.py: direct-run classification pinned (offline) ──


class TestPidnsDirectClassification:
    """Fake bare-mode launches pin the direct (unjailed) verdict mapping."""

    @staticmethod
    def _fake_run(returncode: int, stderr: str = ""):
        def _run(*args: object, **kwargs: object):
            return subprocess.CompletedProcess(args, returncode, "", stderr)

        return _run

    def test_full_when_bare_mode_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4242"])
        monkeypatch.setattr(
            pidns_probe.subprocess, "run", self._fake_run(0)
        )
        assert pidns_probe._classify() == "FULL"

    def test_degraded_on_fail_closed_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4242"])
        stderr = (
            "terminal-jail: namespace creation failed (unshare exit 1); "
            "command not run — on unprivileged hosts try --user"
        )
        monkeypatch.setattr(
            pidns_probe.subprocess, "run", self._fake_run(2, stderr)
        )
        assert pidns_probe._classify() == "DEGRADED"

    def test_unknown_on_unexpected_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pidns_probe, "_nspid_values", lambda: ["4242"])
        monkeypatch.setattr(
            pidns_probe.subprocess, "run", self._fake_run(1, "boom")
        )
        assert pidns_probe._classify().startswith("UNKNOWN")


# ── fs-isolation-probe.py: jailed verdict (offline) ────────────────────────


class TestFsJailAwareVerdict:
    def test_classify_short_circuits_before_any_launch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4021", "1"])
        monkeypatch.delenv("TERMINAL_JAIL_FS_ISOLATION", raising=False)
        monkeypatch.setattr(fs_probe.subprocess, "run", _NoLaunch.run)
        verdict = fs_probe._classify()
        assert verdict.startswith("JAIL-AWARE")
        assert "UNKNOWN" not in verdict

    def test_classify_creates_no_fixture_when_jailed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The pre-fix failure was the mode-600 fixture chmod dying with
        # EINVAL inside the jail; jailed runs must not create it at all.
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4021", "1"])

        def _no_mkdtemp(*args: object, **kwargs: object) -> str:
            raise AssertionError("probe created its fixture while jailed")

        monkeypatch.setattr(fs_probe.tempfile, "mkdtemp", _no_mkdtemp)
        assert fs_probe._classify().startswith("JAIL-AWARE")

    def test_wrapper_observed_mapped_state_is_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_FS_ISOLATION", "mapped")
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4021", "1"])
        verdict = fs_probe._jail_aware_verdict()
        assert verdict.startswith("JAIL-AWARE")
        assert "TERMINAL_JAIL_FS_ISOLATION=mapped" in verdict
        assert "wrapper-observed" in verdict
        assert "UNKNOWN" not in verdict

    def test_wrapper_observed_degraded_state_is_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_FS_ISOLATION", "degraded")
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4021", "1"])
        verdict = fs_probe._jail_aware_verdict()
        assert verdict.startswith("JAIL-AWARE")
        assert "TERMINAL_JAIL_FS_ISOLATION=degraded" in verdict
        assert "NO filesystem isolation" in verdict

    def test_no_marker_names_the_auto_sandbox_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TERMINAL_JAIL_FS_ISOLATION", raising=False)
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4021", "1"])
        verdict = fs_probe._jail_aware_verdict()
        assert "exported no TERMINAL_JAIL_FS_ISOLATION" in verdict

    def test_verdict_carries_direct_run_guidance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4021", "1"])
        verdict = fs_probe._jail_aware_verdict()
        assert "python3 scripts/fs-isolation-probe.py" in verdict
        assert "outer host" in verdict
        assert "NOT a host classification by this probe" in verdict


# ── fs-isolation-probe.py: direct-run classification pinned (offline) ──────


class TestFsDirectClassification:
    """Fake unshare launches pin the direct (unjailed) verdict mapping."""

    @staticmethod
    def _completed(returncode: int, stdout: str = "", stderr: str = ""):
        return subprocess.CompletedProcess(
            ["unshare"], returncode, stdout, stderr
        )

    def test_degraded_when_mapping_denied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4242"])
        mapped = self._completed(
            1, "", "unshare: setgroups failed: Operation not permitted"
        )
        legacy = self._completed(0, "", "")
        monkeypatch.setattr(
            fs_probe, "_run_unshare", lambda flags, payload, timeout=15: (
                mapped if "map-users" in flags else legacy
            )
        )
        verdict = fs_probe._classify()
        assert verdict.startswith("DEGRADED: mapped launch failed")
        assert "uid-mapping denied" in verdict

    def test_full_when_mapping_denies_access(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4242"])
        mapped = self._completed(0, "read_rc=1 write_rc=1\n")
        monkeypatch.setattr(
            fs_probe, "_run_unshare", lambda flags, payload, timeout=15: mapped
        )
        assert fs_probe._classify().startswith("FULL")

    def test_direct_run_is_not_detected_as_jailed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TERMINAL_JAIL_FS_ISOLATION", raising=False)
        monkeypatch.delenv("TERMINAL_JAIL_SECCOMP", raising=False)
        monkeypatch.setattr(fs_probe, "_nspid_values", lambda: ["4096871"])
        assert fs_probe._inside_terminal_jail() is False


# ── End-to-end through the real CLI (host-conditional) ─────────────────────


def _run_probe_through_cli(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI_SCRIPT), sys.executable, str(script)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.integration
class TestJailedProbesThroughCli:
    """Both probes through ./standalone/terminal-jail, as the docs run them.

    On hosts where the auto-sandbox rewrite cannot run (TJ-GAP-034
    degradation contract) the CLI exits 2 before the probe starts — that
    shape is skipped, not failed.
    """

    @staticmethod
    def _skip_on_host_degradation(result: subprocess.CompletedProcess[str]) -> None:
        if result.returncode == 2 and (
            "auto-sandbox modify unavailable" in result.stderr
            or "namespace creation failed" in result.stderr
        ):
            pytest.skip(
                "HOST-DEGRADED-PIDNS: this host cannot run the auto-sandbox "
                "rewrite, so the probe never started (see README Graceful "
                "Degradation)"
            )

    def test_pidns_probe_jailed_reports_jail_aware(self) -> None:
        result = _run_probe_through_cli(PIDNS_PROBE)
        self._skip_on_host_degradation(result)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("JAIL-AWARE"), result.stdout
        assert "UNKNOWN" not in result.stdout

    def test_fs_probe_jailed_reports_jail_aware(self) -> None:
        result = _run_probe_through_cli(FS_PROBE)
        self._skip_on_host_degradation(result)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("JAIL-AWARE"), result.stdout
        assert "UNKNOWN" not in result.stdout

    def test_direct_runs_still_classify_and_exit_zero(self) -> None:
        for script in (PIDNS_PROBE, FS_PROBE):
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            first_line = result.stdout.splitlines()[0] if result.stdout else ""
            assert first_line.split(":")[0] in {
                "FULL",
                "DEGRADED",
                "UNKNOWN",
                "JAIL-AWARE",
            }, f"{script.name}: unexpected direct output {first_line!r}"
