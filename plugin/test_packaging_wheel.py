"""Wheel packaging contract pins (RELPKG-001).

The wheel must be a complete, self-sufficient install: a ``terminal-jail``
console script, the standalone bash CLI plus the three tier loaders shipped
byte-identically as package data, and ``loader_path()`` (fs and net) able to
resolve the bundled copies in an installed wheel. These pins read the source
tree only — no wheel is built here and nothing touches the network; the
fresh-venv build/install probe is the foreman's separate leg. The fast
pyproject/layout pins for the editable install live in test_packaging.py
(TJ-DF-006).
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = PROJECT_ROOT / "plugin" / "terminal_jail"
BUNDLED_DIR = PACKAGE_DIR / "_bundled"

# name inside _bundled/ -> authoritative source in standalone/
BUNDLED_FILES = {
    "terminal-jail": PROJECT_ROOT / "standalone" / "terminal-jail",
    "landlock-loader.py": PROJECT_ROOT / "standalone" / "landlock-loader.py",
    "landlock-net-loader.py": PROJECT_ROOT / "standalone" / "landlock-net-loader.py",
    "seccomp-loader.py": PROJECT_ROOT / "standalone" / "seccomp-loader.py",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pyproject() -> dict:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _load_by_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # before exec_module (dataclass hint walk)
    spec.loader.exec_module(module)
    return module


class TestConsoleScript:
    def test_project_scripts_declare_terminal_jail(self) -> None:
        scripts = _pyproject()["project"]["scripts"]
        assert scripts["terminal-jail"] == "terminal_jail.cli:main"

    def test_entry_module_exposes_main(self) -> None:
        from terminal_jail.cli import main

        assert callable(main)


class TestBundledPackageData:
    def test_package_data_globs_cover_bundled_tree(self) -> None:
        data = _pyproject()["tool"]["setuptools"]["package-data"]["terminal_jail"]
        assert "rules/*.yaml" in data  # the existing contract stays shipped
        assert "_bundled/*" in data

    def test_bundled_copies_are_byte_identical_to_standalone(self) -> None:
        for name, source in BUNDLED_FILES.items():
            bundled = BUNDLED_DIR / name
            assert bundled.is_file(), f"missing bundled copy: {name}"
            assert source.is_file(), f"missing standalone source: {source}"
            assert _sha256(bundled) == _sha256(source), (
                f"bundled {name} drifted from {source}"
            )

    def test_bundled_cli_keeps_env_bash_shebang(self) -> None:
        # TJ-GAP-060: install.sh's integrity check rejects any other shebang;
        # the bundled copy must carry the same constraint.
        first_line = (BUNDLED_DIR / "terminal-jail").open("rb").readline()
        assert first_line == b"#!/usr/bin/env bash\n"


class TestWheelLoaderResolution:
    def test_fs_loader_path_falls_back_to_bundled_wheel_layout(
        self, tmp_path: Path
    ) -> None:
        self._assert_bundled_fallback(tmp_path, "landlock.py", "landlock-loader.py")

    def test_net_loader_path_falls_back_to_bundled_wheel_layout(
        self, tmp_path: Path
    ) -> None:
        self._assert_bundled_fallback(
            tmp_path, "landlock_net.py", "landlock-net-loader.py"
        )

    @staticmethod
    def _assert_bundled_fallback(
        tmp_path: Path, module_name: str, loader_name: str
    ) -> None:
        # Wheel layout: module at <site>/terminal_jail/interruptor/<m>.py,
        # bundled loader at <site>/terminal_jail/_bundled/<loader>. A
        # standalone/ dir appears NOWHERE up the tree, so only the bundled
        # fallback can resolve — while the repository checkout keeps hitting
        # its own standalone/ first (pinned by test_landlock.py).
        pkg_root = tmp_path / "site" / "terminal_jail"
        (pkg_root / "interruptor").mkdir(parents=True)
        (pkg_root / "_bundled").mkdir()
        (pkg_root / "_bundled" / loader_name).write_text("# bundled copy\n")
        # Both siblings land in the synthetic tree: landlock_net.py's by-path
        # import resolves landlock.py NEXT TO ITSELF when no package context
        # exists (landlock_net.py's ImportError fallback branch).
        for sibling in ("landlock.py", module_name):
            (pkg_root / "interruptor" / sibling).write_text(
                (PACKAGE_DIR / "interruptor" / sibling).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        module_file = pkg_root / "interruptor" / module_name
        module_id = f"tj_wheel_layout_{module_name.replace('.', '_')}"
        try:
            module = _load_by_path(module_id, module_file)
            found = module.loader_path()
            assert found == str(pkg_root / "_bundled" / loader_name)
        finally:
            sys.modules.pop(module_id, None)
