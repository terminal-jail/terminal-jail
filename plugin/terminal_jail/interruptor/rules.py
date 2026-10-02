"""Rule set model and rule loader for the interruptor."""

from __future__ import annotations

import sys
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


class RuleSchemaError(ValueError):
    """A rule file LOADED but carries a field whose type the engine cannot use.

    Distinct from a file that cannot be parsed at all: that split is now
    two-stage (TJ-DF-040). A syntax error a REAL YAML parser rejected
    (``RuleParseError``) is still skipped with a loud note — DF-TERMINAL-
    JAIL-6's leniency. The PyYAML-less JSON-fallback failure
    (``RuleFallbackParseError``) ABORTS the load, because without PyYAML
    that fallback is the only path a ``.yaml`` file can take and skipping
    would silently unload the entire installed policy. This error — a
    well-formed document whose field values would explode during
    EVALUATION — always aborts: ``priority: not-a-number`` reaches
    ``RuleSet._sort`` and raises ``TypeError`` inside ``intercept()``,
    which the bridge used to swallow into a fail-open allow (TJ-GAP-070).
    """


class RuleParseError(RuntimeError):
    """A rule file could not be PARSED into a rules document.

    Raised by ``_parse_file`` after its one loud stderr note naming the
    file. ``_load_file`` treats the plain form as DF-TERMINAL-JAIL-6's
    leniency class — skipped, but no longer silent — and the
    ``RuleFallbackParseError`` subclass as a refusal (load aborts,
    TJ-DF-040).
    """


class RuleFallbackParseError(RuleParseError):
    """The PyYAML-less JSON fallback could not parse a ``.yaml`` file.

    TJ-DF-040: on a host without PyYAML the stdlib-json fallback is the
    ONLY path a ``.yaml`` file can take, and YAML is not JSON — so every
    installed rule file (the shipped 00-builtins.yaml mirror included)
    fails here. Skipping would silently unload the whole policy while the
    sandbox layer still ran: the firewall would degrade to
    allow-everything with nothing on the verdict saying so. The load
    ABORTS instead; the bridge converts the raise into the blocking
    ``[bridge-error]`` verdict (TJ-GAP-070 shape).
    """


# ── rule field schema (TJ-GAP-070) ───────────────────────────────────────────
#
# Types are stated for every field the engine READS, in the order the field
# tables of Rule.from_dict / the Matcher dispatch use them. ``bool`` is
# rejected for the numeric fields explicitly: it is an ``int`` subclass, and
# ``priority: true`` would silently sort as 1 rather than fail.
_SCHEMA_TOP_LEVEL: dict[str, tuple[str, type | tuple[type, ...]]] = {
    "id": ("a string", str),
    "description": ("a string", str),
    "priority": ("an integer", int),
    "action": ("a string", str),
    "block_message": ("a string", (str, type(None))),
    "match": ("a mapping", dict),
    "modify": ("a mapping", (dict, type(None))),
}

# Nested MATCH fields the Matcher actually reads (matcher.py dispatch). An
# unknown ``match.type`` is a no-op today (MatchResult() with matched=False),
# so only the TYPES of the keys present are validated here.
_SCHEMA_MATCH: dict[str, tuple[str, type | tuple[type, ...]]] = {
    "type": ("a string", str),
    "pattern": ("a string", str),
    "regex": ("a string", str),
    "command": ("a string", str),
    "path": ("a string", str),
    "operator": ("a string", str),
    "conditions": ("a list", list),
    "not": ("a mapping or a list", (dict, list)),
}

# Nested MODIFY fields (userns / sandbox rewrite).
_SCHEMA_MODIFY: dict[str, tuple[str, type | tuple[type, ...]]] = {
    "type": ("a string", str),
    "command": ("a string", str),
    "prefix": ("a string", str),
    "sandbox": ("a string", str),
}


def _type_matches(value: Any, expected: type | tuple[type, ...]) -> bool:
    """Type test that refuses ``bool`` where a number is expected.

    ``isinstance(True, int)`` is True, so ``priority: true`` would pass a plain
    isinstance check and then sort as 1 — a silent policy change rather than a
    refusal. Every other type is a straight isinstance test.
    """
    if expected is int and isinstance(value, bool):
        return False
    if isinstance(expected, tuple) and int in expected and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def _check_field_group(
    scope: str,
    data: dict[str, Any],
    schema: dict[str, tuple[str, type | tuple[type, ...]]],
) -> str | None:
    """Return the first schema violation in ``data``, or None when it is clean."""
    for field, (label, expected) in schema.items():
        if field not in data:
            continue
        value = data[field]
        if not _type_matches(value, expected):
            return (
                f"field {scope}{field} must be {label}, "
                f"got {type(value).__name__} ({value!r})"
            )
    return None


