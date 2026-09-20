from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from terminal_jail.interruptor import Action, intercept

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
def test_prefix_install_missing_parent_no_cd_error_no_dotdot(
    install_script: Path, tmp_path: Path
) -> None:
    """DF-TERMINAL-JAIL-24: a scratch prefix whose parent does not exist yet
    must not print a raw sh ``can't cd`` error at the top of a successful
    install, and no printed path may carry an un-normalized ``/../`` segment.
    The old `cd <dir>/..` + pwd idiom emitted exactly that error (stderr, with
    the install still succeeding) and fell back to a literal ``<dir>/..`` that
    leaked into the prefix rules WARNING and the rules messages."""
    home = tmp_path / "home"
    home.mkdir()
    install_dir = tmp_path / "opt" / "tj"  # parent opt/ deliberately absent

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

    assert result.returncode == 0, (
        f"Install failed (rc={result.returncode}): "
        f"stderr={result.stderr.decode('utf-8', 'replace')}"
    )
    stdout = result.stdout.decode("utf-8", "replace")
    stderr = result.stderr.decode("utf-8", "replace")
    output = stdout + stderr

    # (a) no raw shell error about the missing parent — the raw line the old
    # script printed was: ./install.sh: NNN: cd: can't cd to <prefix>/..
    assert "can't cd" not in stderr, stderr
    assert "can't cd" not in stdout, stdout
    # (b) every printed path is normalized — no embedded "/../" anywhere.
    assert "/../" not in output, output
    # (c) the install itself is complete and the derived paths are the
    # normalized prefix targets: rules + lib land next to the binary.
    assert (install_dir / "terminal-jail").exists(), output
    prefix = tmp_path / "opt"
    prefix_rules = prefix / "config" / "terminal-jail" / "rules.d" / "00-builtins.yaml"
    assert prefix_rules.exists(), f"default rules not installed to prefix: {prefix_rules}"
    assert str(prefix_rules) in output, output
    assert (prefix / "lib" / "terminal-jail" / "seccomp-loader.py").exists(), output
    # (d) the prefix-scope WARNING still names the (now normalized) target.
    assert "non-default install prefix" in output


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


# ── TJ-GAP-061: opt-in rule packs (--rule-pack / --unrule-pack) ─────────────

DB_PACK = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules" / "packs" / "db.yaml"

# DF-TERMINAL-JAIL-22: the shipped pack's headline vector and benign control
# (mirrored from plugin/test_rule_packs.py). Used to prove a pack the installer
# wrote is LOADED by the live engine — an intercept verdict, not mere presence.
DB_PACK_DROP_DATABASE = 'psql -h db.internal -c "DROP DATABASE prod_app"'
DB_PACK_DROP_DATABASE_RULE = "pack-db-drop-database"
DB_PACK_BENIGN_READ = 'psql -c "SELECT 1"'

# Fixture packs for the refusal paths. The shipped packs are valid by
# construction, so a bad pack must be seeded into a checkout of our own.
_SHADOW_BUILTIN_PACK = """rules:
  - id: "builtin-rm-rf-root"
    description: "attempt to shadow a builtin"
    priority: 950
    action: block
    block_message: "nope"
    match:
      type: pattern
      pattern: "zzz"
"""

_SCHEMA_INVALID_PACK = """rules:
  - id: "pack-broken-no-match"
    description: "no match block"
    priority: 950
    action: block
    block_message: "nope"
"""

_MALFORMED_PACK = "rules: [ this : is : not : valid\n"


def _scratch_checkout(tmp_path: Path) -> Path:
    """A throwaway copy of the installer's checkout surface.

    install.sh resolves its pack source relative to its own directory, so a
    fixture pack can only be exercised from a checkout we own. The copy is
    deliberately minimal: install.sh, the validator, the wrapper, and the
    terminal_jail package tree are everything an install reads.
    """
    checkout = tmp_path / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / "standalone").mkdir()
    (checkout / "plugin").mkdir()
    shutil.copy2(PROJECT_ROOT / "install.sh", checkout / "install.sh")
    shutil.copy2(PROJECT_ROOT / "scripts" / "rule-pack-tool.py", checkout / "scripts")
    shutil.copy2(PROJECT_ROOT / "standalone" / "terminal-jail", checkout / "standalone")
    shutil.copytree(
        PROJECT_ROOT / "plugin" / "terminal_jail",
        checkout / "plugin" / "terminal_jail",
    )
    return checkout


