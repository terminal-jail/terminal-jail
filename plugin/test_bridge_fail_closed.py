"""TJ-GAP-070: engine-evaluation errors must FAIL CLOSED.

Contract (board-decided):
- The bridge's `except Exception` around ``intercept()`` emits a BLOCKING
  verdict (``action: block``) with a ``[bridge-error]`` reason — engine
  failure must never become a silent allow in enforce mode.
- The allow envelope stays ONLY for stdin/transport-level errors (read
  failure, empty stdin, invalid JSON, non-dict payload, missing/non-string
  command, engine ImportError): a host shell invokes the bridge before
  every command, so blocking there could brick the shell itself.
- The wrapper (standalone/terminal-jail) treats any ``[bridge-error]``
  reason as a block in enforce mode (rc 126) and as a loud warning in warn
  mode; empty or non-JSON bridge stdout blocks in enforce mode too.
- The rule loader refuses (loud one-line stderr note naming the file) any
  rule file whose rules fail type validation — e.g. a non-numeric
  ``priority`` — so a typo can no longer reach evaluation time.
- TJ-DF-039: when the parse failure comes from the PyYAML-less JSON fallback
  (on such a host that fallback is the ONLY path a ``.yaml`` rule file can
  take, so an entire installed mirror is affected) the skip is announced with
  one loud stderr note naming the file and the cause.
- TJ-DF-040: that same PyYAML-less JSON-fallback failure now also FAILS
  CLOSED (``RuleParseError`` aborts the load, the bridge emits the blocking
  ``[bridge-error]`` verdict). A fresh host without PyYAML used to degrade
  the whole installed firewall to allow-everything while the sandbox layer
  still ran; now the engine refuses to allow on a policy it cannot read.
  The retained fail-open arms are NARROW and named in ``_load_file``: an
  UNREADABLE file (OSError), and a syntax error a real YAML parser rejected
  (yaml.YAMLError — DF-TERMINAL-JAIL-6's skip-with-warning, only reachable
  when a real parser is present).
"""

from __future__ import annotations

import contextlib
import functools
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from terminal_jail import interruptor_bridge as bridge_module
from terminal_jail.interruptor import Config, intercept

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
BRIDGE_SCRIPT = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor_bridge.py"


def _degraded_marker(stderr: str) -> bool:
    """True when stderr shows the wrapper's documented degraded-host exit:
    namespace creation refused (same detection as
    test_standalone_cli._host_denied_namespaces)."""
    return (
        "Permission denied" in stderr
        or "Operation not permitted" in stderr
        or "namespace creation failed" in stderr
    )


@pytest.fixture(scope="module")
def cli_path() -> Path:
    assert CLI_SCRIPT.exists(), f"CLI script not found: {CLI_SCRIPT}"
    return CLI_SCRIPT


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_rule_file(rules_dir: Path, filename: str, yaml_text: str) -> Path:
    rules_dir.mkdir(parents=True, exist_ok=True)
    path = rules_dir / filename
    path.write_text(yaml_text)
    return path


POISON_PRIORITY_YAML = """\
rules:
  - id: p1
    priority: not-a-number
    match:
      type: pattern
      pattern: ".*"
    action: block
"""


