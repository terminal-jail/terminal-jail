#!/usr/bin/env python3
"""Board-ID guard for the canonical JSONL task board (QA-TERMINAL-JAIL-6).

``.coding-hermes/board/tasks.jsonl`` is a line-oriented snapshot: the normal
update path rewrites the *already present* row for a task id in place.
``events.jsonl`` is the append-only event log, so ``tasks.jsonl`` is expected to
hold exactly ONE row per id. Crash-recovery residue and historical corruption
leave several rows carrying the same id, and a duplicated id makes every later
line-addressed update ambiguous -- a task can be completed, or a QA finding
resolved, by writing to a row that is not the live one (QA-TERMINAL-JAIL-1 has
been observed on eight lines with unrelated titles).

This CLI is the enforcement point:

    validate (default)   exit 0 when every row parses, every id is a non-empty
                         string, no id occurs more than once, and the schema
                         holds: priority (when present) is a "P0".."P5"
                         string, status (when present) is one of
                         pending/complete/blocked. Otherwise exit 1 with
                         per-row line diagnostics naming the field, the row
                         id, and the source line. Null/absent priority or
                         status is allowed and reported as a note, not an
                         error. Exit 2 is reserved for usage/IO errors.
    --compact            fail closed -- nothing is written unless the board
                         validates. Then atomically rewrite the file keeping
                         the LAST raw row for each id, ordered by the source
                         position of that last occurrence. Retained rows are
                         copied byte-for-byte (never re-serialised) so escaping
                         and spacing style survive untouched.
    --migrate-schema     one-shot normalization (JSONL-NORM-002): rewrite bare
                         int priorities 0-5 as "P0".."P5" and the legacy
                         "completed" status as "complete". Only offending
                         lines are re-serialised (each line keeps its own
                         escaping style); every other row stays byte-identical.
                         Refuses to write unless every row parses and ids are
                         unique, re-validates the rewritten board before the
                         atomic replace, and prints a before/after census.

Run from anywhere; the default target is
``<repo>/.coding-hermes/board/tasks.jsonl``:

    .venv/bin/python scripts/board_id_guard.py
    .venv/bin/python scripts/board_id_guard.py --compact
    .venv/bin/python scripts/board_id_guard.py --migrate-schema
    .venv/bin/python scripts/board_id_guard.py path/to/tasks.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BOARD_RELATIVE = Path(".coding-hermes") / "board" / "tasks.jsonl"

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_ERROR = 2

# Board schema (JSONL-NORM-002): stable priority vocabulary and status set.
PRIORITY_PATTERN = re.compile(r"^P[0-5]$")
CANONICAL_STATUSES = ("pending", "complete", "blocked")
PRIORITY_INT_TO_CODE = {0: "P0", 1: "P1", 2: "P2", 3: "P3", 4: "P4", 5: "P5"}
LEGACY_STATUS_ALIASES = {"completed": "complete"}


def default_target() -> Path:
    """Canonical board path for the repo this script ships in."""
    return REPO_ROOT / DEFAULT_BOARD_RELATIVE


@dataclass(frozen=True)
class Row:
    """A valid board row: its 1-based source line, exact bytes, and id."""

    line_no: int
    raw: bytes
    id: str


@dataclass(frozen=True)
class SchemaViolation:
    """A schema defect; diagnostics must name the field, row id, and line."""

    line_no: int
    row_id: str
    field: str
    detail: str


@dataclass
class BoardReport:
    """Result of scanning a board file: usable rows plus every defect."""

    path: Path
    total_lines: int = 0
    rows: list[Row] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    duplicates: dict[str, list[int]] = field(default_factory=dict)
    schema_violations: list[SchemaViolation] = field(default_factory=list)
    # line_no -> [(field, old value, new value), ...] the migration may fix.
    schema_migrations: dict[int, list[tuple[str, object, object]]] = field(
        default_factory=dict
    )
    # (field, line_no, row_id) informational null/absent notes.
    schema_notes: list[tuple[str, int, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and not self.duplicates and not self.schema_violations


def split_lines(data: bytes) -> list[bytes]:
    """Split board bytes into rows, dropping only the final newline artefact."""
    if not data:
        return []
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    return lines


def scan_board(path: Path) -> BoardReport:
    """Read ``path`` and classify every row. Never writes."""
    return scan_bytes(path.read_bytes(), path)


def scan_bytes(data: bytes, path: Path) -> BoardReport:
    """Classify every row of already-read board ``data``. Never writes."""
    report = BoardReport(path=path)
    lines = split_lines(data)
    report.total_lines = len(lines)
    seen: dict[str, list[int]] = {}

    for line_no, raw in enumerate(lines, start=1):
        try:
            value = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            report.problems.append(f"line {line_no}: not valid UTF-8 ({exc.reason})")
            continue
        except json.JSONDecodeError as exc:
            report.problems.append(f"line {line_no}: malformed JSON ({exc.msg})")
            continue
        if not isinstance(value, dict):
            report.problems.append(
                f"line {line_no}: row is not a JSON object ({type(value).__name__})"
            )
            continue
        if "id" not in value:
            report.problems.append(f"line {line_no}: missing id")
            continue
        task_id = value["id"]
        if not isinstance(task_id, str):
            report.problems.append(
                f"line {line_no}: id is not a string ({type(task_id).__name__})"
            )
            continue
        if not task_id.strip():
            report.problems.append(f"line {line_no}: empty id")
            continue

        _scan_row_schema(report, line_no, task_id, value)

        report.rows.append(Row(line_no=line_no, raw=raw, id=task_id))
        seen.setdefault(task_id, []).append(line_no)

    report.duplicates = {
        task_id: line_nos for task_id, line_nos in seen.items() if len(line_nos) > 1
    }
    return report


def _scan_row_schema(
    report: BoardReport, line_no: int, row_id: str, value: dict
) -> None:
    """Collect priority/status violations, migrations, and informational notes.

    Violations make ``validate`` exit 1. Migrations record what the
    ``--migrate-schema`` pass may rewrite (a strict subset: bare int
    priorities 0-5 and the legacy "completed" status). Null/absent priority
    or status is allowed and only noted.
    """
    priority = value.get("priority")
    if priority is None:
        report.schema_notes.append(("priority", line_no, row_id))
    elif isinstance(priority, str):
        if not PRIORITY_PATTERN.match(priority):
            report.schema_violations.append(
                SchemaViolation(
                    line_no=line_no,
                    row_id=row_id,
                    field="priority",
                    detail=f"must match P[0-5] (got {priority!r})",
                )
            )
    elif isinstance(priority, bool):
        report.schema_violations.append(
            SchemaViolation(
                line_no=line_no,
                row_id=row_id,
                field="priority",
                detail=f"must match P[0-5] (got bool {priority!r})",
            )
        )
    elif isinstance(priority, int):
        code = PRIORITY_INT_TO_CODE.get(priority)
        report.schema_violations.append(
            SchemaViolation(
                line_no=line_no,
                row_id=row_id,
                field="priority",
                detail=f"must match P[0-5] (got bare int {priority})",
            )
        )
        if code is not None:
            report.schema_migrations.setdefault(line_no, []).append(
                ("priority", priority, code)
            )
    else:
        report.schema_violations.append(
            SchemaViolation(
                line_no=line_no,
                row_id=row_id,
                field="priority",
                detail=f"must match P[0-5] (got {type(priority).__name__})",
            )
        )

    status = value.get("status")
    if status is None:
        report.schema_notes.append(("status", line_no, row_id))
    elif not isinstance(status, str):
        report.schema_violations.append(
            SchemaViolation(
                line_no=line_no,
                row_id=row_id,
                field="status",
                detail=f"must be a string (got {type(status).__name__})",
            )
        )
    elif status in LEGACY_STATUS_ALIASES or status not in CANONICAL_STATUSES:
        allowed = ", ".join(CANONICAL_STATUSES)
        if status in LEGACY_STATUS_ALIASES:
            kind = "legacy status"
        else:
            kind = "unknown status"
        report.schema_violations.append(
            SchemaViolation(
                line_no=line_no,
                row_id=row_id,
                field="status",
                detail=f"{kind} {status!r} (allowed: {allowed})",
            )
        )
        if status in LEGACY_STATUS_ALIASES:
            report.schema_migrations.setdefault(line_no, []).append(
                ("status", status, LEGACY_STATUS_ALIASES[status])
            )


def format_diagnostics(report: BoardReport) -> list[str]:
    """Human-readable validation report (path, defects, verdict)."""
    out = [f"board: {report.path}", f"rows: {report.total_lines}"]

    if report.problems:
        out.append(f"malformed or invalid rows ({len(report.problems)}):")
        out.extend(f"  {problem}" for problem in report.problems)

    if report.duplicates:
        out.append(f"duplicate ids ({len(report.duplicates)}):")
        ordered = sorted(report.duplicates, key=lambda i: report.duplicates[i][0])
        for task_id in ordered:
            line_nos = report.duplicates[task_id]
            rendered = ", ".join(str(n) for n in line_nos)
            out.append(f"  {task_id}: lines {rendered} ({len(line_nos)} occurrences)")

    if report.schema_violations:
        out.append(f"schema violations ({len(report.schema_violations)}):")
        for violation in report.schema_violations:
            out.append(
                f"  line {violation.line_no}: {violation.row_id}: "
                f"{violation.field} {violation.detail}"
            )

    if report.schema_notes:
        by_field: dict[str, list[str]] = {}
        for note_field, line_no, row_id in report.schema_notes:
            by_field.setdefault(note_field, []).append(f"line {line_no} ({row_id})")
        out.append(f"notes ({len(report.schema_notes)}):")
        for note_field, locations in by_field.items():
            shown = ", ".join(locations[:10])
            if len(locations) > 10:
                shown += ", ..."
            out.append(
                f"  {note_field} is null/absent (allowed): "
                f"{len(locations)} row(s): {shown}"
            )

    if report.ok:
        out.append(f"OK: {len(report.rows)} rows, {len(report.rows)} unique ids")
    else:
        fail = (
            f"FAIL: {len(report.problems)} malformed/invalid row(s), "
            f"{len(report.duplicates)} duplicate id(s)"
        )
        if report.schema_violations:
            fail += f", {len(report.schema_violations)} schema violation(s)"
        out.append(fail)
    return out


def compacted_payload(report: BoardReport) -> bytes:
    """Last raw row per id, ordered by its last occurrence, final newline kept."""
    survivors: dict[str, Row] = {}
    for row in report.rows:
        survivors[row.id] = row  # later row for an id wins
    ordered = sorted(survivors.values(), key=lambda row: row.line_no)
    return b"".join(row.raw + b"\n" for row in ordered)


def atomic_write(path: Path, payload: bytes) -> None:
    """Replace ``path`` in one step; the target is never left half-written."""
    directory = path.parent
    mode = path.stat().st_mode & 0o7777
    fd, tmp_name = tempfile.mkstemp(
        dir=str(directory), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    try:  # durability of the rename itself; not fatal if unsupported
        dir_fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def run_compact(report: BoardReport) -> int:
    """Print diagnostics + before/after/removed summary; rewrite only if sane.

    Duplicate ids are the normal input here -- they are what compaction fixes.
    The refusal case is malformed rows or invalid ids, where "the last row for
    an id" cannot be identified safely.
    """
    for line in format_diagnostics(report):
        print(line)

    if report.problems:
        print(
            "refusing to compact: fix the malformed/invalid rows above first "
            "(file untouched)"
        )
        return EXIT_INVALID

    before = report.total_lines
    survivors = compacted_payload(report)
    extra_copies = sum(len(n) - 1 for n in report.duplicates.values())
    unique = len(report.rows) - extra_copies
    removed = before - unique
    reused = len(report.duplicates)

    if survivors == report.path.read_bytes():
        print(f"compact: {report.path}")
        print(f"before: {before} rows, {unique} unique ids")
        print(f"after:  {unique} rows")
        print(f"removed: {removed} row(s) across {reused} reused id(s)")
        print("no rewrite needed: board is already compact")
        return EXIT_OK

    atomic_write(report.path, survivors)
    print(f"compact: {report.path}")
    print(f"before: {before} rows, {unique} unique ids")
    print(f"after:  {unique} rows")
    print(f"removed: {removed} row(s) across {reused} reused id(s)")
    print(f"rewrote: {report.path} (atomic replace, raw rows preserved)")
    return EXIT_OK


def schema_shape_counts(report: BoardReport) -> dict[str, int]:
    """Census of schema-relevant shapes across the parsed rows."""
    bare_int_priority = 0
    legacy_completed = 0
    null_priority = 0
    for row in report.rows:
        value = json.loads(row.raw.decode("utf-8"))
        priority = value.get("priority")
        status = value.get("status")
        if isinstance(priority, int) and not isinstance(priority, bool):
            bare_int_priority += 1
        if priority is None:
            null_priority += 1
        if status == "completed":
            legacy_completed += 1
    return {
        "bare_int_priority": bare_int_priority,
        "legacy_completed": legacy_completed,
        "null_priority": null_priority,
    }


def _census_line(label: str, report: BoardReport) -> str:
    """One-line census: rows, unique ids, offending counts, violations."""
    counts = schema_shape_counts(report)
    unique = len({row.id for row in report.rows})
    return (
        f"census {label}: {report.total_lines} rows, {unique} unique ids, "
        f"{counts['bare_int_priority']} bare-int priority, "
        f"{counts['legacy_completed']} legacy 'completed' status, "
        f"{counts['null_priority']} null/absent priority, "
        f"{len(report.schema_violations)} schema violation(s)"
    )


def run_migrate(report: BoardReport) -> int:
    """One-shot schema normalization (JSONL-NORM-002): line-targeted rewrite.

    Fail-closed: nothing is written unless every row parses, ids are unique,
    the untouched lines stay byte-identical, and the rewritten board
    re-validates with zero schema violations and a stable row/id census.
    """
    for line in format_diagnostics(report):
        print(line)

    if report.problems or report.duplicates:
        print(
            "refusing to migrate: fix the malformed/invalid rows above first "
            "(file untouched)"
        )
        return EXIT_INVALID

    data = report.path.read_bytes()
    lines = split_lines(data)
    new_lines = list(lines)
    migrated = 0
    for row in report.rows:
        changes = report.schema_migrations.get(row.line_no)
        if not changes:
            continue
        value = json.loads(row.raw.decode("utf-8"))
        # Mirror the line's own escaping style: a "\u"-escaped row was
        # committed escaped, so keep ensure_ascii=True for its re-dump.
        ensure_ascii = b"\\u" in row.raw
        for field_name, _old, new_value in changes:
            value[field_name] = new_value
        new_raw = json.dumps(value, ensure_ascii=ensure_ascii).encode("utf-8")
        if new_raw != row.raw:
            new_lines[row.line_no - 1] = new_raw
            migrated += 1

    rebuild = b"\n".join(new_lines)
    if data.endswith(b"\n"):
        rebuild += b"\n"

    print(_census_line("before", report))

    if rebuild == data:
        print("no rewrite needed: board is already schema-normalized")
        return EXIT_OK

    # Post-conditions, checked before anything is written.
    for line_no, (old, new) in enumerate(zip(lines, new_lines), start=1):
        if line_no not in report.schema_migrations and old != new:
            print(
                f"error: untouched line {line_no} would change; aborting",
                file=sys.stderr,
            )
            return EXIT_ERROR
    new_report = scan_bytes(rebuild, report.path)
    before_unique = len({row.id for row in report.rows})
    after_unique = len({row.id for row in new_report.rows})
    if (
        new_report.problems
        or new_report.duplicates
        or new_report.schema_violations
        or new_report.schema_migrations
        or new_report.total_lines != report.total_lines
        or len(new_report.rows) != len(report.rows)
        or after_unique != before_unique
    ):
        print(
            "refusing to migrate: rewritten board failed re-validation "
            "(file untouched)",
            file=sys.stderr,
        )
        return EXIT_INVALID

    atomic_write(report.path, rebuild)
    print(_census_line("after", new_report))
    print(f"migrated: {migrated} line(s)")
    print(f"rewrote: {report.path} (atomic replace, untouched rows byte-identical)")
    return EXIT_OK


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="board_id_guard.py",
        description=(
            "Validate (and optionally compact/normalize) the canonical JSONL "
            "task board: exactly one row per task id, P-code priorities, "
            "canonical statuses."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help=f"board file to check (default: {DEFAULT_BOARD_RELATIVE})",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help=(
            "keep only the last raw row for each id (refuses to write unless "
            "the board validates; atomic replace)"
        ),
    )
    parser.add_argument(
        "--migrate-schema",
        action="store_true",
        help=(
            "one-shot JSONL-NORM-002 normalization: bare int priorities -> "
            '"P0".."P5", legacy "completed" -> "complete" (line-targeted, '
            "atomic; refuses unless the board parses and re-validates)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = Path(args.path) if args.path else default_target()

    if not target.exists():
        print(f"error: board not found: {target}", file=sys.stderr)
        return EXIT_ERROR
    if not target.is_file():
        print(f"error: not a file: {target}", file=sys.stderr)
        return EXIT_ERROR

    try:
        report = scan_board(target)
    except OSError as exc:
        print(f"error: cannot read {target}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.compact and args.migrate_schema:
        print(
            "error: --compact and --migrate-schema are mutually exclusive",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if args.compact:
        try:
            return run_compact(report)
        except OSError as exc:
            print(f"error: compact failed, file untouched: {exc}", file=sys.stderr)
            return EXIT_ERROR

    if args.migrate_schema:
        try:
            return run_migrate(report)
        except OSError as exc:
            print(f"error: migrate failed, file untouched: {exc}", file=sys.stderr)
            return EXIT_ERROR

    for line in format_diagnostics(report):
        print(line)
    return EXIT_OK if report.ok else EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())