def _install_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    install_dir = tmp_path / "bin"
    install_dir.mkdir(exist_ok=True)
    return {
        **os.environ,
        "HOME": str(home),
        "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
        # Never inherit a rules target from the invoking shell: these tests must
        # write into the scratch prefix only (an empty value == unset here).
        "TERMINAL_JAIL_RULES_DIR": "",
    }


# DF-TERMINAL-JAIL-22: run a test in a named install SCOPE.
#   prefix: custom TERMINAL_JAIL_INSTALL_DIR, no rules-dir env -> the installer
#           resolves prefix-local config the engine does NOT load (the DF-22
#           subject: packs SKIP there — dedicated tests at the bottom).
#   live:   custom install dir + explicit TERMINAL_JAIL_RULES_DIR -> the
#           explicit engine target (always wins). Custom install dir keeps
#           PATH-related writes out of scratch HOME (mirrors _install_env).
#           Pack install/validation/removal tests run in THIS scope: it is
#           engine-loaded, so a pack reported installed is really loaded.
def _install_env_for_scope(
    tmp_path: Path, scope: str
) -> tuple[dict[str, str], Path]:
    """(env, expected rules dir) for the named scope. Never mutates the real
    HOME: both scopes live under tmp_path."""
    env = _install_env(tmp_path)
    if scope == "prefix":
        return env, tmp_path / "config" / "terminal-jail" / "rules.d"
    if scope == "live":
        explicit = tmp_path / "live-rules.d"
        env["TERMINAL_JAIL_RULES_DIR"] = str(explicit)
        return env, explicit
    raise ValueError(f"unknown install scope: {scope}")


def _run_repo_install(
    tmp_path: Path, *args: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    """Run the real checkout's installer (cwd=repo root => local mode)."""
    env = _install_env(tmp_path)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["sh", "install.sh", *args],
        capture_output=True,
        text=False,
        check=False,
        timeout=30,
        cwd=str(PROJECT_ROOT),
        env=env,
    )


def _run_checkout_install(
    checkout: Path,
    tmp_path: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    env = _install_env(tmp_path)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["sh", "install.sh", *args],
        capture_output=True,
        text=False,
        check=False,
        timeout=30,
        cwd=str(checkout),
        env=env,
    )


def _assert_nothing_written(tmp_path: Path) -> None:
    """A parse-time refusal (unknown flag, unsafe pack name) — or a flag-only
    run — leaves no file behind (TJ-GAP-061: flag parsing precedes the install
    section's mkdir). DF-TERMINAL-JAIL-21: a PACK-level refusal is no longer
    covered here — a refused pack is now a loud skip and the base install
    completes; those tests assert the wrapper + rules dir instead."""
    install_dir = tmp_path / "bin"
    assert list(install_dir.iterdir()) == [], sorted(
        path.name for path in install_dir.iterdir()
    )
    assert not (tmp_path / "config").exists()


def _assert_base_install_completed(
    tmp_path: Path, out: str, rules_dir: Path | None = None
) -> None:
    """DF-TERMINAL-JAIL-21 invariant: no matter what happened to a requested
    pack, the base install always completes — wrapper, lib tree, default
    rules file. DF-TERMINAL-JAIL-22: pass rules_dir for the engine-loaded
    scopes (explicit / engine-env) whose default rules land OUTSIDE the
    prefix config tree."""
    install_dir = tmp_path / "bin"
    assert (install_dir / "terminal-jail").exists(), out
    lib_tree = install_dir.parent / "lib" / "terminal-jail" / "plugin"
    assert lib_tree.is_dir(), out
    if rules_dir is None:
        rules_dir = tmp_path / "config" / "terminal-jail" / "rules.d"
    assert (rules_dir / "00-builtins.yaml").exists(), out


@pytest.mark.standalone_cli
def test_install_rule_pack_lands_in_the_resolved_rules_dir(
    tmp_path: Path,
) -> None:
    """--rule-pack db byte-copies the shipped pack next to the default rules
    file, in the directory the install scope resolves to.

    DF-TERMINAL-JAIL-22: run in the ENGINE-LOADED scope (explicit
    TERMINAL_JAIL_RULES_DIR). In the prefix scope the pack skips loudly
    instead of installing (DF-TERMINAL-JAIL-22 tests below) — an installed
    pack must always be an engine-loaded pack."""
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    result = _run_repo_install(tmp_path, "--rule-pack", "db", extra_env=env)
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    pack = rules_dir / "terminal-jail-pack-db.yaml"
    assert pack.exists(), out
    # byte-identical to the shipped pack, and beside the default rules file
    assert pack.read_bytes() == DB_PACK.read_bytes()
    assert (rules_dir / "00-builtins.yaml").exists(), out
    assert f"installed rule pack 'db' to {pack}" in out, out
    # the validator ran and reported the engine-derived builtin count
    assert "rule-pack-tool: pack 'db' valid" in out, out


