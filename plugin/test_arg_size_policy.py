"""TJ-GAP-086 — enforced argument-size maximum (policy, not vibes).

Contract under test:

1. POLICY: ``intercept()`` refuses (clean BLOCK verdict) any command whose
   UTF-8 size exceeds ``TERMINAL_JAIL_INTERRUPTOR_MAX_ARG_BYTES``
   (default 262144 = 256 KiB). The refusal names BOTH the knob and the
   limit in its reason. The check runs BEFORE parsing/evaluation, so an
   oversize input costs O(len) — never the linear scan curve.
2. UNDER-LIMIT BYTE-IDENTITY: verdict behavior for arguments at or under
   the limit is exactly what it was before the policy — same action,
   rule_id, layer, and reason strings.
3. KNOB: the env var raises/lowers the limit; unset/invalid/zero/negative
   values fall back to the DEFAULT (fail-safe — a typo'd knob must never
   re-arm unbounded evaluation).
4. MODE CONTRACTS PRESERVED: warn mode degrades the refusal to
   allow-with-warning (warn never blocks); disabled mode passes through
   (no engine at all). Both still skip evaluation, so the host is
   protected from the stall either way.
5. TRANSPORT FLOW-THROUGH: the refusal flows through the one-shot bridge
   and the resident engine seam as a normal verdict JSON object.

The default sits ABOVE TJ-DF-024's 200 KB benign-latency fixtures on
purpose: those regression tests must stay green unmodified (a 200 KB
command is still evaluated, just no longer guaranteed fast).
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest.mock as mock
from pathlib import Path

import pytest
from terminal_jail.interruptor import Config, intercept

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_SCRIPT = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor_bridge.py"

ENV_KNOB = "TERMINAL_JAIL_INTERRUPTOR_MAX_ARG_BYTES"
DEFAULT_MAX = 262144
RULE_ID = "builtin-max-arg-bytes"

_EMPTY_RULES_ENV = {
    "TERMINAL_JAIL_INTERRUPTOR_RULES_DIR": "",
    "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR": "",
}


def _padded(target_bytes: int) -> str:
    """ASCII command of exactly ``target_bytes`` UTF-8 bytes (echo + pad)."""
    cmd = "echo " + "a" * (target_bytes - 5)
    assert len(cmd.encode()) == target_bytes
    return cmd


@pytest.fixture(autouse=True)
def _pinned_empty_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin both rules dirs empty (quickstart §3a2's reproducibility trick):
    builtins-only engine, no operator policy (this host's user rules re-arm
    auto-sandbox on echo, which would change allow-verdict reasons)."""
    monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_RULES_DIR", "/nonexistent-tj-086")
    monkeypatch.setenv(
        "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR", "/nonexistent-tj-086"
    )


def _verdict(command: str) -> dict:
    """intercept() verdict as the bridge would serialize it."""
    result = intercept(command)
    return {
        "action": result.action,
        "rule_id": result.rule_id,
        "reason": result.reason,
        "layer": getattr(result, "layer", None),
    }


# ── 1. The refusal ──────────────────────────────────────────────────────────


class TestOverLimitRefusal:
    def test_over_default_limit_blocks(self) -> None:
        result = intercept(_padded(DEFAULT_MAX + 1))
        assert result.action == "block"
        assert result.rule_id == RULE_ID

    def test_refusal_names_knob_and_limit(self) -> None:
        """The clean-error requirement: reason names the env var AND the number."""
        oversize = _padded(DEFAULT_MAX + 4096)
        result = intercept(oversize)
        assert ENV_KNOB in result.reason
        assert str(DEFAULT_MAX) in result.reason
        assert "262145" in result.reason or "bytes" in result.reason

    def test_boundary_at_limit_evaluates(self) -> None:
        """Exactly AT the limit is allowed through (limit is a maximum, not
        an exclusive bound on the last legal byte)."""
        result = intercept(_padded(DEFAULT_MAX))
        assert result.action == "allow"

    def test_one_byte_over_refused(self) -> None:
        result = intercept(_padded(DEFAULT_MAX + 1))
        assert result.action == "block"

    def test_refusal_is_cheap(self) -> None:
        """The gate runs before evaluation: a 1 MB refusal is O(len), i.e.
        milliseconds — never the ~30x-of-20KB evaluation curve."""
        huge = _padded(DEFAULT_MAX * 4)  # 1 MiB
        import time

        t0 = time.perf_counter()
        result = intercept(huge)
        wall = time.perf_counter() - t0
        assert result.action == "block"
        assert wall < 0.5


# ── 2. Under-limit byte-identity ────────────────────────────────────────────


