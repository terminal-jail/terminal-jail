from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = PROJECT_ROOT / "install.sh"

EXPECTED_SHEBANG = "#!/usr/bin/env bash"
FAKE_BINARY = EXPECTED_SHEBANG + "\necho 'terminal-jail v0.1.0'\n"


def _shutil_which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


@pytest.fixture(scope="module")
def install_script() -> Path:
    assert INSTALL_SCRIPT.exists(), f"Installer not found: {INSTALL_SCRIPT}"
    return INSTALL_SCRIPT


def _run_install(
    script: Path,
    *,
    install_dir: str | None = None,
    extra_env: dict[str, str] | None = None,
    test_bin: str | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["HOME"] = os.environ.get("HOME", "/tmp")
    if install_dir:
        env["TERMINAL_JAIL_INSTALL_DIR"] = install_dir
    if extra_env:
        env.update(extra_env)
    if test_bin:
        env["PATH"] = test_bin

    return subprocess.run(
        ["sh", str(script)],
        capture_output=True,
        text=False,
        check=False,
        timeout=15,
        env=env,
        cwd=cwd,
    )


def _link_tools(test_bin: Path, *tools: str) -> None:
    """Symlink real tools into test_bin."""
    for tool in tools:
        real = _shutil_which(tool)
        if real:
            (test_bin / tool).symlink_to(real)


def _make_server_dir(tmp_path: Path, binary_content: str = FAKE_BINARY) -> Path:
    """Create a fake 'server' directory with terminal-jail and sha256 file."""
    server = tmp_path / "fake-server"
    server.mkdir(exist_ok=True)
    (server / "terminal-jail").write_text(binary_content)
    result = subprocess.run(
        ["sha256sum", str(server / "terminal-jail")],
        capture_output=True,
        text=True,
        check=False,
    )
    (server / "terminal-jail.sha256").write_text(result.stdout)
    return server


def _make_mock_curl(test_bin: Path, server_dir: Path) -> None:
    """Create a mock curl that copies from server_dir instead of downloading.

    Uses bash because the fallback parameter expansion needs it.
    """
    curl = test_bin / "curl"
    curl.write_text(
        "#!/bin/bash\n"
        "# Mock curl: copies from fake-server instead of real download\n"
        "# install.sh calls: curl -fsSL URL -o OUTFILE\n"
        'url="$2"\n'
        'outfile="$4"\n'
        f"srcdir='{server_dir}'\n"
        "# Extract filename from URL path\n"
        'filename=$(basename "$url")\n'
        'cp "$srcdir/$filename" "$outfile"\n'
    )
    curl.chmod(0o755)


# ── Basic behaviour ────────────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_installer_exists_and_is_executable(install_script: Path) -> None:
    assert install_script.exists()
    st = install_script.stat()
    assert st.st_mode & stat.S_IXUSR, "install.sh should be executable"


@pytest.mark.standalone_cli
def test_installer_syntax(install_script: Path) -> None:
    result = subprocess.run(
        ["sh", "-n", str(install_script)], capture_output=True, check=False
    )
    assert result.returncode == 0, f"Syntax error: {result.stderr.decode()}"


# ── Error: no HOME ─────────────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_no_home(install_script: Path) -> None:
    result = _run_install(install_script, extra_env={"HOME": ""})
    assert result.returncode == 1
    stderr = result.stderr.decode("utf-8")
    assert "HOME is not set" in stderr


# ── Error: non-Linux OS ────────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_non_linux_os(install_script: Path, tmp_path: Path) -> None:
    test_bin = tmp_path / "testbin"
    test_bin.mkdir(exist_ok=True)
    _link_tools(test_bin, "bash", "sh")

    fake_uname = test_bin / "uname"
    fake_uname.write_text("#!/bin/sh\necho Darwin\n")
    fake_uname.chmod(0o755)

    result = _run_install(install_script, test_bin=str(test_bin))
    assert result.returncode == 1
    stderr = result.stderr.decode("utf-8")
    assert "requires Linux" in stderr


# ── Error: no downloader ───────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_no_downloader(install_script: Path, tmp_path: Path) -> None:
    test_bin = tmp_path / "testbin"
    test_bin.mkdir(exist_ok=True)
    _link_tools(test_bin, "bash", "sh", "uname")

    result = _run_install(
        install_script,
        test_bin=str(test_bin),
        install_dir=str(tmp_path / "install"),
        extra_env={"TERMINAL_JAIL_USE_RELEASE": "1"},
    )
    assert result.returncode == 1
    stderr = result.stderr.decode("utf-8")
    assert "curl or wget" in stderr


# ── Error: no checksum tool ────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_no_checksum_tool(install_script: Path, tmp_path: Path) -> None:
    test_bin = tmp_path / "testbin"
    test_bin.mkdir(exist_ok=True)
    _link_tools(test_bin, "bash", "sh", "uname", "curl")

    result = _run_install(
        install_script,
        test_bin=str(test_bin),
        install_dir=str(tmp_path / "install"),
        extra_env={"TERMINAL_JAIL_USE_RELEASE": "1"},
    )
    assert result.returncode == 1
    stderr = result.stderr.decode("utf-8")
    assert "sha256sum or shasum" in stderr


# ── Installation with mocked downloads ────────────────────────────────────


def _setup_full_testbin(tmp_path: Path, server_dir: Path) -> Path:
    """Create test_bin with all needed tools + mock curl."""
    test_bin = tmp_path / "testbin"
    test_bin.mkdir(exist_ok=True)
    _link_tools(
        test_bin,
        "sh",
        "bash",
        "uname",
        "unshare",
        "head",
        "awk",
        "mkdir",
        "mv",
        "chmod",
        "cat",
        "grep",
        "rm",
        "cp",
        "sha256sum",
        "basename",
        "dirname",
    )
    _make_mock_curl(test_bin, server_dir)
    return test_bin


@pytest.mark.standalone_cli
def test_successful_install(install_script: Path, tmp_path: Path) -> None:
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir()
    server_dir = _make_server_dir(tmp_path)
    test_bin = _setup_full_testbin(tmp_path, server_dir)

    result = subprocess.run(
        ["sh", str(install_script)],
        capture_output=True,
        text=False,
        check=False,
        timeout=15,
        env={
            **os.environ,
            "HOME": str(tmp_path),
            "PATH": str(test_bin),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_BASE_URL": f"file://{server_dir}",
            "TERMINAL_JAIL_USE_RELEASE": "1",
        },
    )

    stdout = result.stdout.decode("utf-8")
    stderr = result.stderr.decode("utf-8")
    assert result.returncode == 0, (
        f"Install failed (rc={result.returncode}): stderr={stderr}"
    )
    assert "installed to" in stdout
    assert "checksum OK" in stdout
    assert "done." in stdout

    installed = install_dir / "terminal-jail"
    assert installed.exists(), f"Binary not installed at {installed}"
    assert os.access(installed, os.X_OK), "Installed binary not executable"


@pytest.mark.standalone_cli
def test_bad_shebang_rejected(install_script: Path, tmp_path: Path) -> None:
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir()
    server_dir = _make_server_dir(tmp_path, binary_content="#!/bin/false\necho bad\n")
    test_bin = _setup_full_testbin(tmp_path, server_dir)

    result = subprocess.run(
        ["sh", str(install_script)],
        capture_output=True,
        text=False,
        check=False,
        timeout=15,
        env={
            **os.environ,
            "HOME": str(tmp_path),
            "PATH": str(test_bin),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_BASE_URL": f"file://{server_dir}",
            "TERMINAL_JAIL_USE_RELEASE": "1",
        },
    )

    assert result.returncode == 1
    stderr = result.stderr.decode("utf-8")
    assert "bad shebang" in stderr or "does not look like" in stderr


@pytest.mark.standalone_cli
def test_checksum_fail(install_script: Path, tmp_path: Path) -> None:
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir()
    server_dir = _make_server_dir(tmp_path)
    test_bin = _setup_full_testbin(tmp_path, server_dir)

    # Corrupt the checksum file
    (server_dir / "terminal-jail.sha256").write_text(
        "0000000000000000000000000000000000000000000000000000000000000000  terminal-jail\n"
    )

    result = subprocess.run(
        ["sh", str(install_script)],
        capture_output=True,
        text=False,
        check=False,
        timeout=15,
        env={
            **os.environ,
            "HOME": str(tmp_path),
            "PATH": str(test_bin),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_BASE_URL": f"file://{server_dir}",
            "TERMINAL_JAIL_USE_RELEASE": "1",
        },
    )

    assert result.returncode == 1
    stderr = result.stderr.decode("utf-8")
    assert "checksum verification FAILED" in stderr


@pytest.mark.standalone_cli
def test_creates_install_dir(install_script: Path, tmp_path: Path) -> None:
    install_dir = tmp_path / "nested" / "install-dir"
    server_dir = _make_server_dir(tmp_path)
    test_bin = _setup_full_testbin(tmp_path, server_dir)

    result = subprocess.run(
        ["sh", str(install_script)],
        capture_output=True,
        text=False,
        check=False,
        timeout=15,
        env={
            **os.environ,
            "HOME": str(tmp_path),
            "PATH": str(test_bin),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_BASE_URL": f"file://{server_dir}",
            "TERMINAL_JAIL_USE_RELEASE": "1",
        },
    )

    assert result.returncode == 0
    assert install_dir.is_dir(), f"Install dir not created: {install_dir}"
    assert (install_dir / "terminal-jail").exists()


@pytest.mark.standalone_cli
def test_tmp_files_cleaned_after_install(install_script: Path, tmp_path: Path) -> None:
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir()
    server_dir = _make_server_dir(tmp_path)
    test_bin = _setup_full_testbin(tmp_path, server_dir)

    result = subprocess.run(
        ["sh", str(install_script)],
        capture_output=True,
        text=False,
        check=False,
        timeout=15,
        env={
            **os.environ,
            "HOME": str(tmp_path),
            "PATH": str(test_bin),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_BASE_URL": f"file://{server_dir}",
            "TERMINAL_JAIL_USE_RELEASE": "1",
        },
    )

    assert result.returncode == 0
    temps = list(install_dir.glob(".terminal-jail.*"))
    assert len(temps) == 0, f"Temp files left behind: {temps}"


# ── TJ-GAP-023: release mode requires explicit opt-in ──────────────────────


@pytest.mark.standalone_cli
def test_release_mode_requires_opt_in(install_script: Path, tmp_path: Path) -> None:
    """Absolute-path invocation (curl | sh equivalent) without
    TERMINAL_JAIL_USE_RELEASE=1 must refuse instead of hitting the dead
    release URL."""
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir()
    server_dir = _make_server_dir(tmp_path)
    test_bin = _setup_full_testbin(tmp_path, server_dir)

    result = subprocess.run(
        ["sh", str(install_script)],
        capture_output=True,
        text=False,
        check=False,
        timeout=15,
        env={
            **os.environ,
            "HOME": str(tmp_path),
            "PATH": str(test_bin),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_BASE_URL": f"file://{server_dir}",
        },
    )

    assert result.returncode == 1
    stderr = result.stderr.decode("utf-8")
    assert "release mode is not enabled" in stderr
    assert not (install_dir / "terminal-jail").exists()


# ── TJ-GAP-021: local install ships the bridge + seccomp loader ────────────


@pytest.mark.standalone_cli
def test_local_install_ships_lib_tree(install_script: Path, tmp_path: Path) -> None:
    """./install.sh from a checkout must install the plugin bridge tree and
    seccomp loader next to the binary (fail-closed layout)."""
    install_dir = tmp_path / "bin"
    install_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
        },
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    lib = tmp_path / "lib" / "terminal-jail"
    bridge = lib / "plugin" / "terminal_jail" / "interruptor_bridge.py"
    seccomp = lib / "seccomp-loader.py"
    assert bridge.exists(), f"bridge not shipped: {bridge}"
    assert seccomp.exists(), f"seccomp loader not shipped: {seccomp}"
    assert (lib / "plugin" / "terminal_jail" / "rules" / "00-builtins.yaml").exists()
    assert (install_dir / "terminal-jail").exists()