@pytest.mark.standalone_cli
def test_unrule_pack_removes_only_that_pack(tmp_path: Path) -> None:
    """--unrule-pack removes terminal-jail-pack-db.yaml and nothing else: a
    foreign file beside it and the default rules file both survive.
    DF-TERMINAL-JAIL-22: engine-loaded scope (removal follows install)."""
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    install = _run_repo_install(tmp_path, "--rule-pack", "db", extra_env=env)
    assert install.returncode == 0, install.stderr.decode("utf-8", "replace")

    pack = rules_dir / "terminal-jail-pack-db.yaml"
    foreign = rules_dir / "zz-foreign-user-rules.yaml"
    foreign.write_text("rules: []\n", encoding="utf-8")
    builtins_before = (rules_dir / "00-builtins.yaml").read_bytes()

    result = _run_repo_install(tmp_path, "--unrule-pack", "db", extra_env=env)
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    assert f"removed rule pack 'db' ({pack})" in out, out
    assert not pack.exists(), out
    assert foreign.exists(), "a foreign rule file was removed"
    assert foreign.read_text(encoding="utf-8") == "rules: []\n"
    assert (rules_dir / "00-builtins.yaml").read_bytes() == builtins_before


@pytest.mark.standalone_cli
def test_unrule_pack_for_a_pack_that_is_not_installed(tmp_path: Path) -> None:
    """Removal is idempotent and says so — it never fails on a clean host.
    DF-TERMINAL-JAIL-22: engine-loaded scope."""
    env, _rules_dir = _install_env_for_scope(tmp_path, "live")
    result = _run_repo_install(tmp_path, "--unrule-pack", "db", extra_env=env)
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    assert "is not installed at" in out, out
    assert "nothing was removed" in out, out


