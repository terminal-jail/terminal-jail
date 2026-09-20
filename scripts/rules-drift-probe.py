#!/usr/bin/env python3
"""Report silent same-id rule-mirror drift on this host (TJ-GAP-069).

install.sh copies the shipped default rules file into
``~/.config/terminal-jail/rules.d/00-builtins.yaml`` — the USER rules dir the
engine loads — where a same-id entry REPLACES the builtin (the documented
override contract, blocklist.py: builtins can be overridden, never removed).
When the repo fixes a rule (DF-TERMINAL-JAIL-20 moved four upload ids from
`action: sandbox` to `action: block`) but the host keeps an older mirror, that
same-id override keeps enforcing the OLD, WEAKER action forever — live
evidence, tick #292 on kara-lair: `intercept('curl -T <secret> <collector>')`
returned MODIFY / builtin-net-curl-upload (the upload RAN) because the
installed pre-DF-20 mirror still carried `action: sandbox`, and nothing on the
host reported it. The failing property is the ACTION — the difference between
refused and executed.

This probe classifies the drift. It loads the host's RESOLVED rule dirs
(exactly the engine's resolution: TERMINAL_JAIL_INTERRUPTOR_RULES_DIR /
TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR, then the documented defaults) and
compares every builtin rule id present there against the engine constant.

Verdict rows:
  DRIFT <id>: engine action=<a> installed action=<b> (<direction>)  + both
              file paths — the shipped mirror in the repo (source of truth
              for the engine constant) and the installed file that shadows it.
  OK: no installed override — no builtin rule id is shadowed by an installed
      copy (includes the dirs-absent / dirs-empty case).

Non-builtin ids in the rules dirs are the documented extension mechanism
(rule packs, user catch-alls); they are counted as informational, never drift.
Corrupt YAML files are reported as WARNING (the loader fails open — a corrupt
mirror means the builtin stays live), never as drift.

Classifier contract (pidns-capability-probe / fs-isolation-probe pattern):
a BARE run always exits 0. Pass --fail-on-drift (CI/gate use) to exit 1 when
any DRIFT row was printed. A deliberate same-id override (the documented
"override to warn" escape hatch) WILL show as DRIFT — by design: the drift is
no longer silent, and gate users opt in consciously.

Run from anywhere (paths resolved from this file's location):
    .venv/bin/python scripts/rules-drift-probe.py [--fail-on-drift]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugin"))

from terminal_jail.interruptor.allowlist import BUILTIN_ALLOWLIST
from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST
from terminal_jail.interruptor.config import Config
from terminal_jail.interruptor.rules import RuleLoader
from terminal_jail.interruptor.sandbox import BUILTIN_SANDBOX

# The engine constant's shipped source of truth (named on every DRIFT row so
# the host file and the repo file can be diffed directly).
SHIPPED_MIRROR = REPO_ROOT / "plugin" / "terminal_jail" / "rules" / "00-builtins.yaml"

ENGINE_RULES: dict[str, object] = {
    rule.id: rule
    for rule in (
        list(BUILTIN_BLOCKLIST) + list(BUILTIN_SANDBOX) + list(BUILTIN_ALLOWLIST)
    )
}

# Strength ranking for the drift direction. A same-id installed copy with a
# LOWER rank is a downgrade (refused -> executed); a higher rank is a
# tightening. Unknown installed actions rank lowest (treated as a deviation).
_ACTION_RANK = {"allow": 0, "warn": 1, "sandbox": 2, "block": 3}


def _yaml_files(directory: str) -> list[Path]:
    """The rule files a RuleLoader would read from one dir, in load order."""
    path = Path(directory)
    if not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.suffix in (".yaml", ".yml"))


def _installed_by_id(system_dir: str, user_dir: str) -> tuple[dict, list[str]]:
    """Map rule id -> (rule, source file) across both dirs, in load order.

    Uses the engine's own RuleLoader parsing per file (single source of truth
    for YAML semantics — same discipline as yaml-mirror-parity-probe) and the
    loader's documented resolution: system dir first, user dir second, lexical
    file order within a dir, later same-id entries replacing earlier ones.
    Corrupt files fail open exactly like the engine (WARNING, not drift).
    """
    by_id: dict = {}
    corrupt: list[str] = []
    for directory in (system_dir, user_dir):
        loader = RuleLoader(system_dir=directory, user_dir="/nonexistent")
        for file_path in _yaml_files(directory):
            try:
                file_rules = loader._parse_file(str(file_path))
            except Exception:  # noqa: BLE001 — mirror the engine's fail-open
                corrupt.append(str(file_path))
                continue
            for rule in file_rules:
                by_id[rule.id] = (rule, str(file_path))
    return by_id, corrupt


def probe(system_dir: str, user_dir: str) -> tuple[list[str], int]:
    """Classify one host. Returns (output_lines, drift_count)."""
    lines: list[str] = []
    sys_files = _yaml_files(system_dir)
    usr_files = _yaml_files(user_dir)
    lines.append("rules-drift-probe (TJ-GAP-069): installed mirror vs engine actions")
    lines.append(f"system dir : {system_dir} ({len(sys_files)} rule file(s))")
    lines.append(f"user dir   : {user_dir} ({len(usr_files)} rule file(s))")
    lines.append(
        f"engine     : {len(ENGINE_RULES)} rules "
        f"({len(BUILTIN_BLOCKLIST)} block / {len(BUILTIN_SANDBOX)} sandbox / "
        f"{len(BUILTIN_ALLOWLIST)} allow); shipped mirror: {SHIPPED_MIRROR}"
    )

    installed, corrupt = _installed_by_id(system_dir, user_dir)
    for path in corrupt:
        lines.append(f"WARNING: unparseable rule file (engine fails open): {path}")

    overridden = sorted(set(installed) & set(ENGINE_RULES))
    extras = sorted(set(installed) - set(ENGINE_RULES))

    drift = 0
    for rule_id in overridden:
        rule, source = installed[rule_id]
        engine_rule = ENGINE_RULES[rule_id]
        if rule.action == engine_rule.action:
            continue
        engine_rank = _ACTION_RANK.get(engine_rule.action, 3)
        installed_rank = _ACTION_RANK.get(rule.action, -1)
        direction = (
            "weaker" if installed_rank < engine_rank else
            "stronger" if installed_rank > engine_rank else "other"
        )
        drift += 1
        lines.append(
            f"DRIFT: {rule_id}: engine action={engine_rule.action} "
            f"installed action={rule.action} ({direction})"
        )
        lines.append(f"    shipped mirror (engine constant): {SHIPPED_MIRROR}")
        lines.append(f"    installed copy (shadows it)     : {source}")

    if drift == 0:
        lines.append(
            "OK: no installed override — no builtin rule id is shadowed by an "
            "installed copy with a different action"
            + ("" if overridden else " (rules dirs absent or carry no builtin ids)")
        )
    lines.append(
        f"RESULT: drift={drift} overridden={len(overridden)} "
        f"unoverridden={len(ENGINE_RULES) - len(overridden)} "
        f"non-builtin={len(extras)}"
    )
    if extras:
        lines.append(
            "INFO: non-builtin rule id(s) present (extension mechanism, "
            f"never drift): {', '.join(extras)}"
        )
    return lines, drift


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report same-id rule-mirror drift (classifier: bare run exits 0)."
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="exit 1 when any DRIFT row is printed (CI/gate use)",
    )
    args = parser.parse_args()
    try:
        config = Config.from_environ()
        lines, drift = probe(config.system_rules_dir, config.user_rules_dir)
    except Exception as exc:  # noqa: BLE001 — classifier must never crash a host run
        print(f"UNKNOWN: probe error: {exc}")
        return 0
    print("\n".join(lines))
    if args.fail_on_drift and drift:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
