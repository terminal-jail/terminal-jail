"""TJ-DF-033: the Metrics counters have real, reachable increment sites.

Before this change the 9-counter Metrics dataclass existed but NOTHING in
non-test code incremented it, so scripts/metrics-export.py exported a
structurally all-zero JSON forever (board finding TJ-DF-033). These tests
pin the wiring:

- real ``intercept()`` calls through the interruptor engine increment the
  wrap-path counters (``wrap_count``, ``wrap_time_ns_total``,
  ``commands_wrapped[_user_ns]``, ``byte_budget_rejections``,
  ``perf_regression_alert_count``) — same test patterns as
  plugin/test_interruptor.py;
- the plugin hooks in plugin/__init__.py increment the pass-through
  counters (``commands_passed_disabled``, ``commands_passed_no_unshare``)
  and post-exec ``jail_crashes``;
- BOTH import spellings of the counters module
  (``terminal_jail.plugin`` — engine/bridge path — and
  ``plugin.terminal_jail.plugin`` — Hermes plugin + metrics-export.py
  path) share ONE counter set, so the engine's bumps are exactly what the
  exporter reads.
"""

from __future__ import annotations

import dataclasses

import pytest
from terminal_jail.interruptor import Action, intercept
from terminal_jail.interruptor.config import Config
from terminal_jail.plugin import (
    _COUNTER_FIELDS,
    Metrics,
    _check_byte_budget,
    _check_slow_wrap,
    _max_command_bytes_from_environment,
    _record_wrap,
    get_metrics,
    reset_metrics,
)
from terminal_jail.plugin import (
    reset_metrics as reset_metrics_plugin_spelling,
)

import plugin  # noqa: F401 — Hermes-plugin spelling (plugin/__init__.py)
import plugin.terminal_jail.plugin as plugin_module

# The canonical counter vocabulary. A counter added to the Metrics dataclass
# must appear here (and get a wiring test) — this pin is what stops the
# exporter from silently regressing to structural zeros.
COUNTER_NAMES: tuple[str, ...] = (
    "commands_wrapped",
    "commands_wrapped_user_ns",
    "commands_passed_disabled",
    "commands_passed_no_unshare",
    "jail_crashes",
    "byte_budget_rejections",
    "wrap_time_ns_total",
    "wrap_count",
    "perf_regression_alert_count",
)

# Hermes plugin env vars this suite manipulates (same set as test_plugin.py).
ENVIRONMENT_VARIABLES = (
    "HERMES_TERMINAL_JAIL_ENABLED",
    "HERMES_TERMINAL_JAIL_COMMAND",
    "HERMES_TERMINAL_JAIL_MAX_COMMAND_BYTES",
)

ENV_DISABLED = "HERMES_TERMINAL_JAIL_ENABLED"
ENV_COMMAND = "HERMES_TERMINAL_JAIL_COMMAND"
ENV_MAX_BYTES = "HERMES_TERMINAL_JAIL_MAX_COMMAND_BYTES"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh counters + neutral env for every test (test_plugin.py pattern)."""
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    reset_metrics()


def _counter_values() -> dict[str, int]:
    return dataclasses.asdict(get_metrics())


def _nonzero_counters() -> dict[str, int]:
    return {name: value for name, value in _counter_values().items() if value != 0}


# ---------------------------------------------------------------------------
# Vocabulary pin: the dataclass and the test-side list cannot drift apart.
# ---------------------------------------------------------------------------


def test_counter_vocabulary_is_pinned() -> None:
    """Metrics has exactly the 9 documented counters, in the canonical order."""
    fields = tuple(f.name for f in dataclasses.fields(Metrics))
    assert fields == COUNTER_NAMES
    assert fields == _COUNTER_FIELDS


def test_fresh_counters_are_all_zero() -> None:
    reset_metrics()
    assert _nonzero_counters() == {}


# ---------------------------------------------------------------------------
# Engine wiring: real intercept() calls move the wrap-path counters.
# ---------------------------------------------------------------------------


class TestInterceptWrapCounters:
    def test_real_wrap_increments_wrapped_and_time(self) -> None:
        """A real auto-sandbox wrap bumps commands_wrapped + wrap counters."""
        result = intercept("pytest -q")
        assert result.action == Action.MODIFY
        assert result.modified is not None
        m = _counter_values()
        assert m["commands_wrapped"] == 1
        assert m["commands_wrapped_user_ns"] == 0
        assert m["wrap_count"] == 1
        assert m["wrap_time_ns_total"] > 0
        assert _nonzero_counters().keys() == {
            "commands_wrapped",
            "wrap_count",
            "wrap_time_ns_total",
        }

    def test_wraps_accumulate_across_calls(self) -> None:
        intercept("pytest -q")
        intercept("go test ./...")
        m = _counter_values()
        assert m["wrap_count"] == 2
        assert m["commands_wrapped"] == 2
        assert m["wrap_time_ns_total"] > 0

    def test_user_ns_wrap_counts_in_its_own_counter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mapped (user-namespace) prefix lands in commands_wrapped_user_ns.

        The prefix spelling is host-dependent; inject the TJ-DF-015 mapped
        spelling at the decider's prefix seam and drive a REAL intercept().
        """
        from terminal_jail.interruptor import decider as decider_module

        monkeypatch.setattr(
            decider_module,
            "_UNSHARE_PREFIX",
            "unshare --user --map-users=65534:100000:1 bash -c ",
        )
        result = intercept("pytest -q")
        assert result.action == Action.MODIFY
        assert "--map-users=" in (result.modified or "")
        m = _counter_values()
        assert m["commands_wrapped_user_ns"] == 1
        assert m["commands_wrapped"] == 0
        assert m["wrap_count"] == 1


