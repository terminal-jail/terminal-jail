"""TJ-DF-024 — over-length fast path: long commands must never freeze the engine.

Defect (dogfood satellite, 2026-09-24): one 8KB argument cost 7.5s of CPU
inside ``intercept()`` and 20KB+ never returned — the blocklist regexes
backtrack polynomially on long tokens, so every shimmed shell invocation
carrying a multi-KB argument (base64 blob, long prompt echo) froze. The
fix is an engine-side length guard in ``intercept()``: a command longer
than the matching budget is allowed WITHOUT regex evaluation and marked
``rule_id="over-length-fastpath"`` with a ``[over-length]`` reason prefix.

Contract pinned here:

- The bridge answers an 8KB-arg and a 200KB-arg command quickly (the
  timing bounds are deliberately loose — order of magnitude, not the
  <200ms/<1s acceptance numbers, which are recorded in
  docs/dogfood/2026-09-24-firewall-library-integration.md; a loaded host
  must not flake this suite).
- The fast-path verdict is an ALLOW carrying an explicit marker rule id —
  never a block (the deny-list posture is unchanged: an over-length
  benign command must run), and never indistinguishable from an approved
  allow rule or a default-allow.
- The budget is a real knob: ``TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH``
  (read by config.py like every other interruptor env var); garbage
  values fall back to the default instead of silently disabling the guard.
- Short commands are untouched — rule provenance identical to before.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest
from terminal_jail import interruptor_bridge as bridge_module
from terminal_jail.interruptor import Action, Config, intercept

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_SCRIPT = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor_bridge.py"

FASTPATH_RULE_ID = "over-length-fastpath"
FASTPATH_REASON_PREFIX = "[over-length]"
DEFAULT_MAX_COMMAND_LENGTH = 4000


def _bridge_subprocess(
    payload: dict, extra_env: dict[str, str] | None = None
) -> tuple[dict, float]:
    """Run the bridge as a real subprocess; return (verdict, wall_seconds)."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(BRIDGE_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    wall = time.perf_counter() - t0
    assert proc.returncode == 0, f"bridge rc={proc.returncode}, stderr={proc.stderr!r}"
    verdict = json.loads(proc.stdout.splitlines()[-1])
    return verdict, wall


def _bridge_inproc(stdin_line: str) -> dict:
    """Drive ``interruptor_bridge.main()`` in-process; return the verdict dict."""
    stdin_buf = io.StringIO(stdin_line + "\n")
    stdout_buf = io.StringIO()
    with (
        mock.patch.object(sys, "stdin", stdin_buf),
        mock.patch.object(sys, "stdout", stdout_buf),
    ):
        bridge_module.main()
    return json.loads(stdout_buf.getvalue().splitlines()[-1])


# ── acceptance payloads through the real bridge (criterion 1 + 2) ────────────


class TestOverLengthThroughBridge:
    """The two acceptance payloads, through the same protocol the dogfood run froze on."""

    def test_bridge_8kb_arg_returns_quickly_with_marker(self) -> None:
        verdict, wall = _bridge_subprocess({"command": "echo " + "a" * 8000})
        # Order-of-magnitude guard only: the recorded acceptance numbers
        # (<200ms) live in the dogfood doc; 2s keeps this green on a
        # loaded host while still proving the 7.5s/10s blowup is gone.
        assert wall < 2.0, f"8KB arg took {wall:.2f}s — engine is still matching"
        assert verdict["action"] == "allow"
        assert verdict["rule_id"] == FASTPATH_RULE_ID
        assert verdict["reason"].startswith(FASTPATH_REASON_PREFIX)

    def test_bridge_200kb_arg_returns_quickly_with_marker(self) -> None:
        verdict, wall = _bridge_subprocess({"command": "echo " + "a" * 200_000})
        assert wall < 2.0, f"200KB arg took {wall:.2f}s — engine is still matching"
        assert verdict["action"] == "allow"
        assert verdict["rule_id"] == FASTPATH_RULE_ID

    def test_bridge_8kb_arg_reason_names_the_budget(self) -> None:
        verdict, _ = _bridge_subprocess({"command": "echo " + "a" * 8000})
        assert str(DEFAULT_MAX_COMMAND_LENGTH) in verdict["reason"]
        assert "8005" in verdict["reason"]  # the actual command length

    def test_bridge_over_length_block_vector_is_still_an_allow(self) -> None:
        # A long command whose SHORT prefix would block must not become a
        # block through the fast path: the guard allows, never blocks.
        verdict, _ = _bridge_subprocess({"command": "sudo " + "a" * 8000})
        assert verdict["action"] == "allow"
        assert verdict["rule_id"] == FASTPATH_RULE_ID


