from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final


class _LazyLogger:
    """Logger proxy that resolves the ``logging`` module on first use.

    Importing ``logging`` costs ~38 ms on CPython 3.14 (it drags
    ``traceback`` → ``_colorize`` → ``inspect``/``zipfile``/``tokenize``/
    ``shutil``). Every bridge invocation pays module-import cost before it
    answers a verdict, and the allow path — the overwhelmingly common one —
    logs nothing at all, so importing the whole logging stack to emit
    nothing was the single largest fixed cost of a one-shot evaluation
    (measured PERF-003). ``__getattr__`` delegation keeps every logger
    attribute (``setLevel``, ``addHandler``, ``propagate``, ``name``,
    ``isEnabledFor``) behaving exactly as the real logger does, and
    ``getLogger(name)`` returns the same singleton once resolved, so
    ``caplog`` and handlers are unaffected.
    """

    __slots__ = ("_name", "_logger")

    def __init__(self, name: str) -> None:
        self._name = name
        self._logger: Any = None

    def _resolve(self) -> Any:
        if self._logger is None:
            import logging

            self._logger = logging.getLogger(self._name)
        return self._logger

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)


LOGGER: Final[_LazyLogger] = _LazyLogger("terminal_jail")

_TRUTHY: Final[set[str]] = {"1", "true", "yes", "on"}
_FALSY: Final[set[str]] = {"", "0", "false", "no", "off"}


def package_version() -> str:
    """Return the terminal-jail version — derived, never hardcoded.

    Source of truth is the ``version`` declared in pyproject.toml, which
    setuptools publishes as distribution metadata: an installed copy (wheel
    or ``pip install -e .``) reports its own version via ``importlib.metadata``.
    When the distribution is not installed (bare source checkout), fall back
    to parsing pyproject.toml at the repo root; if even that is unavailable
    (e.g. an isolated single-file import), report ``"unknown"`` rather than
    a stale literal.
    """
    try:
        # Imported HERE, not at module scope: ``importlib.metadata`` costs
        # ~12 ms to import and is only needed to answer a version query, not
        # to evaluate a command (PERF-003). The stdlib always provides it;
        # the guard keeps the module importable without it.
        from importlib import metadata as importlib_metadata
    except ImportError:  # pragma: no cover - stdlib always ships it
        importlib_metadata = None  # type: ignore[assignment]
    if importlib_metadata is not None:
        try:
            return importlib_metadata.version("terminal-jail")
        except importlib_metadata.PackageNotFoundError:
            pass
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        import tomllib

        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
        return str(data["project"]["version"])
    except (ImportError, OSError, KeyError):
        return "unknown"


@dataclass
class Metrics:
    """Observability counters for terminal-jail plugin (T7.1-T7.4).

    Wired in TJ-DF-033: every counter has at least one real increment site
    reachable from production code paths (the interruptor engine's
    ``intercept()`` and the plugin's ``pre_tool_call`` observer).
    Counters are process-local by design: each process (Hermes plugin
    process, standalone CLI bridge invocation) counts only what it saw.
    """

    commands_wrapped: int = 0
    commands_wrapped_user_ns: int = 0
    commands_passed_disabled: int = 0
    commands_passed_no_unshare: int = 0
    jail_crashes: int = 0
    byte_budget_rejections: int = 0
    wrap_time_ns_total: int = 0
    wrap_count: int = 0
    perf_regression_alert_count: int = 0


