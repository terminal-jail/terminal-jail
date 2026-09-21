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
  ``priority`` — so a typo can no longer reach evaluation time. Files the
  schema pass cannot PARSE keep DF-TERMINAL-JAIL-6's skip-with-warning
  behavior.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from terminal_jail import interruptor_bridge as bridge_module
from terminal_jail.interruptor import Config, intercept

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
BRIDGE_SCRIPT = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor_bridge.py"


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
        assert "tj070-warn-ran" in result.stdout, (
            f"warn mode must run the command, stdout={result.stdout!r}"
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
        assert "tj070-garbage-warn-ran" in result.stdout
        assert "WARN" in result.stderr or "WARNING" in result.stderr
        assert result.returncode != 126

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
        assert "tj070-allow-ran" in result.stdout
        assert result.returncode == 0
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
