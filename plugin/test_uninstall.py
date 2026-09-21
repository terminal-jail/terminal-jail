"""TJ-GAP-071: ``./install.sh --uninstall`` — the removal mirror.

Every test runs against a SCRATCH HOME under tmp_path (never the real $HOME):
``_env`` pins HOME, TERMINAL_JAIL_INSTALL_DIR and TERMINAL_JAIL_RULES_DIR into
tmp_path, mirroring ``_install_env`` in test_install.py. The default-scope
tests override HOME only, exactly like a real default install.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = PROJECT_ROOT / "install.sh"

USER_RULE = "rules: []\n"


def _env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    install_dir = tmp_path / "bin"
    install_dir.mkdir(exist_ok=True)
    return {
        **os.environ,
        "HOME": str(home),
        "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
        "TERMINAL_JAIL_RULES_DIR": str(tmp_path / "rules.d"),
    }


def _home_env(tmp_path: Path) -> dict[str, str]:
    """Default install scope: HOME overridden, every knob empty (== unset)."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {
        **os.environ,
        "HOME": str(home),
        "TERMINAL_JAIL_INSTALL_DIR": "",
        "TERMINAL_JAIL_RULES_DIR": "",
    }


def _run(
    tmp_path: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["sh", "install.sh", *args],
        capture_output=True,
        text=False,
        check=False,
        timeout=60,
        cwd=str(PROJECT_ROOT),
        env=env if env is not None else _env(tmp_path),
    )


def _out(result: subprocess.CompletedProcess[bytes]) -> str:
    return (result.stdout + result.stderr).decode("utf-8", "replace")


def _home_tj_files(home: Path) -> list[Path]:
    """Every FILE under the scratch HOME whose name mentions terminal-jail.

    Empty parent directories (~/.config/terminal-jail, ~/.local/lib) are
    deliberately NOT flagged: uninstall preserves the rules dir for
    user-authored content and leaves parent scaffolding alone, exactly like
    the installer does not remove empty dirs it created.
    """
    return [
        p
        for p in home.rglob("*")
        if p.is_file()
        and "terminal-jail" in p.name
        and ".terminal-jail-uninstall." not in p.name
    ]


def _assert_uninstall_clean(result: subprocess.CompletedProcess[bytes]) -> None:
    out = _out(result)
    assert result.returncode == 0, out
    assert "uninstall done." in out, out


# ── install → uninstall leaves ZERO terminal-jail files ───────────────────


@pytest.mark.standalone_cli
def test_uninstall_leaves_zero_terminal_jail_files(tmp_path: Path) -> None:
    """Default-scope install then uninstall: no terminal-jail file survives
    anywhere under the scratch HOME, and `command -v terminal-jail` with the
    scratch bin on PATH finds nothing."""
    home = tmp_path / "home"
    install = _run(tmp_path, env=_home_env(tmp_path))
    assert install.returncode == 0, _out(install)
    assert (home / ".local" / "bin" / "terminal-jail").exists(), _out(install)
    assert _home_tj_files(home), "install produced no files — probe broken"

    uninstall = _run(tmp_path, "--uninstall", env=_home_env(tmp_path))
    out = _out(uninstall)
    _assert_uninstall_clean(uninstall)
    assert _home_tj_files(home) == [], sorted(p.name for p in _home_tj_files(home))
    assert "removed:" in out, out
    assert "removed rc-line:" in out, out

    # command -v against the scratch install dir only: nothing found.
    which = subprocess.run(
        ["sh", "-c", "command -v terminal-jail"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": f"{home / '.local' / 'bin'}:/usr/bin:/bin",
        },
    )
    assert which.returncode != 0 or which.stdout.strip() == "", which.stdout


