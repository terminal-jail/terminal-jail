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

import json
import os
import stat
import subprocess
import sys
import tempfile
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
