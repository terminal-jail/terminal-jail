"""Version-parity gate tests (TJ-REVIEW-072 AC4).

The guard itself lives in ``scripts/check_version_parity.py``; it is the thing
the release checklist runs. These tests keep it honest:

* it passes on this tree (so a release bump that leaves no literals is green);
* it FAILS when a surface restates the version by hand (a temp tree is used so
  the checkout is never mutated), and names the offending ``file:line``;
* the fixture used for that failing arm passes while unmutated, so the red arm
  proves the literal is what trips the gate — not a broken fixture.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GUARD = PROJECT_ROOT / "scripts" / "check_version_parity.py"

# Exactly the surfaces the guard reads; everything else in the tree is noise.
FIXTURE_FILES = (
    "pyproject.toml",
    "plugin/plugin.yaml",
    "plugin/__init__.py",
    "plugin/terminal_jail/__init__.py",
    "plugin/terminal_jail/plugin.py",
    "scripts/metrics-export.py",
    "standalone/terminal-jail",
)


def run_guard(root: Path) -> subprocess.CompletedProcess[str]:
    """Run the guard against ``root`` and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(GUARD), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(root),
        timeout=180,
    )


def build_fixture(destination: Path) -> Path:
    """Copy the version surfaces into ``destination`` as a checkable tree."""
    for relative in FIXTURE_FILES:
        source = PROJECT_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    cli = destination / "standalone" / "terminal-jail"
    cli.chmod(0o755)
    return destination


def test_guard_passes_on_this_tree() -> None:
    """The shipped tree is parity-clean, so the release gate is green."""
    result = run_guard(PROJECT_ROOT)
    assert result.returncode == 0, result.stderr
    assert "RESULT: PASS" in result.stdout
    for surface in FIXTURE_FILES:
        assert surface in result.stdout, f"{surface} missing from guard report"


def test_guard_fails_on_a_hand_written_version_literal(tmp_path: Path) -> None:
    """A restated version is caught, and the guard names its file:line."""
    root = build_fixture(tmp_path / "clean")

    # Premise: the fixture itself is parity-clean, so the red arm is the literal.
    clean = run_guard(root)
    assert clean.returncode == 0, clean.stderr

    metrics = root / "scripts" / "metrics-export.py"
    original = metrics.read_text(encoding="utf-8")
    derived = 'd["version"] = package_version()'
    assert derived in original, "fixture must derive the exported version"
    metrics.write_text(
        original.replace(derived, 'd["version"] = "0.0.0"'), encoding="utf-8"
    )

    mutated = run_guard(root)
    assert mutated.returncode == 1, mutated.stdout
    assert "hand-written version literal '0.0.0'" in mutated.stderr
    assert "scripts/metrics-export.py:" in mutated.stderr
    assert "RESULT: FAIL" in mutated.stderr


def test_guard_fails_on_a_restated_banner_literal(tmp_path: Path) -> None:
    """A banner that restates the version is caught at its own file:line.

    This arm pins the two shapes a naive regex misses: the literal sits in an
    f-string part (FSTRING_MIDDLE on 3.12+) and it carries the conventional
    ``v`` prefix, whose leading word character defeats a plain
    ``(?<![\\w.])`` lookbehind.
    """
    root = build_fixture(tmp_path / "clean-banner")
    clean = run_guard(root)
    assert clean.returncode == 0, clean.stderr

    banner = root / "plugin" / "__init__.py"
    original = banner.read_text(encoding="utf-8")
    derived = 'f"terminal-jail v{package_version()} loaded. "'
    assert derived in original, "fixture banner must derive the version"
    banner.write_text(
        original.replace(derived, 'f"terminal-jail v1.3.4 loaded. "'),
        encoding="utf-8",
    )

    mutated = run_guard(root)
    assert mutated.returncode == 1, mutated.stdout
    assert "hand-written version literal 'v1.3.4'" in mutated.stderr
    assert "plugin/__init__.py:" in mutated.stderr
    assert "no load banner interpolating package_version()" in mutated.stderr
