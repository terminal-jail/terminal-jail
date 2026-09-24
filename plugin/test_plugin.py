from __future__ import annotations

import logging
import os

import pytest

import plugin
import plugin.terminal_jail.plugin as plugin_module

ENVIRONMENT_VARIABLES = (
    "HERMES_TERMINAL_JAIL_ENABLED",
    "HERMES_TERMINAL_JAIL_COMMAND",
    "HERMES_TERMINAL_JAIL_MAX_COMMAND_BYTES",
    "HERMES_TERMINAL_JAIL_LOG_LEVEL",
    "HERMES_TERMINAL_JAIL_USER_NS",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    plugin_module.LOGGER.setLevel(logging.WARNING)
    plugin_module.reset_metrics()


# ---------------------------------------------------------------------------
# Plugin registration & observability (transform functions removed in v1.1.x —
# see TJ-GAP-010 / HOOK-GAP-03: they were dead code, never wired to a hook)
# ---------------------------------------------------------------------------


def test_register_is_callable() -> None:
    """register() is the Hermes plugin entry point."""
    assert callable(plugin.register)


class TestEnabledFromEnvironment:
    """T4.3: HERMES_TERMINAL_JAIL_ENABLED parsing (fail-closed)."""

    def test_disabled_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_ENABLED", "0")
        assert plugin_module._enabled_from_environment() is False

    def test_disabled_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_ENABLED", "false")
        assert plugin_module._enabled_from_environment() is False

    def test_disabled_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_ENABLED", "off")
        assert plugin_module._enabled_from_environment() is False

    def test_disabled_no(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_ENABLED", "no")
        assert plugin_module._enabled_from_environment() is False

    def test_disabled_unrecognised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_ENABLED", "garbage")
        assert plugin_module._enabled_from_environment() is False

    def test_enabled_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HERMES_TERMINAL_JAIL_ENABLED", raising=False)
        assert plugin_module._enabled_from_environment() is True


class TestUnshareExecutableFromEnvironment:
    """T4.4: unshare path resolution."""

    def test_missing_unshare_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_COMMAND", "/nonexistent/unshare")
        assert plugin_module._unshare_executable_from_environment() is None

    def test_empty_command_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_COMMAND", "")
        assert plugin_module._unshare_executable_from_environment() is None

    def test_nul_byte_in_command_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If HERMES_TERMINAL_JAIL_COMMAND contains NUL, return None."""
        monkeypatch.setitem(os.environ, "HERMES_TERMINAL_JAIL_COMMAND", "safe-value")
        original_get = os.environ.get

        def _fake_get(key: str, default: object = None) -> object:
            if key == "HERMES_TERMINAL_JAIL_COMMAND":
                return "unshare\x00malicious"
            return original_get(key, default)

        monkeypatch.setattr(os.environ, "get", _fake_get)
        result = plugin_module._unshare_executable_from_environment()
        assert result is None

    def test_whitespace_command_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_COMMAND", "unshare --user")
        assert plugin_module._unshare_executable_from_environment() is None

    def test_resolved_path_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERMES_TERMINAL_JAIL_COMMAND", "unshare")
        resolved = plugin_module._unshare_executable_from_environment()
        assert resolved is None or "/" in resolved  # unshare may not be on PATH


# ── T4.6: Gateway restart resilience ──────────────────────────────


class TestGatewayRestartResilience:
    """Verify the plugin survives Hermes gateway restarts (module reload)."""

    def test_t46_reload_preserves_register(
        self,
        clean_environment: None,
    ) -> None:
        """After a simulated reload, register() is preserved."""
        import sys

        plugin_keys = [
            k for k in sys.modules if k == "plugin" or k.startswith("plugin.")
        ]
        for key in plugin_keys:
            del sys.modules[key]

        try:
            import importlib

            import plugin as plugin_reloaded

            importlib.reload(plugin_reloaded)

            assert callable(plugin_reloaded.register)
        finally:
            for key in plugin_keys:
                if key in sys.modules:
                    del sys.modules[key]
            import plugin as plugin_restored  # noqa: F401

    def test_t46_idempotent_import(
        self,
        clean_environment: None,
    ) -> None:
        """Importing the plugin module twice does not corrupt register state."""
        import importlib

        import plugin as plugin_ref

        importlib.reload(plugin_ref)

        assert callable(plugin_ref.register)


# ── T7: Observability metrics (export contract) ───────────────────


class TestMetrics:
    """Verify the metrics export surface (T7.1-T7.5)."""

    def test_metrics_initial_zero(self) -> None:
        plugin_module.reset_metrics()
        m = plugin_module.get_metrics()
        assert m.commands_wrapped == 0
        assert m.commands_wrapped_user_ns == 0
        assert m.commands_passed_disabled == 0
        assert m.commands_passed_no_unshare == 0
        assert m.jail_crashes == 0
        assert m.byte_budget_rejections == 0
        assert m.wrap_time_ns_total == 0
        assert m.wrap_count == 0
        assert m.perf_regression_alert_count == 0

    def test_reset_metrics_clears_all(self) -> None:
        plugin_module.reset_metrics()
        m = plugin_module.get_metrics()
        m.commands_wrapped = 7  # simulate a future hook population
        plugin_module.reset_metrics()
        assert plugin_module.get_metrics().commands_wrapped == 0
