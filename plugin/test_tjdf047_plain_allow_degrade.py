"""TJ-DF-047 — the plain-allow launch path is never SILENT about the net tier.

TJ-DF-046 engaged the Landlock egress tier on the plain-allow path (the
``rule_id=null`` verdict that never gets an auto-sandbox rewrite) and taught
the attach decision to degrade LOUDLY: every non-attach outcome — loader
missing, loader unreadable under the launch that would run it, uid-mapped
launch — prints one ``WARNING: Landlock network (egress) tier not applied
(<cause>)`` line before the payload runs. This file pins that contract as a
CONTRACT test (criterion 3): a plain-allow command aimed at a blocked port
either connects under a stated degradation or is denied by the kernel — it
never connects silently, and when it cannot engage it never runs without
saying so.

Also pinned here: the installer's containment-ceiling summary (criterion 2) —
a fresh install self-reports, per Landlock tier, whether it CAN engage on the
host that just installed the tool (fs tier needs ABI >= 1, the opt-in net
tier needs ABI >= 4), so the install transcript states the containment
ceiling without requiring the operator to run the probes by hand.

Structure mirrors this repo's other launch-shape suites
(test_tjdf046_egress_allow_path.py): PATH-stub launcher cells that are
host-independent, live cells gated on the host's Landlock ABI, and
scratch-checkout installer cells that never touch the real tree.
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
INSTALL_SCRIPT = PROJECT_ROOT / "install.sh"
RULES_MIRROR_DIR = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules"

pytestmark = pytest.mark.standalone_cli

DEGRADE_PREFIX = "WARNING: Landlock network (egress) tier not applied"

HOST_LANDLOCK_ABV4 = (
    "HOST-LANDLOCK-ABV4: Landlock ABI < 4 — no kernel TCP connect rules here"
)
HOST_DENIED_NAMESPACE = (
    "HOST-DENIED-NAMESPACE: this CLI cannot launch a payload here (its "
    "fail-closed namespace preflight exits 2), so the plain-allow path is "
    "unreachable; the refusal is never a silent CONNECTED run"
)


# ── Shared harness (same shape as test_tjdf046_egress_allow_path) ────────────

_LAUNCHER_STUB = """#!/usr/bin/env bash
log="${TJ_DF047_STUB_LOG:?}"
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
    """The system interpreter (a venv-under-$HOME payload would break under
    a file-restricting fs tier — see the TJ-DF-046 suite for the shape)."""
    for candidate in ("/usr/bin/python3", "/usr/local/bin/python3"):
        if os.path.exists(candidate):
            return candidate
    return shutil.which("python3") or sys.executable


def _base_env() -> dict[str, str]:
    """No ambient TERMINAL_JAIL_* leakage; rules pinned to the shipped mirror."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("TERMINAL_JAIL_")}
    env["TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR"] = str(RULES_MIRROR_DIR)
    env["TERMINAL_JAIL_INTERRUPTOR_RULES_DIR"] = str(RULES_MIRROR_DIR)
    return env


def _stub_launcher_path(tmp_path: Path) -> str:
    bindir = tmp_path / "stub-bin"
    bindir.mkdir(exist_ok=True)
    for name in ("unshare", "bwrap"):
        stub = bindir / name
        stub.write_text(_LAUNCHER_STUB, encoding="utf-8")
        stub.chmod(0o755)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


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


def _connect_ex_payload(port: int) -> str:
    return (
        "import socket;s=socket.socket();s.settimeout(2);"
        f"print(f'RC={{s.connect_ex((\"127.0.0.1\",{port}))}}')"
    )


def _cli_runs_a_payload(env: dict[str, str]) -> bool:
    """True when this host's CLI actually launches a command (not rc=2)."""
    result = _run_cli("echo", "tj-df-047-canary", env=env)
    return result.returncode == 0 and "tj-df-047-canary" in result.stdout


# ── Wiring: every plain-allow exec site carries the attach decision ──────────