def _bridge_main_inproc(
    stdin_line: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    """Same in-process seam the DF-6 schema tests use (mirrors the helper in
    test_interruptor_integration.py, kept local so this module stands alone)."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    argv = [str(BRIDGE_SCRIPT)]
    env_overlay = (
        mock.patch.dict(os.environ, extra_env)
        if extra_env
        else contextlib.nullcontext()
    )
    with (
        env_overlay,
        mock.patch.object(sys, "argv", argv),
        mock.patch.object(sys, "stdin", io.StringIO(stdin_line + "\n")),
        mock.patch.object(sys, "stdout", stdout),
        mock.patch.object(sys, "stderr", stderr),
    ):
        returncode = 0
        try:
            bridge_module.main()
        except SystemExit as exc:  # pragma: no cover - main() has no exit path
            returncode = exc.code if isinstance(exc.code, int) else 1
    return subprocess.CompletedProcess(
        args=argv,
        returncode=returncode,
        stdout=stdout.getvalue().encode(),
        stderr=stderr.getvalue().encode(),
    )


# ── A. Bridge: engine exception → blocking [bridge-error] verdict ────────────


class TestBridgeEngineExceptionFailsClosed:
    def test_engine_exception_emits_block_verdict(self) -> None:
        """intercept() raising must produce action=block + [bridge-error] reason."""
        with mock.patch(
            "terminal_jail.interruptor.intercept", side_effect=TypeError("boom")
        ):
            proc = _bridge_main_inproc('{"command": "true"}')
        assert proc.returncode == 0
        response = json.loads(proc.stdout.decode())
        assert response["action"] == "block", (
            f"engine exception must fail CLOSED, got {response!r}"
        )
        assert response["rule_id"] == "[bridge-error]"
        reason = response["reason"]
        assert reason.startswith("[bridge-error]"), reason
        assert "fail-closed: blocking command (enforce mode)" in reason
        assert "boom" in reason, f"the exception detail must be surfaced: {reason!r}"

    def test_engine_exception_carries_exception_class_and_detail(self) -> None:
        """The verdict names the exception class and message (operator debuggability)."""
        with mock.patch(
            "terminal_jail.interruptor.intercept",
            side_effect=ValueError("bad priority: 7x"),
        ):
            proc = _bridge_main_inproc('{"command": "echo hello"}')
        reason = json.loads(proc.stdout.decode())["reason"]
        assert "ValueError" in reason
        assert "bad priority: 7x" in reason


# ── B. Transport errors keep the allow envelope ──────────────────────────────


class TestTransportErrorsStayFailOpen:
    @pytest.mark.parametrize(
        "raw_line",
        [
            "",  # empty stdin
            "not json {",  # invalid JSON
            "null",  # non-dict payload
            "{}",  # missing command key
            '{"command": 123}',  # non-string command
        ],
    )
    def test_transport_errors_still_allow(self, raw_line: str) -> None:
        """Malformed stdin/transport keeps the documented allow envelope."""
        proc = _bridge_main_inproc(raw_line)
        assert proc.returncode == 0
        response = json.loads(proc.stdout.decode())
        assert response["action"] == "allow", (
            f"transport errors stay fail-open, got {response!r} for {raw_line!r}"
        )
        assert response["reason"].startswith("[bridge-error]")

    def test_engine_import_error_still_allows(self) -> None:
        """A missing engine is a transport-level error: allow envelope, no crash."""
        with mock.patch.dict(sys.modules, {"terminal_jail.interruptor": None}):
            proc = _bridge_main_inproc('{"command": "true"}')
        assert proc.returncode == 0
        response = json.loads(proc.stdout.decode())
        assert response["action"] == "allow"
        assert "not importable" in response["reason"]


# ── C. Wrapper: [bridge-error] verdicts and garbage stdout block in enforce ──


@pytest.mark.standalone_cli
class TestWrapperVerdictHardening:
    """Drive the real standalone/terminal-jail with a FAKE bridge on PATH.

    The wrapper resolves the bridge via TERMINAL_JAIL_BRIDGE, so a stub
    script stands in for the real one: it emits whatever stdout the test
    sets (valid JSON with a [bridge-error] reason, or plain garbage).
    """

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _host_denies_bare_launch() -> bool:
        """True when the host cannot create the bare-mode namespace.

        Mirrors test_standalone_cli._host_denies_bare_mode: probe once per
        process with a clean-rules bridge; bare mode works (rc 0) or fires
        the documented fail-closed degradation (rc 2 + namespace message).
        On such hosts the warn-mode tests can still verify the firewall's
        warn SEMANTICS (loud warning on stderr, no block box), but cannot
        prove the command actually executed — the wrapper exits 2 at the
        namespace preflight by contract (TJ-GAP-034). Those run-assertions
        SKIP with the HOST-DEGRADED-BARE-LAUNCH marker instead of silently
        passing or failing (GitHub runners are this host class).
        """
        d = tempfile.mkdtemp(prefix="tj-bare-launch-probe-")
        stub = Path(d) / "probe-bridge.py"
        # A clean ALLOW verdict: any failure below the firewall layer is
        # then attributable to the host's namespace preflight, not rules.
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "sys.stdin.readline()\n"
            "sys.stdout.write(json.dumps({'action': 'allow', 'command': '',"
            " 'modified': None, 'rule_id': None, 'reason': ''}))\n"
        )
        stub.chmod(0o755)
        env = os.environ | {
            "TERMINAL_JAIL_BRIDGE": str(stub),
            "USE_INTERRUPTOR": "1",
            "TERMINAL_JAIL_INTERRUPTOR_MODE": "warn",
        }
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [str(CLI_SCRIPT), "true"],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return False
        return result.returncode == 2 and _degraded_marker(result.stderr)

    @staticmethod
    def _fake_bridge(tmp_path: Path, stdout_text: str) -> Path:
        stub = tmp_path / "fake-bridge.py"
        # stdout_text embedded via repr so arbitrary/garbage bytes survive.
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"sys.stdin.readline()\n"
            f"sys.stdout.write({stdout_text!r})\n"
        )
        stub.chmod(0o755)
        return stub

    BRIDGE_ERROR_VERDICT = json.dumps(
        {
            "action": "allow",
            "command": "",
            "modified": None,
            "rule_id": None,
            "reason": "[bridge-error] interrupt() raised an exception — "
            "fail-open: allowing command",
        }
    )

    def test_bridge_error_reason_blocks_in_enforce(self, tmp_path: Path) -> None:
        """A [bridge-error] reason is treated as BLOCK in enforce mode (rc 126)."""
        bridge = self._fake_bridge(tmp_path, self.BRIDGE_ERROR_VERDICT + "\n")
        result = subprocess.run(
            [str(CLI_SCRIPT), "true"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
                "TERMINAL_JAIL_INTERRUPTOR_MODE": "enforce",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 126, (
            f"[bridge-error] reason must block in enforce mode, rc={result.returncode} "
            f"stderr={result.stderr!r}"
        )
        assert "COMMAND BLOCKED" in result.stderr
        assert "[bridge-error]" in result.stderr

    def test_bridge_error_reason_warns_and_runs_in_warn_mode(
        self, tmp_path: Path
    ) -> None:
        """In warn mode the same verdict warns loudly and the command runs."""
        bridge = self._fake_bridge(tmp_path, self.BRIDGE_ERROR_VERDICT + "\n")
        result = subprocess.run(
            [str(CLI_SCRIPT), "echo", "tj070-warn-ran"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
                "TERMINAL_JAIL_INTERRUPTOR_MODE": "warn",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "tj070-warn-ran" in result.stdout or (
            result.returncode == 2 and self._host_denies_bare_launch()
        ), (
            f"warn mode must run the command (or honestly skip on a "
            f"namespace-degraded host), rc={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "WARN" in result.stderr
        assert "[bridge-error]" in result.stderr
        assert "COMMAND BLOCKED" not in result.stderr

    def test_garbage_bridge_stdout_blocks_in_enforce(self, tmp_path: Path) -> None:
        """Non-JSON bridge stdout must block in enforce mode, never `|| echo allow`."""
        bridge = self._fake_bridge(tmp_path, "Traceback (most recent call last):\n")
        result = subprocess.run(
            [str(CLI_SCRIPT), "true"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
                "TERMINAL_JAIL_INTERRUPTOR_MODE": "enforce",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 126, (
            f"garbage bridge stdout must block in enforce mode, rc={result.returncode} "
            f"stderr={result.stderr!r}"
        )
        assert "COMMAND BLOCKED" in result.stderr

    def test_garbage_bridge_stdout_warns_and_runs_in_warn_mode(
        self, tmp_path: Path
    ) -> None:
        """Warn mode treats unusable bridge output as unguarded-execution warning."""
        bridge = self._fake_bridge(tmp_path, "<garbage not json>")
        result = subprocess.run(
            [str(CLI_SCRIPT), "echo", "tj070-garbage-warn-ran"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
                "TERMINAL_JAIL_INTERRUPTOR_MODE": "warn",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        if not (result.returncode == 2 and self._host_denies_bare_launch()):
            # Namespace-capable host: the command must actually have run.
            assert "tj070-garbage-warn-ran" in result.stdout, (
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        # Warn semantics hold on EVERY host: loud warning, never a block.
        assert "WARN" in result.stderr or "WARNING" in result.stderr
        assert result.returncode != 126

    def test_empty_bridge_stdout_blocks_in_enforce(self, tmp_path: Path) -> None:
        """A bridge that exits 0 with EMPTY stdout must block in enforce mode.

        Judge finding on 2e351ff: the fail-closed branch was gated behind
        ``[ -n "$bridge_result" ]``, so an empty command substitution (exit 0,
        no output) skipped the whole verdict path and the command ran
        UNGUARDED with rc 0 — contradicting specs/interruptor.md's
        "stdout empty or not a JSON object → block, exit 126".
        """
        bridge = self._fake_bridge(tmp_path, "")
        result = subprocess.run(
            [str(CLI_SCRIPT), "true"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
                "TERMINAL_JAIL_INTERRUPTOR_MODE": "enforce",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 126, (
            f"empty bridge stdout must block in enforce mode, rc={result.returncode} "
            f"stderr={result.stderr!r}"
        )
        assert "COMMAND BLOCKED" in result.stderr

    def test_empty_bridge_stdout_warns_and_runs_in_warn_mode(
        self, tmp_path: Path
    ) -> None:
        """Warn mode must at least WARN loudly when bridge stdout is empty."""
        bridge = self._fake_bridge(tmp_path, "")
        result = subprocess.run(
            [str(CLI_SCRIPT), "echo", "tj070-empty-warn-ran"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
                "TERMINAL_JAIL_INTERRUPTOR_MODE": "warn",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        if not (result.returncode == 2 and self._host_denies_bare_launch()):
            # Namespace-capable host: the command must actually have run.
            assert "tj070-empty-warn-ran" in result.stdout, (
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        # Warn semantics hold on EVERY host: loud warning, never a block.
        assert "WARN" in result.stderr or "WARNING" in result.stderr
        assert result.returncode != 126

    def test_whitespace_bridge_stdout_blocks_in_enforce(self, tmp_path: Path) -> None:
        """Whitespace-only stdout is just as unusable (boundary control)."""
        bridge = self._fake_bridge(tmp_path, "   ")
        result = subprocess.run(
            [str(CLI_SCRIPT), "true"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
                "TERMINAL_JAIL_INTERRUPTOR_MODE": "enforce",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 126
        assert "COMMAND BLOCKED" in result.stderr

    def test_normal_allow_verdict_unchanged(self, tmp_path: Path) -> None:
        """Control: a normal allow verdict keeps the fast path (command runs, no box)."""
        verdict = json.dumps(
            {
                "action": "allow",
                "command": "echo tj070-allow-ran",
                "modified": None,
                "rule_id": None,
                "reason": "",
            }
        )
        bridge = self._fake_bridge(tmp_path, verdict + "\n")
        result = subprocess.run(
            [str(CLI_SCRIPT), "echo", "tj070-allow-ran"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        if not (result.returncode == 2 and self._host_denies_bare_launch()):
            # Namespace-capable host: the command must actually have run.
            assert "tj070-allow-ran" in result.stdout, (
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
            assert result.returncode == 0
        # On every host an allow verdict must never produce a block box.
        assert "COMMAND BLOCKED" not in result.stderr

    def test_normal_block_verdict_unchanged(self, tmp_path: Path) -> None:
        """Control: a normal block verdict still exits 126 with the block box."""
        verdict = json.dumps(
            {
                "action": "block",
                "command": "true",
                "modified": None,
                "rule_id": "builtin-rm-rf-root",
                "reason": "Blocked.",
            }
        )
        bridge = self._fake_bridge(tmp_path, verdict + "\n")
        result = subprocess.run(
            [str(CLI_SCRIPT), "true"],
            cwd=str(PROJECT_ROOT),
            env=os.environ
            | {
                "TERMINAL_JAIL_BRIDGE": str(bridge),
                "USE_INTERRUPTOR": "1",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 126
        assert "COMMAND BLOCKED" in result.stderr


# ── C/D. Loader: load-time schema pass refuses bad-typed rule files ─────────


class TestLoaderSchemaValidation:
    def test_poison_priority_file_refused_loudly(self, tmp_path: Path) -> None:
        """A non-numeric priority is refused with a LOUD one-line stderr note
        naming the file — and the load ABORTS rather than proceeding with the
        operator's policy silently absent."""
        rules_dir = tmp_path / "rules.d"
        _write_rule_file(rules_dir, "bad.yaml", POISON_PRIORITY_YAML)
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            from terminal_jail.interruptor.rules import RuleLoader, RuleSchemaError

            loader = RuleLoader(system_dir=str(rules_dir))
            with pytest.raises(RuleSchemaError):
                loader.load_all()
        err = stderr.getvalue()
        assert "bad.yaml" in err, f"stderr note must name the file, got: {err!r}"
        assert err.count("\n") == 1, f"exactly one loud line, got: {err!r}"
        assert "priority" in err.lower()
        assert loader.schema_notes and "bad.yaml" in loader.schema_notes[0]

    def test_poison_priority_bridge_verdict_blocks(self, tmp_path: Path) -> None:
        """End-to-end through the BRIDGE (what the wrapper calls): a poison rule
        file must yield a BLOCKING verdict, never a silent allow.

        This is the TJ-GAP-070 repro path: the loader refuses the file, the
        refusal propagates out of ``intercept()``, and the bridge converts it
        into the fail-closed envelope.
        """
        rules_dir = tmp_path / "rules.d"
        _write_rule_file(rules_dir, "bad.yaml", POISON_PRIORITY_YAML)
        empty_system = tmp_path / "empty-system"
        empty_system.mkdir()
        proc = _bridge_main_inproc(
            '{"command": "true"}',
            extra_env={
                "TERMINAL_JAIL_INTERRUPTOR_RULES_DIR": str(empty_system),
                "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR": str(rules_dir),
            },
        )
        assert proc.returncode == 0
        response = json.loads(proc.stdout.decode())
        assert response["action"] == "block", (
            f"poison rule file must fail CLOSED through the bridge, got {response!r}"
        )
        assert response["rule_id"] == "[bridge-error]"
        assert response["reason"].startswith("[bridge-error]")

    def test_poison_priority_intercept_raises(self, tmp_path: Path) -> None:
        """The engine refuses to load, so intercept() raises instead of
        deciding on a partially-typed rule set."""
        from terminal_jail.interruptor.rules import RuleSchemaError

        rules_dir = tmp_path / "rules.d"
        _write_rule_file(rules_dir, "bad.yaml", POISON_PRIORITY_YAML)
        config = Config(mode="enforce", system_rules_dir=str(rules_dir))
        with pytest.raises(RuleSchemaError):
            intercept("true", config=config)

    def test_parse_failure_still_skips_with_warning_not_abort(
        self, tmp_path: Path
    ) -> None:
        """DF-TERMINAL-JAIL-6 does not regress: a file that cannot be PARSED
        (e.g. invalid YAML) is still skipped, and the remaining rules load."""
        rules_dir = tmp_path / "rules.d"
        _write_rule_file(rules_dir, "broken.yaml", "rules: [unclosed")
        _write_rule_file(
            rules_dir,
            "good.yaml",
            """\
rules:
  - id: good-block
    priority: 100
    action: block
    block_message: Blocked by good rule.
    match:
      type: pattern
      pattern: "danger-tool"
""",
        )
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            from terminal_jail.interruptor.rules import RuleLoader

            ruleset = RuleLoader(system_dir=str(rules_dir)).load_all()
        assert ruleset.by_id("good-block") is not None
        assert ruleset.by_id("p1") is None

    def test_clean_rules_still_load(self) -> None:
        """The shipped builtins file passes the schema pass untouched."""
        from terminal_jail.interruptor.rules import RuleLoader

        builtins_dir = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules"
        ruleset = RuleLoader(system_dir=str(builtins_dir)).load_all()
        assert len(ruleset) > 0
        assert ruleset.by_id("builtin-chmod-777-root") is not None

    def test_valid_user_rule_file_still_loads(self, tmp_path: Path) -> None:
        """A well-typed user rule keeps loading (no false refusals)."""
        rules_dir = tmp_path / "rules.d"
        _write_rule_file(
            rules_dir,
            "99-good.yaml",
            """\
rules:
  - id: user-block-force-push
    description: Block force pushes
    priority: 100
    action: block
    block_message: Force push blocked.
    match:
      type: pattern
      pattern: 'git\\s+push\\s+(?:--force|-f)(?:\\s|$)'
""",
        )
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            from terminal_jail.interruptor.rules import RuleLoader

            ruleset = RuleLoader(system_dir=str(rules_dir)).load_all()
        assert ruleset.by_id("user-block-force-push") is not None
        assert stderr.getvalue() == "", "no stderr noise for clean rules"

    def test_non_dict_entry_refused(self, tmp_path: Path) -> None:
        """A non-dict entry in the rules list is a schema violation."""
        rules_dir = tmp_path / "rules.d"
        _write_rule_file(rules_dir, "bad-shape.yaml", "rules:\n  - 42\n")
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            from terminal_jail.interruptor.rules import RuleLoader, RuleSchemaError

            with pytest.raises(RuleSchemaError):
                RuleLoader(system_dir=str(rules_dir)).load_all()
        err = stderr.getvalue()
        assert "bad-shape.yaml" in err

    def test_bool_priority_refused(self, tmp_path: Path) -> None:
        """`priority: true` is refused — bool is an int subclass, so a plain
        isinstance check would let it sort as 1 (silent policy change)."""
        rules_dir = tmp_path / "rules.d"
        _write_rule_file(
            rules_dir,
            "bool-prio.yaml",
            "rules:\n  - id: b1\n    priority: true\n    action: block\n",
        )
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            from terminal_jail.interruptor.rules import RuleLoader, RuleSchemaError

            with pytest.raises(RuleSchemaError):
                RuleLoader(system_dir=str(rules_dir)).load_all()
        assert "bool-prio.yaml" in stderr.getvalue()


# ── E. Loader: PyYAML-less host — the inert mirror is now LOUD (TJ-DF-039) ──


class TestLoaderPyYAMLLessMirrorIsLoud:
    """On a host without PyYAML the stdlib json fallback is the ONLY path a
    ``.yaml`` rule file can take (rules.py), and YAML is not JSON — so every
    installed rule file fails the fallback. Since TJ-DF-040 that failure is
    FAIL-CLOSED: one loud stderr note names the file and the cause (kept
    from TJ-DF-039), ``loader.parse_notes`` carries it for callers that
    cannot capture stderr, and the load ABORTS so the bridge emits the
    blocking ``[bridge-error]`` verdict instead of silently allowing
    everything.
    """

    @staticmethod
    def _install_shipped_mirror(tmp_path: Path) -> Path:
        """The shipped mirror in the dir an installed host reads (user dir)."""
        rules_dir = tmp_path / "rules.d"
        rules_dir.mkdir()
        shipped = (
            PROJECT_ROOT / "plugin" / "terminal_jail" / "rules" / "00-builtins.yaml"
        )
        (rules_dir / shipped.name).write_bytes(shipped.read_bytes())
        return rules_dir

    def test_control_shipped_mirror_loads_its_rules_with_pyyaml(
        self, tmp_path: Path
    ) -> None:
        """Control for the case below: with PyYAML present the SAME fixture is
        a non-empty rule set — so the [] there is caused by the missing parser,
        not by a broken fixture."""
        from terminal_jail.interruptor.rules import RuleLoader

        rules_dir = self._install_shipped_mirror(tmp_path)
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            loader = RuleLoader(system_dir=str(rules_dir), user_dir="/nonexistent")
            ruleset = loader.load_all()
        assert len(ruleset) > 0
        assert stderr.getvalue() == ""
        assert loader.parse_notes == []

    def test_mirror_fails_closed_loudly_without_pyyaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``sys.modules["yaml"] = None`` makes `import yaml` raise ImportError
        # deterministically — the fresh-host-without-PyYAML simulation (same
        # seam as test_rule_packs.py's PyYAML-less cases).
        monkeypatch.setitem(sys.modules, "yaml", None)
        from terminal_jail.interruptor.rules import (
            RuleFallbackParseError,
            RuleLoader,
        )

        rules_dir = self._install_shipped_mirror(tmp_path)
        mirror = rules_dir / "00-builtins.yaml"
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            loader = RuleLoader(system_dir=str(rules_dir), user_dir="/nonexistent")
            # TJ-DF-040: the load ABORTS — a policy the engine cannot read
            # must never come back as an empty, silently-allowed ruleset.
            with pytest.raises(RuleFallbackParseError):
                loader.load_all()
        err = stderr.getvalue()
        # exactly one loud line, naming the file and the cause
        assert err.count("\n") == 1, f"exactly one loud line, got: {err!r}"
        assert str(mirror) in err, f"note must name the file, got: {err!r}"
        assert "PyYAML unavailable" in err, f"note must name the cause: {err!r}"
        assert "NOT loaded" in err, f"note must say the rules are absent: {err!r}"
        assert loader.parse_notes == [err.rstrip("\n")]
        assert loader.schema_notes == []

    def test_without_pyyaml_builtin_still_blocks_via_engine_constants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The PyYAML-less BLOCK capability still exists — via the ENGINE
        builtins with NO rules files at all (dirs absent, nothing to parse).
        On a PyYAML-less host with an INSTALLED mirror the load aborts
        instead (see the tests above); this pins that the fail-closed
        posture removed the mirror path, not the engine's own protection."""
        monkeypatch.setitem(sys.modules, "yaml", None)
        from terminal_jail.interruptor import Action

        config = Config(
            mode="enforce",
            system_rules_dir=str(tmp_path / "absent-system"),
            user_rules_dir=str(tmp_path / "absent-user"),
        )
        result = intercept("rm -rf /", config=config)
        assert result.action == Action.BLOCK
        assert result.rule_id == "builtin-rm-rf-root"

    def test_a_json_rule_file_still_loads_without_pyyaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fallback is real: a JSON rules document (the one shape the
        fallback CAN read) still loads with no note and no stderr noise."""
        monkeypatch.setitem(sys.modules, "yaml", None)
        from terminal_jail.interruptor.rules import RuleLoader

        rules_dir = tmp_path / "rules.d"
        _write_rule_file(
            rules_dir,
            "10-json.yaml",
            json.dumps(
                {
                    "rules": [
                        {
                            "id": "json-block",
                            "priority": 100,
                            "action": "block",
                            "match": {"type": "pattern", "pattern": "danger-tool"},
                        }
                    ]
                }
            ),
        )
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            loader = RuleLoader(system_dir=str(rules_dir), user_dir="/nonexistent")
            ruleset = loader.load_all()
        assert ruleset.by_id("json-block") is not None
        assert stderr.getvalue() == ""
        assert loader.parse_notes == []


# ── F. TJ-DF-040: PyYAML-less JSON-fallback failure FAILS CLOSED ────────────


class TestPyYAMLLessParseFailureFailsClosed:
    """TJ-DF-040. TJ-DF-039 made the PyYAML-less JSON-fallback parse failure
    LOUD but kept it fail-open: on a fresh host without PyYAML the entire
    installed mirror (00-builtins.yaml and every operator ``.yaml`` file —
    the fallback is the ONLY path a ``.yaml`` file can take there) unloaded
    and the firewall silently degraded to allow-everything while the sandbox
    layer still ran. The loud stderr note does not change the verdict.

    The new posture follows the TJ-GAP-070 shape: the fallback failure
    raises ``RuleParseError`` after its one loud note, ``load_all`` ABORTS,
    and the bridge converts it into the blocking ``[bridge-error]``
    verdict — the engine refuses to allow on a policy it cannot read.

    Fail-open survives only for two NARROW, named classes (tests below):
    an UNREADABLE file (OSError — one bad permission must not brick the
    whole ruleset) and a syntax error a REAL YAML parser rejected
    (yaml.YAMLError — DF-TERMINAL-JAIL-6's documented skip-with-warning;
    only reachable when PyYAML is actually importable).
    """

    YAML_ONLY_USER_RULE = """\
rules:
  - id: pack-testonly-yaml-rule
    priority: 100
    action: block
    block_message: blocked by the yaml-only rule
    match:
      type: pattern
      pattern: "danger-tool"
"""

    @staticmethod
    def _yaml_only_rules_dir(tmp_path: Path) -> Path:
        """A rules dir whose ONLY file is YAML a JSON fallback cannot read."""
        rules_dir = tmp_path / "rules.d"
        _write_rule_file(rules_dir, "99-df040.yaml", TestPyYAMLLessParseFailureFailsClosed.YAML_ONLY_USER_RULE)  # fmt: skip
        return rules_dir

    def test_control_yaml_only_rule_blocks_with_pyyaml(self, tmp_path: Path) -> None:
        """(a) Control: WITH PyYAML the yaml-only rule blocks through the
        bridge — the fixture is a real policy, not a broken file."""
        rules_dir = self._yaml_only_rules_dir(tmp_path)
        proc = _bridge_main_inproc(
            '{"command": "danger-tool --do-it"}',
            extra_env={
                "TERMINAL_JAIL_INTERRUPTOR_RULES_DIR": str(tmp_path / "absent-system"),
                "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR": str(rules_dir),
            },
        )
        assert proc.returncode == 0
        response = json.loads(proc.stdout.decode())
        assert response["action"] == "block", response
        assert response["rule_id"] == "pack-testonly-yaml-rule", response

    def test_without_pyyaml_bridge_verdict_is_not_a_plain_allow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(b) The defect: without PyYAML the same policy must NOT yield a
        plain allow verdict — the bridge must return the blocking
        ``[bridge-error]`` envelope (fail closed), not ``{"action":
        "allow"}`` with ``rule_id: null``."""
        monkeypatch.setitem(sys.modules, "yaml", None)
        rules_dir = self._yaml_only_rules_dir(tmp_path)
        proc = _bridge_main_inproc(
            '{"command": "danger-tool --do-it"}',
            extra_env={
                "TERMINAL_JAIL_INTERRUPTOR_RULES_DIR": str(tmp_path / "absent-system"),
                "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR": str(rules_dir),
            },
        )
        response = json.loads(proc.stdout.decode())
        assert response["action"] == "block", (
            f"PyYAML-less parse failure must fail CLOSED, got {response!r}"
        )
        assert response["rule_id"] == "[bridge-error]", response
        assert response["reason"].startswith("[bridge-error]"), response
        assert "fail-closed" in response["reason"], response
        # The TJ-DF-039 loud note stays — the in-proc harness captures it
        # into proc.stderr (the outer mock would race the harness's own
        # capture, and the detail belongs on the bridge's stderr anyway).
        err = proc.stderr.decode()
        assert str(rules_dir / "99-df040.yaml") in err, err
        assert "UNPARSEABLE" in err, err

    def test_without_pyyaml_load_all_raises_rule_parse_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The loader aborts (TJ-GAP-070 style) instead of returning a
        ruleset that silently omits every ``.yaml`` file."""
        monkeypatch.setitem(sys.modules, "yaml", None)
        from terminal_jail.interruptor.rules import (
            RuleLoader,
            RuleParseError,
        )

        rules_dir = self._yaml_only_rules_dir(tmp_path)
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            loader = RuleLoader(system_dir=str(rules_dir), user_dir="/nonexistent")
            with pytest.raises(RuleParseError):
                loader.load_all()
        assert loader.parse_notes, "the loud note is still recorded"

    def test_without_pyyaml_installed_mirror_aborts_intercept(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fresh-host shape: the INSTALLED mirror (shipped
        00-builtins.yaml in the user dir) is YAML-only too, so on a
        PyYAML-less host ``intercept()`` itself must raise rather than
        decide on an empty ruleset (allow-everything)."""
        monkeypatch.setitem(sys.modules, "yaml", None)
        from terminal_jail.interruptor import Action
        from terminal_jail.interruptor.rules import RuleFallbackParseError

        rules_dir = TestLoaderPyYAMLLessMirrorIsLoud._install_shipped_mirror(tmp_path)
        config = Config(
            mode="enforce",
            system_rules_dir=str(tmp_path / "absent-system"),
            user_rules_dir=str(rules_dir),
        )
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            with pytest.raises(RuleFallbackParseError):
                intercept("echo benign", config=config)
        # The loud note still names the mirror (the raise's detail).
        assert "00-builtins.yaml" in stderr.getvalue()
        assert Action.BLOCK  # (import liveness; the posture is the raise)

    def test_unreadable_rule_file_still_fails_open_named_class(
        self, tmp_path: Path
    ) -> None:
        """The retained NARROW fail-open arm: a file that cannot be READ
        (OSError, e.g. permission) is skipped with the loud-note shape so
        one bad permission cannot brick the whole ruleset. Named explicitly
        in ``_load_file``'s comment — this test pins that it did not grow
        back into a blanket ``except Exception``."""
        rules_dir = tmp_path / "rules.d"
        _write_rule_file(
            rules_dir,
            "10-good.yaml",
            """\
rules:
  - id: good-block-df040
    priority: 100
    action: block
    match:
      type: pattern
      pattern: "danger-tool"
""",
        )
        unreadable = rules_dir / "20-locked.yaml"
        unreadable.write_text("rules: []\n")
        unreadable.chmod(0o000)
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            from terminal_jail.interruptor.rules import RuleLoader

            try:
                ruleset = RuleLoader(
                    system_dir=str(rules_dir), user_dir="/nonexistent"
                ).load_all()
            finally:
                unreadable.chmod(0o644)  # let tmp cleanup delete it
        assert ruleset.by_id("good-block-df040") is not None
        # The skip is loud (TJ-DF-039's shape, kept for this class).
        err = stderr.getvalue()
        assert "20-locked.yaml" in err, f"note must name the file: {err!r}"

    def test_yaml_parser_syntax_error_still_skips_df6_leniency(
        self, tmp_path: Path
    ) -> None:
        """DF-TERMINAL-JAIL-6's original leniency survives for the class it
        was written for: a SYNTAX error a real YAML parser rejected
        (yaml.YAMLError). Only reachable with PyYAML present — without it
        the same content fails closed via the JSON fallback (test above)."""
        from terminal_jail.interruptor.rules import RuleLoader

        rules_dir = tmp_path / "rules.d"
        _write_rule_file(rules_dir, "broken.yaml", "rules: [unclosed")
        _write_rule_file(
            rules_dir,
            "good.yaml",
            """\
rules:
  - id: good-block-df040
    priority: 100
    action: block
    match:
      type: pattern
      pattern: "danger-tool"
""",
        )
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            ruleset = RuleLoader(
                system_dir=str(rules_dir), user_dir="/nonexistent"
            ).load_all()
        assert ruleset.by_id("good-block-df040") is not None, (
            "DF-6 skip-with-warning survives for real-parser syntax errors"
        )
