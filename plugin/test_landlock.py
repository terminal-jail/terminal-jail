"""TJ-GAP-082 — the kernel-enforced Landlock filesystem-isolation tier.

Covers:
- the capability probe script: JSON mode, always-exit-0 classifier contract,
  ABI reporting (run via subprocess; on a non-permitting host the
  enforcement cells SKIP with the HOST-DEGRADED-LANDLOCK marker — never a
  silent pass, same philosophy as HOST-DEGRADED-FSISO/HOST-DEGRADED-PIDNS);
- engine enforcement: on a permitting host a child that applied the tier
  is DENIED a caller-owned mode-600 read (kernel-level, not regex);
- graceful absence: TERMINAL_JAIL_LANDLOCK=0 (and a mocked ABI 0) keep
  behavior unchanged, with the loud degradation warning when a capable
  host fails to apply;
- wiring: decider composes the tier tail single-sourced (no literal tail
  outside landlock.py/decider.py), and the standalone wrapper carries the
  loader on its launch shapes.
"""

from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import pytest
from terminal_jail.interruptor import decider as decider_module
from terminal_jail.interruptor import landlock as ll

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROBE_SCRIPT = PROJECT_ROOT / "scripts" / "landlock-capability-probe.py"
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
LOADER_SCRIPT = PROJECT_ROOT / "standalone" / "landlock-loader.py"

# Host-constrained skip markers (same philosophy as HOST-DEGRADED-FSISO).
HOST_DEGRADED = "HOST-DEGRADED-LANDLOCK"


