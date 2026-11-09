"""Wheel packaging contract pins (RELPKG-001).

The wheel must be a complete, self-sufficient install: a ``terminal-jail``
console script, the standalone bash CLI plus the three tier loaders shipped
byte-identically as package data, and ``loader_path()`` (fs and net) able to
resolve the bundled copies in an installed wheel. These pins read the source
tree only — no wheel is built here and nothing touches the network; the
fresh-venv build/install probe is the foreman's separate leg. The fast
pyproject/layout pins for the editable install live in test_packaging.py
(TJ-DF-006). The TJ-DF-061 pins are the exception in DEPTH, not in
network use: they drive the console script END-TO-END from a synthetic
installed-wheel venv (stdlib ``venv`` module plus a file copy — still no
pip, no network) with the venv absent from PATH.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest import mock

import pytest

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


# pip console_scripts shape (REPLPKG-001): the generated wrapper is exec'd
# under the INSTALLING interpreter, so sys.executable IS the venv python —
# the property TJ-DF-061 hands to the wrapper via TERMINAL_JAIL_PYTHON.
_CONSOLE_SCRIPT_TEMPLATE = """#!{python}
# -*- coding: utf-8 -*-
import re
import sys
from terminal_jail.cli import main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
    sys.exit(main())
"""


def _build_installed_venv(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Synthetic installed-wheel venv: stdlib ``venv`` module + file copy.

    The real pip install stays the foreman's separate leg (RELPKG-001);
    this reproduces the installed SHAPE deterministically and offline: the
    package tree copied into the venv's site-packages (so the venv python
    imports ``terminal_jail`` from the INSTALL, not the checkout — proven
    absent before the copy) and a pip-shaped console script at
    ``<venv>/bin/terminal-jail``. ``system_site_packages`` lets the venv
    interpreter resolve PyYAML the same way the installing interpreter
    did. Returns (venv_dir, console_script, site_packages).
    """
    import venv as venv_module

    venv_dir = tmp_path / "venv"
    venv_module.create(venv_dir, with_pip=False, system_site_packages=True)
    venv_python = venv_dir / "bin" / "python3"
    assert venv_python.is_file(), f"venv has no bin/python3: {venv_dir}"
    site = (
        venv_dir
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    assert site.is_dir(), f"unexpected venv layout: no site-packages at {site}"
    assert not (site / "terminal_jail").exists(), "fixture venv not clean"
    shutil.copytree(
        PACKAGE_DIR,
        site / "terminal_jail",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    console = venv_dir / "bin" / "terminal-jail"
    console.write_text(
        _CONSOLE_SCRIPT_TEMPLATE.format(python=venv_python), encoding="utf-8"
    )
    console.chmod(0o755)
    return venv_dir, console, site


def _unactivated_testbin(base: Path) -> str:
    """Minimal PATH for the unactivated-venv invocation shape.

    bash, uname, true, grep, head, echo (+ unshare when present) — NO
    python3 and NO venv bin. The venv-bin absence IS the defect's
    invocation shape (absolute console-script path, venv not activated);
    python3's absence too makes the pins independent of whatever python
    the host PATH would supply: after the fix the bridge path needs only
    TERMINAL_JAIL_PYTHON, and on pre-fix code the bridge invocation fails
    closed loudly. grep/head serve the --user launch tail's subuid reads
    and echo is the payload (exec resolves it from PATH inside the
    namespace — builtins do not apply after `exec`).
    """
    test_bin = base / "testbin"
    test_bin.mkdir(exist_ok=True)
    for name in ("bash", "uname", "true", "grep", "head", "echo"):
        source = shutil.which(name)
        assert source, f"test host lacks {name}"
        (test_bin / name).symlink_to(source)
    unshare = shutil.which("unshare")
    if unshare:
        (test_bin / "unshare").symlink_to(unshare)
    return str(test_bin)


def _unactivated_env(test_bin: str) -> dict[str, str]:
    """Scrubbed env: no inherited TERMINAL_JAIL_* (the wrapper keeps those
    verbatim), the minimal PATH, and the Landlock tiers off — the subject
    is the BRIDGE interpreter handoff (TJ-DF-061), not the tier launch
    tails, which resolve python3 from PATH by design."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("TERMINAL_JAIL_")}
    env["PATH"] = test_bin
    env["TERMINAL_JAIL_LANDLOCK"] = "0"
    env["TERMINAL_JAIL_LANDLOCK_NET"] = "0"
    return env


def _run_console(
    console: Path, base: Path, test_bin: str, *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(console), *args],
        cwd=str(base),
        env=_unactivated_env(test_bin),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _verdict_log_entries(stderr: str) -> list[dict]:
    """Decode the bridge's per-verdict structured stderr log lines
    (REVIEW-TJ-015). Everything else on the stderr surface (proc_view
    attribution, tier banners) is not a verdict record."""
    entries: list[dict] = []
    for line in stderr.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event") == "verdict":
            entries.append(payload)
    return entries


class TestUnactivatedVenvBridgeInterpreter:
    """TJ-DF-061 — the firewall works from an UNACTIVATED venv install.

    A wheel's console script runs under the installing interpreter, whose
    ``sys.executable`` is the venv python; the venv bin is typically NOT
    on PATH (no activation). The wrapper's bridge path — module
    discovery, bridge execution, and the verdict JSON helpers — must
    therefore run under the interpreter the entry point hands it via
    ``TERMINAL_JAIL_PYTHON``: the engine and PyYAML live in that venv.
    Every console-script invocation here is the ABSOLUTE path with a
    minimal PATH containing neither the venv bin nor any python3. The
    launch-requiring arms run in whatever launch shape the host supports
    (bare mode, or the established --user degradation) and skip only when
    the host denies namespaces outright (HOST-DEGRADED-PIDNS, TJ-GAP-042);
    the verdict-path arms run on every Linux host.
    """

    # ch:trace row=TJ-DF-061 spec=board:TJ-DF-061 wave=none:serial test=plugin/test_packaging_wheel.py::TestUnactivatedVenvBridgeInterpreter::test_allow_verdict_runs_command_with_venv_absent_from_path evidence=plugin/test_packaging_wheel.py witness=none:worker-local verdict=PASS:cf28005b evidence=.gitreins/history/2026-11-09/cf28005b/verdict.json commit=15fe8f9b7858e29f5f79f3c1e68255693bcec181 memory=none:foreman-closeout-pending

    @pytest.mark.standalone_cli
    def test_allow_verdict_runs_command_with_venv_absent_from_path(
        self, run_unactivated, launch_mode: tuple[str, ...] | None
    ) -> None:
        if launch_mode is None:
            pytest.skip(
                "HOST-DEGRADED-PIDNS: no namespace support — the launch arm "
                "cannot run on this host"
            )
        result = run_unactivated(*launch_mode, "echo", "tj-df061-allow")
        assert result.returncode == 0, result.stderr
        assert "tj-df061-allow" in result.stdout
        # The defect's signature — the fail-closed [bridge-error] verdict.
        assert "[bridge-error]" not in result.stderr
        assert "COMMAND BLOCKED" not in result.stderr
        # The allow verdict carries a rule_id: the bridge's structured
        # verdict log names the shipped catalog rule that allowed it.
        verdicts = _verdict_log_entries(result.stderr)
        assert verdicts, f"no verdict log entry on stderr: {result.stderr!r}"
        assert verdicts[0].get("action") == "allow"
        assert verdicts[0].get("rule_id") == "allow-echo"

    @pytest.mark.standalone_cli
    def test_builtin_rm_rf_root_still_blocks_with_venv_absent_from_path(
        self, run_unactivated
    ) -> None:
        # The block verdict fires BEFORE any namespace work, so this arm
        # runs on every Linux host — no launch-mode skip. The provenance
        # assertion pins the shipped catalog id: the engine saw the real
        # rule, not a [bridge-error] envelope.
        result = run_unactivated("rm", "-rf", "/")
        assert result.returncode == 126, result.stderr
        assert "COMMAND BLOCKED" in result.stderr
        assert "[bridge-error]" not in result.stderr
        assert "builtin-rm-rf-root" in result.stderr

    @pytest.mark.standalone_cli
    def test_no_interruptor_behaviour_unchanged_with_venv_absent_from_path(
        self, run_unactivated, launch_mode: tuple[str, ...] | None
    ) -> None:
        if launch_mode is None:
            pytest.skip(
                "HOST-DEGRADED-PIDNS: no namespace support — the launch arm "
                "cannot run on this host"
            )
        result = run_unactivated(
            *launch_mode, "--no-interruptor", "echo", "tj-df061-noi"
        )
        assert result.returncode == 0, result.stderr
        assert "tj-df061-noi" in result.stdout
        # The bridge is never invoked: no verdict log line on stderr.
        assert _verdict_log_entries(result.stderr) == []

    @pytest.mark.standalone_cli
    def test_explicit_missing_interpreter_fails_loudly_without_fallback(
        self,
        wheel_install: tuple[Path, Path, Path],
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        console = wheel_install[1]
        base = tmp_path_factory.mktemp("tjdf061-badpy")
        test_bin = _unactivated_testbin(base)
        env = _unactivated_env(test_bin)
        env["TERMINAL_JAIL_PYTHON"] = str(base / "nonexistent" / "python3")
        result = subprocess.run(
            [str(console), "echo", "tj-df061-must-not-run"],
            cwd=str(base),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 126, result.stderr
        assert "COMMAND BLOCKED" in result.stderr
        assert "interruptor-bridge-unavailable" in result.stderr
        # No silent fallback: the command never ran, and the operator's
        # nonexistent interpreter was honored (had the entry point or the
        # wrapper replaced it with a working python, rc would be 0).
        assert "tj-df061-must-not-run" not in result.stdout

    def test_entry_point_exports_installing_interpreter_unless_overridden(
        self,
    ) -> None:
        """The cli.py seam in-process: sys.executable exported under the
        dedicated variable only when the operator has not set one."""
        from terminal_jail import cli as cli_module

        seeded = {
            "TERMINAL_JAIL_VERSION": "0-tjdf061-test",
            "TERMINAL_JAIL_SECCOMP_LOADER": "/tjdf061-unused",
            "TERMINAL_JAIL_LANDLOCK_LOADER": "/tjdf061-unused",
            "TERMINAL_JAIL_LANDLOCK_NET_LOADER": "/tjdf061-unused",
            "TERMINAL_JAIL_BRIDGE": "/tjdf061-unused",
        }
        with mock.patch.dict(os.environ, seeded):
            os.environ.pop("TERMINAL_JAIL_PYTHON", None)
            cli_module._apply_bundled_environment()
            assert os.environ["TERMINAL_JAIL_PYTHON"] == sys.executable
        with mock.patch.dict(
            os.environ, {**seeded, "TERMINAL_JAIL_PYTHON": "/operator/python3"}
        ):
            cli_module._apply_bundled_environment()
            assert os.environ["TERMINAL_JAIL_PYTHON"] == "/operator/python3"


@pytest.fixture(scope="module")
def wheel_install(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path]:
    return _build_installed_venv(tmp_path_factory.mktemp("tjdf061-venv"))


@pytest.fixture(scope="module")
def run_unactivated(
    wheel_install: tuple[Path, Path, Path],
    tmp_path_factory: pytest.TempPathFactory,
):
    console = wheel_install[1]
    base = tmp_path_factory.mktemp("tjdf061-run")
    test_bin = _unactivated_testbin(base)

    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return _run_console(console, base, test_bin, *args)

    return _run


@pytest.fixture(scope="module")
def launch_mode(
    wheel_install: tuple[Path, Path, Path],
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[str, ...] | None:
    """The launch shape this host supports, probed through the fixture:
    ``()`` = bare mode (unshare --mount-proc works), ``("--user",)`` = the
    established degraded fallback (user namespaces only — still a REAL
    launch: the bridge verdict path is identical, only the launch tail
    differs), ``None`` = no namespace support at all → launch arms skip
    (HOST-DEGRADED-PIDNS). A healthy host also proves the whole console
    chain (entry point → exports → wrapper → bridge → verdict → launch)
    before any arm runs; only a rc=2 degradation counts as degraded —
    anything else is a loud fixture failure, never a masked skip."""
    console = wheel_install[1]
    base = tmp_path_factory.mktemp("tjdf061-probe")
    test_bin = _unactivated_testbin(base)
    bare = _run_console(console, base, test_bin, "true")
    if bare.returncode == 0:
        return ()
    user_mode = _run_console(console, base, test_bin, "--user", "true")
    if user_mode.returncode == 0:
        return ("--user",)
    assert bare.returncode == 2 and user_mode.returncode == 2, (
        f"fixture probe failed unexpectedly (bare rc={bare.returncode}, "
        f"user rc={user_mode.returncode}): {bare.stderr!r} / {user_mode.stderr!r}"
    )
    return None
