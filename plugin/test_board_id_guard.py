"""Tests for scripts/board_id_guard.py (QA-TERMINAL-JAIL-6).

The canonical board .coding-hermes/board/tasks.jsonl addresses rows by line, so
a duplicated id silently redirects later updates onto the wrong row. These tests
pin the guard's contract: fail-closed validation with line diagnostics, and a
compaction that keeps the LAST raw row per id byte-for-byte.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GUARD_SCRIPT = PROJECT_ROOT / "scripts" / "board_id_guard.py"


# ── helpers ────────────────────────────────────────────────────────


def run_guard(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the board guard and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(GUARD_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(cwd or PROJECT_ROOT),
    )


def output_of(result: subprocess.CompletedProcess[str]) -> str:
    """Guard diagnostics may land on either stream."""
    return result.stdout + result.stderr


def row(**fields: object) -> bytes:
    """A board row rendered as compact JSON bytes (no newline)."""
    return json.dumps(fields).encode()


def write_board(
    tmp_path: Path, rows: list[bytes], *, trailing_newline: bool = True
) -> Path:
    """Write a board file from raw row bytes."""
    board = tmp_path / "tasks.jsonl"
    payload = b"\n".join(rows)
    if trailing_newline:
        payload += b"\n"
    board.write_bytes(payload)
    return board


def load_guard_module():
    """Import scripts/board_id_guard.py by path (it lives outside plugin/)."""
    spec = importlib.util.spec_from_file_location("board_id_guard", GUARD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclasses resolves string annotations (PEP 563)
    # through sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── validation: clean board ────────────────────────────────────────


def test_clean_unique_board_passes(tmp_path):
    """One row per id validates and exits 0."""
    board = write_board(
        tmp_path,
        [
            row(id="TJ-GAP-001", title="first", status="complete"),
            row(id="TJ-GAP-002", title="second", status="pending"),
            row(id="QA-TERMINAL-JAIL-3", title="third", status="pending"),
        ],
    )
    result = run_guard(str(board))
    assert result.returncode == 0
    assert "OK: 3 rows, 3 unique ids" in result.stdout


def test_empty_board_passes(tmp_path):
    """An empty board has no ids to collide; it is not a validation error."""
    board = tmp_path / "tasks.jsonl"
    board.write_bytes(b"")
    result = run_guard(str(board))
    assert result.returncode == 0
    assert "rows: 0" in result.stdout


def test_missing_file_is_usage_error(tmp_path):
    """A missing target is an IO error (exit 2), distinct from invalid data."""
    result = run_guard(str(tmp_path / "nope.jsonl"))
    assert result.returncode == 2
    assert "board not found" in output_of(result)


def test_default_target_is_canonical_board_path():
    """With no path argument the guard points at the canonical board."""
    module = load_guard_module()
    expected = PROJECT_ROOT / ".coding-hermes" / "board" / "tasks.jsonl"
    assert module.default_target() == expected
    assert module.DEFAULT_BOARD_RELATIVE == Path(".coding-hermes/board/tasks.jsonl")
    assert expected.is_file()


def test_default_invocation_targets_canonical_board():
    """Bare invocation validates the real board without a crash (read-only)."""
    result = run_guard()
    assert result.returncode in (0, 1)  # 0 clean, 1 currently duplicated
    assert str(PROJECT_ROOT / ".coding-hermes" / "board" / "tasks.jsonl") in (
        result.stdout
    )


# ── validation: duplicate ids ──────────────────────────────────────


def test_duplicate_ids_with_unrelated_titles_fail_with_line_numbers(tmp_path):
    """Reused ids with unrelated titles are reported with every source line."""
    board = write_board(
        tmp_path,
        [
            row(id="QA-TERMINAL-JAIL-1", title="harden pidns probe"),
            row(id="TJ-GAP-001", title="unrelated survivor"),
            row(id="QA-TERMINAL-JAIL-1", title="flaky seccomp test"),
            row(id="QA-TERMINAL-JAIL-1", title="docs drift in README"),
            row(id="TJ-GAP-002", title="another survivor"),
        ],
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    text = output_of(result)
    assert "QA-TERMINAL-JAIL-1: lines 1, 3, 4 (3 occurrences)" in text
    assert "duplicate ids (1)" in text
    assert "FAIL: 0 malformed/invalid row(s), 1 duplicate id(s)" in text


def test_duplicate_identical_title_rows_still_rejected(tmp_path):
    """An exact duplicate row is still a duplicate id, not a harmless repeat."""
    duplicated = row(id="DOC-1", title="same title", status="complete")
    board = write_board(tmp_path, [duplicated, duplicated])
    result = run_guard(str(board))
    assert result.returncode == 1
    assert "DOC-1: lines 1, 2 (2 occurrences)" in output_of(result)


def test_several_duplicate_ids_reported_sorted_by_first_line(tmp_path):
    """Every duplicated id is listed, ordered by first occurrence."""
    board = write_board(
        tmp_path,
        [
            row(id="B", title="b1"),
            row(id="A", title="a1"),
            row(id="B", title="b2"),
            row(id="A", title="a2"),
        ],
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    text = output_of(result)
    assert "B: lines 1, 3 (2 occurrences)" in text
    assert "A: lines 2, 4 (2 occurrences)" in text
    assert text.index("B: lines 1, 3") < text.index("A: lines 2, 4")


# ── validation: malformed rows and invalid ids ─────────────────────


def test_malformed_json_reports_source_line(tmp_path):
    """Broken JSON names the offending line."""
    board = write_board(
        tmp_path,
        [
            row(id="TJ-GAP-001", title="fine"),
            b'{"id": "TJ-GAP-002", "title": "truncated"',
        ],
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    assert "line 2: malformed JSON" in output_of(result)


def test_blank_line_is_malformed(tmp_path):
    """An interior blank line is a malformed row, reported by line number."""
    board = write_board(
        tmp_path,
        [row(id="TJ-GAP-001", title="a"), b"", row(id="TJ-GAP-002", title="b")],
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    assert "line 2: malformed JSON" in output_of(result)


def test_non_object_row_rejected(tmp_path):
    """A JSON array/string/number row is not a task row."""
    board = write_board(
        tmp_path, [b'["TJ-GAP-001", "array row"]', row(id="TJ-GAP-002", title="b")]
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    assert "line 1: row is not a JSON object (list)" in output_of(result)


def test_missing_id_rejected(tmp_path):
    """A row without an id field is invalid."""
    board = write_board(tmp_path, [row(title="no id here")])
    result = run_guard(str(board))
    assert result.returncode == 1
    assert "line 1: missing id" in output_of(result)


def test_non_string_id_rejected(tmp_path):
    """Numeric/boolean/null ids are invalid."""
    board = write_board(
        tmp_path,
        [
            b'{"id": 42, "title": "numeric id"}',
            b'{"id": null, "title": "null id"}',
        ],
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    text = output_of(result)
    assert "line 1: id is not a string (int)" in text
    assert "line 2: id is not a string (NoneType)" in text


def test_empty_id_rejected(tmp_path):
    """Empty (and whitespace-only) ids cannot address a row."""
    board = write_board(
        tmp_path, [b'{"id": "", "title": "empty"}', b'{"id": "  ", "title": "ws"}']
    )
    result = run_guard(str(board))
    assert result.returncode == 1
    text = output_of(result)
    assert "line 1: empty id" in text
    assert "line 2: empty id" in text


# ── compaction ─────────────────────────────────────────────────────


def test_compact_keeps_last_raw_row_exactly(tmp_path):
    """Survivors are raw bytes: escaping style, spacing and key order survive."""
    escaped = (
        b'{"id": "DUP-1", "title": "caf\\u00e9 \\ud83d\\ude80", "status": "pending"}'
    )
    raw_utf8 = (
        '{"title": "café 🚀", "id": "DUP-1", "status": "complete", "complexity": 3}'
    ).encode()
    unique = row(id="TJ-GAP-009", title="survivor", status="pending")
    board = write_board(tmp_path, [escaped, raw_utf8, unique])

    result = run_guard("--compact", str(board))
    assert result.returncode == 0
    assert board.read_bytes() == raw_utf8 + b"\n" + unique + b"\n"
    # The escaped first occurrence is gone, the raw last one is intact.
    assert b"\\u00e9" not in board.read_bytes()
    assert "café 🚀".encode() in board.read_bytes()


def test_compact_orders_survivors_by_last_occurrence(tmp_path):
    """A survivor sits where its LAST row sat, not where its first row sat."""
    first_b = row(id="B", title="b first")
    a_first = row(id="A", title="a first")
    b_last = row(id="B", title="b last")
    a_last = row(id="A", title="a last")
    board = write_board(tmp_path, [first_b, a_first, b_last, a_last])

    result = run_guard("--compact", str(board))
    assert result.returncode == 0
    # B's last occurrence is line 3, A's is line 4 -> B then A.
    assert board.read_bytes() == b_last + b"\n" + a_last + b"\n"


def test_compact_summary_and_follow_up_validation(tmp_path):
    """Explicit before/after/removed summary, then validation exits 0."""
    board = write_board(
        tmp_path,
        [
            row(id="QA-TERMINAL-JAIL-1", title="one"),
            row(id="TJ-GAP-001", title="survivor"),
            row(id="QA-TERMINAL-JAIL-1", title="two"),
            row(id="QA-TERMINAL-JAIL-2", title="three"),
            row(id="QA-TERMINAL-JAIL-2", title="four"),
            row(id="QA-TERMINAL-JAIL-2", title="five"),
        ],
    )
    result = run_guard("--compact", str(board))
    assert result.returncode == 0
    text = result.stdout
    assert f"compact: {board}" in text
    assert "before: 6 rows, 3 unique ids" in text
    assert "after:  3 rows" in text
    assert "removed: 3 row(s) across 2 reused id(s)" in text
    assert "raw rows preserved" in text

    follow_up = run_guard(str(board))
    assert follow_up.returncode == 0
    assert "OK: 3 rows, 3 unique ids" in follow_up.stdout


def test_compact_is_idempotent(tmp_path):
    """A second --compact run leaves the bytes identical and exits 0."""
    board = write_board(
        tmp_path,
        [
            row(id="DUP-1", title="a"),
            row(id="DUP-1", title="b"),
            row(id="TJ-GAP-003", title="c"),
        ],
    )
    first = run_guard("--compact", str(board))
    assert first.returncode == 0
    after_first = board.read_bytes()

    second = run_guard("--compact", str(board))
    assert second.returncode == 0
    assert board.read_bytes() == after_first
    assert "removed: 0 row(s) across 0 reused id(s)" in second.stdout
    assert "already compact" in second.stdout


def test_compact_on_clean_board_leaves_bytes_untouched(tmp_path):
    """No duplicates -> no rewrite at all (bytes and content identical)."""
    board = write_board(
        tmp_path, [row(id="TJ-GAP-001", title="a"), row(id="TJ-GAP-002", title="b")]
    )
    before = board.read_bytes()
    result = run_guard("--compact", str(board))
    assert result.returncode == 0
    assert board.read_bytes() == before
    assert "no rewrite needed" in result.stdout


def test_compact_preserves_trailing_newline(tmp_path):
    """Compaction always terminates the file with exactly one newline."""
    board = write_board(
        tmp_path, [row(id="DUP-1", title="a"), row(id="DUP-1", title="b")]
    )
    result = run_guard("--compact", str(board))
    assert result.returncode == 0
    payload = board.read_bytes()
    assert payload.endswith(b"\n")
    assert not payload.endswith(b"\n\n")
    assert payload.count(b"\n") == 1


def test_compact_refuses_malformed_without_rewriting(tmp_path):
    """A malformed row blocks the rewrite entirely; bytes are untouched."""
    board = write_board(
        tmp_path,
        [
            row(id="DUP-1", title="a"),
            b'{"id": "DUP-1", "title": "broken"',
            row(id="DUP-1", title="b"),
        ],
    )
    before = board.read_bytes()
    result = run_guard("--compact", str(board))
    assert result.returncode == 1
    assert board.read_bytes() == before
    assert "refusing to compact" in result.stdout


def test_compact_refuses_invalid_id_without_rewriting(tmp_path):
    """An invalid id (empty/non-string) also blocks the rewrite."""
    board = write_board(
        tmp_path,
        [
            row(id="DUP-1", title="a"),
            row(id="DUP-1", title="b"),
            b'{"id": "", "title": "blank id"}',
        ],
    )
    before = board.read_bytes()
    result = run_guard("--compact", str(board))
    assert result.returncode == 1
    assert board.read_bytes() == before
    assert "refusing to compact" in result.stdout
    assert "line 3: empty id" in result.stdout


def test_compact_leaves_no_temporary_files(tmp_path):
    """The atomic replace cleans up its temp file."""
    board = write_board(
        tmp_path, [row(id="DUP-1", title="a"), row(id="DUP-1", title="b")]
    )
    result = run_guard("--compact", str(board))
    assert result.returncode == 0
    leftovers = [p for p in tmp_path.iterdir() if p.name != "tasks.jsonl"]
    assert leftovers == []


def test_compact_is_a_real_reduction_on_the_duplicate_fixture(tmp_path):
    """End-to-end acceptance shape: validate fails, compact fixes, validate ok."""
    board = write_board(
        tmp_path,
        [
            row(id="QA-TERMINAL-JAIL-1", title="alpha"),
            row(id="QA-TERMINAL-JAIL-1", title="beta"),
            row(id="QA-TERMINAL-JAIL-1", title="gamma"),
        ],
    )
    assert run_guard(str(board)).returncode == 1
    assert run_guard("--compact", str(board)).returncode == 0
    assert run_guard(str(board)).returncode == 0
    assert board.read_bytes() == row(id="QA-TERMINAL-JAIL-1", title="gamma") + b"\n"