@pytest.mark.standalone_cli
def test_local_install_ships_default_rules_to_user_rules_dir(
    install_script: Path, tmp_path: Path
) -> None:
    """TJ-GAP-033: local-mode install must ship the default rules file to the
    selected rules target so the engine actually loads it (the plugin-tree
    copy is not read by RuleLoader).

    DF-TERMINAL-JAIL-8: this test previously asserted the rules landed under
    HOME/.config even for a scratch TERMINAL_JAIL_INSTALL_DIR — an
    out-of-scope write. It now opts in explicitly via TERMINAL_JAIL_RULES_DIR
    (the explicit scope always wins); the derived prefix-scope behavior is
    covered by test_prefix_install_does_not_touch_home_rules.
    """
    install_dir = tmp_path / "bin"
    install_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    rules_dir = tmp_path / "config" / "terminal-jail" / "rules.d"

    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_RULES_DIR": str(rules_dir),
        },
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    shipped = rules_dir / "00-builtins.yaml"
    assert shipped.exists(), f"default rules not installed to rules dir: {shipped}"
    assert "installed default rules" in result.stdout.decode("utf-8", "replace")


@pytest.mark.standalone_cli
def test_local_install_backs_up_customized_user_rules(
    install_script: Path, tmp_path: Path
) -> None:
    """DF-TERMINAL-JAIL-3: the user rules file is deliberate user-editable
    config (same-id override), so a re-install over a customized copy must
    preserve the old content in a sibling .bak-<utc> file and say so —
    never silently clobber it.

    DF-TERMINAL-JAIL-8: the test now seeds the dir the resolution targets via
    an explicit TERMINAL_JAIL_RULES_DIR; the backup semantics are unchanged.
    """
    install_dir = tmp_path / "bin"
    install_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    rules_dir = home / ".config" / "terminal-jail" / "rules.d"
    rules_dir.mkdir(parents=True)
    installed = rules_dir / "00-builtins.yaml"
    customized = "# user edit\nrules: []\n"
    installed.write_text(customized, encoding="utf-8")

    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_RULES_DIR": str(rules_dir),
        },
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    output = (result.stdout + result.stderr).decode("utf-8", "replace")

    # (c) the shipped default replaced the customized file...
    assert "builtin-rm-rf-root" in installed.read_text(encoding="utf-8")
    # (d) ...and exactly the customized content survives in a sibling backup.
    backups = sorted(rules_dir.glob("00-builtins.yaml.bak-*"))
    assert len(backups) == 1, f"expected 1 backup, found {[b.name for b in backups]}"
    assert backups[0].read_text(encoding="utf-8") == customized
    # (e) the installer names the backup path.
    assert str(backups[0]) in output, output