class TestUnderLimitByteIdentity:
    def test_small_allow_verdict_unchanged(self) -> None:
        v = _verdict("echo hello")
        assert v["action"] == "allow"
        assert v["rule_id"] == "allow-echo"
        assert v["layer"] == "engine"
        assert v["reason"] == ""

    def test_block_verdict_unchanged(self) -> None:
        v = _verdict("rm -rf /")
        assert v["action"] == "block"
        assert v["rule_id"] == "builtin-rm-rf-root"

    def test_verdict_identical_with_knob_present(self) -> None:
        """The same under-limit command yields the SAME verdict whether the
        knob is unset, at default, or generous — policy is invisible under
        the limit."""
        verdicts = []
        for env_value in (None, str(DEFAULT_MAX), str(DEFAULT_MAX * 8)):
            if env_value is None:
                os.environ.pop(ENV_KNOB, None)
            else:
                os.environ[ENV_KNOB] = env_value
            verdicts.append(_verdict("echo " + "a" * 50000))
        assert verdicts[0] == verdicts[1] == verdicts[2]
        # Restore: this test deliberately dirties the process env, and the
        # knob leaks into every later test in this module (Config reads it).
        os.environ.pop(ENV_KNOB, None)

    def test_20kb_benign_still_allows_via_evaluation(self) -> None:
        """TJ-DF-024's shape: an 8-20 KB benign command is EVALUATED (allow,
        rule_id null) — not short-circuited by anything."""
        result = intercept("echo " + "a" * 20000)
        assert result.action == "allow"
        assert result.rule_id is None or result.rule_id == "allow-echo"


# ── 3. The knob ─────────────────────────────────────────────────────────────


class TestKnob:
    def test_config_default(self) -> None:
        assert Config().max_arg_bytes == DEFAULT_MAX

    def test_config_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_KNOB, "1000")
        assert Config.from_environ().max_arg_bytes == 1000

    @pytest.mark.parametrize("raw", ["", "abc", "0", "-5", "12.5", "1e6"])
    def test_invalid_values_fall_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        """Fail-safe: a typo'd knob must never re-arm unbounded evaluation."""
        monkeypatch.setenv(ENV_KNOB, raw)
        assert Config.from_environ().max_arg_bytes == DEFAULT_MAX

    def test_raised_knob_allows_oversize(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_KNOB, str(DEFAULT_MAX * 2))
        result = intercept(_padded(DEFAULT_MAX + 1))
        assert result.action == "allow"

    def test_lowered_knob_refuses_small_args(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_KNOB, "100")
        assert intercept(_padded(101)).action == "block"
        assert intercept(_padded(100)).action == "allow"


# ── 4. Mode contracts ───────────────────────────────────────────────────────


class TestModeContracts:
    def test_warn_mode_degrades_to_allow_with_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_MODE", "warn")
        result = intercept(_padded(DEFAULT_MAX + 1))
        assert result.action == "allow"
        assert "[WARN MODE]" in result.reason
        assert ENV_KNOB in result.reason  # still names the knob

    def test_disabled_mode_passes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_MODE", "disabled")
        result = intercept(_padded(DEFAULT_MAX + 1))
        assert result.action == "allow"
        assert result.rule_id is None


# ── 5. Transport flow-through ───────────────────────────────────────────────


def _bridge_main_inproc(stdin_line: str) -> dict:
    """In-process one-shot bridge seam (same shape as
    test_bridge_fail_closed._bridge_main_inproc, kept local)."""
    from terminal_jail import interruptor_bridge as bridge_module

    stdout = io.StringIO()
    with (
        mock.patch.object(sys, "argv", [str(BRIDGE_SCRIPT)]),
        mock.patch.object(sys, "stdin", io.StringIO(stdin_line + "\n")),
        mock.patch.object(sys, "stdout", stdout),
    ):
        bridge_module.main()
    return json.loads(stdout.getvalue())


class TestTransportFlowThrough:
    def test_one_shot_bridge_refuses_oversize(self) -> None:
        verdict = _bridge_main_inproc(json.dumps({"command": _padded(DEFAULT_MAX + 1)}))
        assert verdict["action"] == "block"
        assert verdict["rule_id"] == RULE_ID
        assert ENV_KNOB in verdict["reason"]

    def test_resident_engine_seam_refuses_oversize(self) -> None:
        plugin_dir = str(PROJECT_ROOT / "plugin")
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)
        from terminal_jail import interruptor_resident as resident

        verdict = resident.evaluate_payload({"command": _padded(DEFAULT_MAX + 1)})
        assert verdict["action"] == "block"
        assert verdict["rule_id"] == RULE_ID

    def test_bridge_under_limit_verdict_unchanged(self) -> None:
        verdict = _bridge_main_inproc(json.dumps({"command": "echo hello"}))
        assert verdict["action"] == "allow"
        assert verdict["rule_id"] == "allow-echo"
        assert verdict["layer"] == "engine"


# ── 6. No fastpath marker regression (TJ-DF-024 vocabulary stays clean) ────


def test_no_skip_semantics_vocabulary() -> None:
    """The policy REFUSES; it must never reintroduce the rejected
    length-based SKIP vocabulary (TJ-DF-024's rejected attempt-1)."""
    import inspect

    from terminal_jail import interruptor as pkg

    src = inspect.getsource(pkg)
    assert "over-length-fastpath" not in src
    assert "OVER_LENGTH" not in src
