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
        monkeypatch.setattr(userns, "mapped_launch_ok", lambda flags=None: True)
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

    def test_unshare_prefix_forced_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_UID_MAP", "0")
        monkeypatch.setattr(userns, "_DECISION", None)
        prefix = userns.unshare_prefix()
        assert prefix == f"unshare {userns.LEGACY_USER_FLAGS} bash -c "

    def test_decider_prefix_matches_helper(self) -> None:
        # The decider's module-level prefix must be exactly what the helper
        # decides for this host (single source of truth, engine parity).
        assert decider_module._UNSHARE_PREFIX == userns.unshare_prefix()


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
        text[:idx]
        + 'echo "FLAGS:${UNSHARE_FLAGS}" >&2\nexit 0\n'
        + text[idx:]
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
                '# --- namespace preflight'
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