def validate_rule_document(data: Any) -> str | None:
    """Validate a parsed rules.d document; return the first violation or None.

    The check is deliberately about TYPES the engine reads, not about policy
    completeness: a missing ``priority`` still defaults to 50 and a missing
    ``match`` still matches nothing, so those stay valid. Only a value the
    engine cannot use — the ``priority: not-a-number`` class — is refused.
    """
    if not isinstance(data, dict):
        return f"document must be a mapping, got {type(data).__name__}"
    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        return f"'rules' must be a list, got {type(raw_rules).__name__}"
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            return f"rule #{index + 1} must be a mapping, got {type(raw).__name__}"
        violation = _check_field_group("", raw, _SCHEMA_TOP_LEVEL)
        if violation:
            return f"rule #{index + 1} ({raw.get('id', 'no id')}): {violation}"
        match = raw.get("match")
        if isinstance(match, dict):
            violation = _check_field_group("match.", match, _SCHEMA_MATCH)
            if violation:
                return f"rule #{index + 1} ({raw.get('id', 'no id')}): {violation}"
        modify = raw.get("modify")
        if isinstance(modify, dict):
            violation = _check_field_group("modify.", modify, _SCHEMA_MODIFY)
            if violation:
                return f"rule #{index + 1} ({raw.get('id', 'no id')}): {violation}"
    return None


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

    Failure posture (TJ-GAP-070 as narrowed by TJ-DF-040):

    - A file the PyYAML-less JSON fallback cannot parse REFUSES the load:
      on a host without PyYAML that fallback is the ONLY path a ``.yaml``
      file can take, so the whole installed mirror (00-builtins.yaml
      included) lands there — skipping it would silently unload the
      operator's entire policy while the sandbox layer still ran, i.e.
      allow-everything with nothing on the verdict saying so. The refusal
      is announced with one loud stderr note naming the file (TJ-DF-039)
      and ABORTS the load; the bridge turns it into a blocking
      ``[bridge-error]`` verdict.
    - A file whose content a REAL YAML parser rejected (PyYAML importable)
      is still skipped with a loud one-line stderr note — that is
      DF-TERMINAL-JAIL-6's documented leniency, now narrowed to the class
      it was written for. Same for a file that cannot be READ (OSError):
      one bad permission must not brick the whole ruleset, and the skip
      is announced, never silent.
    - A file that parses but whose FIELDS fail type validation (e.g.
      ``priority: not-a-number``) is REFUSED with a loud one-line stderr
      note naming the file, and the load ABORTS. Silently skipping it
      would be worse than either extreme: the operator's policy would
      appear installed while being absent. Aborting is also what makes
      the failure fail CLOSED — the bridge turns it into a blocking
      ``[bridge-error]`` verdict instead of an allow, so a typo cannot
      silently remove protection.

    ``schema_notes`` collects the loud notes so callers/tests can assert
    them without capturing stderr. ``parse_notes`` collects the same for
    the parse-side failures (TJ-DF-039).
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
        self.schema_notes: list[str] = []
        self.parse_notes: list[str] = []

    def load_all(self) -> RuleSet:
        """Load all rules from system and user directories.

        Rules are loaded in lexical order. User rules override system rules
        (same ID = user wins). Files load in lexical filename order within
        each directory.

        Raises:
            RuleSchemaError: a file parsed but carried fields the engine
                cannot use. The note naming the file has already been written
                to stderr at that point.
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
        """Load rules from a single file (TJ-DF-040 posture).

        The file is expected to contain a top-level ``rules`` list. Three
        failure classes, deliberately NOT one blanket catch:

        - REFUSES (load ABORTS, fail closed): a file the PyYAML-less JSON
          fallback cannot parse (``RuleFallbackParseError``) — on such a
          host that fallback is the ONLY path a ``.yaml`` file can take,
          so skipping would silently unload the entire installed policy
          (shipped mirror included). Same refusal/verdict path as
          ``RuleSchemaError`` (TJ-GAP-070). Also refused: a file that
          parses but violates the field schema.
        - SKIPS with one loud stderr note (fail open, DF-TERMINAL-JAIL-6's
          documented leniency, narrowed): a file whose content a REAL YAML
          parser rejected (``RuleParseError``) — only reachable when
          PyYAML is importable.
        - SKIPS with one loud stderr note (fail open, named arm): a file
          that cannot be READ (OSError). One bad permission must not brick
          the whole ruleset; the file's absence is announced, so it is a
          skip with warning, never a silent one.
        """
        try:
            return self._parse_file(file_path)
        except RuleSchemaError:
            # TJ-GAP-070: bad field types refuse the load (fail closed).
            raise
        except RuleFallbackParseError:
            # TJ-DF-040: without PyYAML this failure class covers EVERY
            # ``.yaml`` file on the host (the shipped mirror included) —
            # skipping it is the allow-everything degradation, so refuse
            # like a schema violation instead.
            raise
        except RuleParseError:
            # DF-TERMINAL-JAIL-6: a real YAML parser rejected the syntax.
            # Only reachable when PyYAML is importable (the fallback path
            # raises the RuleFallbackParseError subclass above), so this
            # skip cannot mask the fresh-host shape. Still loud via the
            # note ``_parse_file`` already wrote.
            return []
        except OSError:
            # Named fail-open arm: UNREADABLE file (permissions, race on
            # delete, loop). Load-time note printed by _parse_file.
            return []

    def _parse_file(self, file_path: str) -> list[Rule]:
        """Parse a YAML file and return a list of Rules.

        Uses stdlib json as fallback if PyYAML is not available. Parse
        failures raise typed errors AFTER the one loud stderr note naming
        the file: ``RuleFallbackParseError`` for the PyYAML-less fallback
        (refused by ``_load_file`` — fail closed, TJ-DF-040) and
        ``RuleParseError`` for a real YAML parser's syntax rejection
        (skipped by ``_load_file`` — DF-TERMINAL-JAIL-6 leniency, loud
        since TJ-DF-039).
        """
        try:
            with open(file_path) as f:
                content = f.read()
        except OSError as exc:
            note = (
                f"terminal-jail: UNREADABLE rule file {file_path} "
                f"({exc}) — the rules in this file are NOT loaded"
            )
            self.parse_notes.append(note)
            print(note, file=sys.stderr, flush=True)
            raise

        rules: list[Rule] = []

        # Try PyYAML first
        try:
            import yaml  # type: ignore[import-untyped]

            # Prefer libyaml's C loader when available: identical safe-load
            # semantics, ~10x faster. The pure-Python loader costs ~9ms per
            # call once install.sh ships the full builtins file into the user
            # rules dir, regressing the warm-start benchmark (E2E-001-GAP-07).
            try:
                if hasattr(yaml, "CSafeLoader"):
                    data = yaml.load(content, Loader=yaml.CSafeLoader)
                else:
                    data = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                # DF-TERMINAL-JAIL-6 leniency class (narrowed by TJ-DF-040):
                # a REAL parser rejected the SYNTAX. One loud note, then a
                # typed error ``_load_file`` skips the file for.
                note = (
                    f"terminal-jail: UNPARSEABLE rule file {file_path} "
                    f"(invalid YAML: {exc}) — the rules in this file are "
                    "NOT loaded"
                )
                self.parse_notes.append(note)
                print(note, file=sys.stderr, flush=True)
                raise RuleParseError(note) from exc
        except ImportError:
            # Fall back to json. On a host WITHOUT PyYAML this is the ONLY path
            # a ``.yaml`` rule file can take — and YAML is not JSON, so
            # ``json.loads`` raises on the shipped mirror (TJ-DF-039): the file
            # would contribute ZERO rules. DF-TERMINAL-JAIL-6's leniency is
            # about the engine's ACTION on an unparseable file; it says nothing
            # about the operator being told, and swallowing this quietly made a
            # whole installed mirror inert with no message anywhere on the host
            # (TJ-DF-039). TJ-DF-040 goes one step further: on such a host
            # skipping EVERY ``.yaml`` file silently degrades the firewall to
            # allow-everything while the sandbox layer still runs, so this
            # class is REFUSED (``RuleFallbackParseError``; ``_load_file``
            # aborts the load and the bridge emits the blocking
            # ``[bridge-error]`` verdict). The note stays one line, in the
            # TJ-GAP-070 style.
            import json

            try:
                data = json.loads(content)
            except Exception as exc:  # noqa: BLE001 — re-raised typed below
                note = (
                    f"terminal-jail: UNPARSEABLE rule file {file_path} "
                    f"(PyYAML unavailable, JSON fallback failed: {exc}) "
                    "— the rules in this file are NOT loaded"
                )
                self.parse_notes.append(note)
                print(note, file=sys.stderr, flush=True)
                raise RuleFallbackParseError(note) from exc

        # TJ-GAP-070: refuse a document the engine cannot EVALUATE. The parse
        # above succeeded, so DF-TERMINAL-JAIL-6's skip path (which is for
        # unparseable files) is not the right remedy here: skipping would make
        # an installed-looking policy silently absent. The note goes to stderr
        # because there is no logger plumbed into the loader; it is one line so
        # it stays readable when a host shell invokes the bridge per command.
        violation = validate_rule_document(data)
        if violation is not None:
            note = (
                f"terminal-jail: REFUSING rule file {file_path}: {violation} "
                "— fix the field type (the rules in this file are NOT loaded)"
            )
            self.schema_notes.append(note)
            print(note, file=sys.stderr, flush=True)
            raise RuleSchemaError(note)

        if not isinstance(data, dict):
            return []

        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            return []

        for raw in raw_rules:
            if isinstance(raw, dict):
                rules.append(Rule.from_dict(raw))

        return rules
