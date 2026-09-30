"""Core types for the interruptor — shared across all modules."""

from __future__ import annotations


class Action:
    """Possible actions the interruptor can take after evaluating a command."""

    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"
    WARN = "warn"
    LOG = "log"
    SANDBOX = "sandbox"


class Layer:
    """Which rule source the deciding rule came from (TJ-GAP-085).

    ``ENGINE`` — a BUILTIN_* rule from the engine's own Python constants
    (blocklist.py / allowlist.py / sandbox.py): no rules file was loaded,
    or the builtin was NOT overridden by a same-id rule.

    ``YAML`` — the shipped rules mirror (``00-builtins.yaml``) loaded from
    a rules.d directory — the system dir, or installed into the user dir,
    where a same-id entry REPLACES the builtin in its layer (TJ-GAP-051's
    silent-downgrade shape; the verdict now says so).

    ``USER`` — any other ``*.yaml`` in the operator's rules.d directory.

    ``PACK`` — a rule pack file the installer names
    ``terminal-jail-pack-*.yaml``.
    """

    ENGINE = "engine"
    YAML = "yaml"
    USER = "user"
    PACK = "pack"


class InterceptResult:
    """Result of evaluating a command against the rule engine.

    ``layer`` (TJ-GAP-085) names the rule source that produced the verdict:
    one of ``Layer`` above, defaulting to ``engine`` — the value that stands
    when no rule file was loaded, when a BUILTIN constant decided, and when
    NO rule matched at all (default-allow). Whenever ``rule_id`` names a
    rule, ``layer`` is the provenance of exactly that rule.
    """

    __slots__ = ("action", "command", "layer", "modified", "reason", "rule_id")

    def __init__(
        self,
        action: str = Action.ALLOW,
        command: str = "",
        modified: str | None = None,
        rule_id: str | None = None,
        reason: str = "",
        layer: str = Layer.ENGINE,
    ) -> None:
        self.action = action
        self.command = command
        self.modified = modified
        self.rule_id = rule_id
        self.reason = reason
        self.layer = layer

    def __repr__(self) -> str:
        return (
            f"InterceptResult(action={self.action!r}, "
            f"rule_id={self.rule_id!r}, layer={self.layer!r}, "
            f"reason={self.reason!r})"
        )