@pytest.mark.standalone_cli
def test_prefix_install_does_not_touch_home_rules(
    install_script: Path, tmp_path: Path
) -> None:
    """DF-TERMINAL-JAIL-8 (the regression): a scratch/custom-prefix install
    (TERMINAL_JAIL_INSTALL_DIR outside $HOME/.local/bin) must never write the
    live user config — the seeded HOME/.config/terminal-jail/rules.d/
    00-builtins.yaml stays byte-identical, no .bak-* appears beside it, and
    the default rules land under <prefix>/config/terminal-jail/rules.d."""
    install_dir = tmp_path / "bin"
    install_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    home_rules_dir = home / ".config" / "terminal-jail" / "rules.d"
    home_rules_dir.mkdir(parents=True)
    home_rules = home_rules_dir / "00-builtins.yaml"
    customized = "# user edit (DF-TERMINAL-JAIL-8)\nrules: []\n"
    home_rules.write_text(customized, encoding="utf-8")

    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
        },
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    output = (result.stdout + result.stderr).decode("utf-8", "replace")

    # (a) the live HOME rules file is byte-identical to the seeded content.
    assert home_rules.read_text(encoding="utf-8") == customized
    # (b) no backup appeared in the live dir (nothing was overwritten there).
    backups = list(home_rules_dir.glob("00-builtins.yaml.bak-*"))
    assert backups == [], f"unexpected backups in live dir: {[b.name for b in backups]}"
    # (c) the prefix-scoped config dir got the shipped default rules.
    prefix_rules = (
        tmp_path / "config" / "terminal-jail" / "rules.d" / "00-builtins.yaml"
    )
    assert prefix_rules.exists(), f"default rules not installed to prefix: {prefix_rules}"
    assert "builtin-rm-rf-root" in prefix_rules.read_text(encoding="utf-8")
    # (d) the installer names the prefix target and warns honestly that the
    # engine will not read it.
    assert str(prefix_rules) in output, output
    assert (
        "non-default install prefix" in output
    ), "prefix-scope WARNING line missing"
    assert "/etc/terminal-jail/rules.d" in output


