"""
terminal-jail interruptor — Bash command firewall.

Sits between the LLM and shell execution, evaluating every command against
a rule engine. Entry point: ``intercept()``.
"""

from __future__ import annotations

import time

from ..plugin import _bump, _record_wrap
from .config import Config
from .decider import Decider
from .matcher import Matcher
from .parser import (
    Segment,
    SegmentType,
    parse_command,
)
from .rules import RuleLoader, RuleSet

__all__ = [
    "Action",
    "Config",
    "Decider",
    "InterceptResult",
    "Matcher",
    "RuleLoader",
    "RuleSet",
    "Segment",
    "SegmentType",
    "Token",
    "TokenType",
    "intercept",
    "parse_command",
]

from .types import Action, InterceptResult, Layer


def intercept(command: str, *, config: Config | None = None) -> InterceptResult:
    """Evaluate a command against all rules and return a decision.

    Args:
        command: The raw shell command string to evaluate.
        config: Runtime configuration. If omitted, loaded from env vars.

    Returns:
        An InterceptResult with the action to take and metadata.

    Metrics (TJ-DF-033): this is the counters' production increment site.
    Disabled mode passes bump ``commands_passed_disabled``; a real wrap
    (MODIFY) bumps ``wrap_count``/``wrap_time_ns_total``/
    ``commands_wrapped[_user_ns]`` and is subject to the byte budget, whose
    rejection bumps ``byte_budget_rejections`` and downgrades the verdict to
    ALLOW. The wrap is measured as the engine evaluation that produced it.
    """
    if config is None:
        config = Config.from_environ()

    # Disabled mode → pass through
    if config.mode == "disabled":
        _bump("commands_passed_disabled")
        return InterceptResult(action=Action.ALLOW, command=command)

    # Empty command → pass through
    stripped = command.strip()
    if not stripped:
        return InterceptResult(action=Action.ALLOW, command=command)

    # Argument-size maximum (TJ-GAP-086): a clean, documented refusal BEFORE
    # parsing/evaluation. Cost at any size is O(len(input)) — one UTF-8
    # length + one slice copy — never the linear engine scan (~0.2 ms/KB),
    # so a stall-sized argument can no longer pin a host at all: it gets a
    # verdict naming the knob (`TERMINAL_JAIL_INTERRUPTOR_MAX_ARG_BYTES`)
    # and the limit. Warn mode still degrades to allow-with-warning below
    # (warn never blocks) and disabled mode already passed through above.
    if config.max_arg_bytes and len(command.encode("utf-8")) > config.max_arg_bytes:
        reason = (
            f"Command exceeds the maximum argument size: {len(command.encode('utf-8'))} "
            f"bytes > {config.max_arg_bytes} (tune with "
            f"TERMINAL_JAIL_INTERRUPTOR_MAX_ARG_BYTES; see README 'Environment "
            f"variables and limits')"
        )
        if config.mode == "warn":
            return InterceptResult(
                action=Action.ALLOW,
                command=command,
                reason=f"[WARN MODE] Would have blocked: {reason}",
            )
        return InterceptResult(
            action=Action.BLOCK,
            command="",
            rule_id="builtin-max-arg-bytes",
            reason=reason,
            layer=Layer.ENGINE,
        )

    # Parse the command into segments
    segments = parse_command(stripped)
    if not segments:
        # Unparseable → pass through with warning
        return InterceptResult(action=Action.ALLOW, command=command)

    # Evaluate each segment through the decider
    decider = Decider(config)
    wrap_started_ns = time.perf_counter_ns()
    result = decider.evaluate(segments, command)
    wrap_elapsed_ns = time.perf_counter_ns() - wrap_started_ns

    # A wrap happened: account for it (counters + perf alert + byte budget).
    # The mapped (user-namespace) launch is recognised by its --map-users
    # flags in the produced command (TJ-DF-015 prefix spellings).
    if result.action == Action.MODIFY and result.modified:
        user_ns = "--map-users=" in result.modified
        if not _record_wrap(result.modified, wrap_elapsed_ns, user_ns=user_ns):
            return InterceptResult(
                action=Action.ALLOW,
                command=command,
                rule_id=result.rule_id,
                reason=(
                    "Auto-sandbox skipped: wrapped command exceeds the "
                    "configured byte budget"
                ),
            )

    # Warn mode → override BLOCK to ALLOW
    if config.mode == "warn" and result.action == Action.BLOCK:
        return InterceptResult(
            action=Action.ALLOW,
            command=command,
            reason=f"[WARN MODE] Would have blocked: {result.reason}",
        )

    return result
