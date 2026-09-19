#!/usr/bin/env python3
"""Rule-pack validator / lister for the terminal-jail installer (TJ-GAP-061).

``install.sh`` is POSIX ``sh`` and cannot parse YAML, so every rule-pack
decision is made here, BEFORE the installer writes anything::

    rule-pack-tool.py validate <pack.yaml> --pack-name <name> [--rules-dir <dir>]
    rule-pack-tool.py list
    rule-pack-tool.py --help

``validate`` exits 0 and prints one summary line when the pack is installable,
and exits 2 with a ONE-LINE reason on stderr when it is refused. Refusal means
"nothing is written" — the installer runs this first and only copies the pack
file on exit 0.

Contract enforced by ``validate``:

* the file parses with the engine's own loader semantics (PyYAML
  ``CSafeLoader`` with a ``safe_load`` fallback, then stdlib ``json`` — the same
  chain as ``plugin/terminal_jail/interruptor/rules.py::_parse_file``);
* it is a mapping carrying a non-empty top-level ``rules:`` list;
* every rule carries ``id``/``action``/``match``, an ``action`` in
  {block, sandbox, allow, warn}, a ``match.type`` the engine's matcher can
  actually dispatch (derived from the engine at run time, never hardcoded), and
  a non-empty ``pattern``/``regex`` for the pattern matcher;
* every id is inside the pack's namespace ``pack-<pack-name>-*``;
* no id repeats inside the pack, and no id collides with
  (a) an ENGINE builtin id — derived at run time from
  ``terminal_jail.interruptor.{blocklist,sandbox,allowlist}`` — or
  (b) an id carried by a rule file already installed in the target rules dir,
  so two packs can never shadow each other.

The destination file ``<rules-dir>/terminal-jail-pack-<name>.yaml`` is
EXCLUDED from (b): that is the file the installer is about to replace, so
re-installing an already-installed pack is not a self-collision.

The tool fails CLOSED where the engine fails OPEN: an installed rule file that
cannot be parsed is a refusal (id collisions cannot be ruled out), not a
silently skipped file.
"""

from __future__ import annotations

import inspect
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

USAGE = """usage: rule-pack-tool.py validate <pack.yaml> --pack-name <name> [--rules-dir <dir>]
       rule-pack-tool.py list
       rule-pack-tool.py --help

validate  Refuse (exit 2, one-line reason on stderr) or accept (exit 0) a rule
          pack before the installer copies it. Checks the schema, the
          pack-<name>-* id namespace, and id collisions against the engine
          builtin rule set plus every rule file installed in --rules-dir.
list      Print <name>\\t<path>\\t<rule count> for every pack shipped next to
          this script (plugin/terminal_jail/rules/packs/*.yaml)."""

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PACKS_DIR = REPO_ROOT / "plugin" / "terminal_jail" / "rules" / "packs"
PLUGIN_DIR = REPO_ROOT / "plugin"

PACK_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
VALID_ACTIONS = ("block", "sandbox", "allow", "warn")
PACK_FILE_PREFIX = "terminal-jail-pack-"
PACK_FILE_SUFFIX = ".yaml"


class PackParseError(Exception):
    """A rule document that could not be read under engine semantics."""