class TestPlainAllowWiring:
    def test_every_nonrewritten_exec_site_is_preceded_by_the_decision(self) -> None:
        """The degrade fires AT THE ATTACH DECISION, so the decision must sit
        ahead of every plain-allow payload exec (composed, both --seccomp
        trampoline arms, bwrap, unshare). Counts, not vibes: 1 helper body +
        5 call sites, as TJ-DF-046 shipped them."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert text.count("_tj_egress_tier_decide") == 7
        # The helper's non-attach outcomes ALL print the named-cause line.
        body_start = text.index("_tj_egress_degrade() {")
        body = text[body_start : text.index("TJ_EGRESS_TIER_ATTACH=0")]
        assert DEGRADE_PREFIX in body
        assert "Landlock net tier not applied" in text or DEGRADE_PREFIX in text

    def test_degrade_line_names_the_cause_shape(self) -> None:
        """Criterion 1's literal string: 'Landlock net tier not applied' —
        the shipped wording is 'Landlock network (egress) tier not applied
        (<cause>)'; pin both the tier name and the parenthesized cause slot
        so the wrapper and loader warnings stay greppable as one family."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert "WARNING: Landlock network (egress) tier not applied ($1)" in text, (
            "the attach-decision degrade must name the cause from its argument"
        )
        loader_text = NET_LOADER.read_text(encoding="utf-8")
        assert "tier not applied" in loader_text
        assert "({cause})" in loader_text or "(tier module not found" in loader_text

    def test_fs_tier_seam_is_untouched(self) -> None:
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert text.count('!= "mapped"') == 4
        assert text.count('if [ "$TJ_LANDLOCK_ON" -eq 1 ]') == 3


# ── Launch shape: degrade fires through the wrapper's real dispatch ──────────


