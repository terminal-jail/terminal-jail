from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
        return tomllib.load(project_file)["project"]["version"]


def test_standalone_reports_pyproject_version() -> None:
    result = subprocess.run(
        [str(PROJECT_ROOT / "standalone" / "terminal-jail"), "--version"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "TERMINAL_JAIL_VERSION": ""},
        timeout=10,
    )

    assert result.stdout.strip() == f"terminal-jail {_project_version()}"


def test_standalone_version_override_still_works() -> None:
    result = subprocess.run(
        [str(PROJECT_ROOT / "standalone" / "terminal-jail"), "--version"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "TERMINAL_JAIL_VERSION": "test-override"},
        timeout=10,
    )

    assert result.stdout.strip() == "terminal-jail test-override"


def test_plugin_manifest_version_matches_pyproject() -> None:
    manifest = (PROJECT_ROOT / "plugin" / "plugin.yaml").read_text(encoding="utf-8")
    match = re.search(r'^version:\s*["\']?([^"\'\s]+)', manifest, re.MULTILINE)

    assert match is not None, "plugin/plugin.yaml must declare a version"
    assert match.group(1) == _project_version()