@pytest.mark.standalone_cli
def test_explicit_rules_dir_wins_over_install_scope(
    install_script: Path, tmp_path: Path
) -> None:
    """DF-TERMINAL-JAIL-8: an explicit TERMINAL_JAIL_RULES_DIR is used
    verbatim for a scratch install (any path allowed), and nothing is written
    under HOME/.config/terminal-jail."""
    install_dir = tmp_path / "bin"
    install_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    custom_rules_dir = tmp_path / "custom-rules"

    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_RULES_DIR": str(custom_rules_dir),
        },
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    output = result.stdout.decode("utf-8", "replace")

    explicit_rules = custom_rules_dir / "00-builtins.yaml"
    assert explicit_rules.exists(), f"rules not installed to explicit dir: {explicit_rules}"
    assert str(explicit_rules) in output
    # No prefix-scope warning for an explicit choice, and no HOME config write.
    assert "non-default install prefix" not in output
    assert not (home / ".config" / "terminal-jail").exists()


@pytest.mark.standalone_cli
def test_default_install_dir_keeps_live_rules_target(
    install_script: Path, tmp_path: Path
) -> None:
    """DF-TERMINAL-JAIL-8: the default install dir ($HOME/.local/bin) keeps
    today's live behavior — rules land in
    $HOME/.config/terminal-jail/rules.d/00-builtins.yaml, with no prefix
    warning."""
    install_dir = tmp_path / "home" / ".local" / "bin"
    home = tmp_path / "home"
    home.mkdir()

    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
        },
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    output = result.stdout.decode("utf-8", "replace")

    live_rules = home / ".config" / "terminal-jail" / "rules.d" / "00-builtins.yaml"
    assert live_rules.exists(), f"default rules not installed to live dir: {live_rules}"
    assert str(live_rules) in output
    assert "non-default install prefix" not in output