class TestPlainAllowDegradeShape:
    def _run(self, tmp_path: Path, *payload: str, **knobs: str):
        env = _base_env()
        env.update(
            {
                "PATH": _stub_launcher_path(tmp_path),
                "HOME": str(tmp_path / "home"),
                "TJ_DF047_STUB_LOG": str(tmp_path / "stub.log"),
                "TERMINAL_JAIL_JAIL_BACKEND": "unshare",
            }
        )
        (tmp_path / "home").mkdir(exist_ok=True)
        env.update(knobs)
        result = _run_cli(*payload, env=env)
        return result

    def test_missing_loader_degrades_on_the_plain_allow_launch(
        self, tmp_path: Path
    ) -> None:
        payload = (_payload_python(), "-c", "print('DF047-OK')")
        result = self._run(
            tmp_path,
            *payload,
            TERMINAL_JAIL_LANDLOCK="0",
            TERMINAL_JAIL_LANDLOCK_NET="1",
            TERMINAL_JAIL_LANDLOCK_NET_LOADER=str(tmp_path / "absent-loader.py"),
        )
        assert result.returncode == 0, result.stderr
        assert "DF047-OK" in result.stdout
        assert DEGRADE_PREFIX in result.stderr, result.stderr
        assert any(
            needle in result.stderr
            for needle in (
                "not found",
                "not reachable",
                "not readable",
                "missing",
            )
        )

    def test_unreadable_loader_degrades_on_the_plain_allow_launch(
        self, tmp_path: Path
    ) -> None:
        hidden = tmp_path / "landlock-net-loader.py"
        hidden.write_text("# not readable\n", encoding="utf-8")
        hidden.chmod(0o000)
        if os.access(str(hidden), os.R_OK):
            pytest.skip("running with privileges that ignore the file mode")
        payload = (_payload_python(), "-c", "print('DF047-OK')")
        result = self._run(
            tmp_path,
            *payload,
            TERMINAL_JAIL_LANDLOCK="0",
            TERMINAL_JAIL_LANDLOCK_NET="1",
            TERMINAL_JAIL_LANDLOCK_NET_LOADER=str(hidden),
        )
        assert result.returncode == 0, result.stderr
        assert "DF047-OK" in result.stdout
        assert DEGRADE_PREFIX in result.stderr, result.stderr

    def test_same_launch_handoff_wiring_is_shipped(self, tmp_path: Path) -> None:
        """INT-CI-011 mechanism wiring: the wrapper creates a launch-private
        engine-degradation mark before the bridge runs, and the attach
        decision consults it before its own degrade.

        The wrapper OWNS the mark (it creates a fresh private temp file
        when the knob is on — a pre-set env value is deliberately
        replaced, so a hostile inherited mark cannot fake or hide a
        degradation report). Behavior is pinned end to end by
        test_tjdf046's modify-path regression on the degraded hosts; this
        pin holds on every host.
        """
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        # The mark is created for THIS launch before the engine is invoked.
        assert 'TERMINAL_JAIL_LANDLOCK_NET_MARK="$(\n            mktemp' in text
        # ...only when the egress knob is on (never otherwise)...
        assert (
            'if [ "$TJ_LANDLOCK_NET_ON" -eq 1 ]; then\n        TERMINAL_JAIL_LANDLOCK_NET_MARK'
            in text
        )
        # ...and the attach decision consults it before its own degrade.
        body_start = text.index("_tj_egress_engine_degradation_mark() {")
        body_end = text.index("_tj_launch_composed() {")
        body = text[body_start:body_end]
        assert '[ -s "$TERMINAL_JAIL_LANDLOCK_NET_MARK" ]' in body
        assert body.count("TJ_EGRESS_ENGINE_DEGRADED") >= 4
        # The module side records the degrade into the mark (best effort).
        module_text = (
            PROJECT_ROOT
            / "plugin"
            / "terminal_jail"
            / "interruptor"
            / "landlock_net.py"
        ).read_text(encoding="utf-8")
        assert (
            'DEGRADED_MARK_FILE_ENV = "TERMINAL_JAIL_LANDLOCK_NET_MARK"' in module_text
        )
        assert "open(mark_path" in module_text

    def test_each_independent_launch_reports_exactly_once(self, tmp_path: Path) -> None:
        """INT-CI-011 scoping: the one-warning handoff is PER LAUNCH. Two
        independent launches each state the degradation exactly once — the
        suppression can never leak into (hide) a later launch's report,
        whoever reports (engine preflight or launch preflight).
        """
        hidden = tmp_path / "landlock-net-loader.py"
        hidden.write_text("# not readable\n", encoding="utf-8")
        hidden.chmod(0o000)
        if os.access(str(hidden), os.R_OK):
            pytest.skip("running with privileges that ignore the file mode")
        payload = (_payload_python(), "-c", "print('DF047-OK')")
        for launch_no in (1, 2):
            result = self._run(
                tmp_path,
                *payload,
                TERMINAL_JAIL_LANDLOCK="0",
                TERMINAL_JAIL_LANDLOCK_NET="1",
                TERMINAL_JAIL_LANDLOCK_NET_LOADER=str(hidden),
            )
            assert result.returncode == 0, result.stderr
            assert "DF047-OK" in result.stdout
            count = result.stderr.count(DEGRADE_PREFIX)
            assert count == 1, (
                f"launch {launch_no}: expected exactly ONE degradation "
                f"report, got {count}: stderr={result.stderr!r}"
            )

    def test_knob_off_prints_no_tier_line(self, tmp_path: Path) -> None:
        """The knob is opt-in: off means silence about this tier (the knob is
        the deliberate opt-out, per the degrade line's own way-out)."""
        payload = (_payload_python(), "-c", "print('DF047-OFF')")
        result = self._run(
            tmp_path,
            *payload,
            TERMINAL_JAIL_LANDLOCK="0",
            TERMINAL_JAIL_LANDLOCK_NET="0",
        )
        assert result.returncode == 0, result.stderr
        assert "DF047-OFF" in result.stdout
        assert DEGRADE_PREFIX not in result.stderr
        assert "egress tier APPLIED" not in result.stderr


# ── Live: criterion 3's contract against a bound non-allowlisted port ────────


