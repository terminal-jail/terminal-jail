"""TJ-REVIEW-076: the net tier's modify-path tail must carry the PINNED interpreter.

Defect (evidence run rev-2026-11-22-tj7, modpath-net1.txt): with
``TERMINAL_JAIL_LANDLOCK_NET=1`` the engine's modify wrap splices the net
tier's launch tail — ``python3 <net-loader> -- <payload>`` with a BARE
``python3`` — after the fs tier's tail. The wrapper's modify preflight
(``_tj_modify_tier_head_prepare``) splices the ``TERMINAL_JAIL_PYTHON``
pin over the FS head alone, so the net head was resolved by bash via PATH
INSIDE the fs tier's domain. On a host whose PATH ``python3`` is an
interpreter the domain can EXECUTE (the read_dir roots carry EXECUTE
beneath HOME) but not fully SERVE (its baked stdlib prefix lives under a
credential surface — the harness venv: ELF under ``~/.hermes/installs``,
stdlib base under ``~/.hermes/tools``, denied by omission), the net
loader died at its OWN encodings import — ``Failed to import encodings``
PermissionError — before the payload ever ran.

The direct exec path never had the defect: every wrapper trampoline
launches the net loader under ``"$_TJ_BRIDGE_PY"`` argv-wise. The fix
mirrors that mechanism at the single place the string tail is built
(``landlock_net._launch_interpreter``): same env var
(``TERMINAL_JAIL_PYTHON``), same default (bare ``python3`` when unset).

Host gates are stated, never assumed:

* Landlock ABI < 4 SKIPs the net-tier cells (the tier's own floor,
  ``landlock_net.NET_ABI_MIN``).
* The hostile-interpreter premise is PROVEN per host, not assumed: the
  fixture (a PATH ``python3`` that is executable inside the fs domain but
  whose stdlib is denied there) must reproduce the exact encodings
  symptom through the fs loader before the modify cells may depend on it.
  A host without such an interpreter SKIPs with a marker — the pin
  contract itself (``_launch_interpreter``) is still asserted everywhere.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from terminal_jail.interruptor import landlock_net as ln

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
FS_LOADER = PROJECT_ROOT / "standalone" / "landlock-loader.py"
RULES_MIRROR_DIR = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules"

pytestmark = pytest.mark.standalone_cli

HOST_LANDLOCK_ABV4 = (
    "HOST-LANDLOCK-ABV4: Landlock ABI < 4 — no kernel TCP connect rules here"
)
HOST_NO_HOSTILE_PYTHON = (
    "HOST-NO-HOSTILE-PYTHON: no interpreter on this PATH is executable "
    "inside the fs tier's domain while its stdlib is denied there, so the "
    "modify-path symptom is not reproducible here; the pin contract is "
    "still asserted by the unit cells"
)

# The payload's own connect verdict, printed by connect_probe.py: EACCES
# (13, kernel egress denial) or ECONNREFUSED (111, nothing listening on
# the probe port — the payload RAN). Both prove the interpreter started.
CONNECT_ERRNO = re.compile(r"errno=(13|111)\b")
ENCODINGS_KILL = "Failed to import encodings"
MODIFY_UNAVAILABLE = "auto-sandbox modify unavailable"

# The premise probe: a payload that only proves its stdlib is importable.
_STDLIB_PROBE = "import encodings, sys\nprint('STDLIB-OK')\n"

# The payload under test: connect to a bound-but-unallowlisted loopback
# port (9151 holds no listener) and print the errno it saw.
_CONNECT_PROBE = (
    "import socket, errno, sys\n"
    "s = socket.socket()\n"
    "try:\n"
    "    s.connect(('127.0.0.1', 9151))\n"
    "    print('connect-ok')\n"
    "except OSError as e:\n"
    "    print(f'errno={e.errno} kind={errno.errorcode.get(e.errno, '?')} "
    "msg={e.strerror}')\n"
)


def _require_net_host() -> None:
    if ln.abi_version() < ln.NET_ABI_MIN:
        pytest.skip(HOST_LANDLOCK_ABV4)


def _payload_python() -> str:
    """The system interpreter the fs tier's grants can fully serve."""
    for candidate in ("/usr/bin/python3", "/usr/local/bin/python3"):
        if os.path.exists(candidate):
            return candidate
    return shutil.which("python3") or sys.executable