@pytest.mark.standalone_cli
@pytest.mark.parametrize(
    ("fixture_name", "body", "needle"),
    [
        ("shadow", _SHADOW_BUILTIN_PACK, "collide with engine builtin ids"),
        ("broken", _SCHEMA_INVALID_PACK, "has no 'match' mapping"),
        ("malformed", _MALFORMED_PACK, "cannot parse"),
    ],
)
def test_install_skips_a_bad_pack_but_still_installs_the_base(
    tmp_path: Path, fixture_name: str, body: str, needle: str
) -> None:
    """DF-TERMINAL-JAIL-21 (deliberate expectation change from the pre-DF-21
    'refusal aborts everything' semantics): schema-invalid, malformed, and
    builtin-shadowing packs are refused by the validator and NOTHING is written
    for the pack itself — but the base install (wrapper, lib tree, default
    rules) always completes, the skip is loud, and the run exits 2.
    DF-TERMINAL-JAIL-22: engine-loaded scope — the prefix scope never reaches
    the validator (packs skip there before any validation)."""
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    checkout = _scratch_checkout(tmp_path)
    (checkout / "plugin" / "terminal_jail" / "rules" / "packs" / f"{fixture_name}.yaml").write_text(
        body, encoding="utf-8"
    )

    result = _run_checkout_install(
        checkout, tmp_path, "--rule-pack", fixture_name, extra_env=env
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 2, out
    assert needle in out, out
    assert f"skipped: pack '{fixture_name}' — REFUSED by the validator, nothing was written" in out, out
    # the pack file itself was never written (fail-closed, validate-before-write)
    assert not (
        rules_dir / f"terminal-jail-pack-{fixture_name}.yaml"
    ).exists(), out
    # ...but the base install completed
    _assert_base_install_completed(tmp_path, out, rules_dir=rules_dir)
    # the end-of-run summary names what installed and what skipped
    assert f"installed: wrapper at {tmp_path / 'bin' / 'terminal-jail'}" in out, out
    assert "base install completed" in out, out


@pytest.mark.standalone_cli
def test_install_refuses_an_already_installed_pack_id(tmp_path: Path) -> None:
    """An id another installed rule file already carries is refused — a pack
    may never shadow a rule that is already live in the rules dir.
    DF-TERMINAL-JAIL-21: the refusal is a loud skip; the base install completes.
    DF-TERMINAL-JAIL-22: engine-loaded scope — the prefix scope skips packs
    before validation ever runs."""
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    checkout = _scratch_checkout(tmp_path)
    rules_dir.mkdir(parents=True)
    (rules_dir / "zz-handwritten.yaml").write_text(
        "rules:\n"
        '  - id: "pack-db-drop-database"\n'
        "    priority: 900\n"
        "    action: warn\n"
        "    match:\n"
        "      type: pattern\n"
        '      pattern: "drop database"\n',
        encoding="utf-8",
    )

    result = _run_checkout_install(
        checkout, tmp_path, "--rule-pack", "db", extra_env=env
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 2, out
    assert "are already installed in" in out, out
    assert "skipped: pack 'db'" in out, out
    assert not (rules_dir / "terminal-jail-pack-db.yaml").exists(), out
    # the seeded file is untouched
    assert "pack-db-drop-database" in (rules_dir / "zz-handwritten.yaml").read_text()
    # the base install completed despite the pack skip (DF-TERMINAL-JAIL-21)
    _assert_base_install_completed(tmp_path, out, rules_dir=rules_dir)


@pytest.mark.standalone_cli
def test_install_skips_an_unknown_rule_pack_but_still_installs_the_base(
    tmp_path: Path,
) -> None:
    """DF-TERMINAL-JAIL-21 (deliberate expectation change: previously exit 2
    with nothing written) — an unknown pack name is a loud skip that suggests
    --list-rule-packs, and the base install completes (exit 2 at the end).
    DF-TERMINAL-JAIL-22: engine-loaded scope."""
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    result = _run_repo_install(
        tmp_path, "--rule-pack", "nope", extra_env=env
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 2, out
    assert "skipped: pack 'nope'" in out, out
    assert "unknown pack name" in out, out
    assert "--list-rule-packs" in out, out
    # the unknown pack wrote nothing, but the base install completed
    assert not (
        rules_dir / "terminal-jail-pack-nope.yaml"
    ).exists(), out
    _assert_base_install_completed(tmp_path, out, rules_dir=rules_dir)


@pytest.mark.standalone_cli
def test_install_refuses_an_unknown_flag(tmp_path: Path) -> None:
    result = _run_repo_install(tmp_path, "--bogus-flag")
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 2, out
    assert "unknown argument '--bogus-flag'" in out, out
    _assert_nothing_written(tmp_path)


@pytest.mark.standalone_cli
def test_install_refuses_an_unsafe_pack_name(tmp_path: Path) -> None:
    """A pack name may not escape the rules directory."""
    result = _run_repo_install(tmp_path, "--rule-pack", "../db")
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 2, out
    assert "invalid pack name '../db'" in out, out
    _assert_nothing_written(tmp_path)


@pytest.mark.standalone_cli
def test_list_rule_packs_names_db(tmp_path: Path) -> None:
    """--list-rule-packs names the shipped pack (and its rule count) without
    touching anything."""
    result = _run_repo_install(tmp_path, "--list-rule-packs")
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    rows = [line for line in out.splitlines() if line.startswith("db\t")]
    assert rows, out
    assert str(DB_PACK) in rows[0], rows
    assert rows[0].endswith("\t3"), rows
    _assert_nothing_written(tmp_path)


@pytest.mark.standalone_cli
def test_install_help_documents_the_rule_pack_flags(tmp_path: Path) -> None:
    result = _run_repo_install(tmp_path, "--help")
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    for flag in ("--rule-pack <name>", "--unrule-pack <name>", "--list-rule-packs"):
        assert flag in out, out
    _assert_nothing_written(tmp_path)


# ── TJ-GAP-065: the PATH hint follows the ACTUAL install dir ────────────────


def _scratch_rc(home: Path) -> Path:
    """A scratch startup file with content the installer must not disturb."""
    home.mkdir(parents=True, exist_ok=True)
    rc = home / ".profile"  # first candidate in the installer's search order
    rc.write_text("# scratch rc\n", encoding="utf-8")
    return rc


@pytest.mark.standalone_cli
def test_custom_install_dir_path_entry_points_at_actual_dir(tmp_path: Path) -> None:
    """TJ-GAP-065: with a non-default TERMINAL_JAIL_INSTALL_DIR the installer
    must never report "added PATH entry" while appending the hardcoded
    $HOME/.local/bin line — the binary is not there, so the shell would still
    say "command not found" after relogin. It appends a line naming the
    ACTUAL install dir instead and never touches $HOME/.local/bin."""
    env = _install_env(tmp_path)
    home = tmp_path / "home"
    rc = _scratch_rc(home)
    install_dir = tmp_path / "bin"

    result = _run_repo_install(tmp_path, extra_env=env)
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    text = rc.read_text(encoding="utf-8")
    # the appended line names the ACTUAL dir ...
    assert f'export PATH="{install_dir}:$PATH"' in text, text
    # ... and the hardcoded default line is gone from this scope
    assert 'export PATH="$HOME/.local/bin:$PATH"' not in text, text
    # exactly one marker block, and the honest message names the rc file
    assert text.count("# terminal-jail") == 1, text
    assert f"added PATH entry to {rc}" in out, out
    # the binary really is where the PATH line points (and nowhere else)
    assert (install_dir / "terminal-jail").exists(), out
    assert not (home / ".local" / "bin" / "terminal-jail").exists(), out
    _assert_base_install_completed(tmp_path, out)


@pytest.mark.standalone_cli
def test_custom_install_dir_path_entry_is_idempotent(tmp_path: Path) -> None:
    """TJ-GAP-065: re-running a custom-prefix install must not duplicate the
    PATH block — the idempotency check greps the exact rendered line."""
    env = _install_env(tmp_path)
    rc = _scratch_rc(tmp_path / "home")

    first = _run_repo_install(tmp_path, extra_env=env)
    out1 = (first.stdout + first.stderr).decode("utf-8", "replace")
    assert first.returncode == 0, out1
    assert "added PATH entry" in out1, out1

    second = _run_repo_install(tmp_path, extra_env=env)
    out2 = (second.stdout + second.stderr).decode("utf-8", "replace")
    assert second.returncode == 0, out2
    text = rc.read_text(encoding="utf-8")
    assert text.count("# terminal-jail") == 1, text
    assert "added PATH entry" not in out2, out2


@pytest.mark.standalone_cli
def test_custom_install_dir_appends_despite_stale_default_block(
    tmp_path: Path,
) -> None:
    """TJ-GAP-065: a scratch rc carrying an OLD default-scope block (marker +
    $HOME/.local/bin line, e.g. from a previous default install or the pre-fix
    bug) must not swallow the custom-prefix entry: the marker grep stays
    scoped to the default branch, so the correct line is still appended."""
    env = _install_env(tmp_path)
    rc = _scratch_rc(tmp_path / "home")
    rc.write_text(
        "# scratch rc\n\n# terminal-jail\nexport PATH=\"$HOME/.local/bin:$PATH\"\n",
        encoding="utf-8",
    )

    result = _run_repo_install(tmp_path, extra_env=env)
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    install_dir = tmp_path / "bin"
    text = rc.read_text(encoding="utf-8")
    assert f'export PATH="{install_dir}:$PATH"' in text, text
    assert "added PATH entry" in out, out


@pytest.mark.standalone_cli
def test_default_install_keeps_classic_path_behavior(tmp_path: Path) -> None:
    """TJ-GAP-065: the default install (no TERMINAL_JAIL_INSTALL_DIR override,
    resolving to $HOME/.local/bin) behaves exactly as before: the classic
    ``export PATH="$HOME/.local/bin:$PATH"`` block is appended when missing,
    and a re-run is idempotent (no duplicate block, no second message)."""
    home = tmp_path / "home"
    env = {
        **os.environ,
        "HOME": str(home),
        # Defend against ambient knobs of the invoking shell (mirrors
        # _install_env): empty == unset for both defaults.
        "TERMINAL_JAIL_INSTALL_DIR": "",
        "TERMINAL_JAIL_RULES_DIR": "",
    }

    first = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=30,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    out1 = (first.stdout + first.stderr).decode("utf-8", "replace")
    assert first.returncode == 0, out1

    rc = home / ".profile"  # created by the installer when no rc exists
    text = rc.read_text(encoding="utf-8")
    assert 'export PATH="$HOME/.local/bin:$PATH"' in text, text
    assert f"added PATH entry to {rc}" in out1, out1
    assert text.count("# terminal-jail") == 1, text
    assert (home / ".local" / "bin" / "terminal-jail").exists(), out1

    second = subprocess.run(
        ["sh", "install.sh"],
        capture_output=True,
        text=False,
        check=False,
        timeout=30,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    out2 = (second.stdout + second.stderr).decode("utf-8", "replace")
    assert second.returncode == 0, out2
    text2 = rc.read_text(encoding="utf-8")
    assert text2.count("# terminal-jail") == 1, text2
    assert "added PATH entry" not in out2, out2


# ── DF-TERMINAL-JAIL-21: pack failure skips instead of aborting the install ──

_PYAML_SHADOW_YAML_BODY = (
    'raise ImportError("PyYAML intentionally shadowed for DF-TERMINAL-JAIL-21 test")\n'
)


def _env_with_shadowed_pyyaml(env: dict[str, str], tmp_path: Path) -> dict[str, str]:
    """Put a fake `python3` shim first on PATH that execs the real python3 with
    PYTHONPATH pointing at a directory whose `yaml.py` raises ImportError —
    `import yaml` then fails deterministically inside the preflight AND inside
    the validator, simulating a fresh host without PyYAML (the dogfood
    scenario: python3.13.5, no PyYAML, no pip). Mirrors the curated-PATH
    fixture style used for the bwrap tests."""
    shadow_dir = tmp_path / "pyyaml-shadow"
    shadow_dir.mkdir(exist_ok=True)
    (shadow_dir / "yaml.py").write_text(
        _PYAML_SHADOW_YAML_BODY, encoding="utf-8"
    )
    python3 = shutil.which("python3")
    assert python3, "the test host has no real python3 to shim"
    shim = shadow_dir / "python3"
    shim.write_text(
        "#!/bin/sh\n"
        f'PYTHONPATH="{shadow_dir}${{PYTHONPATH:+:$PYTHONPATH}}" \\\n'
        f'  exec "{python3}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return {**env, "PATH": f"{shadow_dir}{os.pathsep}{env.get('PATH', '')}"}


def _env_with_no_python3(env: dict[str, str], tmp_path: Path) -> dict[str, str]:
    """PATH curated to the installer's coreutils with NO python3 at all."""
    bindir = tmp_path / "toolbin-no-python3"
    bindir.mkdir(exist_ok=True)
    _link_tools(bindir, *_INSTALL_TOOLS)
    missing = sorted(t for t in _INSTALL_TOOLS if not (bindir / t).exists())
    assert not missing, f"host lacks tools the curated PATH needs: {missing}"
    return {**env, "PATH": str(bindir)}


_JQ_JSON_PACK_BODY = (  # plain JSON on disk (the .yaml suffix is just the name)
    '{"rules": [{"id": "pack-json-pack-ok", "priority": 950, "action": "block",'
    ' "block_message": "no", "match": {"type": "pattern", "pattern": "zzz"}}]}\n'
)


@pytest.mark.standalone_cli
def test_install_with_no_pyyaml_skips_yaml_pack_but_installs_the_base(
    tmp_path: Path,
) -> None:
    """DF-TERMINAL-JAIL-21 regression lock (the dogfood scenario): a fresh host
    WITHOUT PyYAML must still get the base install; the YAML pack is skipped
    loudly, naming PyYAML and both remedies, and the run exits 2. Nothing is
    written for the skipped pack — not even the pack file.
    DF-TERMINAL-JAIL-22: engine-loaded scope."""
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    extra_env = _env_with_shadowed_pyyaml(env, tmp_path)
    result = subprocess.run(
        ["sh", "install.sh", "--rule-pack", "db"],
        capture_output=True,
        text=False,
        check=False,
        timeout=30,
        cwd=str(PROJECT_ROOT),
        env=extra_env,
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 2, out
    assert "PyYAML is required to parse YAML rule packs and was not found" in out, out
    assert "python3-yaml" in out, out
    assert "pip install pyyaml" in out, out
    assert "base install completed" in out, out
    # the base install completed: wrapper, lib tree, default rules
    _assert_base_install_completed(tmp_path, out, rules_dir=rules_dir)
    # the skipped pack wrote NOTHING to the rules dir (fail-closed preflight:
    # the validator never even ran, so no pack file exists)
    assert not (rules_dir / "terminal-jail-pack-db.yaml").exists(), out
    # the validator (whose JSONDecodeError caused the original dogfood failure)
    # never produced a refusal for this pack
    assert "cannot parse" not in out, out


@pytest.mark.standalone_cli
def test_install_with_no_pyyaml_still_installs_a_plain_json_pack(
    tmp_path: Path,
) -> None:
    """The PyYAML preflight must NOT refuse a pack the validator can actually
    read: a pack that parses as plain JSON goes through the validator's stdlib
    json fallback and installs normally — exit 0, wrapper installed.
    DF-TERMINAL-JAIL-22: engine-loaded scope."""
    checkout = _scratch_checkout(tmp_path)
    (checkout / "plugin" / "terminal_jail" / "rules" / "packs" / "json-pack.yaml").write_text(
        _JQ_JSON_PACK_BODY, encoding="utf-8"
    )
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    extra_env = _env_with_shadowed_pyyaml(env, tmp_path)
    result = subprocess.run(
        ["sh", "install.sh", "--rule-pack", "json-pack"],
        capture_output=True,
        text=False,
        check=False,
        timeout=30,
        cwd=str(checkout),
        env=extra_env,
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    pack = rules_dir / "terminal-jail-pack-json-pack.yaml"
    assert pack.exists(), out
    assert pack.read_bytes() == _JQ_JSON_PACK_BODY.encode("utf-8"), out
    assert (rules_dir / "00-builtins.yaml").exists(), out
    assert "installed rule pack 'json-pack'" in out, out
    assert "PyYAML" not in out, out


@pytest.mark.standalone_cli
def test_install_with_no_python3_skips_the_pack_but_installs_the_base(
    tmp_path: Path,
) -> None:
    """No python3 at all (bare distro host): the requested pack skips with a
    specific message naming python3, and the base install completes (exit 2).
    Validating before writing stays the invariant — the pack is never copied
    unvalidated (DF-TERMINAL-JAIL-21).
    DF-TERMINAL-JAIL-22: engine-loaded scope."""
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    extra_env = _env_with_no_python3(env, tmp_path)
    result = subprocess.run(
        ["sh", "install.sh", "--rule-pack", "db"],
        capture_output=True,
        text=False,
        check=False,
        timeout=30,
        cwd=str(PROJECT_ROOT),
        env=extra_env,
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 2, out
    assert "python3 is required to validate a pack BEFORE installing it" in out, out
    assert "install python3" in out, out
    assert "base install completed" in out, out
    _assert_base_install_completed(tmp_path, out, rules_dir=rules_dir)
    assert not (rules_dir / "terminal-jail-pack-db.yaml").exists(), out


@pytest.mark.standalone_cli
def test_install_malformed_pack_with_pyyaml_present_refuses_but_installs_base(
    tmp_path: Path,
) -> None:
    """PyYAML present but the pack is malformed: the validator refuses (nothing
    written for the pack), but the base install completes (exit 2) — the
    same skip-not-abort semantics as the no-PyYAML path.
    DF-TERMINAL-JAIL-22: engine-loaded scope."""
    checkout = _scratch_checkout(tmp_path)
    (checkout / "plugin" / "terminal_jail" / "rules" / "packs" / "malformed.yaml").write_text(
        _MALFORMED_PACK, encoding="utf-8"
    )
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    result = _run_checkout_install(
        checkout, tmp_path, "--rule-pack", "malformed", extra_env=env
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 2, out
    assert "cannot parse" in out, out
    assert "skipped: pack 'malformed'" in out, out
    assert not (rules_dir / "terminal-jail-pack-malformed.yaml").exists(), out
    _assert_base_install_completed(tmp_path, out, rules_dir=rules_dir)


# ── DF-TERMINAL-JAIL-22: prefix-scope packs are skipped, never silently inert ──


@pytest.mark.standalone_cli
def test_prefix_install_skips_rule_pack_instead_of_inert_success(
    tmp_path: Path,
) -> None:
    """DF-TERMINAL-JAIL-22: with a custom TERMINAL_JAIL_INSTALL_DIR and no
    rules-dir env, the resolved rules dir is prefix-local config the engine
    does NOT load. The pack is skipped loudly — naming the exact remediation,
    per the DF-TERMINAL-JAIL-21 skip/exit-2 contract — instead of being
    reported installed-and-inert. Nothing is written for the pack and the
    base install always completes."""
    result = _run_repo_install(tmp_path, "--rule-pack", "db")
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    rules_dir = tmp_path / "config" / "terminal-jail" / "rules.d"
    pack = rules_dir / "terminal-jail-pack-db.yaml"

    assert result.returncode == 2, out
    assert "skipped: pack 'db'" in out, out
    assert "prefix-local config the engine does NOT load" in out, out
    assert str(rules_dir) in out, out
    # exact remediation: every engine-loaded alternative is named
    assert "TERMINAL_JAIL_RULES_DIR=" in out, out
    assert "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=" in out, out
    assert "default install dir" in out, out
    # nothing was written for the pack (fail-closed before the validator)
    assert not pack.exists(), out
    assert not any(rules_dir.glob("terminal-jail-pack-*")), out
    # ...but the base install completed, with the summary + exit 2
    _assert_base_install_completed(tmp_path, out)
    assert "base install completed" in out, out


@pytest.mark.standalone_cli
def test_prefix_install_skips_every_requested_rule_pack(
    tmp_path: Path,
) -> None:
    """DF-TERMINAL-JAIL-22: the prefix gate is per requested pack — two valid
    packs under a custom prefix both skip loudly (the validator never runs,
    so same-id content is irrelevant), nothing is written, exit 2."""
    checkout = _scratch_checkout(tmp_path)
    shutil.copy2(
        DB_PACK, checkout / "plugin" / "terminal_jail" / "rules" / "packs" / "cache.yaml"
    )
    result = _run_checkout_install(
        checkout, tmp_path, "--rule-pack", "db", "--rule-pack", "cache"
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    rules_dir = tmp_path / "config" / "terminal-jail" / "rules.d"
    assert result.returncode == 2, out
    assert "skipped: pack 'db'" in out, out
    assert "skipped: pack 'cache'" in out, out
    # each skip message prints twice: the immediate skip line AND the final
    # summary (PACK_FAILURES is echoed verbatim) — 2 packs x 2 = 4
    assert out.count("prefix-local config the engine does NOT load") == 4, out
    assert not any(rules_dir.glob("terminal-jail-pack-*")), out
    _assert_base_install_completed(tmp_path, out)


@pytest.mark.standalone_cli
def test_prefix_unrule_pack_keeps_idempotent_removal_contract(
    tmp_path: Path,
) -> None:
    """--unrule-pack is not a pack install: it stays scope-agnostic and keeps
    its idempotent not-installed message even in the prefix scope (DF-22
    gates only packs the operator asks to ADD)."""
    result = _run_repo_install(tmp_path, "--unrule-pack", "db")
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    assert "is not installed at" in out, out
    assert "nothing was removed" in out, out


@pytest.mark.standalone_cli
def test_explicit_rules_dir_pack_is_loaded_by_the_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DF-TERMINAL-JAIL-22: an explicit TERMINAL_JAIL_RULES_DIR with a custom
    prefix stays authoritative — the pack is written there byte-identical,
    and the ENGINE loads it: with the scratch engine env pointing at exactly
    that directory, intercept() BLOCKs the pack's DROP DATABASE vector and
    leaves the benign read alone. This is the load-proof, not a
    file-presence proof."""
    env, rules_dir = _install_env_for_scope(tmp_path, "live")
    result = _run_repo_install(tmp_path, "--rule-pack", "db", extra_env=env)
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    pack = rules_dir / "terminal-jail-pack-db.yaml"
    assert pack.exists(), out
    assert pack.read_bytes() == DB_PACK.read_bytes(), out
    assert (rules_dir / "00-builtins.yaml").exists(), out
    _assert_base_install_completed(tmp_path, out, rules_dir=rules_dir)

    # the engine reads exactly this directory (scratch system + user rules)
    monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR", str(rules_dir))
    system_dir = tmp_path / "empty-system-rules.d"
    system_dir.mkdir()
    monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_RULES_DIR", str(system_dir))

    blocked = intercept(DB_PACK_DROP_DATABASE)
    assert blocked.action == Action.BLOCK, blocked
    assert blocked.rule_id == DB_PACK_DROP_DATABASE_RULE, blocked

    benign = intercept(DB_PACK_BENIGN_READ)
    assert benign.action == Action.ALLOW, benign
    assert benign.rule_id is None, benign


@pytest.mark.standalone_cli
def test_engine_env_rules_dir_pack_is_loaded_by_the_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DF-TERMINAL-JAIL-22: a custom-prefix install with the ENGINE's own
    user-rules knob (TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR) exported
    resolves the installer's single rules dir to that exact directory: the
    pack installs there, the prefix-local config dir is never created, and
    the engine loads the pack from it — the same path the CLI reads when run
    with the variable exported."""
    engine_dir = tmp_path / "engine-user-rules.d"
    engine_dir.mkdir()
    result = _run_repo_install(
        tmp_path,
        "--rule-pack",
        "db",
        extra_env={"TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR": str(engine_dir)},
    )
    out = (result.stdout + result.stderr).decode("utf-8", "replace")

    assert result.returncode == 0, out
    pack = engine_dir / "terminal-jail-pack-db.yaml"
    assert pack.exists(), out
    assert pack.read_bytes() == DB_PACK.read_bytes(), out
    assert (engine_dir / "00-builtins.yaml").exists(), out
    assert not (tmp_path / "config").exists(), out
    _assert_base_install_completed(tmp_path, out, rules_dir=engine_dir)

    monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR", str(engine_dir))
    system_dir = tmp_path / "empty-system-rules.d"
    system_dir.mkdir()
    monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_RULES_DIR", str(system_dir))

    blocked = intercept(DB_PACK_DROP_DATABASE)
    assert blocked.action == Action.BLOCK, blocked
    assert blocked.rule_id == DB_PACK_DROP_DATABASE_RULE, blocked

    benign = intercept(DB_PACK_BENIGN_READ)
    assert benign.action == Action.ALLOW, benign
    assert benign.rule_id is None, benign