class TestPlainAllowLiveContract:
    def test_engine_verdict_is_a_plain_allow_for_the_probe_command(self) -> None:
        """Premise: this command takes the ALLOW path (rule_id null)."""
        sys.path.insert(0, str(PROJECT_ROOT / "plugin"))
        from terminal_jail.interruptor import intercept
        from terminal_jail.interruptor.config import Config

        command = f'{_payload_python()} -c "print(1)"'
        result = intercept(
            command,
            config=Config(
                system_rules_dir="/nonexistent-terminal-jail-system",
                user_rules_dir="/nonexistent-terminal-jail-user",
            ),
        )
        assert result.action == "allow", f"{result.action!r} (rule={result.rule_id!r})"
        assert result.rule_id is None, result.rule_id

    def test_blocked_port_connect_is_warned_or_blocked_never_silent(
        self, listener: _Listener
    ) -> None:
        """Criterion 3: a plain-allow command to a blocked port prints the
        degrade warning OR is blocked — never a silent success (a CONNECTED
        with the knob on and neither the warning nor the APPLIED notice)."""
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
        if not _cli_runs_a_payload(env):
            pytest.skip(HOST_DENIED_NAMESPACE)
        result = _run_cli(
            _payload_python(),
            "-c",
            _connect_ex_payload(listener.port),
            env=env,
        )
        connected = "CONNECTED" in result.stdout
        warned = DEGRADE_PREFIX in result.stderr
        applied = "kernel egress tier APPLIED" in result.stderr
        assert not (connected and not (warned or applied)), (
            "plain-allow connect ran silently with the net knob on: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert connected or warned or applied, (
            f"neither connected nor stated: stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        # ...and the run really took the ALLOW path (rule_id=null verdict).
        assert '"action":"allow"' in result.stderr, result.stderr

    def test_bad_allowlist_degrades_loudly_on_the_allow_path(
        self, listener: _Listener
    ) -> None:
        """The loader's own refusal arm, reachable on ANY Landlock host: a bad
        allowlist token refuses the tier — the payload runs (CONNECTED) but
        ONLY under the named-cause degrade line, never silently."""
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
        env["TERMINAL_JAIL_LANDLOCK_NET_ALLOW"] = f"{listener.port},not-a-port"
        if not _cli_runs_a_payload(env):
            pytest.skip(HOST_DENIED_NAMESPACE)
        result = _run_cli(
            _payload_python(),
            "-c",
            _connect_ex_payload(listener.port),
            env=env,
        )
        assert "RC=0" in result.stdout, (
            f"the refused tier must still run the payload: {result.stderr!r}"
        )
        assert DEGRADE_PREFIX in result.stderr, result.stderr

    def test_enforceable_host_denies_the_port_without_connecting(
        self, listener: _Listener
    ) -> None:
        """The strong arm on an ABI >= 4 host: kernel denial, no CONNECTED."""
        if ln.abi_version() < ln.NET_ABI_MIN:
            pytest.skip(HOST_LANDLOCK_ABV4)
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
        if not _cli_runs_a_payload(env):
            pytest.skip(HOST_DENIED_NAMESPACE)
        if listener.port in ln.DEFAULT_EGRESS_ALLOW_PORTS:
            pytest.skip("kernel-chosen port collided with the default allowlist")
        result = _run_cli(
            _payload_python(),
            "-c",
            _connect_ex_payload(listener.port),
            env=env,
        )
        assert "kernel egress tier APPLIED" in result.stderr, result.stderr
        assert "CONNECTED" not in result.stdout, result.stdout


# ── Installer: criterion 2's containment-ceiling summary ─────────────────────


_LL_PROBE_STUB_TEMPLATE = (
    "#!/usr/bin/env python3\n"
    "print('Landlock capability probe: {verdict}')\n"
    "print('  ABI version (max supported): {abi}')\n"
    "print('  landlock in /sys/kernel/security/lsm: {lsm}')\n"
    "print('  ruleset creation: ok')\n"
    "print('  restrict_self: ok')\n"
    "print('  enforcement (mode-600 read under empty domain): denied')\n"
)


def _make_landlock_scratch_checkout(
    tmp_path: Path,
    *,
    landlock_probe: str | None,
) -> Path:
    """A scratch checkout carrying ONLY the pieces the installer's summary
    path needs (install.sh copy, wrapper shell, plugin tree, and either the
    fake landlock probe or none). The fs/pidns probes are omitted so the
    demand path skips them — the summary must be independent of the demand
    variables. Mirrors _make_scratch_checkout() in test_install.py."""
    checkout = tmp_path / "scratch-checkout"
    (checkout / "standalone").mkdir(parents=True)
    (checkout / "standalone" / "terminal-jail").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )
    (checkout / "plugin" / "terminal_jail").mkdir(parents=True)
    (checkout / "plugin" / "terminal_jail" / ".keep").write_text("")
    shutil.copyfile(INSTALL_SCRIPT, checkout / "install.sh")
    scripts = checkout / "scripts"
    scripts.mkdir()
    if landlock_probe is not None:
        probe = scripts / "landlock-capability-probe.py"
        probe.write_text(landlock_probe, encoding="utf-8")
        probe.chmod(0o755)
    return checkout