def _base_env(**overrides: str) -> dict[str, str]:
    """A clean CLI environment: no ambient TERMINAL_JAIL_* leakage."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("TERMINAL_JAIL_")}
    env["TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR"] = str(RULES_MIRROR_DIR)
    env["TERMINAL_JAIL_INTERRUPTOR_RULES_DIR"] = str(RULES_MIRROR_DIR)
    env.update(overrides)
    return env


def _run_cli(*args: str, env: dict[str, str], timeout: int = 120):
    return subprocess.run(
        [str(CLI_SCRIPT), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


@pytest.fixture()
def probe_dir() -> Path:
    """A scratch dir whose path is free of 'pytest' (a probe path holding
    that token trips the auto-pytest rule instead of auto-script, changing
    the verdict arm under test)."""
    import tempfile

    d = Path(tempfile.mkdtemp(prefix="tj-076-netprefix-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _connect_probe_file(workdir: Path) -> Path:
    probe = workdir / "connect_probe.py"
    probe.write_text(_CONNECT_PROBE, encoding="utf-8")
    probe.chmod(0o644)
    return probe


def _hostile_python_dir() -> Path | None:
    """A PATH dir whose ``python3`` poisons getpath inside the fs domain.

    The defect's kill is NOT a failed exec of the hostile interpreter: the
    loader's ``os.execvp("python3")`` gets EACCES on the hostile candidate
    and glibc falls through to the next PATH python (a fully granted one,
    e.g. /usr/bin/python3). The kill happens INSIDE that survivor: with
    argv[0] lacking a slash, CPython getpath re-searches PATH using
    stat/access checks — which PASS for the hostile candidate even though
    execve is denied — lands on it (or on its venv cfg / baked stdlib
    prefix under a denied tree), and the interpreter dies importing
    encodings before any payload code runs. So the fixture is a PATH
    entry, proven by the premise cell below, never assumed.
    """
    ambient = shutil.which("python3")
    if not ambient:
        return None
    bindir = Path(ambient).resolve().parent
    if not (bindir / "python3").exists():
        return None
    return bindir


def _fs_domain_stdlib_dies(hostile_dir: Path, workdir: Path) -> bool:
    """True when a bare ``python3`` on this PATH dies with the exact
    encodings symptom inside the fs tier's domain (the TJ-REVIEW-076
    shape: loader execvp falls through to a granted interpreter whose
    getpath is poisoned by the hostile PATH entry)."""
    probe = workdir / "stdlib_probe.py"
    probe.write_text(_STDLIB_PROBE, encoding="utf-8")
    probe.chmod(0o644)
    env = _base_env(PATH=f"{hostile_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    try:
        proc = subprocess.run(
            [_payload_python(), str(FS_LOADER), "--", "python3", str(probe)],
            cwd=str(workdir),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False
    return ENCODINGS_KILL in proc.stderr and "STDLIB-OK" not in proc.stdout


@pytest.fixture()
def hostile_path(tmp_path: Path) -> str | None:
    """PATH with the hostile ``python3`` first — premise-proven."""
    hostile_dir = _hostile_python_dir()
    if hostile_dir is None:
        return None
    if not _fs_domain_stdlib_dies(hostile_dir, tmp_path):
        return None
    return f"{hostile_dir}{os.pathsep}{os.environ.get('PATH', '')}"


# --- The pin contract (unit, host-independent) --------------------------------


class TestLaunchInterpreterPin:
    def test_pin_carries_terminal_jail_python(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ln.BRIDGE_PYTHON_ENV, "/usr/bin/python3")
        assert ln._launch_interpreter() == "/usr/bin/python3"

    def test_unpinned_keeps_the_historical_python3(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ln.BRIDGE_PYTHON_ENV, raising=False)
        assert ln._launch_interpreter() == "python3"

    def test_empty_pin_keeps_the_historical_python3(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ln.BRIDGE_PYTHON_ENV, "   ")
        assert ln._launch_interpreter() == "python3"

    def test_pinned_token_stays_one_shell_word(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shlex

        monkeypatch.setenv(ln.BRIDGE_PYTHON_ENV, "/opt/py 3.14/bin/python3")
        token = ln._launch_interpreter()
        assert shlex.split(token) == ["/opt/py 3.14/bin/python3"]  # one word
        assert token.startswith("'") and token.endswith("'")


# --- The premise (proves the host can reproduce the defect shape) --------------


class TestHostilePremise:
    def test_hostile_premise(self, tmp_path: Path, hostile_path: str | None) -> None:
        if hostile_path is None:
            pytest.skip(HOST_NO_HOSTILE_PYTHON)
        # hostile_path's fixture already ran the fs-domain proof; this cell
        # only records that the premise held (a None return skips above).

    def test_fs_domain_serves_the_pinned_interpreter(self, tmp_path: Path) -> None:
        """Control: the PINNED interpreter's stdlib is readable in-domain."""
        _require_net_host()
        probe = tmp_path / "stdlib_probe.py"
        probe.write_text(_STDLIB_PROBE, encoding="utf-8")
        probe.chmod(0o644)
        proc = subprocess.run(
            [_payload_python(), str(FS_LOADER), "--", _payload_python(), str(probe)],
            cwd=str(tmp_path),
            env=_base_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        assert "STDLIB-OK" in proc.stdout
        assert ENCODINGS_KILL not in proc.stderr


# --- The arms (full CLI, both verdict paths) -----------------------------------


class TestModifyPathNetTier:
    def test_net_on_modify_reaches_the_payload_connect(
        self, probe_dir: Path, hostile_path: str | None
    ) -> None:
        """The money cell: NET=1 modify must run the PAYLOAD's connect.

        Pre-fix this died at the net loader's own encodings import when
        the PATH ``python3`` was the fs domain's blind interpreter; the
        pinned tail must leave that PATH entry irrelevant.
        """
        _require_net_host()
        if hostile_path is None:
            pytest.skip(HOST_NO_HOSTILE_PYTHON)
        probe = _connect_probe_file(probe_dir)
        env = _base_env(
            TERMINAL_JAIL_LANDLOCK_NET="1",
            TERMINAL_JAIL_PYTHON=_payload_python(),
            PATH=hostile_path,
        )
        proc = _run_cli(_payload_python(), str(probe), env=env)
        combined = proc.stdout + proc.stderr
        assert '"action":"modify"' in combined
        assert MODIFY_UNAVAILABLE not in combined
        assert ENCODINGS_KILL not in combined
        assert "PermissionError" not in combined
        assert CONNECT_ERRNO.search(combined), combined

    def test_net_off_modify_control_reaches_econnrefused(
        self, probe_dir: Path, hostile_path: str | None
    ) -> None:
        """Control: NET=0 modify runs the payload to ECONNREFUSED."""
        if hostile_path is None:
            pytest.skip(HOST_NO_HOSTILE_PYTHON)
        probe = _connect_probe_file(probe_dir)
        env = _base_env(
            TERMINAL_JAIL_LANDLOCK_NET="0",
            TERMINAL_JAIL_PYTHON=_payload_python(),
            PATH=hostile_path,
        )
        proc = _run_cli(_payload_python(), str(probe), env=env)
        combined = proc.stdout + proc.stderr
        assert '"action":"modify"' in combined
        assert MODIFY_UNAVAILABLE not in combined
        assert ENCODINGS_KILL not in combined
        assert "errno=111" in combined, combined


class TestExecPathNetTier:
    def test_net_on_exec_path_keeps_its_good_behavior(
        self, probe_dir: Path, hostile_path: str | None
    ) -> None:
        """The allow path (python3.14 defeats the auto-script regex) was
        never affected — the trampolines pin argv-wise; it must stay so."""
        _require_net_host()
        if hostile_path is None:
            pytest.skip(HOST_NO_HOSTILE_PYTHON)
        interp = "/usr/bin/python3.14"
        if not os.path.exists(interp):
            pytest.skip(f"HOST-NO-{interp}")
        probe = _connect_probe_file(probe_dir)
        env = _base_env(
            TERMINAL_JAIL_LANDLOCK_NET="1",
            TERMINAL_JAIL_PYTHON=_payload_python(),
            PATH=hostile_path,
        )
        proc = _run_cli(interp, str(probe), env=env)
        combined = proc.stdout + proc.stderr
        assert '"action":"allow"' in combined
        assert ENCODINGS_KILL not in combined
        assert "errno=13" in combined, combined