@pytest.mark.standalone_cli
def test_uninstall_removes_installed_pack_and_bak_backups(tmp_path: Path) -> None:
    """Every install-written rules class goes: 00-builtins.yaml, the opt-in
    pack file, and the .bak-<ts> copy a re-install over customized rules
    creates (install.sh DF-TERMINAL-JAIL-3)."""
    env = _env(tmp_path)
    rules_dir = tmp_path / "rules.d"

    first = _run(tmp_path, env=env)
    assert first.returncode == 0, _out(first)
    # customize the builtins so a re-install must create a .bak- backup
    builtins = rules_dir / "00-builtins.yaml"
    builtins.write_text("# user edit\n" + USER_RULE, encoding="utf-8")
    second = _run(tmp_path, "--rule-pack", "db", env=env)
    assert second.returncode == 0, _out(second)
    assert list(rules_dir.glob("00-builtins.yaml.bak-*")), "no .bak created"
    assert (rules_dir / "terminal-jail-pack-db.yaml").exists()

    uninstall = _run(tmp_path, "--uninstall", env=env)
    out = _out(uninstall)
    _assert_uninstall_clean(uninstall)
    assert builtins.exists() is False, out
    assert (rules_dir / "terminal-jail-pack-db.yaml").exists() is False, out
    assert not list(rules_dir.glob("00-builtins.yaml.bak-*")), out
    assert f"removed: {rules_dir / 'terminal-jail-pack-db.yaml'}" in out, out


# ── user-authored rules are PRESERVED and listed ──────────────────────────


@pytest.mark.standalone_cli
def test_uninstall_preserves_user_authored_rule_and_lists_it(tmp_path: Path) -> None:
    """A rules.d file the installer never wrote survives uninstall and is
    explicitly listed: 'left in place (user-authored): <path>'."""
    env = _env(tmp_path)
    rules_dir = tmp_path / "rules.d"
    rules_dir.mkdir(parents=True, exist_ok=True)
    user_rule = rules_dir / "my-own-rule.yaml"
    user_rule.write_text(USER_RULE, encoding="utf-8")

    install = _run(tmp_path, "--rule-pack", "db", env=env)
    assert install.returncode == 0, _out(install)

    uninstall = _run(tmp_path, "--uninstall", env=env)
    out = _out(uninstall)
    _assert_uninstall_clean(uninstall)
    assert user_rule.read_text(encoding="utf-8") == USER_RULE
    assert f"left in place (user-authored): {user_rule}" in out, out


# ── round trip: uninstall → reinstall yields a working install ────────────