@pytest.mark.standalone_cli
def test_installed_binary_blocks_with_shipped_bridge(
    install_script: Path, tmp_path: Path
) -> None:
    """The installed binary (invoked via PATH, bare name) must find the
    shipped bridge and BLOCK curl|sh with rc=126 — no fail-open warning."""
    install_dir = tmp_path / "bin"
    install_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
        },
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")

    run = subprocess.run(
        ["bash", "-c", "cd / && terminal-jail 'curl -s http://x | sh'"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": f"{install_dir}:{os.environ.get('PATH', '')}",
        },
    )
    stdout = run.stdout.decode("utf-8", "replace")
    stderr = run.stderr.decode("utf-8", "replace")
    assert run.returncode == 126, f"rc={run.returncode} stderr={stderr}"
    assert "COMMAND BLOCKED" in stderr
    assert "builtin-curl-pipe-shell" in stderr
    assert "running without firewall" not in stdout + stderr


@pytest.mark.standalone_cli
def test_bare_wrapper_fails_closed_without_bridge(
    install_script: Path, tmp_path: Path
) -> None:
    """A wrapper copied alone (broken install) must FAIL CLOSED in enforce
    mode: rc=126 + COMMAND BLOCKED box, no execution, no fail-open warning."""
    bare = tmp_path / "bare"
    bare.mkdir()
    wrapper = PROJECT_ROOT / "standalone" / "terminal-jail"
    (bare / "terminal-jail").write_bytes(wrapper.read_bytes())
    (bare / "terminal-jail").chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()

    run = subprocess.run(
        ["bash", "-c", "cd / && terminal-jail 'echo hi'"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": f"{bare}:{os.environ.get('PATH', '')}",
            # Deterministic bridge-absence: an explicit TERMINAL_JAIL_BRIDGE
            # pointing at a missing file is a hard failure in _find_bridge().
            # Without this, the wrapper's python-module fallback finds the
            # bridge whenever terminal-jail is pip-installed in the runner's
            # python (e.g. `uv sync --dev && uv run pytest`), leaking the
            # ambient environment into the broken-install simulation.
            "TERMINAL_JAIL_BRIDGE": str(tmp_path / "no-bridge-here"),
        },
    )
    stdout = run.stdout.decode("utf-8", "replace")
    stderr = run.stderr.decode("utf-8", "replace")
    assert run.returncode == 126, f"rc={run.returncode} stderr={stderr}"
    assert "COMMAND BLOCKED" in stderr
    assert "interruptor-bridge-unavailable" in stderr
    assert "hi" not in stdout  # command never executed
    assert "running without firewall" not in stdout + stderr


