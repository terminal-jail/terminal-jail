"""TJ-DF-046 — the Landlock egress tier must engage on the PLAIN-ALLOW path.

The defect: the engine composes the TCP-connect (egress) loader
(``standalone/landlock-net-loader.py``, TJ-GAP-083) into its auto-sandbox
REWRITES only — ``decider.py::_wrap_payload`` composes both loader tails, and
that payload only ever runs on an ``action=modify`` verdict. A ``rule_id=null``
verdict (a command matching NO rule) therefore ran the payload with the net
tier never attached: CONNECTED to every non-allowlisted TCP port, contradicting
the README's kernel-deny contract — "with ``TERMINAL_JAIL_LANDLOCK_NET=1``,
every ``connect(2)`` to a TCP port outside the allowlist fails EPERM/EACCES at
the kernel ... even when the command string matches no egress regex (a raw
``python3 -c "socket...connect(...)"``)".

Three layers, in this repo's usual shape:

* :class:`TestWiring` — host-independent: the wrapper resolves the egress
  loader next to itself (hyphenated name, same walk as the fs loader), parses
  the opt-in knob, and calls the attach decision ahead of every non-rewritten
  payload exec; the filesystem tier's own seam is untouched.
* :class:`TestLaunchShape` — host-independent, PATH-stub proof of the argv the
  launcher receives: with the knob on, ``python3 <landlock-net-loader.py> --``
  sits ahead of the payload; the fs tier, when it also attaches, composes
  around it (egress OUTERMOST, filesystem innermost — a Landlock domain can
  only be INTERSECTED, so the payload's restrictions are identical either way,
  and the innermost position keeps the chain startable); the readability
  preflight runs with the launch's own flags BEFORE the wrap; a missing or
  unreadable loader degrades LOUDLY instead of attaching.
* :class:`TestLive` — host-conditional: the documented ``python3 -c
  socket.connect`` payload against a bound, non-allowlisted loopback port
  (controls included, so a harness that never runs anything cannot pass).

Host gates are stated, never assumed: a host that cannot launch a payload
through the CLI (the fail-closed namespace preflight, rc=2) SKIPs the live
cells with a marker, and the enforcement arm SKIPs when Landlock ABI < 4 (the
tier's own floor, ``landlock_net.NET_ABI_MIN``).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from terminal_jail.interruptor import landlock_net as ln

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
NET_LOADER = PROJECT_ROOT / "standalone" / "landlock-net-loader.py"
FS_LOADER = PROJECT_ROOT / "standalone" / "landlock-loader.py"
RULES_MIRROR_DIR = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules"

pytestmark = pytest.mark.standalone_cli

HOST_LANDLOCK_ABV4 = (
    "HOST-LANDLOCK-ABV4: Landlock ABI < 4 — no kernel TCP connect rules here"
)
HOST_DENIED_NAMESPACE = (
    "HOST-DENIED-NAMESPACE: this CLI cannot launch a payload here (its "
    "fail-closed namespace preflight exits 2), so the allow-path egress "
    "contract is unreachable; the refusal is never a silent CONNECTED run"
)

# Curated PATH stub for the launcher: it records its full argv (NUL-terminated
# tokens, "EOR" record marker) and then EXECUTES the command it was asked to
# run, so the wrapper's real dispatch — probe, wrap decision, trampoline — runs
# end to end without needing a kernel namespace.
_LAUNCHER_STUB = """#!/usr/bin/env bash
log="${TJ_DF046_STUB_LOG:?}"
for a in "$@"; do printf '%s\\0' "$a" >> "$log"; done
printf 'EOR\\0' >> "$log"
args=("$@")
i=0
while [ "$i" -lt "${#args[@]}" ]; do
    case "${args[$i]}" in
        --) i=$((i + 1)); break ;;
        -*) i=$((i + 1)) ;;
        *) break ;;
    esac