# ONE instance per process, shared under BOTH import spellings.
#
# This module is importable as ``terminal_jail.plugin`` (engine path: tests,
# the interruptor engine, the JSON bridge) and as ``plugin.terminal_jail.plugin``
# (Hermes plugin path + scripts/metrics-export.py). Python treats those as two
# distinct module objects, so each would otherwise carry its OWN counter set
# and the exported totals would silently split between spellings. Whichever
# spelling is imported SECOND adopts the first one's _metrics instance (see
# _adopt_shared_metrics), so every importer sees the same counters. Any
# counter added to Metrics must also be added to
# plugin/test_metrics_counters.py::COUNTER_NAMES (which pins this list so
# wiring cannot silently regress to zeros).
_COUNTER_FIELDS: Final[tuple[str, ...]] = (
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

_metrics = Metrics()


def _adopt_shared_metrics() -> None:
    """Make a second-spelling import reuse the first spelling's counters."""
    import sys

    me = sys.modules.get(__name__)
    if me is None or getattr(me, "_METRICS_ADOPTED", False):
        return
    for alias in (
        "plugin.terminal_jail.plugin",
        "terminal_jail.plugin",
    ):
        other = sys.modules.get(alias)
        if other is not None and other is not me and hasattr(other, "_metrics"):
            me._metrics = other._metrics
            break
    me._METRICS_ADOPTED = True


_adopt_shared_metrics()


def get_metrics() -> Metrics:
    """Return the current metrics snapshot (for tests and observability)."""
    return _metrics


def reset_metrics() -> None:
    """Reset all metrics counters to zero (for tests).

    Mutates the shared instance IN PLACE: a second-spelling import binds its
    module-level ``_metrics`` name to the first spelling's instance, so
    rebinding a fresh object here would de-sync the spellings again.
    """
    for field in _COUNTER_FIELDS:
        setattr(_metrics, field, 0)


def _bump(counter: str, amount: int = 1) -> None:
    """Increment one metrics counter (canonical entry point for wiring)."""
    setattr(_metrics, counter, getattr(_metrics, counter) + amount)


def _enabled_from_environment() -> bool:
    raw = os.environ.get("HERMES_TERMINAL_JAIL_ENABLED", "true")
    value = raw.strip().lower()
    if value in _FALSY:
        return False
    if value in _TRUTHY:
        return True
    # Unrecognised non-empty value → fail closed for config, open for command.
    LOGGER.warning(
        "terminal-jail: unrecognised value %r for "
        "HERMES_TERMINAL_JAIL_ENABLED; disabling jail",
        raw,
    )
    return False


def _unshare_executable_from_environment() -> str | None:
    raw = os.environ.get("HERMES_TERMINAL_JAIL_COMMAND", "unshare")
    configured = raw.strip()
    if not configured:
        LOGGER.warning(
            "terminal-jail: HERMES_TERMINAL_JAIL_COMMAND is empty; "
            "PID namespace isolation unavailable"
        )
        return None
    if "\x00" in configured:
        LOGGER.warning(
            "terminal-jail: HERMES_TERMINAL_JAIL_COMMAND contains NUL; "
            "PID namespace isolation unavailable"
        )
        return None
    # Shell whitespace check — reject values containing spaces or tabs.
    if any(c in configured for c in " \t"):
        LOGGER.warning(
            "terminal-jail: HERMES_TERMINAL_JAIL_COMMAND %r contains "
            "shell whitespace; refusing unsafe value",
            configured,
        )
        return None
    # Imported HERE: ``shutil`` is only needed to resolve the unshare
    # executable, and the interruptor engine's metric path never calls this
    # (PERF-003 — module-import cost is paid by every bridge invocation).
    import shutil

    return shutil.which(configured)


# Byte budget for the wrapped command the engine produces (spec §6.3:
# HERMES_TERMINAL_JAIL_MAX_COMMAND_BYTES, default 131072). The wrapping
# plugin that originally consumed this budget was removed (TJ-GAP-010), but
# the interruptor engine still produces wrapped commands — the budget and
# its rejection counter are enforced at intercept() (TJ-DF-033).
_MAX_COMMAND_BYTES_ENV_VAR: Final[str] = "HERMES_TERMINAL_JAIL_MAX_COMMAND_BYTES"
_BYTE_BUDGET_DEFAULT: Final[int] = 131072

# A wrap slower than this is a perf-regression candidate (spec §12).
_WRAP_SLOW_NS: Final[int] = 50_000_000  # 50 ms


def _check_byte_budget(wrapped: str) -> bool:
    """True when the wrapped command is within the configured byte budget."""
    return len(wrapped.encode("utf-8")) <= _max_command_bytes_from_environment()


def _max_command_bytes_from_environment() -> int:
    """Parse ``HERMES_TERMINAL_JAIL_MAX_COMMAND_BYTES`` (spec §6.3).

    Missing/empty variable returns the 131072 default. Non-integer or
    non-positive values log one warning and return the default (T19).
    """
    raw = os.environ.get(_MAX_COMMAND_BYTES_ENV_VAR, "")
    if not raw:
        return _BYTE_BUDGET_DEFAULT
    try:
        value = int(raw, 10)
    except ValueError:
        LOGGER.warning(
            "terminal-jail: unrecognised value %r for %s; using default byte budget %d",
            raw,
            _MAX_COMMAND_BYTES_ENV_VAR,
            _BYTE_BUDGET_DEFAULT,
        )
        return _BYTE_BUDGET_DEFAULT
    if value <= 0:
        LOGGER.warning(
            "terminal-jail: non-positive value %r for %s; using default byte budget %d",
            raw,
            _MAX_COMMAND_BYTES_ENV_VAR,
            _BYTE_BUDGET_DEFAULT,
        )
        return _BYTE_BUDGET_DEFAULT
    return value


def _check_slow_wrap(elapsed_ns: int) -> None:
    """Count a perf-regression alert per spec §12 thresholds.

    A wrap counts as a regression when it exceeds 50ms AND — once the
    running average is established (>= 100 wraps) — is more than 3x the
    running average. Before 100 samples only the absolute 50ms bound applies.
    """
    if elapsed_ns <= _WRAP_SLOW_NS:
        return
    alert = True
    if _metrics.wrap_count >= 100:
        avg = _metrics.wrap_time_ns_total // _metrics.wrap_count
        alert = elapsed_ns > 3 * avg
    if alert:
        _bump("perf_regression_alert_count")


def _record_wrap(
    wrapped: str,
    elapsed_ns: int,
    *,
    user_ns: bool = False,
) -> bool:
    """Record one completed wrap; True when the byte budget accepts it.

    Accounts: wrap_count + wrap_time_ns_total always; commands_wrapped or
    commands_wrapped_user_ns (TJ-DF-015 mapped launch); the spec §12
    perf-regression check; and the byte budget, whose rejection bumps
    byte_budget_rejections. Logging follows spec §6.4: never the command.
    """
    _bump("wrap_count")
    _bump("wrap_time_ns_total", elapsed_ns)
    if user_ns:
        _bump("commands_wrapped_user_ns")
    else:
        _bump("commands_wrapped")
    _check_slow_wrap(elapsed_ns)
    accepted = _check_byte_budget(wrapped)
    if not accepted:
        _bump("byte_budget_rejections")
        LOGGER.warning(
            "terminal-jail: wrapped command exceeds the configured byte "
            "budget (%d bytes); unwrapping",
            len(wrapped.encode("utf-8")),
        )
    return accepted