# ── engine-level verdict shape (criterion 2, in-process) ─────────────────────


class TestOverLengthVerdictShape:
    def test_intercept_marks_over_length_allow(self) -> None:
        cmd = "echo " + "a" * 8000
        result = intercept(cmd)
        assert result.action == Action.ALLOW
        assert result.command == cmd
        assert result.rule_id == FASTPATH_RULE_ID
        assert result.reason.startswith(FASTPATH_REASON_PREFIX)

    def test_marker_is_not_a_rule_id_in_any_builtin_layer(self) -> None:
        from terminal_jail.interruptor.allowlist import BUILTIN_ALLOWLIST
        from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST
        from terminal_jail.interruptor.sandbox import BUILTIN_SANDBOX

        engine_ids = {
            rule.id
            for rule in list(BUILTIN_BLOCKLIST)
            + list(BUILTIN_SANDBOX)
            + list(BUILTIN_ALLOWLIST)
        }
        assert FASTPATH_RULE_ID not in engine_ids

    def test_mode_disabled_stays_plain_allow_without_marker(self) -> None:
        result = intercept("echo " + "a" * 8000, config=Config(mode="disabled"))
        assert result.action == Action.ALLOW
        assert result.rule_id is None
        assert result.reason == ""

    def test_warn_mode_does_not_double_mark_the_fastpath(self) -> None:
        result = intercept("echo " + "a" * 8000, config=Config(mode="warn"))
        assert result.action == Action.ALLOW
        assert result.rule_id == FASTPATH_RULE_ID
        assert not result.reason.startswith("[WARN MODE]")

    def test_short_normal_commands_keep_rule_provenance(self) -> None:
        assert intercept("echo hello").rule_id == "allow-echo"
        assert intercept("ls -la").rule_id == "allow-ls"

    def test_command_exactly_at_budget_still_matches_normally(self) -> None:
        # Boundary: len > budget takes the fast path; AT the budget the
        # regex layers still run (and 'echo …' keeps its allow rule).
        cmd = "echo " + "a" * (DEFAULT_MAX_COMMAND_LENGTH - 5)  # exactly 4000 chars
        assert len(cmd) == DEFAULT_MAX_COMMAND_LENGTH
        result = intercept(cmd)
        assert result.action == Action.ALLOW
        assert result.rule_id == "allow-echo"


# ── the knob ─────────────────────────────────────────────────────────────────


class TestOverLengthKnob:
    def test_config_default(self) -> None:
        assert Config().max_command_length == DEFAULT_MAX_COMMAND_LENGTH
        assert Config.from_environ().max_command_length == DEFAULT_MAX_COMMAND_LENGTH

    def test_env_raises_threshold_short_command_still_matches_normally(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH", "20000")
        result = intercept("echo hello")
        assert result.rule_id == "allow-echo"

    def test_env_lowers_threshold_marks_medium_command(self, monkeypatch) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH", "64")
        result = intercept("echo " + "a" * 100)
        assert result.rule_id == FASTPATH_RULE_ID

    def test_env_zero_disables_the_guard(self, monkeypatch) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH", "0")
        result = intercept("echo " + "a" * 100)
        assert result.rule_id != FASTPATH_RULE_ID

    @pytest.mark.parametrize("bad", ["abc", "", "-5", "12.5"])
    def test_env_garbage_falls_back_to_default(self, monkeypatch, bad: str) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH", bad)
        assert Config.from_environ().max_command_length == DEFAULT_MAX_COMMAND_LENGTH

    def test_knob_reaches_the_bridge_subprocess(self) -> None:
        verdict, wall = _bridge_subprocess(
            {"command": "echo " + "a" * 100},
            extra_env={"TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH": "64"},
        )
        assert wall < 2.0
        assert verdict["rule_id"] == FASTPATH_RULE_ID