done
exec "${args[@]:$i}"
"""


def _payload_python() -> str:
    """An interpreter that also starts under the filesystem tier's domain.

    The wrapper's own loaders are launched with ``python3`` from PATH; the
    PAYLOAD here uses the system interpreter so the fs tier's own file grants
    (system paths, the working tree, temp) cannot make the cells depend on a
    venv under a home the tier denies.
    """
    for candidate in ("/usr/bin/python3", "/usr/local/bin/python3"):
        if os.path.exists(candidate):
            return candidate
    return shutil.which("python3") or sys.executable


def _base_env() -> dict[str, str]:
    """An explicit CLI environment: no ambient TERMINAL_JAIL_* leakage.

    The engine's rules dirs are pinned at the shipped mirror so the verdict is
    the engine's own, independent of whatever this host has installed under
    ``~/.config/terminal-jail/rules.d``.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("TERMINAL_JAIL_")}
    env["TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR"] = str(RULES_MIRROR_DIR)
    env["TERMINAL_JAIL_INTERRUPTOR_RULES_DIR"] = str(RULES_MIRROR_DIR)
    return env


def _stub_launcher_path(tmp_path: Path) -> tuple[str, Path]:
    """PATH with recording ``unshare``/``bwrap`` stubs ahead of the real one."""
    bindir = tmp_path / "stub-bin"
    bindir.mkdir(exist_ok=True)
    for name in ("unshare", "bwrap"):
        stub = bindir / name
        stub.write_text(_LAUNCHER_STUB, encoding="utf-8")
        stub.chmod(0o755)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}", bindir


