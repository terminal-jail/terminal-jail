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
                         string, and no id occurs more than once. Otherwise
                         exit 1 with per-row line diagnostics (source line for
                         malformed rows, every source line for duplicates).
                         Exit 2 is reserved for usage/IO errors.
    --compact            fail closed -- nothing is written unless the board
                         validates. Then atomically rewrite the file keeping
                         the LAST raw row for each id, ordered by the source
                         position of that last occurrence. Retained rows are
                         copied byte-for-byte (never re-serialised) so escaping
                         and spacing style survive untouched.

Run from anywhere; the default target is
``<repo>/.coding-hermes/board/tasks.jsonl``:

    .venv/bin/python scripts/board_id_guard.py
    .venv/bin/python scripts/board_id_guard.py --compact
    .venv/bin/python scripts/board_id_guard.py path/to/tasks.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BOARD_RELATIVE = Path(".coding-hermes") / "board" / "tasks.jsonl"

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_ERROR = 2


def default_target() -> Path:
    """Canonical board path for the repo this script ships in."""
    return REPO_ROOT / DEFAULT_BOARD_RELATIVE


@dataclass(frozen=True)
class Row:
    """A valid board row: its 1-based source line, exact bytes, and id."""

    line_no: int
    raw: bytes
    id: str


@dataclass
class BoardReport:
    """Result of scanning a board file: usable rows plus every defect."""

    path: Path
    total_lines: int = 0
    rows: list[Row] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    duplicates: dict[str, list[int]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems and not self.duplicates


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
    report = BoardReport(path=path)
    lines = split_lines(path.read_bytes())
    report.total_lines = len(lines)
    seen: dict[str, list[int]] = {}

    for line_no, raw in enumerate(lines, start=1):
        try:
            value = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            report.problems.append(
                f"line {line_no}: not valid UTF-8 ({exc.reason})"
            )
            continue
        except json.JSONDecodeError as exc:
            report.problems.append(
                f"line {line_no}: malformed JSON ({exc.msg})"
            )
            continue
        if not isinstance(value, dict):
            report.problems.append(
                f"line {line_no}: row is not a JSON object "
                f"({type(value).__name__})"
            )
            continue
        if "id" not in value:
            report.problems.append(f"line {line_no}: missing id")
            continue
        task_id = value["id"]
        if not isinstance(task_id, str):
            report.problems.append(
                f"line {line_no}: id is not a string "
                f"({type(task_id).__name__})"
            )
            continue
        if not task_id.strip():
            report.problems.append(f"line {line_no}: empty id")
            continue

        report.rows.append(Row(line_no=line_no, raw=raw, id=task_id))
        seen.setdefault(task_id, []).append(line_no)

    report.duplicates = {
        task_id: line_nos
        for task_id, line_nos in seen.items()
        if len(line_nos) > 1
    }
    return report


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
            out.append(
                f"  {task_id}: lines {rendered} "
                f"({len(line_nos)} occurrences)"
            )

    if report.ok:
        out.append(f"OK: {len(report.rows)} rows, {len(report.rows)} unique ids")
    else:
        out.append(
            f"FAIL: {len(report.problems)} malformed/invalid row(s), "
            f"{len(report.duplicates)} duplicate id(s)"
        )
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


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="board_id_guard.py",
        description=(
            "Validate (and optionally compact) the canonical JSONL task board: "
            "exactly one row per task id."
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

    if args.compact:
        try:
            return run_compact(report)
        except OSError as exc:
            print(f"error: compact failed, file untouched: {exc}", file=sys.stderr)
            return EXIT_ERROR

    for line in format_diagnostics(report):
        print(line)
    return EXIT_OK if report.ok else EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())