class TestInterceptDisabledCounter:
    def test_disabled_mode_increments_passed_disabled(self) -> None:
        result = intercept("ls -la", config=Config(mode="disabled"))
        assert result.action == Action.ALLOW
        assert _counter_values()["commands_passed_disabled"] == 1
        # A disabled pass is NOT a wrap and NOT a no-unshare pass.
        assert _counter_values()["commands_wrapped"] == 0
        assert _counter_values()["commands_passed_no_unshare"] == 0

    def test_enabled_mode_does_not_count_disabled_passes(self) -> None:
        intercept("pytest -q")
        assert _counter_values()["commands_passed_disabled"] == 0


class TestByteBudget:
    def test_rejection_downgrades_wrap_to_allow_and_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An over-budget wrap returns the raw command (spec T18) and bumps
        byte_budget_rejections. The attempted wrap is still accounted for in
        wrap_count (measurement of what the engine DID, not what it shipped).
        """
        monkeypatch.setenv(ENV_MAX_BYTES, "16")
        result = intercept("pytest -q")
        assert result.action == Action.ALLOW
        assert result.command == "pytest -q"
        assert result.modified is None
        assert "byte budget" in result.reason
        m = _counter_values()
        assert m["byte_budget_rejections"] == 1
        assert m["wrap_count"] == 1  # attempt measured, verdict downgraded

    def test_within_budget_keeps_the_wrap(self) -> None:
        result = intercept("pytest -q")
        assert result.action == Action.MODIFY
        assert _counter_values()["byte_budget_rejections"] == 0

    @pytest.mark.parametrize("bad", ["not-a-number", "0", "-1", "  "])
    def test_invalid_budget_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch, bad: str
    ) -> None:
        """Spec T19: invalid budgets use the default — no rejection, no bump."""
        monkeypatch.setenv(ENV_MAX_BYTES, bad)
        assert _max_command_bytes_from_environment() == 131072
        result = intercept("pytest -q")
        assert result.action == Action.MODIFY
        assert _counter_values()["byte_budget_rejections"] == 0

    def test_budget_boundary_accepts_exact_fit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spec T17: a wrapped command exactly at the budget is accepted."""
        wrapped = "unshare --user --pid bash -c 'pytest'"
        limit = len(wrapped.encode("utf-8"))
        monkeypatch.setenv(ENV_MAX_BYTES, str(limit))
        assert _check_byte_budget(wrapped) is True
        assert _record_wrap(wrapped, 1_000) is True
        assert _counter_values()["byte_budget_rejections"] == 0

    def test_budget_boundary_rejects_one_over(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wrapped = "unshare --user --pid bash -c 'pytest'"
        limit = len(wrapped.encode("utf-8")) - 1
        monkeypatch.setenv(ENV_MAX_BYTES, str(limit))
        assert _check_byte_budget(wrapped) is False
        assert _record_wrap(wrapped, 1_000) is False
        assert _counter_values()["byte_budget_rejections"] == 1


class TestPerfRegressionAlert:
    def test_slow_wrap_alerts_on_absolute_bound_before_100_samples(
        self,
    ) -> None:
        """Spec §12: >50ms alerts even before the running average exists."""
        assert _record_wrap("x", 60_000_000) is True  # 60 ms > 50 ms
        assert _counter_values()["perf_regression_alert_count"] == 1
        assert _counter_values()["wrap_count"] == 1

    def test_fast_wrap_never_alerts(self) -> None:
        _record_wrap("x", 1_000_000)  # 1 ms
        assert _counter_values()["perf_regression_alert_count"] == 0

    def test_alert_requires_3x_running_average_after_100_samples(self) -> None:
        """After >=100 samples the 3x-average gate joins the absolute bound:
        60ms with a 1ms average is 60x and alerts; 5ms with a 1ms average is
        under the 50ms absolute bound and does not."""
        m = get_metrics()
        m.wrap_count = 100
        m.wrap_time_ns_total = 100_000_000  # 1 ms average
        _check_slow_wrap(60_000_000)  # >50ms AND >3x avg → alert
        assert _counter_values()["perf_regression_alert_count"] == 1
        reset_metrics()
        m = get_metrics()
        m.wrap_count = 100
        m.wrap_time_ns_total = 100_000_000
        _check_slow_wrap(5_000_000)  # 5ms: under the absolute bound → no alert
        assert _counter_values()["perf_regression_alert_count"] == 0

    def test_intercept_alert_path_is_reachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The engine's timing seam feeds the alert: a wrap measured at 60ms
        through a REAL intercept() lands in the alert counter (absolute-bound
        arm; the 3x-average arm is covered in the seam tests above)."""
        import terminal_jail.interruptor as engine

        class _ScriptedClock:
            """perf_counter_ns() returning scripted readings: t0=0, t1=60ms."""

            def __init__(self) -> None:
                self._readings = iter((0, 60_000_000))

            def perf_counter_ns(self) -> int:
                return next(self._readings)

        monkeypatch.setattr(engine, "time", _ScriptedClock())
        result = intercept("pytest -q")
        assert result.action == Action.MODIFY
        m = _counter_values()
        assert m["wrap_time_ns_total"] == 60_000_000
        assert m["perf_regression_alert_count"] == 1


# ---------------------------------------------------------------------------
# Plugin hook wiring (plugin/__init__.py).
# ---------------------------------------------------------------------------


class TestPluginHookCounters:
    def test_disabled_hook_arm_counts_pass(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_DISABLED, "0")
        plugin._on_pre_tool_call(  # type: ignore[attr-defined]
            tool_name="terminal", args={"command": "ls -la"}
        )
        assert _counter_values()["commands_passed_disabled"] == 1

    def test_no_unshare_hook_arm_counts_pass(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_DISABLED, "1")
        monkeypatch.setenv(ENV_COMMAND, "/nonexistent/tj-unshare-probe")
        plugin._on_pre_tool_call(  # type: ignore[attr-defined]
            tool_name="terminal", args={"command": "ls -la"}
        )
        assert _counter_values()["commands_passed_no_unshare"] == 1
        assert _counter_values()["commands_passed_disabled"] == 0

    def test_non_terminal_tool_counts_nothing(self) -> None:
        plugin._on_pre_tool_call(  # type: ignore[attr-defined]
            tool_name="read_file", args={"command": "ls -la"}
        )
        assert _nonzero_counters() == {}

    def test_jail_crashes_counts_wrapped_nonzero_exit(self) -> None:
        plugin._on_transform_terminal_output(  # type: ignore[attr-defined]
            command="unshare --user --pid bash -c 'exit 7'",
            output="",
            returncode=7,
        )
        assert _counter_values()["jail_crashes"] == 1

    def test_zero_exit_does_not_count_a_crash(self) -> None:
        plugin._on_transform_terminal_output(  # type: ignore[attr-defined]
            command="unshare --user --pid bash -c 'true'",
            output="",
            returncode=0,
        )
        assert _nonzero_counters() == {}

    def test_unwrapped_nonzero_exit_is_not_a_jail_crash(self) -> None:
        plugin._on_transform_terminal_output(  # type: ignore[attr-defined]
            command="pytest -q",
            output="",
            returncode=1,
        )
        assert _nonzero_counters() == {}


# ---------------------------------------------------------------------------
# One counter set under both import spellings.
# ---------------------------------------------------------------------------


class TestSharedCounterState:
    def test_both_spellings_bind_the_same_instance(self) -> None:
        """terminal_jail.plugin (engine) and plugin.terminal_jail.plugin
        (Hermes + metrics-export.py) must share ONE _metrics instance —
        separate instances would split totals between spellings and the
        exporter would read only its own spelling's half."""
        assert plugin_module._metrics is get_metrics(), (
            "import spellings desynced: engine bumps would be invisible to the exporter"
        )

    def test_reset_through_one_spelling_zeroes_the_other(self) -> None:
        _record_wrap("x", 1_000)
        assert _counter_values()["wrap_count"] == 1
        reset_metrics_plugin_spelling()
        assert _counter_values()["wrap_count"] == 0

    def test_engine_bump_is_visible_to_the_exporter_path(self) -> None:
        """The exact import scripts/metrics-export.py uses sees engine bumps."""
        intercept("pytest -q")
        # metrics-export.py does: from plugin.terminal_jail.plugin import get_metrics
        exported = dataclasses.asdict(plugin_module.get_metrics())
        assert exported["wrap_count"] == 1
        assert exported["commands_wrapped"] == 1