def _run_cli(*args: str, env: dict[str, str], timeout: int = 60):
    return subprocess.run(
        [str(CLI_SCRIPT), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _records(log: Path) -> list[list[str]]:
    """Parse the stub's argv log: NUL-terminated args, "EOR" ends a record."""
    if not log.exists():
        return []
    records: list[list[str]] = []
    current: list[bytes] = []
    for token in log.read_bytes().split(b"\0"):
        if token == b"EOR":
            records.append([t.decode("utf-8", "replace") for t in current])
            current = []
        else:
            current.append(token)
    return records


def _payload_argv(record: list[str]) -> list[str]:
    """The argv the trampoline receives: `bash -c 'exec "$@"' terminal-jail ...`.

    Indexed from the trampoline itself so the helper works for both backends
    (bubblewrap separates options from the payload with `--`, unshare does not).
    """
    return record[record.index("bash") :]


def _launch_records(log: Path) -> list[list[str]]:
    return [r for r in _records(log) if "bash" in r]


class _Listener:
    """A loopback TCP listener on a kernel-chosen, non-allowlisted port."""

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            conn.close()

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=3)


@pytest.fixture()
def listener():
    server = _Listener()
    try:
        yield server
    finally:
        server.close()


def _connect_payload(port: int) -> str:
    return (
        "import socket;s=socket.socket();s.settimeout(2);"
        f"s.connect(('127.0.0.1',{port}));print('CONNECTED')"
    )


def _cli_runs_a_payload(env: dict[str, str]) -> bool:
    """True when this host's CLI actually launches a command (not rc=2)."""
    result = _run_cli("echo", "tj-df-046-canary", env=env)
    return result.returncode == 0 and "tj-df-046-canary" in result.stdout


# ── Wiring: the wrapper carries the allow-path attach ────────────────────────


class TestWiring:
    def test_wrapper_resolves_the_egress_loader_next_to_itself(self) -> None:
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert 'LANDLOCK_NET_LOADER="${TERMINAL_JAIL_LANDLOCK_NET_LOADER:-}"' in text
        assert '"${SCRIPT_DIR}/landlock-net-loader.py"' in text
        assert '"${INSTALLED_LIB_DIR}/landlock-net-loader.py"' in text
        # The fs loader's own resolution stays exactly where it was.
        assert 'LANDLOCK_LOADER="${TERMINAL_JAIL_LANDLOCK_LOADER:-}"' in text
        assert '"${SCRIPT_DIR}/landlock-loader.py"' in text

    def test_net_loader_resolution_uses_the_hyphenated_name(self) -> None:
        """The egress loader is landlock-net-loader.py — never the fs loader."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        start = text.index(
            'LANDLOCK_NET_LOADER="${TERMINAL_JAIL_LANDLOCK_NET_LOADER:-}"'
        )
        end = text.index("TJ_LANDLOCK_NET_ON=0")
        block = text[start:end]
        assert "landlock-net-loader.py" in block
        assert "landlock-loader.py" not in block, (
            "the egress loader resolution names the filesystem loader"
        )

    def test_wrapper_parses_the_opt_in_knob(self) -> None:
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert 'case "${TERMINAL_JAIL_LANDLOCK_NET:-}" in' in text
        assert "1|true|yes|on|" in text  # truthy spellings, engine-identical
        # The fs tier's knob decision stays untouched.
        assert 'case "${TERMINAL_JAIL_LANDLOCK:-}" in' in text

    def test_attach_decision_probes_readability_under_the_launch(self) -> None:
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert "_tj_egress_tier_decide() {" in text
        # The probe is the fs tier's own: readability INSIDE the target
        # namespace, with the launch's exact flags (bubblewrap keeps its `--`).
        assert 'if "$@" test -r "$LANDLOCK_NET_LOADER"' in text
        assert "--here) ;" in text or '"${1:-}" = "--here"' in text

    def test_attach_decision_precedes_every_payload_exec(self) -> None:
        """Probe before wrap: the decision call sits ahead of each exec site."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        exec_sites = [
            # composed launch (payload runs without an inner namespace)
            'exec bash -c \'exec "$@"\' terminal-jail python3 "$LANDLOCK_NET_LOADER" -- "$@"',
            # seccomp trampoline (the loader chain the trampoline exec's)
            'bash -c \'exec python3 "$@"\' terminal-jail "$SECCOMP_LOADER" python3 "$LANDLOCK_NET_LOADER" -- "$@"',
            # fs tier composed with the egress tier (egress outermost)
            'bash -c \'exec "$@"\' terminal-jail python3 "$LANDLOCK_NET_LOADER" -- python3 "$LANDLOCK_LOADER" -- "$@"',
            # egress tier alone, unshare arm
            'exec unshare \\\n            $UNSHARE_FLAGS \\\n            bash -c \'exec "$@"\' terminal-jail python3 "$LANDLOCK_NET_LOADER" -- "$@"',
        ]
        for site in exec_sites:
            assert site in text, site
        # 1 helper body + 5 call sites (composed, seccomp x2, bwrap, unshare).
        assert text.count("_tj_egress_tier_decide") == 7

    def test_degrade_line_names_the_tier_and_the_way_out(self) -> None:
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert "WARNING: Landlock network (egress) tier not applied" in text
        assert "TERMINAL_JAIL_LANDLOCK_NET=0" in text

    def test_fs_tier_seam_is_untouched(self) -> None:
        """The filesystem tier's own attach shape must not drift."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert text.count('!= "mapped"') == 4  # 1 bwrap selection + 3 fs attaches
        assert (
            'bash -c \'exec "$@"\' terminal-jail python3 "$LANDLOCK_LOADER" -- "$@"'
            in text
        )
        assert text.count('if [ "$TJ_LANDLOCK_ON" -eq 1 ]') == 3

    def test_net_loader_script_is_the_documented_one(self) -> None:
        """The tier's loader is shipped and is the module's own entry point."""
        assert NET_LOADER.is_file()
        assert Path(ln.loader_path() or "") == NET_LOADER


# ── Launch shape: the argv the launcher receives (host-independent stubs) ────


class TestLaunchShape:
    """The wrapper's real dispatch, driven through a recording launcher stub."""

    def _run(self, tmp_path: Path, *payload: str, **knobs: str):
        path, _ = _stub_launcher_path(tmp_path)
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        env = _base_env()
        env.update(
            {
                "PATH": path,
                "HOME": str(home),
                "TJ_DF046_STUB_LOG": str(tmp_path / "stub.log"),
                "TERMINAL_JAIL_JAIL_BACKEND": "unshare",
            }
        )
        env.update(knobs)
        result = _run_cli(*payload, env=env)
        return result, tmp_path / "stub.log"

    def test_knob_off_is_byte_identical_to_the_pre_fix_argv(
        self, tmp_path: Path
    ) -> None:
        """No tiers: the trampoline argv is exactly the pre-TJ-DF-046 shape."""
        payload = (_payload_python(), "-c", "print('SHAPE-OK')")
        result, log = self._run(
            tmp_path,
            *payload,
            TERMINAL_JAIL_LANDLOCK="0",
            TERMINAL_JAIL_LANDLOCK_NET="0",
        )
        assert result.returncode == 0, result.stderr
        assert "SHAPE-OK" in result.stdout
        launches = _launch_records(log)
        assert len(launches) == 1
        assert _payload_argv(launches[0]) == [
            "bash",
            "-c",
            'exec "$@"',
            "terminal-jail",
            *payload,
        ]

    def test_knob_on_attaches_the_egress_loader_on_the_allow_path(
        self, tmp_path: Path
    ) -> None:
        payload = (_payload_python(), "-c", "print('SHAPE-OK')")
        result, log = self._run(
            tmp_path,
            *payload,
            TERMINAL_JAIL_LANDLOCK="0",
            TERMINAL_JAIL_LANDLOCK_NET="1",
        )
        assert result.returncode == 0, result.stderr
        assert "SHAPE-OK" in result.stdout
        launches = _launch_records(log)
        assert len(launches) == 1
        argv = _payload_argv(launches[0])
        assert argv == [
            "bash",
            "-c",
            'exec "$@"',
            "terminal-jail",
            "python3",
            str(NET_LOADER),
            "--",
            *payload,
        ]

    def test_knob_on_composes_with_the_fs_tier_egress_outermost(
        self, tmp_path: Path
    ) -> None:
        payload = (_payload_python(), "-c", "print('SHAPE-OK')")
        result, log = self._run(tmp_path, *payload, TERMINAL_JAIL_LANDLOCK_NET="1")
        launches = _launch_records(log)
        assert len(launches) == 1
        argv = _payload_argv(launches[0])
        assert argv == [
            "bash",
            "-c",
            'exec "$@"',
            "terminal-jail",
            "python3",
            str(NET_LOADER),
            "--",
            "python3",
            str(FS_LOADER),
            "--",
            *payload,
        ]
        # ...and the composed chain is STARTABLE: the payload ran.
        assert result.returncode == 0, result.stderr
        assert "SHAPE-OK" in result.stdout

    def test_fs_tier_argv_is_unchanged_with_the_knob_off(self, tmp_path: Path) -> None:
        payload = (_payload_python(), "-c", "print('SHAPE-OK')")
        result, log = self._run(tmp_path, *payload, TERMINAL_JAIL_LANDLOCK_NET="0")
        launches = _launch_records(log)
        assert len(launches) == 1
        assert _payload_argv(launches[0]) == [
            "bash",
            "-c",
            'exec "$@"',
            "terminal-jail",
            "python3",
            str(FS_LOADER),
            "--",
            *payload,
        ]

    def test_readability_probe_runs_before_the_wrap(self, tmp_path: Path) -> None:
        """The preflight is the launch's own flags, and it precedes the wrap."""
        payload = (_payload_python(), "-c", "print('SHAPE-OK')")
        _, log = self._run(tmp_path, *payload, TERMINAL_JAIL_LANDLOCK_NET="1")
        records = _records(log)
        probes = [
            i
            for i, r in enumerate(records)
            if r[-3:] == ["test", "-r", str(NET_LOADER)]
        ]
        launches = [i for i, r in enumerate(records) if "bash" in r]
        assert probes, f"no egress-loader readability probe fired: {records!r}"
        assert launches, f"no launcher record: {records!r}"
        assert probes[0] < launches[0]
        # The probe carries the launch's own flags (the namespace shape).
        assert records[probes[0]][0].startswith("-")

    def test_missing_loader_degrades_loudly_and_still_runs_the_payload(
        self, tmp_path: Path
    ) -> None:
        payload = (_payload_python(), "-c", "print('SHAPE-OK')")
        result, log = self._run(
            tmp_path,
            *payload,
            TERMINAL_JAIL_LANDLOCK="0",
            TERMINAL_JAIL_LANDLOCK_NET="1",
            TERMINAL_JAIL_LANDLOCK_NET_LOADER=str(tmp_path / "not-shipped.py"),
        )
        assert result.returncode == 0, result.stderr
        assert "SHAPE-OK" in result.stdout
        assert "WARNING: Landlock network (egress) tier not applied" in result.stderr
        argv = _payload_argv(_launch_records(log)[0])
        assert str(NET_LOADER) not in argv and "not-shipped.py" not in " ".join(argv)

    def test_unreadable_loader_degrades_loudly(self, tmp_path: Path) -> None:
        payload = (_payload_python(), "-c", "print('SHAPE-OK')")
        hidden = tmp_path / "landlock-net-loader.py"
        hidden.write_text("# not readable\n", encoding="utf-8")
        hidden.chmod(0o000)
        if os.access(str(hidden), os.R_OK):
            pytest.skip("running with privileges that ignore the file mode")
        result, log = self._run(
            tmp_path,
            *payload,
            TERMINAL_JAIL_LANDLOCK="0",
            TERMINAL_JAIL_LANDLOCK_NET="1",
            TERMINAL_JAIL_LANDLOCK_NET_LOADER=str(hidden),
        )
        assert result.returncode == 0, result.stderr
        assert "SHAPE-OK" in result.stdout
        assert "WARNING: Landlock network (egress) tier not applied" in result.stderr
        assert "cannot read" in result.stderr
        argv = _payload_argv(_launch_records(log)[0])
        assert str(hidden) not in argv


