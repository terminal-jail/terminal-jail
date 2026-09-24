"""TJ-DF-015 — real uid mapping for --user with a loud degraded fallback.

Covers:
- parity: the engine helper (plugin/terminal_jail/interruptor/userns.py)
  produces the same flag fragments the standalone wrapper uses on this host;
- the wrapper preflights the mapped launch and only promotes it when the
  probe passes (simulated with a PATH-stub unshare that passes probes);
- the legacy mapping-less path stays reachable on preflight failure and via
  TERMINAL_JAIL_UID_MAP=0|off|false, always with the loud
  `no filesystem isolation` warning;
- host-conditional integration: on a mapped-capable host a jailed process
  must be DENIED a caller-owned mode-600 read and a home write; on a
  degraded host the tests SKIP with the HOST-DEGRADED-FSISO marker (same
  philosophy as HOST-DEGRADED-PIDNS) — never a silent pass.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from terminal_jail.interruptor import decider as decider_module
from terminal_jail.interruptor import userns

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"


def _run_cli(
    cli: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(cli), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


# ── Engine helper unit tests ───────────────────────────────────────────────


class _LaunchDouble:
    """Launch runner double (DF-TERMINAL-JAIL-15 test seam).

    Lets a test shape a host that the dev box cannot be: namespace creation
    succeeding while the payload's file access is broken. Records every
    (argv, timeout) so tests can assert the probe budgets and the
    short-circuit behaviour.
    """

    def __init__(
        self,
        *,
        ns_creation_ok: bool = True,
        read_rc: int = 0,
        write_rc: int = 0,
    ) -> None:
        self.ns_creation_ok = ns_creation_ok
        self.read_rc = read_rc
        self.write_rc = write_rc
        self.calls: list[tuple[list[str], int]] = []

    def __call__(
        self, argv: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(argv), timeout))
        if argv[-1] == "true":  # namespace-creation preflight
            rc = 0 if self.ns_creation_ok else 1
            return subprocess.CompletedProcess(argv, rc, "", "")
        return subprocess.CompletedProcess(  # in-launch property payload
            argv,
            0,
            f"read_rc={self.read_rc} write_rc={self.write_rc}\n",
            "",
        )

    def properties(self) -> list[tuple[list[str], int]]:
        """The launches that ran the property payload (not the `true` probe)."""
        return [call for call in self.calls if call[0][-1] != "true"]


class TestUsernsHelper:
    def test_mapped_flags_fragments(self) -> None:
        flags = userns.mapped_user_flags()
        assert "--user" in flags
        assert "--map-users=65534:" in flags
        assert ":1" in flags
        assert "--map-groups=65534:" in flags
        assert "-S 65534" in flags
        assert "-G 65534" in flags
        assert "--pid --fork" in flags
        assert "--kill-child=SIGKILL" in flags

    def test_subid_range_start_reads_caller_entry(self) -> None:
        # This host: kara:100000:65536 in both files (may be others users).
        subuid, subgid = userns.subid_range_start()
        assert isinstance(subuid, int) and subuid > 0
        assert isinstance(subgid, int) and subgid > 0

    def test_subid_range_start_falls_back_without_entry(self) -> None:
        assert userns.subid_range_start("no-such-user-tj015") == (
            userns.DEFAULT_SUBID_START,
            userns.DEFAULT_SUBID_START,
        )

    def test_uid_map_disabled_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for value in ("0", "off", "false", "OFF", "False"):
            monkeypatch.setenv("TERMINAL_JAIL_UID_MAP", value)
            assert userns.uid_map_disabled() is True
        monkeypatch.setenv("TERMINAL_JAIL_UID_MAP", "1")
        assert userns.uid_map_disabled() is False
        monkeypatch.delenv("TERMINAL_JAIL_UID_MAP", raising=False)
        assert userns.uid_map_disabled() is False

    def test_unshare_prefix_mapped_when_probe_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # DF-TERMINAL-JAIL-15: namespace creation is no longer sufficient —
        # the mapped prefix is selected only when the file-access property
        # preflight passes as well (simulated with the runner seam).
        monkeypatch.setattr(userns, "mapped_launch_ok", lambda flags=None: True)
        monkeypatch.setattr(
            userns, "_LAUNCH_RUNNER", _LaunchDouble(read_rc=0, write_rc=0)
        )
        monkeypatch.setattr(userns, "_DECISION", None)
        monkeypatch.setattr(userns, "_DECISION", None)
        prefix = userns.unshare_prefix()
        assert prefix == f"unshare {userns.mapped_user_flags()} bash -c "

    def test_unshare_prefix_falls_back_when_probe_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(userns, "mapped_launch_ok", lambda flags=None: False)
        monkeypatch.setattr(userns, "_DECISION", None)
        prefix = userns.unshare_prefix()
        assert prefix == f"unshare {userns.LEGACY_USER_FLAGS} bash -c "

    def test_unshare_prefix_forced_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_UID_MAP", "0")
        monkeypatch.setattr(userns, "_DECISION", None)
        prefix = userns.unshare_prefix()
        assert prefix == f"unshare {userns.LEGACY_USER_FLAGS} bash -c "

    def test_decider_prefix_matches_helper(self) -> None:
        # The decider's module-level prefix must be exactly what the helper
        # decides for this host (single source of truth, engine parity).
        assert decider_module._UNSHARE_PREFIX == userns.unshare_prefix()


class TestFileAccessPreflight:
    """DF-TERMINAL-JAIL-15 — the transparent auto-sandbox launch is chosen on
    the property that matters (the payload can still read the caller's
    mode-600 files and write in the caller's cwd), never on namespace
    creation alone."""

    def test_capable_host_without_file_access_falls_back_to_legacy(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The capable-host shape: `unshare <mapped flags> true` succeeds (this
        # dev host cannot create that mapping, a capable host can), yet the
        # payload inside it is denied the caller's mode-600 file and the
        # caller's cwd — measured on this host with a root-created mapped
        # namespace (see the DF-TERMINAL-JAIL-15 evidence).
        double = _LaunchDouble(read_rc=1, write_rc=1)
        monkeypatch.setattr(userns, "_LAUNCH_RUNNER", double)
        monkeypatch.setattr(userns, "_DECISION", None)

        assert userns.mapped_launch_ok() is True
        assert userns.mapped_file_access_ok() is False

        prefix = userns.unshare_prefix()
        assert prefix == f"unshare {userns.LEGACY_USER_FLAGS} bash -c "
        assert "--map-users" not in prefix
        warning = capsys.readouterr().err
        assert warning.count("WARNING") == 1, "exactly ONE loud warning"
        assert "no filesystem isolation" in warning
        assert "TERMINAL_JAIL_UID_MAP=0" in warning
        assert "DF-TERMINAL-JAIL-15" in warning
        # The named cause is the one this host shape produced: the payload's
        # host uid is the caller's subordinate uid.
        assert f"subordinate uid {userns.subid_range_start()[0]}" in warning, warning

    def test_warning_names_the_observed_marker_not_an_assumed_cause(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A creatable mapped launch that fails the property for another reason
        # (here: a caller cwd it cannot write) must not be attributed to the
        # uid mapping — the warning quotes the marker it actually observed.
        monkeypatch.setattr(userns, "mapped_launch_ok", lambda flags=None: True)
        monkeypatch.setattr(
            userns, "_LAUNCH_RUNNER", _LaunchDouble(read_rc=0, write_rc=1)
        )
        monkeypatch.setattr(userns, "_DECISION", None)

        assert userns.unshare_prefix() == (
            f"unshare {userns.LEGACY_USER_FLAGS} bash -c "
        )
        warning = capsys.readouterr().err
        assert "read_rc=0 write_rc=1" in warning, warning
        assert "subordinate uid" not in warning, warning

    def test_warning_reports_a_missing_marker(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A launch that exits 0 without producing the marker (e.g. a payload
        # that never ran) is reported as such, never as the DAC case.
        def silent(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(userns, "mapped_launch_ok", lambda flags=None: True)
        monkeypatch.setattr(userns, "_LAUNCH_RUNNER", silent)
        monkeypatch.setattr(userns, "_DECISION", None)

        assert userns.unshare_prefix() == (
            f"unshare {userns.LEGACY_USER_FLAGS} bash -c "
        )
        assert "no marker" in capsys.readouterr().err

    def test_property_pass_selects_the_mapped_prefix(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        double = _LaunchDouble(read_rc=0, write_rc=0)
        monkeypatch.setattr(userns, "_LAUNCH_RUNNER", double)
        monkeypatch.setattr(userns, "_DECISION", None)

        assert userns.mapped_file_access_ok() is True
        assert userns.unshare_prefix() == (
            f"unshare {userns.mapped_user_flags()} bash -c "
        )
        assert capsys.readouterr().err == "", "no degradation warning on a pass"

    def test_both_property_halves_are_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Reading the caller's file is not enough, and neither is writing:
        # a launch counts as usable only when BOTH succeed.
        for read_rc, write_rc in ((1, 0), (0, 1), (1, 1)):
            monkeypatch.setattr(
                userns,
                "_LAUNCH_RUNNER",
                _LaunchDouble(read_rc=read_rc, write_rc=write_rc),
            )
            assert userns.mapped_file_access_ok() is False, (read_rc, write_rc)

    def test_probe_budgets_are_bounded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A preflight that can hang is worse than no preflight: every launch
        # carries an explicit timeout (the runner double asserts on it).
        double = _LaunchDouble()
        monkeypatch.setattr(userns, "_LAUNCH_RUNNER", double)
        assert userns.mapped_launch_ok() is True
        assert [call[1] for call in double.calls] == [userns._PROBE_TIMEOUT]
        assert userns.mapped_file_access_ok() is True
        assert [call[1] for call in double.properties()] == [userns._PROPERTY_TIMEOUT]
        assert userns._PROBE_TIMEOUT > 0 and userns._PROPERTY_TIMEOUT > 0

    def test_timeout_counts_as_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def runner(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            if argv[-1] == "true":
                return subprocess.CompletedProcess(argv, 0, "", "")
            raise subprocess.TimeoutExpired(argv, timeout)

        monkeypatch.setattr(userns, "_LAUNCH_RUNNER", runner)
        monkeypatch.setattr(userns, "_DECISION", None)
        assert userns.mapped_file_access_ok() is False
        assert userns.unshare_prefix() == (
            f"unshare {userns.LEGACY_USER_FLAGS} bash -c "
        )

    def test_launch_error_and_nonzero_exit_are_failures(self) -> None:
        assert userns.mapped_file_access_ok(runner=lambda argv, timeout: None) is False

        def failing(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 1, "", "unshare: EPERM")

        assert userns.mapped_file_access_ok(runner=failing) is False

    def test_probe_files_are_cleaned_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import tempfile

        before = {
            entry
            for entry in os.listdir(tempfile.gettempdir())
            if entry.startswith("tj-fsaccess-")
        }
        monkeypatch.setattr(userns, "_LAUNCH_RUNNER", _LaunchDouble())
        assert userns.mapped_file_access_ok() is True
        after = {
            entry
            for entry in os.listdir(tempfile.gettempdir())
            if entry.startswith("tj-fsaccess-")
        }
        assert after == before, "probe scratch dirs must not leak"

    def test_namespace_creation_failure_skips_the_property_probe(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Unchanged degraded-host behaviour: legacy prefix, no property probe
        # (no added latency), and no new warning noise.
        double = _LaunchDouble(ns_creation_ok=False)
        monkeypatch.setattr(userns, "_LAUNCH_RUNNER", double)
        monkeypatch.setattr(userns, "_DECISION", None)

        assert userns.unshare_prefix() == (
            f"unshare {userns.LEGACY_USER_FLAGS} bash -c "
        )
        assert double.properties() == []
        assert capsys.readouterr().err == ""

    def test_mapped_launch_needs_the_property_not_just_creation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Behavioural core of DF-TERMINAL-JAIL-15, on the pre-DF-15 surface.

        A host that can CREATE the mapped launch must still not get it when
        the payload cannot reach the caller's files. `raising=False` keeps the
        RED run honest: on the pre-fix module the property seam does not exist,
        the capability is never consulted, and this test fails by ASSERTION
        (mapped prefix returned) rather than by AttributeError.
        """
        monkeypatch.setattr(userns, "mapped_launch_ok", lambda flags=None: True)
        monkeypatch.setattr(
            userns, "mapped_file_access_ok", lambda *a, **k: False, raising=False
        )
        monkeypatch.setattr(userns, "_DECISION", None)

        prefix = userns.unshare_prefix()
        assert prefix == f"unshare {userns.LEGACY_USER_FLAGS} bash -c "
        assert "--map-users" not in prefix
        assert "no filesystem isolation" in capsys.readouterr().err


# ── Wrapper parity (flag fragments) ────────────────────────────────────────


def _wrapper_user_flags() -> str:
    """Extract the UNSHARE_FLAGS the wrapper builds for --user.

    Runs a COPY of the wrapper with an early exit inserted right before the
    preflight (the launch section has fully built $UNSHARE_FLAGS by then),
    so no real namespace is created. The extraction anchor is the wrapper's
    own `# --- namespace preflight` section marker.
    """
    text = CLI_SCRIPT.read_text(encoding="utf-8")
    anchor = "# --- namespace preflight"
    idx = text.index(anchor)
    instrumented = (
        text[:idx] + 'echo "FLAGS:${UNSHARE_FLAGS}" >&2\nexit 0\n' + text[idx:]
    )
    copy = PROJECT_ROOT / ".pytest_tj015_wrapper_extract"
    copy.write_text(instrumented, encoding="utf-8")
    copy.chmod(0o755)
    try:
        result = _run_cli(
            copy,
            "--user",
            "true",
            extra_env={"TERMINAL_JAIL_INTERRUPTOR_MODE": "disabled"},
        )
    finally:
        copy.unlink(missing_ok=True)
    for line in result.stderr.splitlines():
        if line.startswith("FLAGS:"):
            return line[len("FLAGS:") :].strip()
    raise AssertionError(
        f"no FLAGS line from instrumented wrapper (rc={result.returncode}, "
        f"stderr={result.stderr!r})"
    )


class TestWrapperParity:
    def test_wrapper_flags_match_engine_helper(self) -> None:
        wrapper_flags = _wrapper_user_flags()
        if os.environ.get("TERMINAL_JAIL_UID_MAP", "").lower() in ("0", "off", "false"):
            pytest.skip(
                "HOST-DEGRADED-FSISO: uid mapping disabled via TERMINAL_JAIL_UID_MAP"
            )
        if userns.mapped_launch_ok():
            expected = userns.mapped_user_flags()
        else:
            # LEGACY_USER_FLAGS already carries the leading --user (it mirrors
            # the full decider prefix flag set).
            expected = userns.LEGACY_USER_FLAGS
        assert wrapper_flags == expected, (
            f"wrapper flags {wrapper_flags!r} != engine helper flags {expected!r}"
        )

    def test_wrapper_source_carries_mapping_fragments(self) -> None:
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        # Mapped launch fragments must be constructed in the wrapper.
        assert "--map-users=${_tj_nobody_uid}:${_tj_subuid}:1" in text
        assert "--map-groups=${_tj_nobody_gid}:${_tj_subgid}:1" in text
        assert "-S ${_tj_nobody_uid} -G ${_tj_nobody_gid}" in text
        assert "TERMINAL_JAIL_FS_ISOLATION" in text
        assert "TERMINAL_JAIL_UID_MAP" in text
        assert "no filesystem isolation" in text
        # The kill-child obfuscation pattern must be intact: the literal
        # flag text never appears in the file.
        assert "--kill-child" not in text

    def test_preflight_pass_promotes_mapped_flags(self, tmp_path: Path) -> None:
        """A PASSING mapped preflight must promote the mapped launch (no
        degradation warning). On hosts where the real mapped launch still
        fails unprivileged (e.g. AppArmor), the launch itself fails after
        promotion — the assertion here is that the warning is ABSENT, i.e.
        the preflight (not a hardcoded fallback) decides."""
        stub = tmp_path / "stubbin"
        stub.mkdir()
        (stub / "unshare").write_text(
            "#!/bin/bash\n"
            'args=("$@")\n'
            'last="${args[@]: -1}"\n'
            'if [ "$last" = "true" ]; then exit 0; fi\n'
            'exec /usr/bin/unshare "${args[@]}"\n',
            encoding="utf-8",
        )
        (stub / "unshare").chmod(0o755)
        result = _run_cli(
            CLI_SCRIPT,
            "--user",
            "printenv",
            "TERMINAL_JAIL_FS_ISOLATION",
            extra_env={"PATH": f"{stub}:{os.environ.get('PATH', '')}"},
        )
        assert "no filesystem isolation" not in result.stderr, (
            "preflight-passing host must NOT warn (mapped launch should be used)"
        )
        if userns.mapped_launch_ok():
            assert result.returncode == 0
            assert result.stdout.strip() == "mapped"


# ── Wrapper behavior (degraded + forced-off paths) ─────────────────────────


class TestDegradedFallback:
    def test_degraded_host_warns_and_keeps_working(self) -> None:
        if userns.mapped_launch_ok():
            pytest.skip(
                "HOST-MAPPED-FSISO: this host supports the mapped launch — "
                "the degraded path is not reachable by default"
            )
        result = _run_cli(CLI_SCRIPT, "--user", "echo", "tj015-degraded")
        assert result.returncode == 0
        assert "tj015-degraded" in result.stdout
        assert "no filesystem isolation" in result.stderr
        # Machine-readable marker says degraded.
        marker = _run_cli(
            CLI_SCRIPT, "--user", "printenv", "TERMINAL_JAIL_FS_ISOLATION"
        )
        assert marker.stdout.strip() == "degraded"

    def test_uid_map_off_forces_legacy_with_warning(self) -> None:
        for value in ("0", "off", "false"):
            result = _run_cli(
                CLI_SCRIPT,
                "--user",
                "echo",
                f"tj015-off-{value}",
                extra_env={"TERMINAL_JAIL_UID_MAP": value},
            )
            assert result.returncode == 0, result.stderr
            assert f"tj015-off-{value}" in result.stdout
            assert "no filesystem isolation" in result.stderr
            assert "disabled by request" in result.stderr

    def test_bare_mode_never_gets_user_flags(self) -> None:
        # TJ-GAP-034 contract: bare mode has no automatic --user fallback —
        # the non---user branch keeps --mount-proc and never injects --user.
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert 'UNSHARE_FLAGS="$UNSHARE_FLAGS --mount-proc"' in text
        bare_block = text[
            text.index('UNSHARE_FLAGS="--pid --fork') : text.index(
                "# --- namespace preflight"
            )
        ]
        bare_branch = bare_block[
            bare_block.index("else") : bare_block.index("fi", bare_block.index("else"))
        ]
        assert "--user" not in bare_branch


# ── Host-conditional integration ───────────────────────────────────────────


@pytest.mark.integration
class TestFilesystemIsolation:
    def test_mapped_jail_denies_caller_files(self, tmp_path: Path) -> None:
        if os.environ.get("TERMINAL_JAIL_UID_MAP", "").lower() in (
            "0",
            "off",
            "false",
        ):
            pytest.skip(
                "HOST-DEGRADED-FSISO: uid mapping disabled via TERMINAL_JAIL_UID_MAP"
            )
        if not userns.mapped_launch_ok():
            pytest.skip(
                "HOST-DEGRADED-FSISO: host denies uid mapping inside "
                "unprivileged user namespaces (see scripts/fs-isolation-probe.py)"
            )
        secret = tmp_path / "secret600"
        secret.write_text("tj-df-015\n", encoding="utf-8")
        os.chmod(secret, 0o600)
        os.chown(secret, os.geteuid(), os.getegid())
        marker = _run_cli(
            CLI_SCRIPT, "--user", "printenv", "TERMINAL_JAIL_FS_ISOLATION"
        )
        assert marker.returncode == 0
        assert marker.stdout.strip() == "mapped"
        read_result = _run_cli(CLI_SCRIPT, "--user", "cat", str(secret))
        assert read_result.returncode != 0, (
            "mapped jail must DENY reading a caller-owned mode-600 file"
        )
        home_probe = Path.home() / f".tj015-probe-{os.getpid()}"
        try:
            write_result = _run_cli(CLI_SCRIPT, "--user", "touch", str(home_probe))
            assert write_result.returncode != 0, (
                "mapped jail must DENY creating a file in the caller's HOME"
            )
        finally:
            home_probe.unlink(missing_ok=True)


@pytest.mark.integration
class TestFileAccessPreflightLive:
    """The property preflight against this host's REAL unshare.

    The mapping-less flags DO preserve the caller's file access here, so
    varying only the property (a writable vs an unwritable cwd) shows the
    probe measures file access — not merely "unshare exists".
    """

    @staticmethod
    def _legacy_launch_works() -> bool:
        try:
            result = subprocess.run(
                ["unshare", *userns.LEGACY_USER_FLAGS.split(), "true"],
                capture_output=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    def test_property_passes_where_the_launch_preserves_access(
        self, tmp_path: Path
    ) -> None:
        if not self._legacy_launch_works():
            pytest.skip("HOST-DEGRADED-USERNS: no user namespace on this host")
        assert (
            userns.mapped_file_access_ok(
                flags=userns.LEGACY_USER_FLAGS, cwd=str(tmp_path)
            )
            is True
        ), "a launch that preserves the caller's file access must pass"
        assert list(tmp_path.iterdir()) == [], "cwd probe file must be cleaned up"

    def test_property_fails_when_the_cwd_cannot_be_written(
        self, tmp_path: Path
    ) -> None:
        if not self._legacy_launch_works():
            pytest.skip("HOST-DEGRADED-USERNS: no user namespace on this host")
        locked = tmp_path / "locked"
        locked.mkdir()
        os.chmod(locked, 0o500)
        try:
            assert (
                userns.mapped_file_access_ok(
                    flags=userns.LEGACY_USER_FLAGS, cwd=str(locked)
                )
                is False
            ), "a launch that cannot write the caller's cwd must NOT pass"
            assert list(locked.iterdir()) == []
        finally:
            os.chmod(locked, 0o700)