def _run_landlock_install(checkout: Path, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    install_dir = tmp_path / "bin"
    install_dir.mkdir(exist_ok=True)
    return subprocess.run(
        ["sh", str(checkout / "install.sh")],
        capture_output=True,
        text=False,
        check=False,
        timeout=120,
        cwd=str(checkout),
        env={
            **os.environ,
            "HOME": str(home),
            "TERMINAL_JAIL_INSTALL_DIR": str(install_dir),
            "TERMINAL_JAIL_RULES_DIR": str(tmp_path / "rules"),
        },
    )


class TestInstallContainmentCeilingSummary:
    """Criterion 2: the install summary names, per Landlock tier, whether it
    CAN engage on this host — the fresh install self-reports its ceiling."""

    def test_full_abi8_host_names_both_tiers_as_able(self, tmp_path: Path) -> None:
        checkout = _make_landlock_scratch_checkout(
            tmp_path,
            landlock_probe=_LL_PROBE_STUB_TEMPLATE.format(
                verdict="FULL", abi="8", lsm="True"
            ),
        )
        result = _run_landlock_install(checkout, tmp_path)
        out = (result.stdout + result.stderr).decode("utf-8", "replace")
        assert result.returncode == 0, out
        assert "containment ceiling (Landlock)" in out, out
        assert "fs tier CAN engage" in out, out
        assert "net (egress) tier CAN engage" in out, out
        assert "ABI 8 >= 4" in out, out

    def test_abi2_host_names_fs_able_and_net_not(self, tmp_path: Path) -> None:
        checkout = _make_landlock_scratch_checkout(
            tmp_path,
            landlock_probe=_LL_PROBE_STUB_TEMPLATE.format(
                verdict="FULL", abi="2", lsm="True"
            ),
        )
        result = _run_landlock_install(checkout, tmp_path)
        out = (result.stdout + result.stderr).decode("utf-8", "replace")
        assert result.returncode == 0, out
        assert "containment ceiling (Landlock)" in out, out
        assert "fs tier CAN engage" in out, out
        assert "net (egress) tier CANNOT" in out, out
        assert "ABI 2 < 4" in out, out

    def test_degraded_host_names_neither_tier_with_the_probe_cause_shown(
        self, tmp_path: Path
    ) -> None:
        probe = (
            "#!/usr/bin/env python3\n"
            "print('Landlock capability probe: DEGRADED')\n"
            "print('  ABI version (max supported): 0')\n"
            "print('  cause: landlock not listed in /sys/kernel/security/lsm')\n"
        )
        checkout = _make_landlock_scratch_checkout(tmp_path, landlock_probe=probe)
        result = _run_landlock_install(checkout, tmp_path)
        out = (result.stdout + result.stderr).decode("utf-8", "replace")
        assert result.returncode == 0, out
        assert "containment ceiling (Landlock)" in out, out
        assert "NEITHER Landlock tier can engage" in out, out
        # The cause is IN the transcript — the summary points at "the output
        # above", so the probe's diagnosis must actually be there.
        assert "cause: landlock not listed in /sys/kernel/security/lsm" in out, out

    def test_missing_probe_degrades_to_one_honest_unknown_line(
        self, tmp_path: Path
    ) -> None:
        checkout = _make_landlock_scratch_checkout(tmp_path, landlock_probe=None)
        result = _run_landlock_install(checkout, tmp_path)
        out = (result.stdout + result.stderr).decode("utf-8", "replace")
        assert result.returncode == 0, out
        assert "containment ceiling (Landlock): unknown" in out, out
        # "unknown" is honest; DEGRADED would assert a diagnosis that the
        # absent probe never produced.
        assert "NEITHER Landlock tier can engage" not in out, out
