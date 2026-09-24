#!/usr/bin/env python3
"""GTFOBins-sweep harness — catalog shape vs live engine verdicts (TJ-GAP-059).

GTFOBins describes several hundred binaries that can spawn a shell, read or
write an arbitrary file, load a library, or open a reverse shell. terminal-jail
deliberately does NOT try to block them all: vim, less, git and tar are the
legitimate tools of the very work the jail protects, so blocking them destroys
the sandbox's reason to exist. The consequence is that most of the GTFOBins
surface is ALLOWED — and until now that allow surface was invisible and
unguarded: nobody could say which invocation shapes the fleet had consciously
accepted, and a rules change could silently flip one of those decisions.

This harness is the measuring stick, not the wall. It sweeps a small
machine-readable seed catalog of real GTFOBins invocation shapes against the
live engine and reports, per GTFOBins function class (shell, sudo, file-read,
file-write, library-load, reverse-shell, ...):

  * a verdict matrix   — rows = function class, columns = live verdict counts,
                         with the binaries behind each count,
  * a coverage line    — how many recorded postures still match live verdicts,
  * POSTURE-DRIFT      — definitive postures the engine no longer honors,
  * REVIEW             — live ALLOW/MODIFY/SANDBOX verdicts with no conscious
                         posture recorded yet (the queue for a human decision).

Postures (per binary, per function class) are one of:

  allowed-conscious  the engine allows the invocation and we accept it — the
                     dual-use tool doing its designed job (say, `git status`).
  blocked            the engine must block it (an accepted protection, say
                     `sudo`). A silently-allowed `blocked` posture is the
                     regression this harness exists to catch.
  review             no conscious decision yet. The live verdict is reported
                     for visibility but never fails the gate.

It changes no rules and blocks nothing: it measures the shipped engine and
makes the conscious ALLOW decisions visible and regression-guarded in CI.

Hermetic by design: the sweep constructs the engine's Config with rule
directories that cannot exist, so it measures the SHIPPED built-ins
(BUILTIN_BLOCKLIST / BUILTIN_SANDBOX / BUILTIN_ALLOWLIST) identically on a dev
box, a hardened host (which has the 00-builtins.yaml mirror installed as user
rules), and CI. A host-local softening rule must not be able to edit what this
report claims.

The catalog is a SEED: ~18 binaries, one representative invocation per function
class, every entry carrying a rationale. It is meant to grow.

Usage:
    python3 scripts/gtfobins-sweep.py                    # full text report, exit 0
    python3 scripts/gtfobins-sweep.py --format json      # same data as JSON
    python3 scripts/gtfobins-sweep.py --check            # exit 1 on posture drift
    python3 scripts/gtfobins-sweep.py --check --stdout   # explicit stdout form

Requires PyYAML (a declared runtime dependency of this repo) and the repo's
`plugin/` directory on sys.path (bootstrapped below, so running from the repo
root works with the repo .venv python even when the package is not installed).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugin"
DEFAULT_CATALOG = REPO_ROOT / "scripts" / "gtfobins-catalog-seed.yaml"

# Rule directories that can never exist (this tree is never created): the sweep
# must observe the shipped engine's built-ins, never a host's rules.d overrides.
_NO_RULES_DIR = str(REPO_ROOT / "scripts" / ".gtfobins-sweep-no-rules.d")

POSTURE_ALLOWED_CONSCIOUS = "allowed-conscious"
POSTURE_BLOCKED = "blocked"
POSTURE_REVIEW = "review"
POSTURES = (POSTURE_ALLOWED_CONSCIOUS, POSTURE_BLOCKED, POSTURE_REVIEW)

# Mirrors terminal_jail.interruptor.types.Action (plain str constants in the
# engine). A test pins these equal to the engine's own attributes so the report
# cannot drift from the engine's vocabulary.
ACTION_ALLOW = "allow"
ACTION_BLOCK = "block"
ACTION_MODIFY = "modify"
ACTION_WARN = "warn"
ACTION_COLUMNS = (ACTION_BLOCK, ACTION_ALLOW, ACTION_MODIFY, ACTION_WARN)

CLASS_MATCH = "match"
CLASS_DRIFT_UNPROTECTED = "DRIFT-UNPROTECTED"
CLASS_DRIFT_OVERBLOCKED = "DRIFT-OVERBLOCKED"
CLASS_REVIEW = "REVIEW"

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_CATALOG_ERROR = 2

_TOP_KEYS = frozenset({"schema_version", "entries"})
_ENTRY_KEYS = frozenset({"name", "rationale", "classes"})
_CLASS_KEYS = frozenset({"class", "invocation", "expected", "note"})

CHECK_RULE_HELP = """\
--check exit rule:
  exit 1 when a DEFINITIVE posture drifted: an expected=blocked row that no
  longer blocks (DRIFT-UNPROTECTED) or an expected=allowed-conscious row that is
  no longer allowed (DRIFT-OVERBLOCKED). Rows marked expected=review have no
  conscious posture yet, so their live verdict is listed in the REVIEW section
  but never fails --check -- that is what lets the seed catalog carry observed
  ALLOW vectors while CI stays green.
  Exit 2 (fatal) only on catalog load/parse errors, naming the catalog path.
  Without --check the report is advisory and the exit code is 0.