@pytest.mark.standalone_cli
def test_bare_wrapper_warn_mode_passes(install_script: Path, tmp_path: Path) -> None:
    """Warn mode keeps the explicit opt-out: warning on stderr, command runs."""
    bare = tmp_path / "bare"
    bare.mkdir()
    wrapper = PROJECT_ROOT / "standalone" / "terminal-jail"
    (bare / "terminal-jail").write_bytes(wrapper.read_bytes())
    (bare / "terminal-jail").chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()

    run = subprocess.run(
        ["bash", "-c", "cd / && terminal-jail 'echo hi'"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": f"{bare}:{os.environ.get('PATH', '')}",
            "TERMINAL_JAIL_INTERRUPTOR_MODE": "warn",
            # Same deterministic bridge-absence as the enforce-mode test above.
            "TERMINAL_JAIL_BRIDGE": str(tmp_path / "no-bridge-here"),
        },
    )
    stderr = run.stderr.decode("utf-8", "replace")
    assert "running without firewall" in stderr


# ── TJ-DF-002: seccomp loader resolves plugin dir in installed layout ────────


def _run_installed_loader(loader: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run the seccomp loader with TERMINAL_JAIL_SECCOMP=1 (as the wrapper
    does for --seccomp) and a clean sys.path so only the loader's own
    _setup_path() can make terminal_jail importable."""
    env = {
        **os.environ,
        "TERMINAL_JAIL_SECCOMP": "1",
        "PYTHONPATH": "",
    }
    return subprocess.run(
        [sys.executable, str(loader), *args],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        env=env,
    )


@pytest.mark.standalone_cli
def test_bare_wrapper_unshare_failure_exits_2(
    install_script: Path, tmp_path: Path
) -> None:
    """TJ-GAP-034: namespace-creation failure must exit 2 with a message
    (README "Graceful Degradation" contract), not leak raw unshare rc=1.
    Simulated with a fake unshare in PATH that fails — warn mode + missing
    bridge so the wrapper reaches the launch section.

    TJ-GAP-054: the failure is pinned to the unshare backend explicitly. Under
    the default `auto` selector a present bubblewrap legitimately takes over
    and runs the command, so this test names the backend whose failure
    contract it asserts; the auto selector's own degradation paths (bwrap
    missing / bwrap probe failing) live in plugin/test_backend_selection.py.
    """
    bare = tmp_path / "bare"
    bare.mkdir()
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    wrapper = PROJECT_ROOT / "standalone" / "terminal-jail"
    (bare / "terminal-jail").write_bytes(wrapper.read_bytes())
    (bare / "terminal-jail").chmod(0o755)
    fake_unshare = fakebin / "unshare"
    fake_unshare.write_text("#!/bin/sh\nexit 1\n")
    fake_unshare.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()

    run = subprocess.run(
        ["bash", "-c", "cd / && terminal-jail 'echo hi'"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": f"{bare}:{fakebin}:{os.environ.get('PATH', '')}",
            # Deterministic bridge-absence (see test_bare_wrapper_* above).
            "TERMINAL_JAIL_BRIDGE": str(tmp_path / "no-bridge-here"),
            "TERMINAL_JAIL_INTERRUPTOR_MODE": "warn",
            # TJ-GAP-054: pin the backend this test exercises (see docstring).
            "TERMINAL_JAIL_JAIL_BACKEND": "unshare",
        },
    )
    stdout = run.stdout.decode("utf-8", "replace")
    stderr = run.stderr.decode("utf-8", "replace")
    assert run.returncode == 2, f"rc={run.returncode} stderr={stderr}"
    assert "namespace creation failed" in stderr
    assert "hi" not in stdout  # command never executed


@pytest.mark.standalone_cli
def test_installed_seccomp_loader_imports_plugin_and_runs_command(
    install_script: Path, tmp_path: Path
) -> None:
    """TJ-DF-002: the loader must resolve the plugin tree in the EXACT layout
    install.sh ships (loader at <lib>/terminal-jail/, plugin package at
    <lib>/terminal-jail/plugin/terminal_jail/) — no ModuleNotFoundError, and
    the wrapped command must execute."""
    install_dir = tmp_path / "bin"
    install_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
        },
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")

    loader = tmp_path / "lib" / "terminal-jail" / "seccomp-loader.py"
    assert loader.exists(), f"installed loader not found: {loader}"
    assert (
        tmp_path / "lib" / "terminal-jail" / "plugin" / "terminal_jail" / "seccomp.py"
    ).exists()

    run = _run_installed_loader(loader, "echo", "tj-df-002-ok")
    stdout = run.stdout.decode("utf-8", "replace")
    stderr = run.stderr.decode("utf-8", "replace")
    combined = stdout + stderr
    assert run.returncode == 0, f"rc={run.returncode} stderr={stderr}"
    assert "ModuleNotFoundError" not in combined
    assert "No module named 'terminal_jail'" not in combined
    assert "tj-df-002-ok" in stdout, f"command output missing: stdout={stdout!r}"


@pytest.mark.standalone_cli
def test_repo_layout_seccomp_loader_imports_plugin_and_runs_command(
    tmp_path: Path,
) -> None:
    """TJ-DF-002: the loader must keep resolving the plugin tree in the REPO
    layout (loader at standalone/, plugin package at plugin/terminal_jail/)."""
    loader = PROJECT_ROOT / "standalone" / "seccomp-loader.py"
    assert loader.exists()

    run = _run_installed_loader(loader, "echo", "tj-df-002-repo-ok")
    stdout = run.stdout.decode("utf-8", "replace")
    stderr = run.stderr.decode("utf-8", "replace")
    combined = stdout + stderr
    assert run.returncode == 0, f"rc={run.returncode} stderr={stderr}"
    assert "ModuleNotFoundError" not in combined
    assert "No module named 'terminal_jail'" not in combined
    assert "tj-df-002-repo-ok" in stdout, f"command output missing: stdout={stdout!r}"


# ── TJ-GAP-055: bubblewrap is an OPTIONAL external dependency ────────────────
#
# Contract (README *Bubblewrap backend*, specs/cli.md §4 + §8) and spec row
# specs/cli.md §9 CLI-26: bubblewrap is an optional distro package the CLI
# resolves from PATH at run time, never vendored by this repository — so
# install.sh may ADVISE about it but must not download, build, package-install,
# or vendor it, and a missing bwrap must never fail an install (util-linux
# unshare remains the fallback backend).
#
# These cases run the installer against a curated PATH (real coreutils, no
# host bwrap), so they are deterministic whether or not the host has
# bubblewrap installed, need no network, and never touch the real HOME.

# Tools the LOCAL-mode install path invokes (cd/pwd/command/printf are shell
# builtins). unshare is deliberately NOT linked: its absence is what proves the
# required-tool WARNING and the optional-bwrap NOTE are different contracts.
_INSTALL_TOOLS = (
    "awk",
    "bash",
    "cat",
    "chmod",
    "cmp",
    "cp",
    "date",
    "dirname",
    "grep",
    "head",
    "mkdir",
    "mv",
    "rm",
    "sh",
    "uname",
)

# Commands that would mean install.sh itself downloads, builds, or installs
# bubblewrap. Only a command POSITION counts: the advisory legitimately names
# "apt install bubblewrap" / "dnf install bubblewrap" as advice to the user.
_FORBIDDEN_AT_COMMAND_POSITION_RE = re.compile(
    r"(?:^|[;&|]|\$\(|``|\()\s*"
    r"(curl|wget|git|tar|make|gcc|g\+\+|cc|cp|mv|dd|"
    r"apt|apt-get|dnf|yum|apk|pacman|pip|pip3|uv|npm|yarn|unzip)\b"
)

# Extensions that would betray vendored source or a redistributed package.
_VENDORED_SUFFIXES = (
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".o",
    ".a",
    ".deb",
    ".rpm",
    ".tar",
    ".gz",
    ".xz",
    ".zst",
    ".patch",
)


def _curated_install_bin(tmp_path: Path, *, bwrap: bool) -> Path:
    """Curated installer PATH: real coreutils, host bwrap always excluded."""
    bindir = tmp_path / ("toolbin-present" if bwrap else "toolbin-absent")
    bindir.mkdir(exist_ok=True)
    _link_tools(bindir, *_INSTALL_TOOLS)
    missing = sorted(t for t in _INSTALL_TOOLS if not (bindir / t).exists())
    assert not missing, f"host lacks tools the curated PATH needs: {missing}"
    if bwrap:
        stub = bindir / "bwrap"
        stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)
    return bindir


def _run_local_install(
    tmp_path: Path, bindir: Path
) -> tuple[subprocess.CompletedProcess[bytes], Path]:
    install_dir = tmp_path / "bin"
    install_dir.mkdir(exist_ok=True)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    result = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=20,
        cwd=str(PROJECT_ROOT),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "PATH": str(bindir),
        },
    )
    return result, install_dir


@pytest.mark.standalone_cli
def test_installer_bwrap_note_is_advisory_and_install_still_succeeds(
    tmp_path: Path,
) -> None:
    """TJ-GAP-055: with no bubblewrap on PATH the installer prints an advisory
    NOTE (distro package, unshare fallback, no-vendoring boundary) and still
    exits 0 with the binary installed — bwrap is never a preflight error."""
    bindir = _curated_install_bin(tmp_path, bwrap=False)
    result, install_dir = _run_local_install(tmp_path, bindir)
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    assert "optional bubblewrap (bwrap) not found" in out, out
    assert "apt install bubblewrap" in out, out
    assert "dnf install bubblewrap" in out, out
    assert "unshare backend" in out, out
    assert "never downloads, builds, or redistributes it" in out, out
    # Contrast: the REQUIRED tool is warned about as a warning; bubblewrap is
    # not — the optional dependency must never be phrased as a requirement.
    assert "unshare (util-linux) is required" in out, out
    assert "bubblewrap (bwrap) is required" not in out, out
    # ...and the install completed anyway.
    installed = install_dir / "terminal-jail"
    assert installed.exists(), out
    assert installed.stat().st_mode & stat.S_IXUSR, out
    assert "terminal-jail installer: done." in out, out


@pytest.mark.standalone_cli
def test_installer_is_silent_about_bwrap_when_it_is_present(tmp_path: Path) -> None:
    """TJ-GAP-055: the note is real detection, not an unconditional banner."""
    bindir = _curated_install_bin(tmp_path, bwrap=True)
    result, install_dir = _run_local_install(tmp_path, bindir)
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    assert "bubblewrap" not in out, out
    assert (install_dir / "terminal-jail").exists(), out


@pytest.mark.standalone_cli
def test_installer_writes_no_bubblewrap_artifact(tmp_path: Path) -> None:
    """TJ-GAP-055: a local install must deposit no bubblewrap artifact — no
    binary named bwrap/bubblewrap and no vendored source or redistributed
    package anywhere under the install scope."""
    bindir = _curated_install_bin(tmp_path, bwrap=False)
    result, install_dir = _run_local_install(tmp_path, bindir)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(
        "utf-8", "replace"
    )

    scopes = [install_dir, tmp_path / "lib", tmp_path / "home"]
    files = [p for scope in scopes if scope.exists() for p in scope.rglob("*")]

    named = [str(p) for p in files if "bwrap" in p.name.lower()]
    assert named == [], f"bubblewrap artifact written by the installer: {named}"

    vendored = [
        str(p)
        for p in files
        if p.is_file() and p.suffix.lower() in _VENDORED_SUFFIXES
    ]
    assert vendored == [], f"vendored source/package deposited: {vendored}"


@pytest.mark.standalone_cli
def test_install_sh_never_downloads_or_vendors_bubblewrap(
    install_script: Path,
) -> None:
    """TJ-GAP-055 source invariant: every bwrap mention in install.sh is advice.
    No line that names bubblewrap may run a downloader, a build tool, a package
    manager, or a file copy, and no such line may gate an exit — the distro
    package is the only installation path, and the installer stays advisory."""
    lines = install_script.read_text(encoding="utf-8").splitlines()
    bwrap_lines = [
        (number, line)
        for number, line in enumerate(lines, 1)
        if "bwrap" in line.lower()
    ]
    assert bwrap_lines, "install.sh no longer mentions bwrap — audit would be vacuous"
    assert any(
        "command -v bwrap" in line for _, line in bwrap_lines
    ), "install.sh must detect bwrap with command -v"

    offenders = [
        (number, line.strip())
        for number, line in bwrap_lines
        if _FORBIDDEN_AT_COMMAND_POSITION_RE.search(line)
        or re.search(r"\bexit\b", line)
    ]
    assert offenders == [], (
        "install.sh acts on bubblewrap instead of advising about it "
        f"(download/build/install/vendor or exit): {offenders}"
    )
