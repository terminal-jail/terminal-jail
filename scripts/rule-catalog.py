"""Generate docs/rule-catalog.md from the shipped default rules file.

DF-TERMINAL-JAIL-9: the built-in rule count has rotted repeatedly in the docs
(README/quickstart carried 30, then 54, as the engine grew). The count and the
per-rule catalog are therefore DERIVED, never hand-stated: this script parses
the shipped rules mirror (plugin/terminal_jail/rules/00-builtins.yaml — the
byte-copy install.sh drops into the user rules dir, i.e. the live firewall on
an installed host) and emits the committed catalog.

The mirror-only source is deliberate: the YAML file needs no PYTHONPATH and no
engine import, and plugin/test_packaging.py::
test_shipped_rules_yaml_mirrors_engine_builtin_ids independently enforces
mirror == engine, so a catalog generated from the mirror is parity-safe.

Usage:
    python3 scripts/rule-catalog.py             # (re)write docs/rule-catalog.md
    python3 scripts/rule-catalog.py --check     # exit 1 if the committed file drifted
    python3 scripts/rule-catalog.py --stdout    # print the catalog, write nothing

Byte-stability contract: the output must be identical across runs on an
unchanged rules file — run with --check after any rules change (or wire it
into the pre-commit gate) and re-commit the regenerated catalog.

Requires PyYAML (a declared runtime dependency of this repo;
``uv sync --dev`` or ``pip install pyyaml`` provides it).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_YAML = REPO_ROOT / "plugin" / "terminal_jail" / "rules" / "00-builtins.yaml"
CATALOG = REPO_ROOT / "docs" / "rule-catalog.md"

# Layer order = decider evaluation order (blocklist first, first match wins).
LAYERS = [
    ("block", "Critical Blocklist", "1000", "block"),
    ("sandbox", "Auto-Sandbox", "700", "rewrite into a namespace wrap (`modify`)"),
    ("allow", "Always-Allow", "500", "allow; further evaluation stops"),
]


def load_rules() -> list[dict]:
    data = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8"))
    rules = data.get("rules") if isinstance(data, dict) else None
    if not rules or not all(isinstance(r, dict) and "id" in r for r in rules):
        raise SystemExit(
            f"ERROR: {RULES_YAML} does not parse as a rules list "
            "(expected a top-level 'rules:' mapping of {id, action, ...} entries)"
        )
    return rules


def esc(text: str) -> str:
    """Escape pipe characters so a description cannot break the table cell."""
    return text.replace("|", "\\|")


def render(rules: list[dict]) -> str:
    counts = {action: 0 for action, _, _, _ in LAYERS}
    for rule in rules:
        action = rule.get("action")
        if action not in counts:
            raise SystemExit(
                f"ERROR: rule {rule['id']!r} has unknown action {action!r} — "
                "extend LAYERS in scripts/rule-catalog.py before regenerating"
            )
        counts[action] += 1

    out: list[str] = []
    out.append("# Built-in rule catalog")
    out.append("")
    out.append("<!-- GENERATED FILE — do not edit by hand.")
    out.append("     Regenerate:  python3 scripts/rule-catalog.py")
    out.append("     Drift gate:  python3 scripts/rule-catalog.py --check -->")
    out.append("")
    out.append(
        "This catalog is **generated** by `scripts/rule-catalog.py` from the "
        "shipped default rules file `plugin/terminal_jail/rules/"
        "00-builtins.yaml`. Editing it by hand achieves nothing — the next "
        "regeneration overwrites the edit. The rules file mirrors the engine "
        "constants (`BUILTIN_BLOCKLIST` / `BUILTIN_SANDBOX` / `BUILTIN_ALLOWLIST` "
        "in `plugin/terminal_jail/interruptor/`), and "
        "`plugin/test_packaging.py` enforces that the two stay identical "
        "(same ids, same patterns, same actions), so this catalog tracks the "
        "shipped engine."
    )
    out.append("")
    out.append("## Totals")
    out.append("")
    out.append("| Layer | Action | Priority | Rules |")
    out.append("|---|---|---|---:|")
    for action, title, priority, verdict in LAYERS:
        out.append(f"| {title} | `{action}` | {priority} | {counts[action]} |")
    out.append(f"| **Total** | | | **{len(rules)}** |")
    out.append("")
    out.append(
        f"**{len(rules)} built-in rules — {counts['block']} block + "
        f"{counts['sandbox']} sandbox + {counts['allow']} allow.** To recount "
        "at any time: `python3 scripts/rule-catalog.py --check` re-derives "
        "these numbers from the rules file and exits 1 if the committed "
        "catalog has drifted from it."
    )
    out.append("")
    out.append("## Rules by layer")
    out.append("")
    for action, title, priority, verdict in LAYERS:
        out.append(f"### {title} (`{action}`, priority {priority})")
        out.append("")
        out.append(f"Verdict on match: {verdict}.")
        out.append("")
        out.append("| Rule id | Scope |")
        out.append("|---|---|")
        for rule in rules:
            if rule.get("action") != action:
                continue
            desc = esc(str(rule.get("description", "")))
            out.append(f"| `{rule['id']}` | {desc} |")
        out.append("")
    out.append("## Reading the catalog")
    out.append("")
    out.append(
        "- The decider evaluates blocklist → allowlist → auto-sandbox → user "
        "rules; **first match wins**. Priorities order rules within a layer; "
        "they do not move a rule between layers."
    )
    out.append(
        "- A user rule under `~/.config/terminal-jail/rules.d/` (or "
        "`/etc/terminal-jail/rules.d/`) whose id matches one of these ids "
        "**replaces** the built-in in its layer — that is the supported way "
        "to soften a built-in to `warn`. There is no way to remove one."
    )
    out.append(
        "- A command matching **no** rule at all is ALLOWED (default-allow "
        "posture); `\"rule_id\": null` on an allow verdict is that case, not "
        "an approved decision."
    )
    out.append(
        "- All built-in rules are `match: type: pattern` rules (regex over the "
        "command, engine matcher semantics: `re.search` with `re.IGNORECASE`)."
    )
    out.append(
        "- Opt-in rule packs install additional rules with `pack-<name>-*` ids "
        "and never grow this set (see README *Rule packs*)."
    )
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="exit 1 if the committed catalog drifted")
    group.add_argument("--stdout", action="store_true", help="print the catalog, write nothing")
    args = parser.parse_args()

    rendered = render(load_rules())
    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    totals = (
        f"{len(load_rules())} rules "
        f"({sum(1 for r in load_rules() if r['action'] == 'block')} block / "
        f"{sum(1 for r in load_rules() if r['action'] == 'sandbox')} sandbox / "
        f"{sum(1 for r in load_rules() if r['action'] == 'allow')} allow)"
    )
    if args.check:
        if not CATALOG.exists():
            print(f"[catalog] MISSING {CATALOG} — run: python3 scripts/rule-catalog.py")
            return 1
        if CATALOG.read_text(encoding="utf-8") == rendered:
            print(f"[catalog] OK — {totals}; docs/rule-catalog.md up to date")
            return 0
        print(f"[catalog] DRIFT — {totals}; committed docs/rule-catalog.md is stale")
        print("          regenerate: python3 scripts/rule-catalog.py")
        return 1

    CATALOG.write_text(rendered, encoding="utf-8")
    print(f"[catalog] wrote {CATALOG} ({totals})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
