"""Schema tests for scripts/board_id_guard.py (JSONL-NORM-002).

The board's ``priority`` field drifted between "P1"-style strings and bare
ints, and ``status`` still carried the legacy ``completed`` synonym next to
``complete`` -- so any count, sort or filter over these fields is one drifted
row away from being wrong. These tests pin the guard's schema contract:

- validate rejects a bare-int priority and any status outside
  pending/complete/blocked, naming the field, the row id, and the source
  line; null/absent priority or status is a note, not an error;
- --migrate-schema normalizes ONLY the offending lines (line-targeted,
  each line keeping its own \\u-escaping style), re-validates before the
  atomic replace, prints a before/after census, and is idempotent.

Tests never write to the real board: every case runs against a tmp_path
fixture.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GUARD_SCRIPT = PROJECT_ROOT / "scripts" / "board_id_guard.py"


# -- helpers ---------------------------------------------------------


def run_guard(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the board guard and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(GUARD_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT),
    )


def combined_output(result: subprocess.CompletedProcess[str]) -> str:
    """Guard diagnostics may land on either stream."""
    return result.stdout + result.stderr


def board_row(**fields: object) -> bytes:
    """A board row rendered as compact JSON bytes (no newline)."""
    return json.dumps(fields).encode()


def write_board_file(
    tmp_path: Path, rows: list[bytes], name: str = "tasks.jsonl"
) -> Path:
    """Write a board file from raw row bytes."""
    board = tmp_path / name
    board.write_bytes(b"\n".join(rows) + b"\n")
    return board


def load_guard_module():
    """Import scripts/board_id_guard.py by path (it lives outside tests/)."""
    spec = importlib.util.spec_from_file_location("board_id_guard", GUARD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclasses resolves string annotations (PEP 563)
    # through sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# -- validation: schema violations -----------------------------------


def test_validate_rejects_bare_int_priority_and_legacy_status(tmp_path):
    """A drifted row fails validation naming field, row id, and source line."""
    board = write_board_file(
        tmp_path,
        [
            board_row(id="TJ-NORM-001", title="fine", status="complete", priority="P1"),
            board_row(
                id="TJ-NORM-002", title="int priority", status="pending", priority=2
            ),
            board_row(id="TJ-NORM-003", title="legacy status", status="completed"),
        ],
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    text = combined_output(result)
    assert "line 2: TJ-NORM-002: priority must match P[0-5] (got bare int 2)" in text
    assert (
        "line 3: TJ-NORM-003: status legacy status 'completed' "
        "(allowed: pending, complete, blocked)" in text
    )
    assert "schema violations (2):" in text
    assert (
        "FAIL: 0 malformed/invalid row(s), 0 duplicate id(s), "
        "2 schema violation(s)" in text
    )


def test_validate_allows_canonical_vocabulary(tmp_path):
    """P0..P5 strings and pending/complete/blocked all validate cleanly."""
    pairs = [
        ("pending", "P0"),
        ("complete", "P1"),
        ("blocked", "P2"),
        ("pending", "P3"),
        ("complete", "P4"),
        ("pending", "P5"),
    ]
    rows = [
        board_row(id=f"TJ-NORM-{n:03d}", status=status, priority=priority)
        for n, (status, priority) in enumerate(pairs, start=1)
    ]
    board = write_board_file(tmp_path, rows)
    result = run_guard(str(board))
    assert result.returncode == 0
    assert "OK: 6 rows, 6 unique ids" in result.stdout


def test_validate_null_priority_and_status_are_notes_not_errors(tmp_path):
    """Null/absent priority or status is allowed and reported informationally."""
    board = write_board_file(
        tmp_path,
        [
            board_row(id="EVT-RELTOOL-001", status=None, priority=None),
            board_row(id="EVT-RELTOOL-002", status="pending"),  # absent priority
        ],
    )
    result = run_guard(str(board))
    assert result.returncode == 0
    text = combined_output(result)
    assert "schema violations" not in text
    assert "notes (3):" in text
    assert "priority is null/absent (allowed): 2 row(s):" in text
    assert "status is null/absent (allowed): 1 row(s):" in text
    assert "line 1 (EVT-RELTOOL-001)" in text


def test_validate_rejects_unmappable_and_wrongly_typed_values(tmp_path):
    """Out-of-range ints, bools, and non-string statuses are plain violations."""
    board = write_board_file(
        tmp_path,
        [
            board_row(id="TJ-NORM-007", status="pending", priority=7),
            board_row(id="TJ-NORM-008", status="pending", priority=True),
            board_row(id="TJ-NORM-009", status=3, priority="P1"),
        ],
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    text = combined_output(result)
    assert "line 1: TJ-NORM-007: priority must match P[0-5] (got bare int 7)" in text
    assert "line 2: TJ-NORM-008: priority must match P[0-5] (got bool True)" in text
    assert "line 3: TJ-NORM-009: status must be a string (got int)" in text
    # None of these may offer a migration: only 0-5 ints and 'completed' do.
    assert "migrated:" not in result.stdout


# -- migration: line-targeted rewrite ---------------------------------


def test_migrate_normalizes_only_the_offending_lines(tmp_path):
    """Untouched rows stay byte-identical; offending lines carry the fixes."""
    survivor = board_row(id="TJ-OK-001", title="fine", status="complete", priority="P1")
    int_priority = board_row(
        id="TJ-NORM-002", title="drift", status="pending", priority=2
    )
    legacy_status = board_row(id="TJ-NORM-003", title="legacy", status="completed")
    board = write_board_file(tmp_path, [survivor, int_priority, legacy_status])

    result = run_guard("--migrate-schema", str(board))
    assert result.returncode == 0
    lines = board.read_bytes().split(b"\n")
    assert lines[0] == survivor, "compliant row must stay byte-identical"
    assert b'"priority": "P2"' in lines[1]
    assert b'"status": "pending"' in lines[1]
    assert lines[2] == board_row(id="TJ-NORM-003", title="legacy", status="complete"), (
        lines[2]
    )
    text = result.stdout
    assert (
        "census before: 3 rows, 3 unique ids, 1 bare-int priority, "
        "1 legacy 'completed' status, 1 null/absent priority, "
        "2 schema violation(s)" in text
    )
    assert (
        "census after: 3 rows, 3 unique ids, 0 bare-int priority, "
        "0 legacy 'completed' status, 1 null/absent priority, "
        "0 schema violation(s)" in text
    )
    assert "migrated: 2 line(s)" in text


def test_migrate_preserves_a_lines_unicode_escape_style(tmp_path):
    """A \\u-escaped row keeps its escaping AND gets both fixes."""
    escaped = (
        b'{"id": "D-4", "title": "caf\\u00e9", "status": "completed", "priority": 3}'
    )
    board = write_board_file(tmp_path, [escaped])
    result = run_guard("--migrate-schema", str(board))
    assert result.returncode == 0
    after = board.read_bytes()
    assert b"caf\\u00e9" in after, "escaped row must stay escaped"
    value = json.loads(after.decode("utf-8"))
    assert value == {
        "id": "D-4",
        "title": "caf\u00e9",
        "status": "complete",
        "priority": "P3",
    }


def test_migrate_refuses_a_malformed_board_without_writing(tmp_path):
    """A malformed row blocks the rewrite entirely; bytes are untouched."""
    board = write_board_file(
        tmp_path,
        [
            board_row(id="TJ-NORM-001", status="pending", priority=2),
            b'{"id": "TJ-NORM-002", "title": "broken"',
        ],
    )
    before = board.read_bytes()
    result = run_guard("--migrate-schema", str(board))
    assert result.returncode == 1
    assert board.read_bytes() == before
    assert "refusing to migrate" in result.stdout


def test_migrate_is_idempotent_and_clean_boards_need_no_rewrite(tmp_path):
    """A clean board triggers no rewrite; a migrated board stabilizes."""
    clean = write_board_file(
        tmp_path,
        [
            board_row(id="TJ-NORM-001", status="pending", priority="P1"),
            board_row(id="TJ-NORM-002", status="complete", priority="P2"),
        ],
    )
    clean_run = run_guard("--migrate-schema", str(clean))
    assert clean_run.returncode == 0
    before = clean.read_bytes()
    assert "no rewrite needed: board is already schema-normalized" in clean_run.stdout
    assert clean.read_bytes() == before

    dirty = write_board_file(
        tmp_path,
        [board_row(id="TJ-NORM-003", status="completed", priority=1)],
        name="dirty.jsonl",
    )
    first = run_guard("--migrate-schema", str(dirty))
    assert first.returncode == 0
    after_first = dirty.read_bytes()
    second = run_guard("--migrate-schema", str(dirty))
    assert second.returncode == 0
    assert dirty.read_bytes() == after_first
    assert "no rewrite needed: board is already schema-normalized" in second.stdout


def test_migrated_board_revalidates_clean(tmp_path):
    """End-to-end acceptance shape: validate fails, migrate fixes, validate ok."""
    board = write_board_file(
        tmp_path,
        [
            board_row(id="TJ-NORM-001", status="pending", priority=0),
            board_row(id="TJ-NORM-002", status="completed", priority=1),
            board_row(id="TJ-NORM-003", status="blocked", priority=None),
        ],
    )
    assert run_guard(str(board)).returncode == 1
    assert run_guard("--migrate-schema", str(board)).returncode == 0
    follow_up = run_guard(str(board))
    assert follow_up.returncode == 0
    assert "OK: 3 rows, 3 unique ids" in follow_up.stdout
    assert "schema violations" not in combined_output(follow_up)


def test_compact_and_migrate_are_mutually_exclusive(tmp_path):
    """Combining both write modes is a usage error, not a silent choice."""
    board = write_board_file(tmp_path, [board_row(id="TJ-NORM-001", status="pending")])
    before = board.read_bytes()
    result = run_guard("--compact", "--migrate-schema", str(board))
    assert result.returncode == 2
    assert board.read_bytes() == before
    assert "mutually exclusive" in combined_output(result)


# -- module-level contract --------------------------------------------


def test_guard_module_exports_schema_constants():
    """The schema vocabulary is importable and pinned."""
    module = load_guard_module()
    assert module.EXIT_OK == 0
    assert module.EXIT_INVALID == 1
    assert module.EXIT_ERROR == 2
    for code in ("P0", "P1", "P2", "P3", "P4", "P5"):
        assert module.PRIORITY_PATTERN.match(code)
    assert module.PRIORITY_INT_TO_CODE == {
        0: "P0",
        1: "P1",
        2: "P2",
        3: "P3",
        4: "P4",
        5: "P5",
    }
    assert module.CANONICAL_STATUSES == ("pending", "complete", "blocked")
    assert module.LEGACY_STATUS_ALIASES == {"completed": "complete"}
