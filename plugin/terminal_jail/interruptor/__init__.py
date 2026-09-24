"""
terminal-jail interruptor — Bash command firewall.

Sits between the LLM and shell execution, evaluating every command against
a rule engine. Entry point: ``intercept()``.
"""

from __future__ import annotations

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

from .types import Action, InterceptResult

# The over-length fast-path marker (TJ-DF-024). Deliberately NOT a rule id:
# a synthetic id in a rule list would have to land in the YAML mirror
# (plugin/test_packaging.py pins the BUILTIN_* id set against
# 00-builtins.yaml in both directions), and a matching rule would still pay
# regex cost on exactly the payloads the fast path exists to skip. The
# marker rides an ALLOW verdict so a script can distinguish a fast-path
# pass-through from both an approved allow rule and a default-allow.
OVER_LENGTH_RULE_ID = "over-length-fastpath"
OVER_LENGTH_REASON_PREFIX = "[over-length]"


def intercept(command: str, *, config: Config | None = None) -> InterceptResult:
    """Evaluate a command against all rules and return a decision.

    Args:
        command: The raw shell command string to evaluate.
        config: Runtime configuration. If omitted, loaded from env vars.

    Returns:
        An InterceptResult with the action to take and metadata.
    """
    if config is None:
        config = Config.from_environ()

    # Disabled mode → pass through
    if config.mode == "disabled":
        return InterceptResult(action=Action.ALLOW, command=command)

    # Empty command → pass through
    stripped = command.strip()
    if not stripped:
        return InterceptResult(action=Action.ALLOW, command=command)

    # Over-length fast path (TJ-DF-024): the blocklist regexes backtrack
    # polynomially on long tokens — an 8KB argument cost ~7.5s of pure CPU
    # inside the matcher and 20KB+ never returned, freezing every shimmed
    # shell invocation that carried one. Past the matching budget the
    # command is ALLOWED without any regex evaluation and marked with the
    # OVER_LENGTH_RULE_ID marker. This is an allow-with-marker, never a
    # block: the engine's deny-list posture is unchanged (a legitimately
    # long benign command must still run), and a destructive SHORT prefix
    # inside an over-length command is not re-classified either — the
    # length guard trades match coverage on huge commands for bounded,
    # predictable latency. Budget 0 disables the guard.
    budget = config.max_command_length
    if budget and len(command) > budget:
        return InterceptResult(
            action=Action.ALLOW,
            command=command,
            rule_id=OVER_LENGTH_RULE_ID,
            reason=(
                f"{OVER_LENGTH_REASON_PREFIX} command is {len(command)} chars, "
                f"over the {budget}-char matching budget — allowed without "
                "regex evaluation (set TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH "
                "to tune, 0 to disable the fast path)"
            ),
        )

    # Parse the command into segments
    segments = parse_command(stripped)
    if not segments:
        # Unparseable → pass through with warning
        return InterceptResult(action=Action.ALLOW, command=command)

    # Evaluate each segment through the decider
    decider = Decider(config)
    result = decider.evaluate(segments, command)

    # Warn mode → override BLOCK to ALLOW
    if config.mode == "warn" and result.action == Action.BLOCK:
        return InterceptResult(
            action=Action.ALLOW,
            command=command,
            reason=f"[WARN MODE] Would have blocked: {result.reason}",
        )

    return result