# ── Live: the documented shape, against a bound non-allowlisted port ─────────


class TestLive:
    def test_engine_verdict_is_a_plain_allow_for_the_probe_command(self) -> None:
        """Premise: this command takes the ALLOW path (rule_id null, no rewrite).

        Without this the live cells could be measuring the rewrite path, whose
        loader composition was never broken.
        """
        sys.path.insert(0, str(PROJECT_ROOT / "plugin"))
        from terminal_jail.interruptor import intercept
        from terminal_jail.interruptor.config import Config

        command = f'{_payload_python()} -c "{_connect_payload(19999)}"'
        result = intercept(
            command,
            config=Config(
                system_rules_dir="/nonexistent-terminal-jail-system",
                user_rules_dir="/nonexistent-terminal-jail-user",
            ),
        )
        assert result.action == "allow", f"{result.action!r} (rule={result.rule_id!r})"
        assert result.rule_id is None, result.rule_id
        assert not result.modified, result.modified

    def test_knob_off_control_prints_connected(self, listener: _Listener) -> None:
        """Control: the harness can observe a connection it causes."""
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "0"
        if not _cli_runs_a_payload(env):
            pytest.skip(HOST_DENIED_NAMESPACE)
        result = _run_cli(
            _payload_python(), "-c", _connect_payload(listener.port), env=env
        )
        assert "CONNECTED" in result.stdout, (
            f"the control did not connect: rc={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_knob_on_is_never_silently_connected(self, listener: _Listener) -> None:
        """Criterion 1: engage the tier, or say loudly why not — never both silent."""
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
        if not _cli_runs_a_payload(env):
            pytest.skip(HOST_DENIED_NAMESPACE)
        result = _run_cli(
            _payload_python(), "-c", _connect_payload(listener.port), env=env
        )
        connected = "CONNECTED" in result.stdout
        warned = "Landlock network (egress) tier not applied" in result.stderr
        applied = "kernel egress tier APPLIED" in result.stderr
        assert not (connected and not (warned or applied)), (
            "the payload ran CONNECTED with the egress knob on and no "
            f"degradation stated: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # ...and the run really took the ALLOW path (the defect's precondition).
        assert '"action":"allow"' in result.stderr, result.stderr

    def test_knob_on_blocks_the_non_allowlisted_port_where_enforceable(
        self, listener: _Listener
    ) -> None:
        """The strong arm: kernel denial, proven with a bound listener."""
        if ln.abi_version() < ln.NET_ABI_MIN:
            pytest.skip(HOST_LANDLOCK_ABV4)
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
        if not _cli_runs_a_payload(env):
            pytest.skip(HOST_DENIED_NAMESPACE)
        if listener.port in ln.DEFAULT_EGRESS_ALLOW_PORTS:
            pytest.skip("kernel-chosen port collided with the default allowlist")
        result = _run_cli(
            _payload_python(), "-c", _connect_payload(listener.port), env=env
        )
        assert "kernel egress tier APPLIED" in result.stderr, result.stderr
        assert "CONNECTED" not in result.stdout, (
            f"the payload connected under the egress tier: {result.stdout!r}"
        )
        assert "PermissionError" in result.stderr or "Errno 13" in result.stderr, (
            result.stderr
        )

    def test_knob_on_still_allows_an_allowlisted_port(
        self, listener: _Listener
    ) -> None:
        """No over-block: the port IS in the allowlist, so the connect succeeds."""
        if ln.abi_version() < ln.NET_ABI_MIN:
            pytest.skip(HOST_LANDLOCK_ABV4)
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
        env["TERMINAL_JAIL_LANDLOCK_NET_ALLOW"] = str(listener.port)
        if not _cli_runs_a_payload(env):
            pytest.skip(HOST_DENIED_NAMESPACE)
        result = _run_cli(
            _payload_python(), "-c", _connect_payload(listener.port), env=env
        )
        assert "CONNECTED" in result.stdout, (
            f"an allowlisted port was over-blocked: rc={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_documented_shape_prints_no_connected_without_a_listener(self) -> None:
        """Criterion 2: the README's literal shape (no listener on the port)."""
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
        result = _run_cli(
            "python3",
            "-c",
            "import socket; s=socket.socket(); s.settimeout(1); "
            "s.connect(('127.0.0.1', 9999)); print('CONNECTED')",
            env=env,
        )
        combined = result.stdout + result.stderr
        assert "CONNECTED" not in combined, (
            f"the documented shape reported a connection with no listener: {combined!r}"
        )

    def test_composed_launch_attaches_the_egress_tier(self) -> None:
        """The knob is honored in composed mode too (no namespace needed).

        Composed mode is only reachable when the inner namespace cannot be
        created — on this host that is a HOST-DENIED-NAMESPACE skip, which the
        refusal (rc=2, never a silent run) keeps honest.
        """
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
        env["TERMINAL_JAIL_COMPOSED"] = "on"
        result = _run_cli("echo", "tj-df-046-composed", env=env)
        if "COMPOSED MODE" not in result.stderr:
            pytest.skip(
                "this host creates inner namespaces, so composed mode is "
                "unreachable here"
            )
        assert "tj-df-046-composed" in result.stdout, result.stderr
        assert "egress: enforced by terminal-jail" in result.stderr or (
            "Landlock network (egress) tier not applied" in result.stderr
        ), result.stderr
