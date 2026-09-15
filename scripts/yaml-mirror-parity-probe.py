"""YAML-mirror parity probe for terminal-jail (TJ-GAP-032, TJ-GAP-051).

The shipped default rules file (plugin/terminal_jail/rules/00-builtins.yaml) is
copied by install.sh into ``~/.config/terminal-jail/rules.d/`` — the directory
the engine loads as USER rules. The loader's same-id override REPLACES a builtin
with the user rule, so on any host that ran the documented install path the YAML
patterns ARE the live engine. A pattern that drifts weaker than its Python
counterpart silently weakens live verdicts (TJ-GAP-051: 12 verdicts flipped from
block/modify to allow).

This probe gates that:
  1. rule ids: shipped set == engine BUILTIN_* set,
  2. patterns: every shipped pattern string is byte-identical to the engine
     pattern — compared as LOADED values through the engine's own RuleLoader,
     never by manually un-escaping YAML source (double-unescaping fabricates
     false mismatches),
  3. behavior: the block/benign vector batteries (killpg vectors retained from
     TJ-GAP-032, plus the TJ-GAP-051 quoted-argv / script vectors) return the
     same verdict under both patterns,
  4. totals: loader per-layer counts match the engine constants.

Exit 0 = parity holds. Exit 1 = drift (either direction), reported per rule.

Run from anywhere (all paths are resolved from this file's location):
    .venv/bin/python scripts/yaml-mirror-parity-probe.py

Gateway-filter note: write regex-bearing probes to a FILE and run the file —
never inline ``python3 -c`` with patterns containing $, \\s or \\\\.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugin"))

from terminal_jail.interruptor.allowlist import BUILTIN_ALLOWLIST
from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST
from terminal_jail.interruptor.rules import RuleLoader
from terminal_jail.interruptor.sandbox import BUILTIN_SANDBOX

RULES_DIR = REPO_ROOT / "plugin" / "terminal_jail" / "rules"

ENGINE_RULES = {
    rule.id: rule
    for rule in (
        list(BUILTIN_BLOCKLIST) + list(BUILTIN_SANDBOX) + list(BUILTIN_ALLOWLIST)
    )
}
BLOCK_TOTAL = len(BUILTIN_BLOCKLIST)
SANDBOX_TOTAL = len(BUILTIN_SANDBOX)
ALLOW_TOTAL = len(BUILTIN_ALLOWLIST)

# TJ-GAP-032 killpg battery (retained): process-group kill vectors + benign
# controls. Every entry must match identically under the engine and YAML form.
BLOCK_VECTORS = [
    "os.killpg(1, signal.SIGTERM)",
    "os.killpg(0, 9)",
    "os.kill(1, signal.SIGKILL)",
    "process.kill(-1, ...)",
    "kill(1, 9)",
    "killpg(0, 2)",
]
BENIGN_VECTORS = [
    "os.killpg(2, signal.SIGTERM)",
    "kill(42, 9)",
    "os.kill(123, 1)",
]

# TJ-GAP-051 vectors: the exact command strings whose verdicts flipped when the
# YAML mirror carried the weaker pattern. (vector, expected_match)
# NOTE: wrapper-quoted argv (the standalone CLI single-quotes every token) is
# quote-stripped by the matcher BEFORE matching, so the vectors below are the
# stripped forms the patterns actually see (see TestQuotedArgvBypass, which
# pins the full quoted -> blocked path).
SCRIPT_VECTORS = [
    ("./script.sh", True),
    ("./deploy.py", True),
    ("bash evil_script.sh", True),
    ("python3 deploy.py", True),
    ("bash ./scripts/run.sh", True),
    ("echo hello", False),
]
FORK_BOMB_VECTORS = [
    (":(){ :|:& };:", True),
    (": (){ : |: & };:", True),
    ("echo ':'", False),
]
MKFS_VECTORS = [
    ("mkfs.ext4 /dev/sdb1", True),
    ("mkfs .ext4 /dev/sdb1", True),
    ("echo mkfs", False),
]

VECTOR_BATTERY: dict[str, list[tuple[str, bool]]] = {
    "builtin-killpg-pid1": [(v, True) for v in BLOCK_VECTORS]
    + [(v, False) for v in BENIGN_VECTORS],
    "auto-script": SCRIPT_VECTORS,
    "builtin-fork-bomb": FORK_BOMB_VECTORS,
    "builtin-mkfs": MKFS_VECTORS,
}


def matches(pattern: str, vector: str) -> bool:
    """Engine semantics: re.search with re.IGNORECASE (see interruptor matcher)."""
    return bool(re.search(pattern, vector, re.IGNORECASE))


def check_ids(loaded) -> bool:
    yaml_ids = {rule.id for rule in loaded.rules}
    engine_ids = set(ENGINE_RULES)
    only_yaml = sorted(yaml_ids - engine_ids)
    only_engine = sorted(engine_ids - yaml_ids)
    ok = not only_yaml and not only_engine
    print(
        f"[ids] yaml={len(yaml_ids)} engine={len(engine_ids)} "
        f"only-in-yaml={only_yaml} only-in-engine={only_engine} "
        f"-> {'OK' if ok else 'MISMATCH'}"
    )
    return ok


def check_patterns(loaded) -> bool:
    ok = True
    for rule_id in sorted(ENGINE_RULES):
        engine_rule = ENGINE_RULES[rule_id]
        yaml_rule = loaded.by_id(rule_id)
        if yaml_rule is None:
            print(f"[pattern] {rule_id}: MISSING from shipped YAML")
            ok = False
            continue
        engine_pattern = engine_rule.match.get("pattern", "")
        yaml_pattern = yaml_rule.match.get("pattern", "")
        if engine_pattern != yaml_pattern:
            ok = False
            print(f"[pattern] {rule_id}: DRIFT")
            print(f"    engine={engine_pattern!r}")
            print(f"    yaml  ={yaml_pattern!r}")
    print(
        f"[pattern] {len(ENGINE_RULES)} shipped rules compared -> "
        f"{'OK' if ok else 'MISMATCH'}"
    )
    return ok


def check_vectors(loaded) -> bool:
    ok = True
    for rule_id, vectors in sorted(VECTOR_BATTERY.items()):
        engine_pattern = ENGINE_RULES[rule_id].match.get("pattern", "")
        yaml_rule = loaded.by_id(rule_id)
        if yaml_rule is None:
            print(f"[vector] {rule_id}: MISSING from shipped YAML")
            ok = False
            continue
        yaml_pattern = yaml_rule.match.get("pattern", "")
        for vector, expected in vectors:
            engine_match = matches(engine_pattern, vector)
            yaml_match = matches(yaml_pattern, vector)
            good = engine_match == yaml_match == expected
            ok &= good
            print(
                f"[vector] {'OK ' if good else 'MISMATCH'} {rule_id} "
                f"{vector!r}: engine={engine_match} yaml={yaml_match} "
                f"expected={expected}"
            )
    return ok


def check_totals(loaded) -> bool:
    block = [r for r in loaded.rules if r.action == "block"]
    sandbox = [r for r in loaded.rules if r.action == "sandbox"]
    allow = [r for r in loaded.rules if r.action == "allow"]
    ok = (
        len(block) == BLOCK_TOTAL
        and len(sandbox) == SANDBOX_TOTAL
        and len(allow) == ALLOW_TOTAL
        and len(loaded.rules) == len(ENGINE_RULES)
    )
    print(
        f"[totals] block={len(block)}/{BLOCK_TOTAL} sandbox={len(sandbox)}/"
        f"{SANDBOX_TOTAL} allow={len(allow)}/{ALLOW_TOTAL} "
        f"total={len(loaded.rules)}/{len(ENGINE_RULES)} "
        f"-> {'OK' if ok else 'MISMATCH'}"
    )
    return ok


def main() -> int:
    print(f"repo root : {REPO_ROOT}")
    print(f"rules dir : {RULES_DIR}")
    print(f"engine    : {len(ENGINE_RULES)} rules "
          f"({BLOCK_TOTAL} block / {SANDBOX_TOTAL} sandbox / {ALLOW_TOTAL} allow)")
    # user_dir pinned to a non-existent path: this probe checks the SHIPPED file
    # only, never a host's already-installed (possibly stale) copy.
    loaded = RuleLoader(system_dir=str(RULES_DIR), user_dir="/nonexistent").load_all()

    ok = check_ids(loaded)
    ok &= check_patterns(loaded)
    ok &= check_vectors(loaded)
    ok &= check_totals(loaded)

    print("ALL PROBES PASS" if ok else "PROBE FAILURES: shipped YAML mirror is not parity-clean")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