def _refuse(reason: str) -> int:
    """Print a one-line refusal on stderr and return the refusal exit code."""
    print(f"rule-pack-tool: refused: {reason}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# engine-derived facts (never a hardcoded list)
# ---------------------------------------------------------------------------


def _import_engine(module: str) -> Any:
    """Import a ``terminal_jail.interruptor`` submodule from the repo checkout."""
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.insert(0, str(PLUGIN_DIR))
    import importlib

    return importlib.import_module(module)


def _engine_builtin_ids() -> set[str]:
    """The rule ids the engine ships as builtins (blocklist/sandbox/allowlist)."""
    blocklist = _import_engine("terminal_jail.interruptor.blocklist").BUILTIN_BLOCKLIST
    sandbox = _import_engine("terminal_jail.interruptor.sandbox").BUILTIN_SANDBOX
    allowlist = _import_engine("terminal_jail.interruptor.allowlist").BUILTIN_ALLOWLIST
    return {rule.id for rule in [*blocklist, *sandbox, *allowlist]}


def _engine_match_types() -> set[str]:
    """The match types the engine's matcher can dispatch.

    Derived from ``Matcher.match_segment``'s dispatch table in the engine
    source, so a pack can never declare a type the engine would silently
    ignore (an unknown type returns a non-match and the rule never fires).
    """
    matcher = _import_engine("terminal_jail.interruptor.matcher")
    dispatch_src = inspect.getsource(matcher.Matcher.match_segment)
    return set(re.findall(r'"([a-z_]+)"\s*:\s*self\._match_\w+', dispatch_src))


# ---------------------------------------------------------------------------
# document loading (engine semantics)
# ---------------------------------------------------------------------------


def _load_document(path: Path) -> Any:
    """Parse one rule document the way the engine's loader does.

    ``rules.py::_parse_file`` tries PyYAML (``CSafeLoader`` when libyaml is
    available, else ``safe_load``) and falls back to stdlib ``json`` only when
    PyYAML is missing. Mirrored here so a pack that the engine could load is
    never refused for a parsing difference.
    """
    with open(path) as handle:  # engine opens without an explicit encoding
        content = handle.read()

    try:
        import yaml

        if hasattr(yaml, "CSafeLoader"):
            return yaml.load(content, Loader=yaml.CSafeLoader)
        return yaml.safe_load(content)
    except ImportError:
        return json.loads(content)


def _load_rule_entries(path: Path, *, require_rules_key: bool) -> list[Any]:
    """Return the top-level ``rules`` list of a rule document.

    Raises ``PackParseError`` when the document is not a mapping, when the
    ``rules`` key is missing (only when ``require_rules_key`` — the engine
    itself defaults a missing key to an empty list) or is not a list.
    """
    try:
        data = _load_document(path)
    except Exception as exc:
        # A PyYAML ParserError is multi-line; the refusal contract is exactly
        # ONE line on stderr, so the parser text is folded onto one.
        detail = " ".join(f"{exc.__class__.__name__}: {exc}".split())
        raise PackParseError(f"cannot parse ({detail})") from exc

    if not isinstance(data, dict):
        raise PackParseError("top-level document is not a YAML mapping")

    if require_rules_key and "rules" not in data:
        raise PackParseError("no top-level 'rules' key")

    raw = data.get("rules", [])
    if not isinstance(raw, list):
        raise PackParseError("top-level 'rules' key is not a list")
    return raw


# ---------------------------------------------------------------------------
# collision oracle
# ---------------------------------------------------------------------------


def _installed_rule_ids(rules_dir: Path, exclude: Path) -> list[tuple[str, Path]]:
    """``(rule id, file)`` for every ``*.yaml``/``*.yml`` rule file installed.

    Fails closed: a file the engine could not parse is an error here, because
    a parser failure would make its ids invisible to the collision check.
    """
    found: list[tuple[str, Path]] = []
    if not rules_dir.is_dir():
        return found

    for path in sorted(rules_dir.iterdir()):
        if path.suffix not in (".yaml", ".yml"):
            continue
        if path.resolve() == exclude.resolve():
            continue
        try:
            entries = _load_rule_entries(path, require_rules_key=False)
        except PackParseError as exc:
            raise PackParseError(
                f"installed rule file {path} cannot be read ({exc}) — "
                "id collisions cannot be ruled out"
            ) from exc
        for entry in entries:
            if isinstance(entry, dict):
                rule_id = entry.get("id")
                if isinstance(rule_id, str) and rule_id:
                    found.append((rule_id, path))
    return found


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def _parse_named_options(args: list[str], allowed: tuple[str, ...]) -> tuple[dict, list[str]]:
    """Split ``args`` into option values and positionals (``--opt value``/``=``).

    Kept hand-rolled (no argparse) because a refusal must be exactly ONE line
    on stderr — argparse would dump usage blocks.
    """
    options: dict[str, str] = {}
    positionals: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg.startswith("--"):
            name, sep, inline = arg.partition("=")
            key = name[2:]
            if key not in allowed:
                raise ValueError(f"unknown option {name!r}")
            if sep:
                value = inline
            else:
                index += 1
                if index >= len(args):
                    raise ValueError(f"option {name!r} requires a value")
                value = args[index]
            options[key] = value
        elif arg.startswith("-") and arg != "-":
            raise ValueError(f"unknown option {arg!r}")
        else:
            positionals.append(arg)
        index += 1
    return options, positionals


def cmd_validate(args: list[str]) -> int:
    """Validate one pack file for installation into the resolved rules dir."""
    try:
        options, positionals = _parse_named_options(args, ("pack-name", "rules-dir"))
    except ValueError as exc:
        return _refuse(f"{exc} (try: rule-pack-tool.py --help)")

    if len(positionals) != 1:
        return _refuse(
            "validate takes exactly one pack file path "
            f"(got {len(positionals)}) — see rule-pack-tool.py --help"
        )
    pack_path = Path(positionals[0])

    pack_name = options.get("pack-name")
    if pack_name is None:
        return _refuse("validate requires --pack-name <name>")
    if not PACK_NAME_RE.fullmatch(pack_name):
        return _refuse(
            f"invalid pack name {pack_name!r} (expected [a-z0-9][a-z0-9-]*)"
        )

    if not pack_path.is_file():
        return _refuse(f"pack file not found: {pack_path}")

    try:
        builtin_ids = _engine_builtin_ids()
        match_types = _engine_match_types()
    except Exception as exc:  # noqa: BLE001 — refusal path: any failure refuses
        return _refuse(
            "cannot read the engine rule constants "
            f"({exc.__class__.__name__}: {exc}) — refusing rather than "
            "validating against a guessed list"
        )
    if not builtin_ids:
        return _refuse("the engine reported an empty builtin rule set — refusing")
    if not match_types:
        return _refuse(
            "cannot derive the engine's match types from "
            "interruptor/matcher.py — refusing"
        )

    try:
        entries = _load_rule_entries(pack_path, require_rules_key=True)
    except PackParseError as exc:
        return _refuse(f"{pack_path}: {exc}")

    if not entries:
        return _refuse(
            f"{pack_path}: top-level 'rules' list is empty — a pack that "
            "installs no rule is refused"
        )

    id_re = re.compile(rf"pack-{re.escape(pack_name)}-[a-z0-9][a-z0-9-]*")
    ids: list[str] = []
    for position, entry in enumerate(entries):
        where = f"rules[{position}]"
        if not isinstance(entry, dict):
            return _refuse(f"{pack_path}: {where} is not a mapping")
        rule_id = entry.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            return _refuse(f"{pack_path}: {where} has no 'id'")
        action = entry.get("action")
        if action not in VALID_ACTIONS:
            return _refuse(
                f"{pack_path}: {where} ({rule_id}) action {action!r} is not one "
                f"of {list(VALID_ACTIONS)}"
            )
        match = entry.get("match")
        if not isinstance(match, dict) or not match:
            return _refuse(f"{pack_path}: {where} ({rule_id}) has no 'match' mapping")
        match_type = match.get("type", "pattern")  # the matcher's own default
        if match_type not in match_types:
            return _refuse(
                f"{pack_path}: {where} ({rule_id}) match type {match_type!r} is "
                f"not dispatchable by the engine (valid: {sorted(match_types)})"
            )
        if match_type == "pattern":
            pattern = match.get("pattern") or match.get("regex")
            if not isinstance(pattern, str) or not pattern.strip():
                return _refuse(
                    f"{pack_path}: {where} ({rule_id}) is a pattern rule without "
                    "a non-empty 'pattern'/'regex'"
                )
        ids.append(rule_id)

    # Check order is deliberate: the COLLISION oracles run before the namespace
    # check so a pack that tries to shadow a builtin is refused for exactly that
    # reason instead of being masked by "id outside the pack namespace".
    duplicates = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
    if duplicates:
        return _refuse(
            f"{pack_path}: duplicate rule id(s) inside the pack: {duplicates}"
        )

    builtin_hits = sorted(set(ids) & builtin_ids)
    if builtin_hits:
        return _refuse(
            f"{pack_path}: rule id(s) {builtin_hits} collide with engine builtin "
            "ids — a pack may never shadow a builtin"
        )

    namespace_violations = [
        (position, rule_id)
        for position, rule_id in enumerate(ids, start=1)
        if not id_re.fullmatch(rule_id)
    ]
    if namespace_violations:
        position, rule_id = namespace_violations[0]
        return _refuse(
            f"{pack_path}: rules[{position - 1}] id {rule_id!r} is outside the "
            f"pack namespace 'pack-{pack_name}-*'"
        )

    rules_dir = Path(
        options.get("rules-dir")
        or os.environ.get("TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR")
        or str(Path.home() / ".config" / "terminal-jail" / "rules.d")
    )
    destination = rules_dir / f"{PACK_FILE_PREFIX}{pack_name}{PACK_FILE_SUFFIX}"
    try:
        installed = _installed_rule_ids(rules_dir, exclude=destination)
    except PackParseError as exc:
        return _refuse(f"{exc}")

    installed_hits = sorted(
        {rule_id for rule_id, _ in installed if rule_id in set(ids)}
    )
    if installed_hits:
        sources = sorted(
            {
                str(path)
                for rule_id, path in installed
                if rule_id in set(installed_hits)
            }
        )
        return _refuse(
            f"{pack_path}: rule id(s) {installed_hits} are already installed in "
            f"{rules_dir} ({', '.join(sources)}) — refusing to shadow them"
        )

    counts = Counter(entry["action"] for entry in entries)
    breakdown = ", ".join(f"{count} {action}" for action, count in sorted(counts.items()))
    print(
        f"rule-pack-tool: pack '{pack_name}' valid — {len(entries)} rule(s) "
        f"({breakdown}); checked against {len(builtin_ids)} engine builtin ids "
        f"and {len(installed)} installed rule id(s) in {rules_dir}; installs to "
        f"{destination}"
    )
    return 0


def cmd_list(args: list[str]) -> int:
    """Print ``<name>\\t<path>\\t<rule count>`` for every shipped pack."""
    if args:
        return _refuse(
            f"list takes no arguments (got {len(args)}) — see rule-pack-tool.py --help"
        )
    if not PACKS_DIR.is_dir():
        return _refuse(f"no rule packs directory at {PACKS_DIR}")

    rows: list[tuple[str, Path, int]] = []
    for path in sorted(PACKS_DIR.glob("*.yaml")):
        try:
            entries = _load_rule_entries(path, require_rules_key=True)
        except PackParseError as exc:
            return _refuse(f"shipped pack {path} cannot be read ({exc})")
        rows.append((path.stem, path, len(entries)))

    for name, path, count in rows:
        print(f"{name}\t{path}\t{count}")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    command = argv[0]
    if command in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if command == "validate":
        return cmd_validate(argv[1:])
    if command == "list":
        return cmd_list(argv[1:])
    return _refuse(f"unknown subcommand {command!r} (expected 'validate' or 'list')")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