"""


class CatalogError(Exception):
    """Raised for any catalog load/parse/validation failure."""


@dataclass(frozen=True)
class CatalogRow:
    """One (binary, function class) row of the seed catalog."""

    binary: str
    function_class: str
    invocation: str
    expected: str
    rationale: str
    note: str = ""


@dataclass(frozen=True)
class RowResult:
    """A catalog row plus the live engine verdict for its invocation."""

    binary: str
    function_class: str
    invocation: str
    expected: str
    rationale: str
    note: str
    action: str
    rule_id: str | None
    classification: str

    @property
    def drifted(self) -> bool:
        """True when a definitive posture no longer matches the live verdict."""
        return self.classification in (
            CLASS_DRIFT_UNPROTECTED,
            CLASS_DRIFT_OVERBLOCKED,
        )


@dataclass(frozen=True)
class SweepReport:
    """The catalog path plus every swept row."""

    catalog_path: str
    results: tuple[RowResult, ...]


# ── engine access ──────────────────────────────────────────────────


def load_engine() -> ModuleType:
    """Import the live engine module, bootstrapping sys.path first.

    The import is deliberately function-local: importing this module must have
    no side effects, and the repo checkout's ``plugin/`` directory is where
    ``terminal_jail`` lives when the package is not pip-installed (the CI test
    job installs pytest + PyYAML only).
    """
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.insert(0, str(PLUGIN_DIR))
    import terminal_jail.interruptor as engine

    return engine


def hermetic_config(engine: ModuleType) -> Any:
    """Engine config that ignores every host rule directory (see module doc)."""
    return engine.Config(
        mode="enforce",
        system_rules_dir=_NO_RULES_DIR,
        user_rules_dir=_NO_RULES_DIR,
    )


def classify(expected: str, action: str) -> str:
    """Map (expected posture, live action) onto a classification label."""
    if expected == POSTURE_REVIEW:
        return CLASS_REVIEW
    if expected == POSTURE_BLOCKED:
        return CLASS_MATCH if action == ACTION_BLOCK else CLASS_DRIFT_UNPROTECTED
    return CLASS_MATCH if action == ACTION_ALLOW else CLASS_DRIFT_OVERBLOCKED


def sweep(rows: Sequence[CatalogRow]) -> tuple[RowResult, ...]:
    """Evaluate every catalog row in-process against the live engine.

    Only string evaluation happens here: the invocations are matched by the
    engine's rule patterns, never executed.
    """
    engine = load_engine()
    config = hermetic_config(engine)
    results: list[RowResult] = []
    for row in rows:
        verdict = engine.intercept(row.invocation, config=config)
        action = str(verdict.action)
        rule_id = verdict.rule_id if isinstance(verdict.rule_id, str) else None
        results.append(
            RowResult(
                binary=row.binary,
                function_class=row.function_class,
                invocation=row.invocation,
                expected=row.expected,
                rationale=row.rationale,
                note=row.note,
                action=action,
                rule_id=rule_id,
                classification=classify(row.expected, action),
            )
        )
    return tuple(results)


# ── catalog loading ────────────────────────────────────────────────


def _one_line(text: str) -> str:
    """Collapse YAML folded/block scalars into one whitespace-normal line."""
    return " ".join(text.split())


def load_catalog(path: Path) -> tuple[CatalogRow, ...]:
    """Load and validate the seed catalog; raise CatalogError on any problem."""
    if not path.is_file():
        raise CatalogError(f"catalog not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogError(f"{path}: unreadable: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CatalogError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise CatalogError(f"{path}: top level must be a mapping with 'entries'")
    unknown = sorted(set(raw) - _TOP_KEYS)
    if unknown:
        raise CatalogError(f"{path}: unknown top-level key(s): {', '.join(unknown)}")
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise CatalogError(f"{path}: 'entries' must be a non-empty list")

    rows: list[CatalogRow] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        rows.extend(_parse_entry(path, index, entry, seen))
    return tuple(rows)


def _parse_entry(
    path: Path, index: int, entry: Any, seen: set[str]
) -> list[CatalogRow]:
    """Validate one catalog entry and return its rows."""
    where = f"{path}: entries[{index}]"
    if not isinstance(entry, dict):
        raise CatalogError(f"{where}: must be a mapping")
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise CatalogError(f"{where}: 'name' must be a non-empty string")
    name = name.strip()
    where = f"{path}: entries[{index}] ('{name}')"
    if name in seen:
        raise CatalogError(f"{where}: duplicate binary name")
    seen.add(name)
    unknown = sorted(set(entry) - _ENTRY_KEYS)
    if unknown:
        raise CatalogError(f"{where}: unknown key(s): {', '.join(unknown)}")
    rationale = entry.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise CatalogError(f"{where}: 'rationale' must be a non-empty string")
    classes = entry.get("classes")
    if not isinstance(classes, list) or not classes:
        raise CatalogError(f"{where}: 'classes' must be a non-empty list")

    rows: list[CatalogRow] = []
    for cls_index, cls in enumerate(classes):
        rows.append(_parse_class(path, where, cls_index, cls, name, rationale))
    return rows


def _parse_class(
    path: Path,
    entry_where: str,
    index: int,
    cls: Any,
    name: str,
    rationale: str,
) -> CatalogRow:
    """Validate one (binary, function class) row."""
    where = f"{entry_where}: classes[{index}]"
    if not isinstance(cls, dict):
        raise CatalogError(f"{where}: must be a mapping")
    unknown = sorted(set(cls) - _CLASS_KEYS)
    if unknown:
        raise CatalogError(f"{where}: unknown key(s): {', '.join(unknown)}")
    function_class = cls.get("class")
    if not isinstance(function_class, str) or not function_class.strip():
        raise CatalogError(f"{where}: 'class' must be a non-empty string")
    invocation = cls.get("invocation")
    if not isinstance(invocation, str) or not invocation.strip():
        raise CatalogError(f"{where}: 'invocation' must be a non-empty string")
    if "\n" in invocation:
        raise CatalogError(f"{where}: 'invocation' must be a single line")
    expected = cls.get("expected")
    if expected not in POSTURES:
        raise CatalogError(
            f"{where}: 'expected' must be one of {'/'.join(POSTURES)}, got {expected!r}"
        )
    note = cls.get("note", "")
    if not isinstance(note, str):
        raise CatalogError(f"{where}: 'note' must be a string when present")
    return CatalogRow(
        binary=name,
        function_class=function_class.strip(),
        invocation=invocation.strip(),
        expected=expected,
        rationale=_one_line(rationale),
        note=_one_line(note),
    )


# ── report data ────────────────────────────────────────────────────


def coverage(results: Sequence[RowResult]) -> tuple[int, int, float]:
    """Return (matched, definitive_total, percent) over definitive postures.

    ``expected=review`` rows carry no expectation, so they are excluded from
    the denominator -- coverage is "of the decisions we made, how many still
    hold", not "how much of the GTFOBins surface we have decided about".
    """
    definitive = [r for r in results if r.expected != POSTURE_REVIEW]
    matched = sum(1 for r in definitive if r.classification == CLASS_MATCH)
    total = len(definitive)
    percent = round(100.0 * matched / total, 1) if total else 0.0
    return matched, total, percent


def action_counts(results: Sequence[RowResult]) -> dict[str, int]:
    """Live verdict counts for every action seen, in a stable order."""
    counts: dict[str, int] = {action: 0 for action in ACTION_COLUMNS}
    for result in results:
        counts[result.action] = counts.get(result.action, 0) + 1
    return counts


def matrix(results: Sequence[RowResult]) -> dict[str, dict[str, Any]]:
    """Per-function-class live verdict counts plus the binaries behind them."""
    out: dict[str, dict[str, Any]] = {}
    for result in results:
        cell = out.setdefault(result.function_class, {})
        cell[result.action] = cell.get(result.action, 0) + 1
        # Sorted set: a binary appears once per distinct verdict, so a class
        # where one binary straddles block/allow keeps that contrast (php) while
        # two same-verdict rows of one binary (nice/shell) do not duplicate.
        cell.setdefault("binaries", set()).add(f"{result.binary}({result.action})")
    for cell in out.values():
        cell["binaries"] = sorted(cell["binaries"])
    return out


def drifted(results: Sequence[RowResult]) -> list[RowResult]:
    """Rows whose definitive posture no longer matches the live verdict."""
    return [r for r in results if r.drifted]


def reviewed(results: Sequence[RowResult]) -> list[RowResult]:
    """Rows with no conscious posture yet (live verdict shown for visibility)."""
    return [r for r in results if r.classification == CLASS_REVIEW]


def _rule(r: RowResult) -> str:
    return r.rule_id or "-"


# ── rendering ──────────────────────────────────────────────────────


def render_text(report: SweepReport) -> str:
    """Render the human report: matrix, coverage, drift, review, row detail."""
    results = report.results
    matched, total, percent = coverage(results)
    drift = drifted(results)
    review = reviewed(results)
    counts = action_counts(results)
    binaries = len({r.binary for r in results})

    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("GTFOBins sweep - catalog shape vs live engine verdicts (TJ-GAP-059)")
    lines.append("=" * 78)
    lines.append(f"catalog : {report.catalog_path}")
    lines.append("engine  : hermetic Config - shipped built-ins, host rules.d ignored")
    lines.append(f"entries : {binaries} binaries / {len(results)} class rows")
    lines.append(
        "verdicts: "
        + ", ".join(f"{action}={counts.get(action, 0)}" for action in ACTION_COLUMNS)
    )
    lines.append("")
    lines.append("Function-class verdict matrix (live verdict counts, then binaries)")
    lines.append("-" * 78)
    header = f"{'function class':<16}"
    for action in ACTION_COLUMNS:
        header += f" {action:>6}"
    header += "  binaries"
    lines.append(header)
    cells = matrix(results)
    for function_class in sorted(cells):
        cell = cells[function_class]
        row = f"{function_class:<16}"
        for action in ACTION_COLUMNS:
            row += f" {cell.get(action, 0):>6}"
        row += "  " + ", ".join(cell["binaries"])
        lines.append(row)
    lines.append("")
    lines.append(
        f"gtfobins-coverage: {matched}/{total} postures match expected ({percent:.1f}%)"
    )
    lines.append(
        f"review backlog   : {len(review)} row(s) with no conscious posture yet "
        "(excluded from coverage)"
    )
    lines.append("")

    if drift:
        lines.append("POSTURE-DRIFT (definitive postures the engine no longer honors)")
        lines.append("-" * 78)
        for r in drift:
            lines.append(
                f"{r.classification:<18} {r.binary}/{r.function_class} "
                f"expected={r.expected} live={r.action} rule={_rule(r)} "
                f"invocation={r.invocation}"
            )
    else:
        lines.append("POSTURE-DRIFT (definitive postures the engine no longer honors)")
        lines.append("-" * 78)
        lines.append("none - every definitive posture matches the live engine verdict")
    lines.append("")

    if review:
        lines.append("REVIEW (live verdicts not yet consciously accepted)")
        lines.append("-" * 78)
        for r in review:
            lines.append(
                f"REVIEW  {r.binary}/{r.function_class} live={r.action} "
                f"rule={_rule(r)} invocation={r.invocation}"
            )
    else:
        lines.append("REVIEW (live verdicts not yet consciously accepted)")
        lines.append("-" * 78)
        lines.append("none - every row carries a conscious posture")
    lines.append("")

    lines.append("Row detail (catalog order)")
    lines.append("-" * 78)
    lines.append(
        f"{'binary':<10} {'class':<12} {'expected':<17} {'live':<7} "
        f"{'rule':<32} invocation"
    )
    for r in results:
        lines.append(
            f"{r.binary:<10} {r.function_class:<12} {r.expected:<17} "
            f"{r.action:<7} {_rule(r):<32} {r.invocation}"
        )
    lines.append("")
    return "\n".join(lines)


def report_payload(report: SweepReport) -> dict[str, Any]:
    """The report as plain data (shared by --format json)."""
    results = report.results
    matched, total, percent = coverage(results)
    return {
        "catalog": report.catalog_path,
        "engine": "hermetic",
        "entries": {
            "binaries": len({r.binary for r in results}),
            "rows": len(results),
        },
        "verdicts": action_counts(results),
        "coverage": {
            "matched": matched,
            "total": total,
            "percent": percent,
            "review_rows": len(reviewed(results)),
        },
        "matrix": matrix(results),
        "rows": [
            {
                "binary": r.binary,
                "class": r.function_class,
                "invocation": r.invocation,
                "expected": r.expected,
                "action": r.action,
                "rule_id": r.rule_id,
                "classification": r.classification,
                "rationale": r.rationale,
                "note": r.note,
            }
            for r in results
        ],
        "drift": [
            {
                "classification": r.classification,
                "binary": r.binary,
                "class": r.function_class,
                "invocation": r.invocation,
                "expected": r.expected,
                "action": r.action,
                "rule_id": r.rule_id,
            }
            for r in drifted(results)
        ],
        "review": [
            {
                "binary": r.binary,
                "class": r.function_class,
                "invocation": r.invocation,
                "action": r.action,
                "rule_id": r.rule_id,
            }
            for r in reviewed(results)
        ],
    }


def render_json(report: SweepReport) -> str:
    """Byte-stable JSON rendering (sorted keys) of the same data as the text."""
    return json.dumps(report_payload(report), indent=2, sort_keys=True)


# ── CLI ────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (its epilog documents the --check rule)."""
    parser = argparse.ArgumentParser(
        description=(
            "Sweep the GTFOBins seed catalog against the live terminal-jail "
            "engine and report per-function-class verdicts, coverage, posture "
            "drift and the review backlog. Measurement only: this changes no "
            "rules."
        ),
        epilog=CHECK_RULE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG),
        help=(
            "catalog YAML to sweep (default: "
            "scripts/gtfobins-catalog-seed.yaml, resolved from the repo root)"
        ),
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help=(
            "print the report to stdout and write no files (this is already "
            "the default; accepted for CLI parity with scripts/rule-catalog.py, "
            "whose default writes docs/)"
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 on posture drift; see the exit rule below",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="report format (default: text)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sweep. Returns 0 (ok), 1 (--check drift); exits 2 on catalog error."""
    args = build_parser().parse_args(argv)
    catalog_path = Path(args.catalog)
    try:
        rows = load_catalog(catalog_path)
    except CatalogError as exc:
        print(f"gtfobins-sweep: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_CATALOG_ERROR) from exc

    report = SweepReport(catalog_path=str(catalog_path), results=sweep(rows))
    drift = drifted(report.results)

    if args.format == "json":
        sys.stdout.write(render_json(report) + "\n")
    else:
        sys.stdout.write(render_text(report) + "\n")
        if args.check:
            if drift:
                print(f"[check] FAIL - {len(drift)} posture(s) drifted")
            else:
                print("[check] OK - no posture drift")

    if args.check and drift:
        return EXIT_DRIFT
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