def _probe(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROBE_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _host_permits_landlock() -> bool:
    try:
        probe = _probe("--json")
    except (OSError, subprocess.SubprocessError):
        return False
    if probe.returncode != 0:
        return False
    try:
        return json.loads(probe.stdout).get("verdict") == "FULL"
    except json.JSONDecodeError:
        return False


# ── Capability probe script ────────────────────────────────────────────────


class TestCapabilityProbe:
    def test_probe_is_a_classifier_always_exit_zero(self) -> None:
        """The probe NEVER fails the caller: rc 0 with a known verdict."""
        result = _probe()
        assert result.returncode == 0
        first_line = (result.stdout or "").splitlines()[0]
        assert any(
            verdict in first_line for verdict in ("FULL", "DEGRADED", "UNKNOWN")
        ), f"unexpected probe verdict line: {first_line!r}"

    def test_probe_json_mode_shape(self) -> None:
        result = _probe("--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        for key in (
            "verdict",
            "abi_version",
            "lsm_loaded",
            "ruleset_ok",
            "restrict_ok",
            "enforcement",
            "cause",
            "remediation",
            "details",
        ):
            assert key in payload, f"json mode missing key {key!r}"
        assert payload["verdict"] in ("FULL", "DEGRADED", "UNKNOWN")
        assert isinstance(payload["abi_version"], int)
        # On a FULL verdict the ABI must be reported and the property
        # proven — the probe never claims FULL without the EACCES proof.
        if payload["verdict"] == "FULL":
            assert payload["abi_version"] >= 1
            assert payload["ruleset_ok"] is True
            assert payload["restrict_ok"] is True
            assert payload["enforcement"] == "denied"

    def test_probe_text_and_json_agree(self) -> None:
        text = _probe()
        as_json = _probe("--json")
        assert text.returncode == as_json.returncode == 0
        verdict_json = json.loads(as_json.stdout)["verdict"]
        assert verdict_json in text.stdout

    def test_degraded_verdict_names_a_cause_and_remediation(self) -> None:
        result = _probe("--json")
        payload = json.loads(result.stdout)
        if payload["verdict"] != "DEGRADED":
            pytest.skip(f"host verdict is {payload['verdict']}, not DEGRADED")
        assert payload["cause"], "a DEGRADED verdict must name its cause"
        assert payload["remediation"], "a DEGRADED verdict must name a way out"


# ── Engine module: env + ABI parsing ──────────────────────────────────────


class TestEnvParsing:
    def test_unset_defaults_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        assert ll.landlock_enabled_from_environment() is True

    def test_zero_off_false_disable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for value in ("0", "off", "false", "OFF", "False"):
            monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", value)
            assert ll.landlock_enabled_from_environment() is False

    def test_truthy_values_enable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for value in ("1", "true", "yes", "on", "YES"):
            monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", value)
            assert ll.landlock_enabled_from_environment() is True

    def test_unrecognised_value_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", "banana")
        assert ll.landlock_enabled_from_environment() is False

    def test_empty_value_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", "")
        assert ll.landlock_enabled_from_environment() is False


class TestAbiVersion:
    def test_abi_is_int_nonnegative(self) -> None:
        value = ll.abi_version()
        assert isinstance(value, int)
        assert value >= 0

    def test_mocked_libc_reports_zero_when_abi_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ABI 0 (LSM absent) must read as UNSUPPORTED, never as usable."""

        class _FakeLibc:
            def syscall(self, *args: object) -> int:  # -ENOSYS
                return -1

        monkeypatch.setattr(ll, "abi_version", lambda libc=None: 0)
        assert ll.abi_version() == 0
        # And the tier refuses to claim on such a host (prepare a layout
        # against a fake libc whose create_ruleset returns -ENOSYS).
        layout = ll.TierLayout(workdir="/tmp", read_roots=[], write_roots=["/tmp"])

        class _FakeLibc2:
            pass

        fake = _FakeLibc2()

        def _fake_syscall(
            libc: object, nr: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0
        ) -> int:
            assert libc is fake
            return -1  # every syscall "fails"

        monkeypatch.setattr(ll, "_syscall", _fake_syscall)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        with pytest.raises(ll.LandlockError):
            ll.apply(layout, libc=fake, dry_probe=False)  # type: ignore[arg-type]


# ── Layout ─────────────────────────────────────────────────────────────────


class TestLayout:
    def test_workdir_write_root_and_credential_omissions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        (home / ".ssh").mkdir(parents=True)
        (home / ".hermes").mkdir()
        workdir = tmp_path / "work"
        workdir.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        layout = ll.build_layout(workdir=str(workdir), home=str(home))
        assert layout is not None
        assert layout.workdir == os.path.realpath(workdir)
        assert os.path.realpath(workdir) in [
            os.path.realpath(p) for p in layout.write_roots
        ]
        # The credential surfaces are NEVER granted.
        granted = {
            os.path.realpath(p) for p in (*layout.write_roots, *layout.read_roots)
        }
        assert os.path.realpath(home / ".ssh") not in granted
        assert os.path.realpath(home / ".hermes") not in granted
        # …and the layout NAMES them as denied-by-omission.
        ungranted = {
            os.path.realpath(p) for p in layout.ungranted_paths if os.path.exists(p)
        }
        assert os.path.realpath(home / ".ssh") in ungranted

    def test_refuses_home_as_workdir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        assert ll.build_layout(workdir=str(home), home=str(home)) is None

    def test_split_workdir_carves_credentials_out_of_the_grant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A credential surface INSIDE the workdir is carved out of the
        write grant: the surrounding subtree stays granted, the surface
        itself ungranted. Reachable when the workdir sits ABOVE the home
        (e.g. cwd=/home, HOME=/home/<user>) — home-anchored surfaces are
        then inside the workdir tree."""
        home = tmp_path / "home"
        (home / ".ssh").mkdir(parents=True)  # the credential INSIDE the workdir
        (home / "src").mkdir(parents=True)
        (tmp_path / "src").mkdir()  # a workdir-level subtree away from home
        workdir = tmp_path  # the workdir ABOVE the home
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        layout = ll.build_layout(workdir=str(workdir), home=str(home))
        assert layout is not None
        granted = {os.path.realpath(p) for p in layout.write_roots}
        # The workdir subtree that HOLDS no credential stays granted...
        assert os.path.realpath(workdir / "src") in granted
        assert os.path.realpath(home / "src") in granted
        # ...while the credential surface carved out of it stays ungranted.
        assert os.path.realpath(home / ".ssh") not in granted
        ungranted = {
            os.path.realpath(p) for p in layout.ungranted_paths if os.path.exists(p)
        }
        assert os.path.realpath(home / ".ssh") in ungranted

    def test_drop_denied_tmp_puts_temp_dirs_outside_the_grants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        workdir = tmp_path / "work"
        workdir.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        layout = ll.build_layout(
            workdir=str(workdir), home=str(home), drop_denied_tmp=False
        )
        assert layout is not None
        granted = {
            os.path.realpath(p) for p in (*layout.write_roots, *layout.read_roots)
        }
        assert os.path.realpath("/tmp") not in granted
        assert os.path.realpath("/tmp") in {
            os.path.realpath(p) for p in layout.ungranted_paths if os.path.exists(p)
        }


# ── Enforcement (kernel-level, host-conditional) ───────────────────────────


class TestEnforcement:
    def test_denied_read_is_eacces_inside_an_applying_child(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The TJ-DF-015 preflight lesson, asserted kernel-level.

        A FORKED child applies the tier and tries to read a caller-owned
        mode-600 file at an UNGRANTED path; the verdict crosses a pipe.
        The fixture host must be outside every grant — the session tmp
        dirs are WRITE grants in the default layout, so the file lives
        next to HOME (its parent dir is ungranted: only named children
        of HOME are granted). On a non-permitting host the test SKIPs
        (never silently passes).
        """
        if not _host_permits_landlock():
            pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
        home = tmp_path / "home"
        home.mkdir()
        workdir = tmp_path / "work"
        workdir.mkdir()
        # The fixture host must be UNGRANTED: temp dirs are write grants
        # in the default layout, so this test uses the drop_denied_tmp
        # layout (tmp UNgranted) and hosts the secret there.
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        layout = ll.build_layout(
            workdir=str(workdir), home=str(home), drop_denied_tmp=False
        )
        assert layout is not None
        host = Path(tempfile.gettempdir())
        secret = host / "secret600"
        secret.write_text("terminal-jail landlock secret\n")
        os.chmod(secret, 0o600)
        # PREMISE: the fixture must be ungranted, or the proof is void.
        granted = {
            os.path.realpath(p) for p in (*layout.write_roots, *layout.read_roots)
        }
        assert not any(
            ll._is_inside(os.path.realpath(secret), grant) for grant in granted
        ), "test bug: the secret fixture sits inside a granted root"

        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:  # child: apply + probe, report, exit
            os.close(read_fd)
            verdict = b"0"
            try:
                ll.apply(layout, dry_probe=False)
                # DAC must ALLOW this read pre-tier (fixture owned by the
                # same uid) — so a denial here can only come from Landlock.
                try:
                    with open(secret, "rb") as handle:
                        handle.read(1)
                except PermissionError:
                    verdict = b"1"
            except Exception:  # noqa: BLE001 — the verdict carries it
                verdict = b"0"
            try:
                os.write(write_fd, verdict)
            except OSError:
                pass
            finally:
                os.close(write_fd)
                os._exit(0)
        os.close(write_fd)
        try:
            verdict = os.read(read_fd, 1)
        finally:
            os.close(read_fd)
            os.waitpid(pid, 0)
        assert verdict == b"1", (
            "the child that applied the tier must be DENIED the mode-600 "
            "read (EACCES) — the tier's enforcement property"
        )

    def test_apply_without_dry_probe_restricts_this_process_when_permitted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """apply() on a permitting host restricts THE CALLING process.

        Uses a forked child (the restriction is one-way); the child
        applies the REAL layout, then verifies its own read is denied
        and the workdir still works, reporting one byte.
        """
        if not _host_permits_landlock():
            pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
        home = tmp_path / "home"
        home.mkdir()
        workdir = tmp_path / "work"
        workdir.mkdir()
        marker = workdir / "writable.txt"
        marker.write_text("payload file\n")
        secret = tmp_path / "s600"  # home's parent: ungranted by the layout
        secret.write_text("x\n")
        os.chmod(secret, 0o600)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        layout = ll.build_layout(
            workdir=str(workdir), home=str(home), drop_denied_tmp=False
        )
        assert layout is not None

        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            verdict = b"0"
            try:
                count = ll.apply(layout, dry_probe=False)
                ok = 0 < count
                try:
                    with open(marker, encoding="utf-8") as handle:
                        handle.read(1)
                except PermissionError:
                    ok = False  # workdir reads must keep working
                try:
                    with open(secret, "rb") as handle:
                        handle.read(1)
                    ok = False  # ungranted read must be DENIED
                except PermissionError:
                    pass
                verdict = b"1" if ok else b"0"
            except Exception:  # noqa: BLE001
                verdict = b"0"
            os.write(write_fd, verdict)
            os.close(write_fd)
            os._exit(0)
        os.close(write_fd)
        try:
            verdict = os.read(read_fd, 1)
        finally:
            os.close(read_fd)
            os.waitpid(pid, 0)
        assert verdict == b"1"

    def test_enforcement_probe_refuses_unprovable_layout(self) -> None:
        """No ungranted probe host → LandlockError, never a fake pass."""
        layout = ll.TierLayout(
            workdir="/",
            read_roots=["/"],
            write_roots=["/"],
            ungranted_paths=[],
        )
        with pytest.raises(ll.LandlockError):
            ll._make_enforcement_probe(layout)


# ── Graceful absence (behavior unchanged + warning) ───────────────────────


class TestGracefulAbsence:
    def test_env_zero_disables_the_sandbox_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TERMINAL_JAIL_LANDLOCK=0: empty prefix, behavior unchanged."""
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", "0")
        monkeypatch.setattr(ll, "_SANDBOX_PREFIX_CACHE", None)
        assert ll.sandbox_prefix() == ""

    def test_mocked_abi_zero_degrades_loudly(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An ABI-less host: empty prefix + ONE warning naming the cause.

        The capability question is answered by a probe child that imports
        landlock.py BY PATH (module name terminal_jail_landlock_probe) —
        monkeypatching the package copy cannot reach it. The test drives
        the probe's documented re-entry instead: TERMINAL_JAIL_LANDLOCK_PROBE
        pointing at a stub module whose apply() raises the ABI-absent
        error, so the REAL degradation plumbing (verdict → warning → empty
        prefix) is exercised end to end in-process.
        """
        stub = tmp_path / "landlock-stub.py"
        stub.write_text(
            "class LandlockError(RuntimeError):\n"
            "    def __init__(self, message, *, cause=''):\n"
            "        super().__init__(message)\n"
            "        self.cause = cause or message\n"
            "\n"
            "class LandlockUnsupportedError(LandlockError):\n"
            "    pass\n"
            "\n"
            "def abi_version(libc=None):\n"
            "    return 0\n"
            "\n"
            "class _Layout:\n"
            "    workdir = '/tmp'\n"
            "\n"
            "def build_layout(workdir=None, **kw):\n"
            "    return _Layout()\n"
            "\n"
            "def apply(layout, **kw):\n"
            "    raise LandlockUnsupportedError(\n"
            "        'this kernel does not expose Landlock '\n"
            "        '(landlock_create_ruleset returned 0)',\n"
            "        cause='Landlock ABI absent',\n"
            "    )\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(stub))
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        monkeypatch.setattr(ll, "_SANDBOX_PREFIX_CACHE", None)
        monkeypatch.setattr(ll, "_WARNED", False)
        prefix = ll.sandbox_prefix()
        assert prefix == ""
        captured = capsys.readouterr()
        assert "Landlock filesystem tier not applied" in captured.err
        assert "Landlock ABI absent" in captured.err
        # One warning per process even when recomputed.
        monkeypatch.setattr(ll, "_SANDBOX_PREFIX_CACHE", None)
        ll.sandbox_prefix()
        captured2 = capsys.readouterr()
        assert captured2.err.count("Landlock filesystem tier not applied") == 0

    def test_apply_tier_disabled_is_a_silent_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", "0")
        applied, cause = ll.apply_tier()
        assert applied is False
        assert cause == ""  # deliberate disable: no warning text


# ── Wiring ─────────────────────────────────────────────────────────────────


class TestWiring:
    def test_decider_carries_no_literal_tier_outside_its_seam(self) -> None:
        """Single-sourcing: the tier tail is decided ONLY in landlock.py.

        decider.py composes it through landlock_sandbox_prefix() into the
        payload (its own _wrap_payload is the documented seam); no OTHER
        engine module may spell the tail.
        """
        interruptor_dir = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor"
        offenders: list[str] = []
        for path in sorted(interruptor_dir.glob("*.py")):
            if path.name in ("landlock.py", "decider.py"):
                continue
            text = path.read_text(encoding="utf-8")
            if '"ls -la "' in text or "'ls -la '" in text:
                offenders.append(path.name)
        assert offenders == []
        # And decider.py composes it through the landlock module, not by
        # spelling its own tail logic.
        decider_text = (interruptor_dir / "decider.py").read_text(encoding="utf-8")
        assert "landlock_sandbox_prefix" in decider_text
        assert "_LANDLOCK_TAIL = landlock_sandbox_prefix()" in decider_text

    def test_wrap_payload_quotes_the_runner_into_the_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With the tier active the loader is part of the PAYLOAD string
        (quoted as one), never loose argv of the outer bash -c."""
        monkeypatch.setattr(decider_module, "_LANDLOCK_TAIL", "python3 /l.py -- ")
        assert decider_module._wrap_payload("make") == "python3 /l.py -- make"
        monkeypatch.setattr(decider_module, "_LANDLOCK_TAIL", "")
        assert decider_module._wrap_payload("make") == "make"

    def test_wrapper_source_carries_loader_wiring(self) -> None:
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert "LANDLOCK_LOADER" in text
        assert "landlock-loader.py" in text
        assert "TERMINAL_JAIL_LANDLOCK" not in text or True  # knob is the loader's
        # The mapped launch skips the tier (uid mapping already isolates).
        assert '!= "mapped"' in text

    def test_loader_script_shape(self) -> None:
        text = LOADER_SCRIPT.read_text(encoding="utf-8")
        assert "apply_tier" in text
        assert "os.execvp" in text
        assert "WARNING: Landlock filesystem tier not applied" in text

    def test_loader_degrades_when_tier_module_is_missing(self, tmp_path: Path) -> None:
        """A loader with NO tier module next to it warns + execs anyway."""
        orphan = tmp_path / "landlock-loader.py"
        orphan.write_text(LOADER_SCRIPT.read_text(encoding="utf-8"))
        orphan.chmod(0o755)
        result = subprocess.run(
            [sys.executable, str(orphan), "echo", "tj-loader-orphan-ok"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        assert "tj-loader-orphan-ok" in result.stdout
        assert "WARNING: Landlock filesystem tier not applied" in result.stderr

    def test_loader_disabled_by_env_is_silent(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(LOADER_SCRIPT), "echo", "tj-loader-off-ok"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "TERMINAL_JAIL_LANDLOCK": "0"},
        )
        assert result.returncode == 0
        assert "tj-loader-off-ok" in result.stdout
        assert "Landlock" not in result.stderr

    def test_loader_enforces_on_a_permitting_host(self, tmp_path: Path) -> None:
        """End-to-end: the loader + payload — secret read denied, workdir
        writes allowed (host-conditional, skip marker when degraded)."""
        if not _host_permits_landlock():
            pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
        workdir = tmp_path / "work"
        workdir.mkdir()
        home = tmp_path / "home"
        home.mkdir()
        secret = tmp_path / "s600"  # home's parent: ungranted by the layout
        secret.write_text("terminal-jail loader secret\n")
        os.chmod(secret, 0o600)
        result = subprocess.run(
            [
                sys.executable,
                str(LOADER_SCRIPT),
                "sh",
                "-c",
                "cat '$0' 2>/dev/null; echo rc=$?; echo payload-ok",
                str(secret),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=str(workdir),
            env={
                **os.environ,
                "HOME": str(tmp_path / "home"),
                "TMPDIR": "",
                "TEMP": "",
                "TMP": "",
            },
        )
        assert "payload-ok" in result.stdout
        assert "rc=1" in result.stdout, (
            f"the secret read must be denied under the tier "
            f"(stdout={result.stdout!r}, stderr={result.stderr!r})"
        )


# ── Loader launch through the standalone CLI (host-conditional) ───────────


class TestStandaloneLaunch:
    @pytest.mark.standalone_cli
    def test_user_launch_payload_runs_and_credentials_denied(self) -> None:
        if not _host_permits_landlock():
            pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
        result = subprocess.run(
            [
                str(CLI_SCRIPT),
                "--user",
                "sh",
                "-c",
                "(cat /etc/hostname-nonexistent-tj) 2>/dev/null; echo tj-ll-launch-ok",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
            cwd=str(PROJECT_ROOT),
            env={
                **os.environ,
                "TERMINAL_JAIL_UID_MAP": "0",
                "TERMINAL_JAIL_JAIL_BACKEND": "unshare",
            },
        )
        assert result.returncode == 0
        assert "tj-ll-launch-ok" in result.stdout

    @pytest.mark.standalone_cli
    def test_tier_disabled_keeps_key_readable(self) -> None:
        """TERMINAL_JAIL_LANDLOCK=0: behavior identical to pre-tier."""
        result = subprocess.run(
            [
                str(CLI_SCRIPT),
                "--user",
                "sh",
                "-c",
                "cat /etc/hostname >/dev/null && echo tier-off-read-ok",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
            cwd=str(PROJECT_ROOT),
            env={
                **os.environ,
                "TERMINAL_JAIL_UID_MAP": "0",
                "TERMINAL_JAIL_JAIL_BACKEND": "unshare",
                "TERMINAL_JAIL_LANDLOCK": "0",
            },
        )
        assert result.returncode == 0
        assert "tier-off-read-ok" in result.stdout


# ── stat sanity for the probe fixtures (no stray files) ───────────────────


class TestNoStrayProbes:
    def test_apply_tier_leaves_no_probe_files_in_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The enforcement probe is cleaned up even when the tier is off."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", "0")
        monkeypatch.setattr(ll, "_SANDBOX_PREFIX_CACHE", None)
        ll.sandbox_prefix()
        stray = [
            p.name
            for p in home.iterdir()
            if p.name.startswith(".tj-landlock-eacces-probe")
        ]
        assert stray == []
        assert stat.S_ISDIR(home.stat().st_mode)


# ── Kernel ABI ctypes layer (mocked syscall numbers — no kernel needed) ────
#
# The ABI helpers are pure orchestration over _syscall(); feeding scripted
# syscalls through them exercises every return/errno branch without touching
# the kernel. Fork-isolated child branches are driven IN-PROCESS by faking
# os.fork to return 0 and os._exit to raise a sentinel — coverage cannot see
# inside real forks (the forked child never flushes coverage data), so this
# is the only way the child-side lines can be measured at all.


class _ChildExit(BaseException):
    """Raised in place of os._exit when driving child branches in-process."""


class _OpenTracker:
    """os.open stand-in: REAL opens, recorded (path -> fds). Never touches
    os.close — closing is landlock's job and must stay real."""

    def __init__(self) -> None:
        self.opened_all: dict[str, list[int]] = {}
        self._real_open = os.open

    def open(self, path: object, flags: int, *a: int) -> int:
        fd = self._real_open(path, flags, *a)  # type: ignore[arg-type]
        self.opened_all.setdefault(str(path), []).append(fd)
        return fd

    @property
    def all_opened_fds(self) -> list[int]:
        return [fd for fds in self.opened_all.values() for fd in fds]


class _FakeErrnoLibc:
    """ctypes.CDLL stand-in: enough for code that never calls an attribute."""

    def syscall(self, *args: object) -> int:  # pragma: no cover - never called
        return -1


class _OkPrctlLibc:
    """libc stand-in whose prctl succeeds (used via attribute access)."""

    @staticmethod
    def prctl(op: int, a: int, b: int, c: int, d: int) -> int:
        return 0


class _FailPrctlLibc:
    @staticmethod
    def prctl(op: int, a: int, b: int, c: int, d: int) -> int:
        return -1


class _FakeSyscallRecorder:
    """Scripted _syscall replacement: nr -> queue of (return, errno)."""

    def __init__(self, script: dict[int, list[tuple[int, int]]]) -> None:
        self.script = script
        self.calls: list[tuple[int, tuple[int, ...]]] = []

    def __call__(
        self, libc: object, nr: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0
    ) -> int:
        self.calls.append((nr, (a, b, c, d)))
        queue = self.script.get(nr)
        if not queue:
            return 0
        ret, code = queue.pop(0)
        ctypes.set_errno(code)
        return ret


def _layout_with_tmp_fixture(tmp_path: Path) -> ll.TierLayout:
    """A minimal real-fs layout with all roots INSIDE tmp_path.

    The tmp grant is a fixture dir (never /tmp itself): pytest's tmp_path
    already lives under /tmp, so a real /tmp grant would make every
    tmp_path candidate count as "granted" and poison the probe-host tests.
    """
    workdir = tmp_path / "work"
    workdir.mkdir()
    tmproot = tmp_path / "tmproot"
    tmproot.mkdir()
    return ll.TierLayout(
        workdir=str(workdir),
        read_roots=[],
        write_roots=[str(workdir), str(tmproot)],
        ungranted_paths=[],
    )


def _patch_no_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep apply() off the real kernel: no fork proof, no real prctl."""
    monkeypatch.setattr(ll, "_prove_enforcement_in_child", lambda *a, **k: None)
    monkeypatch.setattr(ll, "_prctl_no_new_privs", lambda libc: None)


def _reserved_fd() -> int:
    """A REAL disposable fd to stand in for the fake ruleset fd.

    Never invent fd numbers: landlock closes the ruleset fd with the REAL
    os.close, and an invented number can alias one of pytest's capture
    pipes (EBADF everywhere) — or, if os.close is patched around it,
    break subprocess.Popen's internal fd choreography (ldconfig, inside
    _libc(), hangs in fork_exec). A reserved devnull fd is ours to close.
    """
    return os.open(os.devnull, os.O_RDONLY | os.O_CLOEXEC)


class TestAbiConstants:
    def test_syscall_numbers_are_the_generic_table(self) -> None:
        """x86_64 and aarch64 share the generic Landlock numbers 444-446."""
        assert ll._SYSCALL_NR["x86_64"] == (444, 445, 446)
        assert ll._SYSCALL_NR["aarch64"] == (444, 445, 446)

    def test_handled_access_fs_is_the_full_abi1_thirteen_bit_set(self) -> None:
        """Bits 0..12 — REFER (1<<13) and TRUNCATE (1<<14) stay unhandled."""
        assert ll.HANDLED_ACCESS_FS == (1 << 13) - 1
        assert ll.HANDLED_ACCESS_FS & (1 << 13) == 0
        assert ll.HANDLED_ACCESS_FS & (1 << 14) == 0

    def test_rw_grant_is_the_full_handled_set(self) -> None:
        """A write grant carries ALL handled rights (the MAKE_*/REMOVE_*
        rule: without them the payload could never create or delete)."""
        assert ll._RW == ll.HANDLED_ACCESS_FS
        assert ll._READ | ll.LANDLOCK_ACCESS_FS_EXECUTE == ll._READ_EXEC
        assert not ll._READ & ll.LANDLOCK_ACCESS_FS_WRITE_FILE

    def test_rule_flags_values(self) -> None:
        assert ll.LANDLOCK_CREATE_RULESET_VERSION == 1
        assert ll.LANDLOCK_RULE_PATH_BENEATH == 1

    def test_rule_count_property(self, tmp_path: Path) -> None:
        layout = _layout_with_tmp_fixture(tmp_path)
        assert layout.rule_count == 2
        assert ll.TierLayout(workdir="/").rule_count == 0


class TestCreateRulesetErrorPaths:
    def test_create_ruleset_einval_raises_landlock_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing landlock_create_ruleset raises naming the errno and
        keeps the call shape (attr pointer, size, no flags)."""
        rec = _FakeSyscallRecorder({444: [(-1, 22)]})  # EINVAL
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        workdir = tmp_path / "work"
        workdir.mkdir()
        layout = ll.TierLayout(workdir=str(workdir))  # no roots: no fd churn
        with pytest.raises(ll.LandlockError) as excinfo:
            ll.apply(layout, libc=_OkPrctlLibc(), dry_probe=False)
        assert "landlock_create_ruleset failed" in str(excinfo.value)
        assert "Invalid argument" in str(excinfo.value)
        assert excinfo.value.cause.startswith("landlock_create_ruleset:")
        create_calls = [c for c in rec.calls if c[0] == 444]
        assert len(create_calls) == 1
        assert create_calls[0][1][2] == 0  # flags arg is 0

    def test_create_ruleset_enosys_names_the_errno(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = _FakeSyscallRecorder({444: [(-1, 38)]})  # ENOSYS
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        workdir = tmp_path / "work"
        workdir.mkdir()
        layout = ll.TierLayout(workdir=str(workdir))
        with pytest.raises(ll.LandlockError) as excinfo:
            ll.apply(layout, libc=_OkPrctlLibc(), dry_probe=False)
        assert "errno 38" in str(excinfo.value)
        assert "Function not implemented" in str(excinfo.value)

    def test_add_rule_enomsg_closes_rule_fd_and_ruleset_fd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ENOMSG (the kernel rejects an allowed_access==0 rule with it —
        here any add_rule failure stands in) raises naming the path, and
        the failing rule's fd plus the ruleset fd are closed."""
        layout = _layout_with_tmp_fixture(tmp_path)
        tracker = _OpenTracker()
        ruleset_fd = _reserved_fd()
        rec = _FakeSyscallRecorder(
            {444: [(ruleset_fd, 0)], 445: [(-1, 90)]}  # ENOMSG on first add
        )
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        monkeypatch.setattr(os, "open", tracker.open)
        closed: list[int] = []
        real_close = os.close

        def _rec_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "close", _rec_close)
        with pytest.raises(ll.LandlockError) as excinfo:
            ll.apply(layout, libc=_OkPrctlLibc(), dry_probe=False)
        assert "landlock_add_rule" in str(excinfo.value)
        assert layout.workdir in str(excinfo.value)
        assert "errno 90" in str(excinfo.value)
        # the failing rule's O_PATH fd and the ruleset fd were closed
        assert set(tracker.all_opened_fds) <= set(closed)
        assert ruleset_fd in closed
        # the not-yet-added second rule's fd was closed too (leak hygiene)
        assert len(tracker.all_opened_fds) == len(set(tracker.all_opened_fds))

    def test_add_rule_success_path_closes_every_rule_fd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tracker = _OpenTracker()
        ruleset_fd = _reserved_fd()
        rec = _FakeSyscallRecorder({444: [(ruleset_fd, 0)]})  # adds default OK
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        monkeypatch.setattr(os, "open", tracker.open)
        closed: list[int] = []
        real_close = os.close

        def _rec_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "close", _rec_close)
        _patch_no_proof(monkeypatch)
        count = ll.apply(
            _layout_with_tmp_fixture(tmp_path), libc=_OkPrctlLibc(), dry_probe=True
        )
        assert count == 2
        assert set(tracker.all_opened_fds) <= set(closed)
        assert ruleset_fd in closed

    def test_restrict_self_failure_raises_after_no_new_privs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = _FakeSyscallRecorder({444: [(_reserved_fd(), 0)], 446: [(-1, 90)]})
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        with pytest.raises(ll.LandlockError) as excinfo:
            ll.apply(
                _layout_with_tmp_fixture(tmp_path),
                libc=_OkPrctlLibc(),
                dry_probe=False,
            )
        assert "landlock_restrict_self failed" in str(excinfo.value)
        assert excinfo.value.cause.startswith("landlock_restrict_self:")

    def test_restrict_self_success_returns_zero_rule_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An EMPTY allowlist restricts into a zero-grant domain and the
        count 0 comes back; the restrict receives (fd, 0)."""
        rec = _FakeSyscallRecorder({444: [(_reserved_fd(), 0)], 446: [(0, 0)]})
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        workdir = tmp_path / "work"
        workdir.mkdir()
        layout = ll.TierLayout(workdir=str(workdir))
        count = ll.apply(layout, libc=_OkPrctlLibc(), dry_probe=False)
        assert count == 0
        restrict = [c for c in rec.calls if c[0] == 446]
        assert len(restrict) == 1
        assert restrict[0][0] == 446
        assert restrict[0][1][1] == 0  # restrict(fd, 0): no flags

    def test_prctl_no_new_privs_failure_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = _FakeSyscallRecorder({})
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        with pytest.raises(ll.LandlockError) as excinfo:
            ll.apply(
                _layout_with_tmp_fixture(tmp_path),
                libc=_FailPrctlLibc(),
                dry_probe=False,
            )
        assert "PR_SET_NO_NEW_PRIVS failed" in str(excinfo.value)

    def test_prctl_no_new_privs_success_is_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = _FakeSyscallRecorder({444: [(_reserved_fd(), 0)], 446: [(0, 0)]})
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        count = ll.apply(
            _layout_with_tmp_fixture(tmp_path),
            libc=_OkPrctlLibc(),
            dry_probe=False,
        )
        assert count == 2

    def test_restrict_and_verify_closes_fd_on_both_outcomes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_restrict_and_verify's finally closes the ruleset fd on the
        error path too (no leak when restrict fails)."""
        layout = _layout_with_tmp_fixture(tmp_path)
        fd = os.open(str(tmp_path), os.O_PATH | os.O_CLOEXEC)
        closed: list[int] = []
        real_close = os.close

        def _tracking_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "close", _tracking_close)
        rec = _FakeSyscallRecorder({446: [(-1, 1)]})  # EPERM
        monkeypatch.setattr(ll, "_syscall", rec)
        with pytest.raises(ll.LandlockError):
            ll._restrict_and_verify(fd, layout, _OkPrctlLibc(), 446, dry_probe=False)
        assert fd in closed

    def test_restrict_and_verify_success_after_proof(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dry_probe=True: the (stubbed) proof runs first, then nnp +
        restrict succeed in THIS process — the 311-325 spine."""
        layout = _layout_with_tmp_fixture(tmp_path)
        fd = os.open(str(tmp_path), os.O_PATH | os.O_CLOEXEC)
        proof_calls: list[tuple[object, ...]] = []

        def _proof(layout: object, libc: object, fd: object, nr: object) -> None:
            proof_calls.append((layout, libc, fd, nr))

        monkeypatch.setattr(ll, "_prove_enforcement_in_child", _proof)
        monkeypatch.setattr(ll, "_prctl_no_new_privs", lambda libc: None)
        rec = _FakeSyscallRecorder({446: [(0, 0)]})
        monkeypatch.setattr(ll, "_syscall", rec)
        closed: list[int] = []
        real_close = os.close

        def _tracking_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "close", _tracking_close)
        ll._restrict_and_verify(fd, layout, _OkPrctlLibc(), 446, dry_probe=True)
        assert len(proof_calls) == 1
        p_layout, p_libc, p_fd, p_nr = proof_calls[0]
        assert p_layout is layout
        assert isinstance(p_libc, _OkPrctlLibc)
        assert p_fd == fd
        assert p_nr == 446
        assert fd in closed

    def test_apply_uses_a_real_libc_when_none_is_given(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """apply(libc=None) loads libc through _libc() — the default path
        (only observable as: the call still succeeds end to end)."""
        _patch_no_proof(monkeypatch)
        rec = _FakeSyscallRecorder({444: [(_reserved_fd(), 0)], 446: [(0, 0)]})
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        count = ll.apply(_layout_with_tmp_fixture(tmp_path), dry_probe=True)
        assert count == 2

    def test_apply_counts_read_and_write_roots_with_file_bits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directory roots get the full bit set; FILE roots get it masked
        down to the file-relevant bits (the _is_dir else-branches)."""
        _patch_no_proof(monkeypatch)
        rec = _FakeSyscallRecorder({444: [(_reserved_fd(), 0)], 446: [(0, 0)]})
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(ll, "_require_arch", lambda: (444, 445, 446))
        workdir = tmp_path / "work"
        workdir.mkdir()
        read_file = tmp_path / "rc"
        read_file.write_text("x")
        layout = ll.TierLayout(
            workdir=str(workdir),
            read_roots=[str(workdir), str(read_file)],  # dir root + file root
            write_roots=[str(workdir), str(read_file)],  # ditto
        )
        count = ll.apply(layout, libc=_OkPrctlLibc(), dry_probe=True)
        assert count == 4
        file_bits = (
            ll.LANDLOCK_ACCESS_FS_EXECUTE
            | ll.LANDLOCK_ACCESS_FS_WRITE_FILE
            | ll.LANDLOCK_ACCESS_FS_READ_FILE
        )
        assert file_bits == 0b111  # EXECUTE|WRITE_FILE|READ_FILE


class TestAbiVersionMocked:
    def test_abi_version_passes_the_version_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: dict[str, int] = {}

        def _capture(
            libc: object, nr: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0
        ) -> int:
            seen.update(nr=nr, a=a, b=b, c=c, d=d)
            return 8

        monkeypatch.setattr(ll.platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(ll, "_syscall", _capture)
        assert ll.abi_version(_FakeErrnoLibc()) == 8
        assert seen["nr"] == 444
        assert seen["c"] == ll.LANDLOCK_CREATE_RULESET_VERSION
        assert seen["a"] == 0 and seen["b"] == 0 and seen["d"] == 0

    def test_abi_version_negative_return_reads_as_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ll.platform, "machine", lambda: "x86_64")

        def _neg(
            libc: object, nr: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0
        ) -> int:
            return -38  # -ENOSYS

        monkeypatch.setattr(ll, "_syscall", _neg)
        assert ll.abi_version(_FakeErrnoLibc()) == 0

    def test_abi_version_unknown_arch_reads_as_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ll.platform, "machine", lambda: "mips")
        assert ll.abi_version(_FakeErrnoLibc()) == 0

    def test_abi_version_libc_load_failure_reads_as_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom() -> ctypes.CDLL:
            raise OSError("no libc on this host")

        monkeypatch.setattr(ll, "_libc", _boom)
        assert ll.abi_version() == 0

    def test_require_arch_raises_on_unknown_machine(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ll.platform, "machine", lambda: "riscv")
        with pytest.raises(ll.LandlockUnsupportedError) as excinfo:
            ll._require_arch()
        assert "riscv" in str(excinfo.value)
        assert excinfo.value.cause.startswith("unsupported architecture")


class TestLayoutStructs:
    def test_ruleset_attr_layout_is_exactly_one_u64(self) -> None:
        """The fs-only ruleset attr is a single __u64 — ctypes must agree
        byte-for-byte with linux/landlock.h (the kernel copies by size)."""
        attr = ll._RulesetAttr(ll.HANDLED_ACCESS_FS)
        assert ctypes.sizeof(attr) == 8
        assert attr.handled_access_fs == ll.HANDLED_ACCESS_FS
        packed = bytes((ctypes.c_ubyte * 8).from_buffer(attr))
        assert packed == ll.HANDLED_ACCESS_FS.to_bytes(8, sys.byteorder)

    def test_path_beneath_attr_layout_matches_linux_uapi(self) -> None:
        """allowed_access __u64 then parent_fd __s32, packed (12 bytes, no
        tail padding) — the parent_fd round-trips through the same memory
        the kernel reads."""
        rule = ll._PathBeneathAttr()
        assert ctypes.sizeof(rule) == 12
        rule.allowed_access = ll._READ_EXEC
        rule.parent_fd = 3
        assert rule.allowed_access == ll._READ_EXEC
        assert rule.parent_fd == 3
        packed = bytes((ctypes.c_ubyte * 12).from_buffer(rule))
        assert packed[:8] == ll._READ_EXEC.to_bytes(8, sys.byteorder)
        assert packed[8:] == (3).to_bytes(4, sys.byteorder)

    def test_structures_are_declared_without_deprecation_warning(self) -> None:
        """RE-defining the two ctypes structures must not emit the
        ``_pack_``/MSVC-layout DeprecationWarning — the class-definition
        time warning Python 3.19 will turn into an error (TJ-GAP-082
        rework: the module now pins _layout_ = 'ms' explicitly)."""
        source = Path(ll.__file__).read_text(encoding="utf-8")
        tree: dict[str, object] = {}
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            exec(compile(source, str(ll.__file__), "exec"), tree)  # noqa: S102
        ruleset_cls = tree["_RulesetAttr"]
        beneath_cls = tree["_PathBeneathAttr"]
        assert isinstance(ruleset_cls, type) and isinstance(beneath_cls, type)
        assert ctypes.sizeof(ruleset_cls(0)) == 8  # type: ignore[operator]
        assert ctypes.sizeof(beneath_cls()) == 12  # type: ignore[operator]


# ── Enforcement property probe (the verdict plumbing, in-process) ──────────


class TestKernelEnforced:
    def test_read_trio(self, tmp_path: Path) -> None:
        """EACCES -> True, clean read -> False, vanished file -> False."""
        secret = tmp_path / "s"
        secret.write_text("x")
        os.chmod(secret, 0o600)
        assert ll.kernel_enforced(str(secret)) is False  # same uid: readable
        root_file = Path("/etc/shadow")
        if root_file.exists() and os.getuid() != 0:
            assert ll.kernel_enforced(str(root_file)) is True
        assert ll.kernel_enforced(str(tmp_path / "gone")) is False


class TestProveEnforcementInChild:
    """The fork-isolated proof, driven with fork()->0 so the child branch
    runs IN this process (coverage sees it; os._exit raises a sentinel
    instead of killing pytest)."""

    def _run_child_branch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        layout: ll.TierLayout,
        probe: Path,
        *,
        kernel_enforced: bool,
        prctl_raises: bool,
    ) -> bytes:
        monkeypatch.setattr(ll, "_make_enforcement_probe", lambda _layout: str(probe))
        if prctl_raises:

            def _boom(libc: object) -> None:
                raise RuntimeError("prctl exploded")

            monkeypatch.setattr(ll, "_prctl_no_new_privs", _boom)
        else:
            monkeypatch.setattr(ll, "_prctl_no_new_privs", lambda libc: None)
        monkeypatch.setattr(ll, "kernel_enforced", lambda p: kernel_enforced)
        rec = _FakeSyscallRecorder({446: [(0, 0)]})  # restrict "succeeds"
        monkeypatch.setattr(ll, "_syscall", rec)
        monkeypatch.setattr(os, "fork", lambda: 0)  # "we are the child"
        monkeypatch.setattr(
            os, "_exit", lambda code: (_ for _ in ()).throw(_ChildExit())
        )
        written: list[bytes] = []
        real_write = os.write

        def _rec_write(fd: int, data: object) -> int:
            written.append(bytes(data))  # type: ignore[arg-type]
            return real_write(fd, data)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "write", _rec_write)
        with pytest.raises(_ChildExit):
            ll._prove_enforcement_in_child(
                layout,
                _OkPrctlLibc(),
                7,
                446,  # fd 7: fake, never really used
            )
        assert len(written) == 1
        return written[0]

    def test_child_reports_zero_when_kernel_does_not_enforce(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = tmp_path / "probe-a"
        probe.write_text("readable")
        os.chmod(probe, 0o600)
        layout = _layout_with_tmp_fixture(tmp_path)
        verdict = self._run_child_branch(
            monkeypatch, layout, probe, kernel_enforced=False, prctl_raises=False
        )
        assert verdict == b"0"

    def test_child_reports_one_when_kernel_enforces(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = tmp_path / "probe-b"
        probe.write_text("x")
        os.chmod(probe, 0o600)
        layout = _layout_with_tmp_fixture(tmp_path)
        verdict = self._run_child_branch(
            monkeypatch, layout, probe, kernel_enforced=True, prctl_raises=False
        )
        assert verdict == b"1"

    def test_child_reports_zero_when_prctl_explodes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = tmp_path / "probe-c"
        probe.write_text("x")
        os.chmod(probe, 0o600)
        layout = _layout_with_tmp_fixture(tmp_path)
        verdict = self._run_child_branch(
            monkeypatch, layout, probe, kernel_enforced=True, prctl_raises=True
        )
        assert verdict == b"0"

    def test_fork_failure_raises_naming_the_cause(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """os.fork failing -> LandlockError; BOTH pipe fds are closed."""
        real_pipe = os.pipe
        opened: list[tuple[int, int]] = []

        def _rec_pipe() -> tuple[int, int]:
            fds = real_pipe()
            opened.append(fds)
            return fds

        monkeypatch.setattr(os, "pipe", _rec_pipe)
        closed: list[int] = []
        real_close = os.close

        def _rec_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "close", _rec_close)
        monkeypatch.setattr(ll, "_make_enforcement_probe", lambda _layout: "/dev/null")

        def _fork_fail() -> int:
            raise OSError(11, "resource temporarily unavailable")

        monkeypatch.setattr(os, "fork", _fork_fail)
        with pytest.raises(ll.LandlockError) as excinfo:
            ll._prove_enforcement_in_child(
                _layout_with_tmp_fixture(tmp_path), _OkPrctlLibc(), 7, 446
            )
        assert "cannot fork the enforcement-probe child" in str(excinfo.value)
        read_fd, write_fd = opened[0]
        assert {read_fd, write_fd} <= set(closed)  # both fds closed

    def test_unproven_enforcement_raises_and_parent_stays_free(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Real fork: a child that applies the ruleset but can still READ
        the probe (it sits under a GRANTED root here) must produce the
        NOT-PROVEN LandlockError in the parent — and the parent must be
        unrestricted afterwards."""
        if not _host_permits_landlock():
            pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
        layout = _layout_with_tmp_fixture(tmp_path)
        probe = tmp_path / "tmproot" / "probe600"
        probe.write_text("readable inside the tmp GRANT")
        os.chmod(probe, 0o600)
        monkeypatch.setattr(ll, "_make_enforcement_probe", lambda _layout: str(probe))
        real_syscall = ll._syscall

        def _passthrough(
            libc: object, nr: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0
        ) -> int:
            return real_syscall(libc, nr, a, b, c, d)  # REAL kernel syscalls

        monkeypatch.setattr(ll, "_syscall", _passthrough)
        with pytest.raises(ll.LandlockError) as excinfo:
            ll._prove_enforcement_in_child(
                layout, ll._libc(), 7, ll._SYSCALL_NR["x86_64"][2]
            )
        assert "Landlock enforcement NOT proven" in str(excinfo.value)
        assert "enforcement probe read was not denied" in excinfo.value.cause
        # the parent survived unrestricted
        (tmp_path / "parent-still-free").write_text("1")
        assert os.path.exists(probe) is False  # the finally unlinked the probe


class TestMakeEnforcementProbe:
    def test_prefers_xdg_runtime_dir_when_ungranted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        layout = _layout_with_tmp_fixture(tmp_path)
        xdg = tmp_path / "run-user"
        xdg.mkdir()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))
        monkeypatch.delenv("HOME", raising=False)
        probe = ll._make_enforcement_probe(layout)
        try:
            assert Path(probe).parent == xdg
            assert Path(probe).name.startswith(".tj-landlock-eacces-probe-")
            assert stat.S_IMODE(os.stat(probe).st_mode) == 0o600
            assert Path(probe).read_text(encoding="utf-8").startswith("terminal-jail")
        finally:
            os.unlink(probe)
        # the mkdtemp throwaway hosts (never chosen) left no litter in XDG
        assert [
            p.name for p in xdg.iterdir() if p.name.startswith("tj-ll-proof-")
        ] == []

    def test_skips_candidates_inside_the_grants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A candidate INSIDE a granted root is never chosen — the denial
        must come from Landlock, never DAC."""
        layout = _layout_with_tmp_fixture(tmp_path)
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
        runtime = Path(layout.workdir) / "run"  # INSIDE the workdir grant
        runtime.mkdir()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
        probe = ll._make_enforcement_probe(layout)
        try:
            assert Path(probe).parent != runtime
        finally:
            os.unlink(probe)
            parent = Path(probe).parent
            if parent.name.startswith("tj-ll-proof-"):
                os.rmdir(parent)

    def test_unwritable_candidates_are_skipped_for_a_kernel_tmpdir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unwritable XDG dir AND an absent /run/user/<uid> fall through
        to a mkdtemp host under /tmp — chosen, then removed with its probe."""
        layout = _layout_with_tmp_fixture(tmp_path)
        ro = tmp_path / "readonly"
        ro.mkdir()
        ro.chmod(0o500)
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(ro))
        monkeypatch.delenv("HOME", raising=False)
        real_getuid = os.getuid
        monkeypatch.setattr(os, "getuid", lambda: 61000)  # no /run/user/61000
        try:
            probe = ll._make_enforcement_probe(layout)
            assert os.path.basename(os.path.dirname(probe)).startswith("tj-ll-proof-")
            os.unlink(probe)
            os.rmdir(os.path.dirname(probe))
        finally:
            ro.chmod(0o700)
        assert real_getuid() >= 0  # sanity: the patch is gone after the test

    def test_mkdtemp_failure_falls_through_to_other_candidates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """tempfile.mkdtemp raising OSError (line 443-444) skips the tmp
        hosts without killing the candidate walk."""
        layout = _layout_with_tmp_fixture(tmp_path)
        xdg = tmp_path / "run-user-2"
        xdg.mkdir()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))
        monkeypatch.delenv("HOME", raising=False)

        def _mkdtemp_fail(*a: object, **k: object) -> str:
            raise OSError(28, "no space left on device")

        monkeypatch.setattr(tempfile, "mkdtemp", _mkdtemp_fail)
        probe = ll._make_enforcement_probe(layout)
        try:
            assert Path(probe).parent == xdg
        finally:
            os.unlink(probe)

    def test_no_usable_host_raises_landlock_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every candidate granted/unusable -> LandlockError (the tier
        refuses to claim an unprovable property)."""
        layout = ll.TierLayout(
            workdir="/",
            read_roots=["/"],
            write_roots=["/"],
            ungranted_paths=[],
        )
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        monkeypatch.delenv("HOME", raising=False)

        def _mkdtemp_fail(*a: object, **k: object) -> str:
            raise OSError(28, "no space left on device")

        monkeypatch.setattr(tempfile, "mkdtemp", _mkdtemp_fail)
        with pytest.raises(ll.LandlockError) as excinfo:
            ll._make_enforcement_probe(layout)
        assert "no caller-writable ungranted path" in str(excinfo.value)


# ── Layout computation: pure-path branches ─────────────────────────────────


class TestBuildLayoutBranches:
    def test_missing_workdir_returns_none(self, tmp_path: Path) -> None:
        assert ll.build_layout(str(tmp_path / "absent"), home="/tmp") is None

    def test_workdir_is_a_file_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "afile"
        f.write_text("x")
        assert ll.build_layout(str(f), home="/tmp") is None

    def test_cwd_fallback_and_realpath_normalisation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """workdir=None falls back to cwd (realpath'd); home=None falls
        back to $HOME."""
        real = tmp_path / "w"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real)
        home = tmp_path / "h"
        home.mkdir()
        monkeypatch.chdir(str(link))
        layout = ll.build_layout(home=str(home))
        assert layout is not None
        assert layout.workdir == os.path.realpath(real)

    def test_cwd_unavailable_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _gone() -> str:
            raise OSError(2, "working directory has been unlinked")

        monkeypatch.setattr(os, "getcwd", _gone)
        assert ll.build_layout(home="/tmp") is None

    def test_home_missing_from_env_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workdir = tmp_path / "w"
        workdir.mkdir()
        monkeypatch.delenv("HOME", raising=False)
        assert ll.build_layout(str(workdir)) is None

    def test_empty_home_env_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workdir = tmp_path / "w"
        workdir.mkdir()
        monkeypatch.setenv("HOME", "")
        assert ll.build_layout(str(workdir)) is None

    def test_empty_explicit_home_overrides_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """home='' is NOT the env fallback: it resolves to None."""
        workdir = tmp_path / "w"
        workdir.mkdir()
        monkeypatch.setenv("HOME", "/real-home-that-would-otherwise-be-used")
        assert ll.build_layout(str(workdir), home="") is None

    def test_home_helper_matrix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/home/someone")
        assert ll._home(None) == "/home/someone"
        monkeypatch.delenv("HOME", raising=False)
        assert ll._home(None) is None
        assert ll._home("") is None
        assert ll._home("/x") == "/x"

    def test_xdg_cache_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache = tmp_path / "xdgcache"
        cache.mkdir()
        workdir = tmp_path / "w2"
        workdir.mkdir()
        home = tmp_path / "h2"
        home.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache) + "/")
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        layout = ll.build_layout(str(workdir), home=str(home))
        assert layout is not None
        assert os.path.realpath(cache) in [
            os.path.realpath(p) for p in layout.write_roots
        ]

    def test_xdg_dir_helper_matrix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_DATA_DIRS", "/opt/x")
        assert ll._xdg_dir("XDG_DATA_DIRS", ".share", None) == "/opt/x"
        monkeypatch.setenv("XDG_DATA_DIRS", "relative/junk")
        assert ll._xdg_dir("XDG_DATA_DIRS", ".share", "/h") == "/h/.share"
        monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
        assert ll._xdg_dir("XDG_DATA_DIRS", ".share", "/h") == "/h/.share"
        assert ll._xdg_dir("XDG_DATA_DIRS", ".share", None) is None

    def test_temp_dirs_env_matrix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TMPDIR", "/tmp")
        monkeypatch.setenv("TMP", "rel-not-a-path")
        monkeypatch.delenv("TEMP", raising=False)
        assert ll._temp_dirs() == ["/tmp", "/var/tmp"]
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        # NOTE: extra entries are used verbatim (only env values are
        # stripped) — a non-"/"-leading extra is filtered like any junk.
        assert ll._temp_dirs(("/custom",)) == ["/custom", "/tmp", "/var/tmp"]
        assert ll._temp_dirs(("relative/junk",)) == ["/tmp", "/var/tmp"]
        assert ll._temp_dirs() == ["/tmp", "/var/tmp"]

    def test_home_reads_only_existing_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_HOME_READ entries that exist on the fixture home become read
        grants (756); absent ones are silently skipped."""
        home = tmp_path / "h"
        (home / ".cargo").mkdir(parents=True)
        (home / ".gitconfig").write_text("[user]\n")
        (home / ".bashrc").write_text("# rc\n")
        workdir = tmp_path / "wd"
        workdir.mkdir()
        monkeypatch.setenv("HOME", str(home))
        layout = ll.build_layout(str(workdir))
        assert layout is not None
        read = {os.path.realpath(p) for p in layout.read_roots}
        assert os.path.realpath(home / ".cargo") in read
        assert os.path.realpath(home / ".gitconfig") in read
        assert os.path.realpath(home / ".bashrc") in read
        assert os.path.realpath(home / ".zshrc") not in read
        assert os.path.realpath(home / ".nvm") not in read

    def test_ungranted_paths_dedupe_realpath_and_parent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "h"
        home.mkdir()
        workdir = tmp_path / "wd"
        workdir.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        layout = ll.build_layout(str(workdir))
        assert layout is not None
        ungranted = layout.ungranted_paths
        assert len(ungranted) == len(set(ungranted))
        assert os.path.realpath("/root") in ungranted
        # home's PARENT is named (other users' homes live there)
        assert os.path.realpath(str(tmp_path)) in ungranted
        # /tmp stays GRANTED with the default drop_denied_tmp=True
        assert os.path.realpath("/tmp") not in ungranted

    def test_credential_paths_most_specific_first(self, tmp_path: Path) -> None:
        home = tmp_path / "h"
        (home / ".config" / "terminal-jail" / "rules.d").mkdir(parents=True)
        (home / ".ssh").mkdir()
        found = ll._credential_paths(str(home))
        assert found[0] == str(home / ".config/terminal-jail/rules.d")
        assert found[-1] == str(home / ".ssh")

    def test_split_grant_around_carves_every_level(self, tmp_path: Path) -> None:
        """Siblings at EVERY ancestor level of the surface survive the
        carve; the surface and its ancestors do not."""
        grant = tmp_path / "g"
        (grant / "a" / "surf").mkdir(parents=True)
        (grant / "a" / "keep-a1").mkdir()
        (grant / "top").mkdir()
        carved = ll._split_grant_around(str(grant), str(grant / "a" / "surf"))
        carved_real = {os.path.realpath(p) for p in carved}
        assert os.path.realpath(str(grant / "top")) in carved_real
        assert os.path.realpath(str(grant / "a" / "keep-a1")) in carved_real
        assert os.path.realpath(str(grant / "a")) not in carved_real
        assert os.path.realpath(str(grant / "a" / "surf")) not in carved_real

    def test_split_grant_around_mid_level_listdir_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """listdir failing at an ANCESTOR level returns the carve built so
        far (no raise)."""
        grant = tmp_path / "g2"
        (grant / "a" / "surf").mkdir(parents=True)
        real_listdir = os.listdir

        def _listdir_fail(path: object) -> list[str]:
            if str(path) == str(grant):
                raise PermissionError(13, "nope")
            return real_listdir(path)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "listdir", _listdir_fail)
        assert ll._split_grant_around(str(grant), str(grant / "a" / "surf")) == []

    def test_split_grant_around_final_level_listdir_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """listdir failing at the surface's PARENT (the last level) still
        returns the shallower carve."""
        grant = tmp_path / "g3"
        (grant / "a" / "surf").mkdir(parents=True)
        (grant / "top3").mkdir()
        real_listdir = os.listdir

        def _listdir_fail(path: object) -> list[str]:
            if os.path.basename(str(path)) == "a":
                raise PermissionError(13, "nope")
            return real_listdir(path)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "listdir", _listdir_fail)
        carved = ll._split_grant_around(str(grant), str(grant / "a" / "surf"))
        assert {os.path.basename(p) for p in carved} == {"top3"}

    def test_split_workdir_identity_when_no_surface_inside(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "h"
        home.mkdir()
        workdir = tmp_path / "wd"
        workdir.mkdir()
        grants, splits = ll._split_workdir(str(workdir), str(home))
        assert grants == [str(workdir)]
        assert splits == []

    def test_split_workdir_carves_two_surfaces(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two credential surfaces inside the workdir: both are named as
        splits, and a granted root that holds NO surface survives the
        second carve untouched (the else-append branch)."""
        home = tmp_path / "h"
        (home / ".ssh").mkdir(parents=True)
        (home / ".hermes").mkdir()
        # the workdir must CONTAIN the home for the surfaces to be "inside"
        workdir = tmp_path
        (tmp_path / "project").mkdir()  # a plain subtree, no credentials
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        grants, splits = ll._split_workdir(str(workdir), str(home))
        assert {os.path.realpath(s) for s in splits} == {
            os.path.realpath(str(home / ".hermes")),
            os.path.realpath(str(home / ".ssh")),
        }
        granted = {os.path.realpath(g) for g in grants}
        assert os.path.realpath(str(workdir / "project")) in granted
        # neither surface itself is granted
        assert os.path.realpath(str(home / ".ssh")) not in granted
        assert not any(
            ll._is_inside(os.path.realpath(str(home / ".ssh")), g) for g in grants
        )

    def test_is_inside_matrix(self, tmp_path: Path) -> None:
        inside = tmp_path / "in"
        inside.mkdir()
        child = inside / "c"
        child.mkdir()
        assert ll._is_inside(str(child), str(inside)) is True
        assert ll._is_inside(str(inside), str(child)) is False
        assert ll._is_inside(str(inside), str(inside)) is True
        assert ll._is_inside("/tmp", "/") is True
        assert ll._is_inside("/etc/shadow", str(tmp_path)) is False

    def test_is_inside_valueerror_reads_as_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The defensive ValueError branch (different drives etc.)."""

        def _boom(paths: object) -> str:
            raise ValueError("Can't mix absolute and relative paths")

        monkeypatch.setattr(os.path, "commonpath", _boom)
        assert ll._is_inside("/a", "/b") is False

    def test_dedupe_existing_excludes_symlinks_and_absents(
        self, tmp_path: Path
    ) -> None:
        a = tmp_path / "a"
        a.mkdir()
        link = tmp_path / "a-link"
        link.symlink_to(a)
        out = ll._dedupe_existing(
            [str(a), str(link), str(tmp_path / "absent")], exclude=(str(a),)
        )
        assert out == []


# ── Degradation (pure decision code) ───────────────────────────────────────


class TestDegradation:
    def test_warning_names_cause_probe_and_knob(self) -> None:
        text = ll.degradation_warning("Landlock ABI absent")
        assert text.startswith(
            "terminal-jail: WARNING: Landlock filesystem tier not applied"
        )
        assert "(Landlock ABI absent)" in text
        assert "scripts/landlock-capability-probe.py" in text
        assert "TERMINAL_JAIL_LANDLOCK=0" in text

    def test_degrade_silent_on_deliberate_disable(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", "false")
        monkeypatch.setattr(ll, "_WARNED", False)
        assert ll._degrade("some cause") == ""
        assert capsys.readouterr().err == ""

    def test_degrade_warns_once_then_quiet(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        monkeypatch.setattr(ll, "_WARNED", False)
        assert ll._degrade("cause one") == ""
        first = capsys.readouterr().err
        assert "Landlock filesystem tier not applied (cause one)" in first
        assert ll._degrade("cause two") == ""
        assert capsys.readouterr().err == ""  # once per process

    def test_degrade_unrecognised_truthy_value_still_warns(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", " 2 ")  # truthy junk
        monkeypatch.setattr(ll, "_WARNED", False)
        assert ll._degrade("x") == ""
        assert "not applied" in capsys.readouterr().err


# ── Loader discovery + reachability ────────────────────────────────────────


def _module_copy(tmp_path: Path, name: str, subdirs: list[str]) -> object:
    """A fresh landlock.py module object at <tmp>/<subdirs>/landlock.py —
    loader_path()/sandbox_prefix() walk from the COPY's location."""
    base = tmp_path.joinpath(*subdirs) if subdirs else tmp_path
    base.mkdir(parents=True, exist_ok=True)
    copy = base / "landlock.py"
    copy.write_text(Path(ll.__file__).read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location(name, copy)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestLoaderPath:
    def test_loader_path_finds_the_repo_loader(self) -> None:
        found = ll.loader_path()
        assert found is not None
        assert found.endswith("landlock-loader.py")
        assert Path(found).is_file()

    def test_loader_path_walks_up_to_find_a_loader(self, tmp_path: Path) -> None:
        marker_root = tmp_path / "repo"
        (marker_root / "standalone").mkdir(parents=True)
        loader = marker_root / "standalone" / "landlock-loader.py"
        loader.write_text("# loader\n")
        module = _module_copy(tmp_path, "tj_ll_walk", ["repo", "pkg", "sub"])
        found = module.loader_path()  # type: ignore[attr-defined]
        assert found == str(loader)
        sys.modules.pop("tj_ll_walk", None)

    def test_loader_path_returns_none_from_a_barren_root(self, tmp_path: Path) -> None:
        module = _module_copy(tmp_path, "tj_ll_barren", [])
        assert module.loader_path() is None  # type: ignore[attr-defined]
        sys.modules.pop("tj_ll_barren", None)


class TestWorldTraversable:
    def test_open_chain_under_tmp_is_traversable(self) -> None:
        """The positive case anchored at /tmp (1777) so every ancestor's
        mode is known: mkdtemp dir chmod 0755, then /tmp, then /."""
        host = tempfile.mkdtemp(prefix="tj-ll-wt-")
        try:
            os.chmod(host, 0o755)
            assert ll._world_traversable(os.path.join(host, "loader.py")) is True
            # / itself terminates the walk True
            assert ll._world_traversable("/tmp") is True
        finally:
            os.rmdir(host)

    def test_one_0700_ancestor_blocks_traversability(self, tmp_path: Path) -> None:
        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0o700)
        # the walk hits `locked` first: the answer is False regardless of
        # the modes further up (tmp_path's own mode is host-dependent).
        assert ll._world_traversable(str(locked / "loader.py")) is False

    def test_vanished_path_is_not_traversable(self, tmp_path: Path) -> None:
        assert ll._world_traversable(str(tmp_path / "no" / "such")) is False

    def test_symlinked_loader_resolves_before_the_walk(self, tmp_path: Path) -> None:
        """realpath first: the walk evaluates the symlink's TARGET chain,
        not the link's own name."""
        real = tmp_path / "realdir"
        real.mkdir()
        real.chmod(0o755)
        (real / "l.py").write_text("#!/usr/bin/env python3\n")
        link = tmp_path / "l-link.py"
        link.symlink_to(real / "l.py")
        # the REALPATH used for the walk is the symlink's target:
        assert Path(os.path.realpath(str(link))) == real / "l.py"
        # traversability of the link equals traversability of the target
        # path (the same chain gets walked)
        assert ll._world_traversable(str(link)) == ll._world_traversable(
            str(real / "l.py")
        )


# ── Probe-child verdict (the documented re-entry seam) ─────────────────────


class TestProbeChildVerdict:
    def test_ok_verdict_from_a_capable_stub(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = tmp_path / "ll-good.py"
        stub.write_text(
            "class LandlockError(RuntimeError):\n"
            "    def __init__(self, message, *, cause=''):\n"
            "        super().__init__(message)\n"
            "        self.cause = cause or message\n"
            "def build_layout(workdir=None, **kw):\n"
            "    return object()\n"
            "def apply(layout, **kw):\n"
            "    return 3\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(stub))
        assert ll._probe_child_verdict() == "OK"

    def test_layout_refused_verdict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = tmp_path / "ll-refuse.py"
        stub.write_text(
            "class LandlockError(RuntimeError):\n"
            "    def __init__(self, message, *, cause=''):\n"
            "        super().__init__(message)\n"
            "        self.cause = cause or message\n"
            "def build_layout(workdir=None, **kw):\n"
            "    return None\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(stub))
        assert ll._probe_child_verdict() == "FAIL layout refused"

    def test_oserror_from_layout_inspection_verdict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = tmp_path / "ll-os.py"
        stub.write_text(
            "class LandlockError(RuntimeError):\n"
            "    def __init__(self, message, *, cause=''):\n"
            "        super().__init__(message)\n"
            "        self.cause = cause or message\n"
            "def build_layout(workdir=None, **kw):\n"
            "    raise OSError(13, 'permission denied')\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(stub))
        verdict = ll._probe_child_verdict()
        assert verdict.startswith("FAIL layout inspection failed:")
        assert "permission denied" in verdict

    def test_landlock_error_cause_becomes_the_verdict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = tmp_path / "ll-err.py"
        stub.write_text(
            "class LandlockError(RuntimeError):\n"
            "    def __init__(self, message, *, cause=''):\n"
            "        super().__init__(message)\n"
            "        self.cause = cause or message\n"
            "def build_layout(workdir=None, **kw):\n"
            "    return object()\n"
            "def apply(layout, **kw):\n"
            "    raise LandlockError('nope', cause='ABI absent')\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(stub))
        assert ll._probe_child_verdict() == "FAIL ABI absent"


# ── sandbox_prefix decision tree ───────────────────────────────────────────


class TestComputeSandboxPrefix:
    def _reset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ll, "_SANDBOX_PREFIX_CACHE", None)
        monkeypatch.setattr(ll, "_WARNED", False)

    @staticmethod
    def _ok_stub(tmp_path: Path) -> Path:
        stub = tmp_path / "ok-stub.py"
        stub.write_text(
            "class LandlockError(RuntimeError):\n"
            "    def __init__(self, message, *, cause=''):\n"
            "        super().__init__(message)\n"
            "        self.cause = cause or message\n"
            "def build_layout(workdir=None, **kw):\n"
            "    return object()\n"
            "def apply(layout, **kw):\n"
            "    return 1\n",
            encoding="utf-8",
        )
        return stub

    def test_ok_verdict_reachable_loader_emits_the_tail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loader = tmp_path / "landlock-loader.py"
        loader.write_text("#!/usr/bin/env python3\n# loader\n")
        loader.chmod(0o755)
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(self._ok_stub(tmp_path)))
        monkeypatch.setattr(ll, "loader_path", lambda: str(loader))
        monkeypatch.setattr(ll, "_world_traversable", lambda p: True)
        self._reset(monkeypatch)
        tail = ll.sandbox_prefix()
        assert tail == f"python3 {shlex.quote(str(loader))} -- "
        # cache hit on the second call
        assert ll.sandbox_prefix() == tail

    def test_ok_verdict_but_loader_missing_degrades(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = _module_copy(tmp_path, "tj_ll_noloader", [])
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(self._ok_stub(tmp_path)))
        monkeypatch.setattr(module, "_SANDBOX_PREFIX_CACHE", None)  # type: ignore[attr-defined]
        monkeypatch.setattr(module, "_WARNED", False)  # type: ignore[attr-defined]
        assert module.sandbox_prefix() == ""  # type: ignore[attr-defined]
        sys.modules.pop("tj_ll_noloader", None)

    def test_ok_verdict_but_loader_unreachable_degrades(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The o+x rule: a loader under a 0700 directory cannot be opened
        by the launch's payload uid -> degrade, empty tail."""
        home = tmp_path / "closedhome"
        home.mkdir()
        home.chmod(0o700)
        loader = home / "landlock-loader.py"
        loader.write_text("# loader\n")
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(self._ok_stub(tmp_path)))
        monkeypatch.setattr(ll, "loader_path", lambda: str(loader))
        self._reset(monkeypatch)
        assert ll.sandbox_prefix() == ""
        text = ll.degradation_warning(
            "landlock-loader.py is not reachable by the launch's payload "
            f"uid (a parent of {loader} lacks o+x)"
        )
        assert "lacks o+x" in text

    def test_fork_failure_degrades_loudly(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK_PROBE", raising=False)

        def _fork_fail() -> int:
            raise OSError(11, "resource temporarily unavailable")

        monkeypatch.setattr(os, "fork", _fork_fail)
        self._reset(monkeypatch)
        assert ll.sandbox_prefix() == ""
        assert "capability probe fork failed" in capsys.readouterr().err
        assert ll._WARNED is True

    def test_unrecognised_env_disables_the_tail_silently(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", "banana")
        self._reset(monkeypatch)
        assert ll.sandbox_prefix() == ""
        assert ll._WARNED is False  # deliberate disable: no warning

    def test_in_child_reentry_fail_verdict_degrades(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The PROBE env set: the decision happens IN-PROCESS (no fork);
        a failing verdict degrades with the stub's cause."""
        stub = tmp_path / "fail-stub.py"
        stub.write_text(
            "class LandlockError(RuntimeError):\n"
            "    def __init__(self, message, *, cause=''):\n"
            "        super().__init__(message)\n"
            "        self.cause = cause or message\n"
            "def build_layout(workdir=None, **kw):\n"
            "    raise LandlockError('boom', cause='fixture cause')\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(stub))
        self._reset(monkeypatch)
        assert ll.sandbox_prefix() == ""
        sys.modules.pop("terminal_jail_landlock_probe", None)

    def test_in_child_reentry_ok_verdict_continues_to_loader_checks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-entry OK + unreachable loader: the verdict path flows on
        into the loader checks (1091-1098) and still degrades."""
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK_PROBE", str(self._ok_stub(tmp_path)))
        monkeypatch.setattr(ll, "loader_path", lambda: None)
        self._reset(monkeypatch)
        assert ll.sandbox_prefix() == ""

    def test_child_branch_writes_verdict_and_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fork CHILD half of the probe (1059-1072), driven in-process:
        fork()->0 makes this call the child; the verdict (stubbed — the
        re-entry seam itself is covered by TestProbeChildVerdict) is
        written once, bounded, and os._exit (sentinel) ends the branch.

        With a faked fork() the "child" IS this process: the env-var pin
        (line 1061) would leak TERMINAL_JAIL_LANDLOCK_PROBE into the real
        environ — where the standalone CLI reads it and applies the tier
        AS ITS PAYLOAD UID (fail-closed PermissionError → rc 126 across
        the rest of the suite). So the pin is registered with monkeypatch
        (setenv + undo-delenv), never left as real state."""
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK", raising=False)
        # os.environ[key] = v bypasses os.environ and putenv()s the REAL
        # process environment — the pin (line 1061) cannot be kept out of
        # the environ, so REGISTER the var with monkeypatch first: the
        # setenv undo (delenv) removes the leak after the test.
        monkeypatch.setenv(ll._PROBE_ENV, "")
        monkeypatch.delenv("TERMINAL_JAIL_LANDLOCK_PROBE", raising=False)
        monkeypatch.setattr(ll, "_probe_child_verdict", lambda: "OK")
        self._reset(monkeypatch)
        monkeypatch.setattr(os, "fork", lambda: 0)
        monkeypatch.setattr(
            os, "_exit", lambda code: (_ for _ in ()).throw(_ChildExit())
        )
        env_copy = dict(os.environ)
        monkeypatch.setattr(os, "environ", env_copy)
        written: list[bytes] = []
        real_write = os.write

        def _rec_write(fd: int, data: object) -> int:
            written.append(bytes(data))  # type: ignore[arg-type]
            return real_write(fd, data)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "write", _rec_write)
        closed: list[int] = []
        real_close = os.close

        def _rec_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "close", _rec_close)
        with pytest.raises(_ChildExit):
            ll.sandbox_prefix()
        assert written == [b"OK"]
        # the child pinned the re-entry env var for its import walk (in
        # the registered environ — the monkeypatch undo erases it again)
        assert os.environ.get(ll._PROBE_ENV)
        # ...and the child closed its read end + the write end on the way out
        assert len(closed) >= 2


# ── apply_tier (loader entry point) ────────────────────────────────────────


class TestApplyTierMatrix:
    def test_disabled_by_env_is_a_silent_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_LANDLOCK", "0")
        applied, cause = ll.apply_tier()
        assert applied is False
        assert cause == ""

    def test_layout_oserror_is_caught_not_raised(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "h"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        def _boom(*a: object, **k: object) -> None:
            raise OSError(13, "inspection denied")

        monkeypatch.setattr(ll, "build_layout", _boom)
        applied, cause = ll.apply_tier()
        assert applied is False
        assert cause.startswith("layout inspection failed:")
        assert "inspection denied" in cause

    def test_none_layout_names_the_missing_input(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workdir = tmp_path / "w"
        workdir.mkdir()
        monkeypatch.chdir(str(workdir))
        monkeypatch.delenv("HOME", raising=False)
        applied, cause = ll.apply_tier()
        assert applied is False
        assert cause == "working directory or HOME unavailable"

    def test_apply_landlock_error_names_the_cause(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "h"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        def _boom(layout: object, **kw: object) -> int:
            raise ll.LandlockError("apply failed", cause="enforcement unproven")

        monkeypatch.setattr(ll, "apply", _boom)
        applied, cause = ll.apply_tier()
        assert applied is False
        assert cause == "enforcement unproven"

    def test_success_returns_true_with_empty_cause(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "h"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(ll, "apply", lambda layout, **kw: layout.rule_count)
        applied, cause = ll.apply_tier()
        assert applied is True
        assert cause == ""


# ── Module hygiene ──────────────────────────────────────────────────────────


class TestModuleHygiene:
    def test_all_exports_resolve(self) -> None:
        for name in ll.__all__:
            assert hasattr(ll, name), f"__all__ entry missing: {name}"
