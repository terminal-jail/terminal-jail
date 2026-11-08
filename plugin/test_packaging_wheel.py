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
import os
import subprocess
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


class TestWheelLoaderModuleResolution:
    """TJ-DF-060 — the loaders' OWN search resolves the wheel layout.

    The bundled loader copies ship at ``<site>/terminal_jail/_bundled/``
    while the tier modules are SIBLINGS under
    ``<site>/terminal_jail/interruptor/``. The search walked only
    repo-shaped paths (``<current>/plugin/terminal_jail/interruptor`` and
    bare ``<current>``), so an installed wheel degraded BOTH tiers with
    the module-not-found warning. The fix adds ``<current>/interruptor``
    to the same walk. These pins prove both loaders RESOLVE AND EXECUTE
    the sibling module there (in-process, host-independent), that the
    real exec path stays free of the module-not-found warning, and that
    an ``interruptor`` directory WITHOUT the module still degrades
    loudly (the negative control — the test FAILS if the search ever
    resolves a module from a directory that has none).
    """

    # ch:trace row=TJ-DF-060 spec=none:dogfood-row wave=none:serial test=plugin/test_packaging_wheel.py::TestWheelLoaderModuleResolution::test_fs_loader_resolves_and_executes_sibling_module_in_wheel_layout doc=none:scope-fence evidence=none:worker-local-until-foreman-freezes witness=none:worker-branch verdict=none:open-finding commit=none:worker-commit memory=none:not-written

    @staticmethod
    def _build_wheel_tree(
        tmp_path: Path,
        loader_name: str,
        sibling_modules: tuple[str, ...],
        *,
        populate_interruptor: bool = True,
    ) -> tuple[Path, Path]:
        """The installed-wheel shape: <site>/terminal_jail/{interruptor,_bundled}."""
        pkg_root = tmp_path / "site" / "terminal_jail"
        (pkg_root / "interruptor").mkdir(parents=True)
        bundled = pkg_root / "_bundled"
        bundled.mkdir()
        (bundled / loader_name).write_text(
            (PROJECT_ROOT / "standalone" / loader_name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        if populate_interruptor:
            # Both siblings land in the synthetic tree: landlock_net.py's
            # by-path import resolves landlock.py NEXT TO ITSELF when no
            # package context exists (landlock_net.py's ImportError
            # fallback branch — the same behavior a real wheel relies on).
            for sibling in sibling_modules:
                (pkg_root / "interruptor" / sibling).write_text(
                    (PACKAGE_DIR / "interruptor" / sibling).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
        return bundled / loader_name, pkg_root / "interruptor"

    @staticmethod
    def _run_loader_from_wheel_tree(
        loader_copy: Path, tmp_path: Path, *payload: str, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(loader_copy), *payload],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=str(tmp_path),
            env=env,
        )

    @staticmethod
    def _find_via_loader_source(loader_copy: Path, func_name: str) -> object:
        """Execute the loader source with __file__ INSIDE the synthetic tree.

        The search derives everything from ``__file__``, so pointing a
        compiled copy of the real loader at the wheel-layout copy
        exercises the exact production function against the exact
        installed shape — no monkeypatching of the search itself.
        """
        namespace: dict[str, object] = {
            "__file__": str(loader_copy),
            "__name__": "tj_wheel_layout_probe",
        }
        exec(  # noqa: S102 — the loader is the unit under test
            compile(
                loader_copy.read_text(encoding="utf-8"),
                str(loader_copy),
                "exec",
            ),
            namespace,
        )
        return namespace[func_name]()

    def test_fs_loader_resolves_and_executes_sibling_module_in_wheel_layout(
        self, tmp_path: Path
    ) -> None:
        loader_copy, interruptor = self._build_wheel_tree(
            tmp_path, "landlock-loader.py", ("landlock.py",)
        )
        try:
            module = self._find_via_loader_source(loader_copy, "_find_landlock_module")
        finally:
            sys.modules.pop("terminal_jail_landlock_standalone", None)
        assert module is not None, (
            "the wheel-layout loader must resolve the SIBLING interruptor "
            "tier module (TJ-DF-060: the search never looked there)"
        )
        assert module.__file__ == str(interruptor / "landlock.py")  # type: ignore[attr-defined]
        assert callable(module.apply_tier)  # type: ignore[attr-defined]

    def test_net_loader_resolves_and_executes_sibling_module_in_wheel_layout(
        self, tmp_path: Path
    ) -> None:
        loader_copy, interruptor = self._build_wheel_tree(
            tmp_path, "landlock-net-loader.py", ("landlock.py", "landlock_net.py")
        )
        try:
            module = self._find_via_loader_source(
                loader_copy, "_find_landlock_net_module"
            )
        finally:
            sys.modules.pop("terminal_jail_landlock_net_standalone", None)
            sys.modules.pop("terminal_jail_landlock_fs_by_path", None)
        assert module is not None, (
            "the wheel-layout net loader must resolve the SIBLING "
            "interruptor tier module (TJ-DF-060)"
        )
        assert module.__file__ == str(interruptor / "landlock_net.py")  # type: ignore[attr-defined]
        assert callable(module.apply_net_tier)  # type: ignore[attr-defined]

    def test_fs_loader_exec_path_from_wheel_tree_has_no_module_not_found(
        self, tmp_path: Path
    ) -> None:
        loader_copy, _ = self._build_wheel_tree(
            tmp_path, "landlock-loader.py", ("landlock.py",)
        )
        env = dict(os.environ)
        env.pop("TERMINAL_JAIL_LANDLOCK", None)  # default: enabled
        result = self._run_loader_from_wheel_tree(
            loader_copy, tmp_path, "echo", "tj-wheel-fs-ok", env=env
        )
        assert result.returncode == 0
        assert "tj-wheel-fs-ok" in result.stdout
        assert "tier module not found next to the loader" not in result.stderr, (
            f"the wheel-layout loader must resolve the sibling tier module; "
            f"stderr={result.stderr!r}"
        )

    def test_net_loader_exec_path_from_wheel_tree_is_silent_when_disabled(
        self, tmp_path: Path
    ) -> None:
        loader_copy, _ = self._build_wheel_tree(
            tmp_path, "landlock-net-loader.py", ("landlock.py", "landlock_net.py")
        )
        env = dict(os.environ)
        env.pop("TERMINAL_JAIL_LANDLOCK_NET", None)  # default: off → silent
        result = self._run_loader_from_wheel_tree(
            loader_copy, tmp_path, "echo", "tj-wheel-net-ok", env=env
        )
        assert result.returncode == 0
        assert "tj-wheel-net-ok" in result.stdout
        # The tier is off AND the module resolves: NOTHING to report.
        assert "terminal-jail:" not in result.stderr, (
            f"a disabled, RESOLVED net tier must stay silent (no "
            f"module-not-found warning); stderr={result.stderr!r}"
        )

    def test_wheel_layout_interruptor_without_module_still_degrades_loudly(
        self, tmp_path: Path
    ) -> None:
        """Negative control: an ``interruptor`` SIBLING directory that
        holds no ``landlock.py`` must NOT satisfy the new search base —
        the loader warns (exit 0, payload unchanged). This test FAILS if
        the search ever resolves a module from a directory without one."""
        loader_copy, _ = self._build_wheel_tree(
            tmp_path,
            "landlock-loader.py",
            (),
            populate_interruptor=False,
        )
        env = dict(os.environ)
        env.pop("TERMINAL_JAIL_LANDLOCK", None)
        result = self._run_loader_from_wheel_tree(
            loader_copy, tmp_path, "echo", "tj-wheel-neg-ok", env=env
        )
        assert result.returncode == 0
        assert "tj-wheel-neg-ok" in result.stdout
        assert "tier module not found next to the loader" in result.stderr
