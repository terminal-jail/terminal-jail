"""Rule set model and rule loader for the interruptor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# The placeholder shown when a rule declares no block_message of its own. It is
# deliberately generic, so it must never REPLACE a message that names the shape
# and scope of a policy — see ``inherit_override_message``.
DEFAULT_BLOCK_MESSAGE = "Command blocked by security policy."


class Rule:
    """A single rule in the interruptor rule engine.

    Rules are loaded from YAML files and define what to do when a
    command pattern matches.
    """

    __slots__ = (
        "action",
        "block_message",
        "block_message_explicit",
        "description",
        "id",
        "match",
        "modify",
        "priority",
    )

    def __init__(
        self,
        rule_id: str,
        description: str = "",
        priority: int = 50,
        action: str = "block",
        block_message: str | None = None,
        match: dict[str, Any] | None = None,
        modify: dict[str, Any] | None = None,
    ) -> None:
        self.id = rule_id
        self.description = description
        self.priority = priority
        self.action = action
        self.block_message = (
            block_message if block_message is not None else DEFAULT_BLOCK_MESSAGE
        )
        # Whether the caller/YAML supplied a message at all — distinct from the
        # message's value, since a rule may legitimately declare the placeholder
        # verbatim. A same-id override that declared none inherits the message
        # of the rule it replaces (DF-TERMINAL-JAIL-25).
        self.block_message_explicit = block_message is not None
        self.match = match or {}
        self.modify = modify

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rule:
        """Create a Rule from a YAML-derived dict.

        An omitted ``block_message`` stays DISTINGUISHABLE from one that was
        supplied: the key is passed through as ``None`` so a same-id override
        can inherit the overridden rule's message instead of silently
        reverting to the generic placeholder (DF-TERMINAL-JAIL-25).
        """
        return cls(
            rule_id=data.get("id", "unknown"),
            description=data.get("description", ""),
            priority=data.get("priority", 50),
            action=data.get("action", "block"),
            block_message=data.get("block_message"),
            match=data.get("match"),
            modify=data.get("modify"),
        )

    def __repr__(self) -> str:
        return f"Rule(id={self.id!r}, action={self.action!r}, priority={self.priority})"


class RuleSet:
    """A collection of rules, loaded from one or more rule files.

    Supports priority-ordered evaluation and built-in default rules.
    """

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self._rules: list[Rule] = rules or []
        self._sort()

    def _sort(self) -> None:
        """Sort rules by priority descending (highest first)."""
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def add(self, rule: Rule) -> None:
        """Add a rule and re-sort."""
        self._rules.append(rule)
        self._sort()

    def extend(self, rules: list[Rule]) -> None:
        """Add multiple rules and re-sort."""
        self._rules.extend(rules)
        self._sort()

    @property
    def rules(self) -> list[Rule]:
        """Get rules in evaluation order (highest priority first)."""
        return list(self._rules)

    def by_id(self, rule_id: str) -> Rule | None:
        """Find a rule by its ID."""
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return f"RuleSet({len(self._rules)} rules)"


def inherit_override_message(override: Rule, replaced: Rule | None) -> Rule:
    """Carry ``replaced``'s block_message onto ``override`` when it declared none.

    A same-id rule REPLACES the rule it shadows in its layer, so the replaced
    rule's message is the only description of the policy that is left. Before
    this, an override that supplied no ``block_message`` fell back to the
    generic placeholder — which is what the warn path then printed, so a
    downgraded verdict read::

        terminal-jail: WARNING - would have blocked: Command blocked by
        security policy.

    and told the operator nothing about which policy it was deciding on. The
    loss was at the MERGE, not on the warn path: the same omission also
    produced the generic text on a plain ``action: block`` override.

    Mutates and returns ``override`` (rules are per-layer objects built once
    per Decider, never shared with the built-in constant). ``replaced`` is
    ``None`` when no rule carried that id, in which case there is nothing to
    inherit and the rule keeps its own message.
    """
    if replaced is not None and not override.block_message_explicit:
        override.block_message = replaced.block_message
    return override


class RuleLoader:
    """Loads rules from YAML files in one or more directories.

    File loading is lenient — invalid files are skipped with a warning.
    """

    def __init__(
        self,
        system_dir: str = "/etc/terminal-jail/rules.d",
        user_dir: str = "",
    ) -> None:
        self.system_dir = system_dir
        self.user_dir = user_dir or str(
            Path.home() / ".config" / "terminal-jail" / "rules.d"
        )

    def load_all(self) -> RuleSet:
        """Load all rules from system and user directories.

        Rules are loaded in lexical order. User rules override system rules
        (same ID = user wins). Files load in lexical filename order within
        each directory.
        """
        rules: list[Rule] = []
        seen_ids: set[str] = set()

        for directory in [self.system_dir, self.user_dir]:
            directory_rules = self._load_directory(directory)
            for rule in directory_rules:
                replaced: Rule | None = None
                if rule.id in seen_ids:
                    # Override: replace existing rule
                    replaced = next((r for r in rules if r.id == rule.id), None)
                    rules = [r for r in rules if r.id != rule.id]
                # A later file's same-id rule shadows the earlier one, so an
                # omitted block_message would otherwise erase the only
                # description of the policy (DF-TERMINAL-JAIL-25) — this is the
                # seam the documented remedy uses (a pack rule overridden by a
                # later-sorting zz-local.yaml).
                rules.append(inherit_override_message(rule, replaced))
                seen_ids.add(rule.id)

        return RuleSet(rules)

    def _load_directory(self, directory: str) -> list[Rule]:
        """Load all rules from a single directory."""
        path = Path(directory)
        if not path.is_dir():
            return []

        rules: list[Rule] = []
        for file_path in sorted(path.iterdir()):
            if file_path.suffix not in (".yaml", ".yml"):
                continue
            file_rules = self._load_file(str(file_path))
            rules.extend(file_rules)
        return rules

    def _load_file(self, file_path: str) -> list[Rule]:
        """Load rules from a single YAML file.

        The file is expected to contain a top-level ``rules`` list.
        If the file can't be parsed, returns empty (fail-open).
        """
        try:
            return self._parse_file(file_path)
        except Exception:  # noqa: BLE001 — fail-open on file parse errors
            return []

    def _parse_file(self, file_path: str) -> list[Rule]:
        """Parse a YAML file and return a list of Rules.

        Uses stdlib json as fallback if PyYAML is not available.
        """
        with open(file_path) as f:
            content = f.read()

        rules: list[Rule] = []

        # Try PyYAML first
        try:
            import yaml  # type: ignore[import-untyped]

            # Prefer libyaml's C loader when available: identical safe-load
            # semantics, ~10x faster. The pure-Python loader costs ~9ms per
            # call once install.sh ships the full builtins file into the user
            # rules dir, regressing the warm-start benchmark (E2E-001-GAP-07).
            if hasattr(yaml, "CSafeLoader"):
                data = yaml.load(content, Loader=yaml.CSafeLoader)
            else:
                data = yaml.safe_load(content)
        except ImportError:
            # Fall back to json
            import json

            data = json.loads(content)

        if not isinstance(data, dict):
            return []

        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            return []

        for raw in raw_rules:
            if isinstance(raw, dict):
                rules.append(Rule.from_dict(raw))

        return rules
