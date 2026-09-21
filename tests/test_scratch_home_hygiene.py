"""Tests for scripts/scratch-home-hygiene.sh (DF-TERMINAL-JAIL-27).

A dogfood leg that redirects HOME into /tmp can let a tool write its own
credential file into the scratch tree; when that tree is group/world readable
the scratch area becomes a key store (the leaked
``/tmp/dogfood-tj/home/.bunker/config.yaml`` case). These tests pin the
checker's contract: a loose tree carrying a credential-shaped file fails, the
same file under 0700 is suppressed, a clean root exits 0, and the checker never
echoes file contents — only paths and mode strings.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKER = PROJECT_ROOT / "scripts" / "scratch-home-hygiene.sh"

# Obviously-fake credential value. The checker may print PATHS and MODE STRINGS
# only, so this string must never reach stdout or stderr.
SECRET_VALUE = "not-a-real-token-value"
SECRET_LINE = f"token: {SECRET_VALUE}"


# ── helpers ────────────────────────────────────────────────────────


def run_checker(scan_root: Path) -> subprocess.CompletedProcess[str]:
    """Run the checker against an explicit scan root (never the real /tmp)."""
    return subprocess.run(
        [str(CHECKER), str(scan_root)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT),
    )


def output_of(result: subprocess.CompletedProcess[str]) -> str:
    """Findings and the FAIL line may land on either stream."""
    return result.stdout + result.stderr


def make_scratch_dir(root: Path, name: str, mode: int) -> Path:
    """Create root/<name>, a ``dogfood-*`` scratch tree, at an explicit mode.

    ``Path.mkdir`` mode is masked by the umask, so the mode is set afterwards.
    """
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    return path


def write_credential_file(
    directory: Path,
    name: str,
    body: str,
    mode: int = 0o644,
) -> Path:
    """Write a credential-shaped fixture file at an explicit mode."""
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    os.chmod(path, mode)
    return path


# ── the checker itself ─────────────────────────────────────────────


def test_checker_ships_executable():
    """The hygiene checker is a runnable script, not just source."""
    assert CHECKER.is_file()
    assert os.access(CHECKER, os.X_OK)


def test_clean_scratch_root_exits_zero():
    """A clean (empty, 0700) scratch tree under the scan root is not a finding."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_scratch_dir(root, "dogfood-clean", 0o700)
        result = run_checker(root)
        assert result.returncode == 0, output_of(result)
        assert "FINDING" not in output_of(result)


# ── loose tree: credential file is a finding ───────────────────────


def test_loose_dir_with_world_readable_config_flags():
    """0755 scratch tree + world-readable config.yaml holding a token -> fail."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        scratch = make_scratch_dir(root, "dogfood-leak", 0o755)
        credential = write_credential_file(
            scratch / "home" / ".bunker",
            "config.yaml",
            SECRET_LINE + "\n",
        )
        result = run_checker(root)
        output = output_of(result)
        assert result.returncode != 0, output
        assert "FINDING" in output
        assert str(credential) in output
        assert "dir-mode=755" in output


def test_loose_dir_flags_credential_content_with_innocuous_name():
    """A credential-assignment line is a finding even under a harmless name."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        scratch = make_scratch_dir(root, "dogfood-content", 0o755)
        credential = write_credential_file(
            scratch,
            "notes.txt",
            f"api_key: {SECRET_VALUE}\n",
        )
        result = run_checker(root)
        output = output_of(result)
        assert result.returncode != 0, output
        assert str(credential) in output


def test_loose_dir_without_credential_shaped_files_is_clean():
    """A loose tree with no credential-shaped file makes no finding."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        scratch = make_scratch_dir(root, "dogfood-innocent", 0o755)
        write_credential_file(scratch, "readme.txt", "hello, no secrets\n")
        result = run_checker(root)
        assert result.returncode == 0, output_of(result)


# ── tight tree: permissions suppress the finding ───────────────────


def test_tight_dir_with_same_file_exits_zero():
    """The same credential file under 0700 is suppressed by tight perms."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        scratch = make_scratch_dir(root, "dogfood-tight", 0o700)
        write_credential_file(
            scratch / "home" / ".bunker",
            "config.yaml",
            SECRET_LINE + "\n",
        )
        result = run_checker(root)
        assert result.returncode == 0, output_of(result)
        assert "FINDING" not in output_of(result)


# ── privacy: contents are never echoed ─────────────────────────────


def test_checker_never_echoes_file_contents():
    """Findings report paths and modes only — never the credential value."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        loose = make_scratch_dir(root, "dogfood-loose", 0o755)
        write_credential_file(loose, "config.yaml", SECRET_LINE + "\n")
        tight = make_scratch_dir(root, "dogfood-tight", 0o700)
        write_credential_file(tight, "config.yaml", SECRET_LINE + "\n")

        result = run_checker(root)
        output = output_of(result)

        # The loose tree must be reported ...
        assert result.returncode != 0, output
        # ... and the value it contains must not be.
        assert SECRET_VALUE not in output
        assert "token:" not in output
