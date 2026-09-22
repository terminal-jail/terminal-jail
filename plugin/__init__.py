"""
terminal-jail — observability plugin for Hermes terminal commands.

CURRENT LIMITATION (2026-07-20, HOOK-GAP-03): Hermes core does NOT expose a
pre-execution command-transform hook. The plugin's former command-wrapping
functions were removed in v1.1.x as dead code — they could not be wired to
command execution without a core change. The ``pre_tool_call`` hook can only
BLOCK or ALLOW tool calls — it cannot modify the command string.

This plugin provides:
- Observability via ``transform_terminal_output`` (stub — returns output unchanged)
- A pre_tool_call observer for tracking terminal tool usage
- Metrics export (``get_metrics`` / ``scripts/metrics-export.py``)

PID namespace wrapping is provided by the standalone CLI (``unshare``) and
the interruptor firewall, not by this plugin.
"""

from __future__ import annotations

import logging
from typing import Any

from .terminal_jail.plugin import (
    _enabled_from_environment,
    _unshare_executable_from_environment,
)

logger = logging.getLogger(__name__)


def _on_pre_tool_call(
    tool_name: str = "",
    args: Any = None,
    **kwargs: Any,
) -> None:
    """Observer: log terminal tool usage for observability.

    This fires before every tool call. We can only observe/log — we cannot
    transform the command here (the hook only supports block/allow).
    """
    if tool_name != "terminal":
        return

    command = args.get("command", "") if isinstance(args, dict) else ""
    jail_enabled = _enabled_from_environment()
    unshare_available = _unshare_executable_from_environment() is not None

    if jail_enabled and unshare_available:
        logger.info(
            "terminal-jail: observed terminal command (%d bytes); "
            "pre-execution wrapping is unavailable",
            len(command),
        )
    elif jail_enabled and not unshare_available:
        logger.warning(
            "terminal-jail: jail enabled but unshare not found; "
            "running command without isolation"
        )
    elif not jail_enabled:
        logger.debug("terminal-jail: disabled, passing through")


def _on_transform_terminal_output(
    command: str,
    output: str,
    returncode: int,
    **kwargs: Any,
) -> str | None:
    """Transform terminal output — primarily observability.

    Stub — returns the output unchanged. Output annotation is not
    implemented (observability-only plugin; see specs/plugin.md §10.1).
    """
    return None  # Don't modify output


def register(ctx) -> None:
    """Register terminal-jail hooks with the Hermes plugin system."""
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("transform_terminal_output", _on_transform_terminal_output)

    logger.info(
        "terminal-jail v1.2.0 loaded. "
        "NOTE: pre-execution command wrapping requires Hermes core "
        "pre-execution hooks (see task HOOK-GAP-03). "
        "Observability hooks registered."
    )


__all__ = [
    "register",
]