@pytest.mark.standalone_cli
def test_uninstall_then_reinstall_round_trip(tmp_path: Path) -> None:
    """install → uninstall → install again: the second install is complete
    (wrapper, default rules, PATH block re-appended exactly once) and the
    wrapper actually runs."""
    home = tmp_path / "home"
    env = _home_env(tmp_path)

    first = _run(tmp_path, env=env)
    assert first.returncode == 0, _out(first)
    uninstall = _run(tmp_path, "--uninstall", env=env)
    _assert_uninstall_clean(uninstall)
    # the marker block is fully gone (marker line included), so the reinstall
    # must re-append instead of treating the leftovers as "already present"
    profile = home / ".profile"
    if profile.exists():
        assert "terminal-jail" not in profile.read_text(encoding="utf-8")

    reinstall = _run(tmp_path, env=env)
    out = _out(reinstall)
    assert reinstall.returncode == 0, out
    assert "added PATH entry" in out, out
    assert (home / ".local" / "bin" / "terminal-jail").exists(), out
    assert (
        home / ".config" / "terminal-jail" / "rules.d" / "00-builtins.yaml"
    ).exists(), out
    profile_text = profile.read_text(encoding="utf-8")
    assert profile_text.count("# terminal-jail") == 1, profile_text

    run = subprocess.run(
        [str(home / ".local" / "bin" / "terminal-jail"), "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        },
    )
    assert run.returncode == 0, run.stderr
    assert "terminal-jail" in run.stdout + run.stderr


# ── never-installed host: clean no-op ──────────────────────────────────────


@pytest.mark.standalone_cli
def test_uninstall_on_never_installed_home_is_clean_noop(tmp_path: Path) -> None:
    """Uninstall on a fresh scratch HOME: rc 0, explicitly nothing to do."""
    result = _run(tmp_path, "--uninstall", env=_home_env(tmp_path))
    out = _out(result)
    _assert_uninstall_clean(result)
    assert "nothing to uninstall" in out, out
    assert "removed:" not in out, out


@pytest.mark.standalone_cli
def test_uninstall_is_idempotent(tmp_path: Path) -> None:
    """A second uninstall after a real one is still a no-op success (rc 0)."""
    env = _env(tmp_path)
    install = _run(tmp_path, env=env)
    assert install.returncode == 0, _out(install)
    first = _run(tmp_path, "--uninstall", env=env)
    _assert_uninstall_clean(first)
    assert "removed:" in _out(first)
    second = _run(tmp_path, "--uninstall", env=env)
    out = _out(second)
    _assert_uninstall_clean(second)
    assert "removed:" not in out, out
    assert "nothing to uninstall" in out, out


# ── custom install dir scope: wrapper, lib tree, rules, rc line ───────────


@pytest.mark.standalone_cli
def test_uninstall_custom_scope_removes_every_target(tmp_path: Path) -> None:
    """A custom TERMINAL_JAIL_INSTALL_DIR install removes the wrapper, the
    <prefix>/lib/terminal-jail tree, the resolved rules dir contents, and the
    '# terminal-jail' PATH block from the seeded rc file."""
    env = _env(tmp_path)
    home = tmp_path / "home"
    install_dir = tmp_path / "bin"
    rules_dir = tmp_path / "rules.d"
    rc = home / ".bashrc"
    rc.write_text("# scratch rc\n", encoding="utf-8")

    install = _run(tmp_path, "--rule-pack", "db", env=env)
    assert install.returncode == 0, _out(install)
    assert (install_dir / "terminal-jail").exists(), _out(install)
    assert (install_dir.parent / "lib" / "terminal-jail" / "plugin").is_dir(), _out(
        install
    )
    assert (rules_dir / "terminal-jail-pack-db.yaml").exists(), _out(install)
    assert f'export PATH="{install_dir}:$PATH"' in rc.read_text(encoding="utf-8")

    uninstall = _run(tmp_path, "--uninstall", env=env)
    out = _out(uninstall)
    _assert_uninstall_clean(uninstall)
    assert (install_dir / "terminal-jail").exists() is False, out
    assert (install_dir.parent / "lib" / "terminal-jail").exists() is False, out
    assert (rules_dir / "terminal-jail-pack-db.yaml").exists() is False, out
    rc_text = rc.read_text(encoding="utf-8")
    assert "terminal-jail" not in rc_text, rc_text
    assert f"removed rc-line: {rc}" in out, out


# ── flag hygiene ───────────────────────────────────────────────────────────


@pytest.mark.standalone_cli
def test_uninstall_help_documents_the_flags(tmp_path: Path) -> None:
    result = _run(tmp_path, "--help", env=_home_env(tmp_path))
    out = _out(result)
    assert result.returncode == 0, out
    assert "--uninstall" in out, out
    assert "--uninstall-systemd" in out, out
    assert "left in place" in out or "PRESERVED" in out, out


@pytest.mark.standalone_cli
@pytest.mark.parametrize(
    "args",
    [
        ("--uninstall", "--rule-pack", "db"),
        ("--uninstall", "--unrule-pack", "db"),
        ("--uninstall", "--list-rule-packs"),
        ("--uninstall-systemd",),
    ],
)
def test_uninstall_rejects_bad_combinations_before_writing(
    tmp_path: Path, args
) -> None:
    """Parse-time refusals: rc 2, nothing written anywhere."""
    env = _env(tmp_path)
    home = tmp_path / "home"
    install_dir = tmp_path / "bin"
    result = _run(tmp_path, *args, env=env)
    out = _out(result)
    assert result.returncode == 2, out
    assert "cannot be combined" in out or "only means something together" in out, out
    assert list(install_dir.iterdir()) == [], sorted(
        p.name for p in install_dir.iterdir()
    )
    assert _home_tj_files(home) == []


@pytest.mark.standalone_cli
def test_unrule_pack_still_works_unchanged(tmp_path: Path) -> None:
    """--unrule-pack keeps its scoped single-file contract next to the new
    --uninstall verb: only terminal-jail-pack-<name>.yaml is removed."""
    env = _env(tmp_path)
    rules_dir = tmp_path / "rules.d"
    install = _run(tmp_path, "--rule-pack", "db", env=env)
    assert install.returncode == 0, _out(install)

    result = _run(tmp_path, "--unrule-pack", "db", env=env)
    out = _out(result)
    assert result.returncode == 0, out
    assert (rules_dir / "terminal-jail-pack-db.yaml").exists() is False, out
    assert (rules_dir / "00-builtins.yaml").exists(), out
    assert (tmp_path / "bin" / "terminal-jail").exists(), out
