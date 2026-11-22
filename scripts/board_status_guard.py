#!/usr/bin/env python3
"""Board status-lowering guard for the canonical JSONL board (QA-TERMINAL-JAIL-26).

``.coding-hermes/board/tasks.jsonl`` rows are supposed to move forward:
pending -> blocked -> complete. A stale checkout that commits an older board
snapshot silently RE-OPENS already-closed rows (complete -> pending), which
is how this board has repeatedly lost state. This CLI is the enforcement
point: it compares every row id's status in the working-tree board against a
base ref (default ``origin/main``) and refuses to pass while any shared id's
status rank went down.

Status rank (higher = further along): complete=3, blocked=2, pending=1.

    validate (default)   exit 0 when no id present in both boards lowered
                         its status. Equal statuses, raised statuses
                         (pending->blocked, pending->complete,
                         blocked->complete), ids only in the new board (new
                         rows) and ids only in the base (deletions are not
                         this guard's business) all pass. Otherwise exit 1,
                         printing one line per violation naming the row and
                         both statuses, plus a short summary line.
    --board PATH         working-tree board to check (default:
                         <repo>/.coding-hermes/board/tasks.jsonl, repo
                         resolved via ``git rev-parse --show-toplevel``).
    --base REF           git ref holding the baseline board (default
                         origin/main), read via ``git show REF:<board
                         path>``.
    --install-hook       install a clearly marked block into the pre-commit
                         hook (located via ``git rev-parse --git-path
                         hooks/pre-commit``) that runs this guard only when
                         the staged diff touches the board file, refusing
                         the commit (non-zero) when the guard exits 1.
                         Placement rules, so the block actually runs:
                         (a) in a boardctl-chained hook -- an epilogue
                         marked ``# board-lint epilogue (managed by
                         boardctl install)`` or a
                         ``boardctl_lint_existing_status=$?`` capture
                         line preceded by a lone ``)`` -- the block is
                         inserted INSIDE the wrapped-body subshell,
                         before the body's terminating ``exit`` when it
                         ends with one (otherwise that exit would strand
                         the block, unreachable), or immediately before
                         the closing ``)`` when the body falls off its
                         end; a bare ``exit 1`` there only leaves the
                         subshell and its status propagates into the
                         capture line, so the epilogue's final ``exit``
                         refuses the commit.
                         (b) otherwise, when the hook's last non-blank
                         line is a terminating ``exit``, the block goes
                         immediately before that line. (c) any other
                         hook gets the block appended at the end.
                         Idempotent: a re-run detects its marker and makes
                         no change. Never run this in a linked worktree
                         whose hooks live in a shared common git dir; the
                         tests exercise it only inside throwaway tmp repos.

Fail-open policy: infrastructure problems -- missing base ref, unreadable
base board, malformed JSONL line, unknown status string -- produce a warning
on stderr and exit 0. The guard must never wedge a commit; it only refuses
the one defect it exists to catch (a lowered status). Unknown status strings
are never guessed into the rank table.

Run from anywhere inside the checkout:

    .venv/bin/python scripts/board_status_guard.py
    .venv/bin/python scripts/board_status_guard.py --base HEAD~1
    .venv/bin/python scripts/board_status_guard.py --install-hook
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BOARD_RELATIVE = Path(".coding-hermes") / "board" / "tasks.jsonl"

EXIT_OK = 0
EXIT_LOWERED = 1
EXIT_ERROR = 2

# Forward-only status ladder over this board's closed vocabulary. The board
# validation CI rejects every other value (e.g. 'in_progress'/'done'), so
# anything outside the table is skipped with a note, never guessed.
STATUS_RANK = {"complete": 3, "blocked": 2, "pending": 1}

HOOK_MARKER = "# >>> board status-lowering guard (QA-TERMINAL-JAIL-26) >>>"
HOOK_MARKER_END = "# <<< board status-lowering guard (QA-TERMINAL-JAIL-26) <<<"

# POSIX sh; safe anywhere inside an existing hook body -- install_hook picks
# the placement (see hook_insert_line_index): before a terminating exit or,
# in a boardctl-chained hook, as the last live statement inside the
# wrapped-body subshell (its bare `exit 1` only leaves the subshell, and the
# status propagates into boardctl_lint_existing_status). The block runs the
# guard only when the staged diff touches the board file and turns a guard
# exit 1 into a refused commit. A missing guard script is skipped (fail-open)
# so the block can never wedge commits it cannot evaluate. The marker lines
# are the idempotency contract: a re-run of --install-hook detects them and
# makes no change.
HOOK_BLOCK = (
    HOOK_MARKER
    + "\n"
    + r"""# Refuses commits that lower a board row status relative to origin/main
# (QA-TERMINAL-JAIL-26). Installed by:
#   .venv/bin/python scripts/board_status_guard.py --install-hook
# Re-running that command detects the marker above and makes no change.
# Runs ONLY when the staged diff touches the board file; the guard itself
# is fail-open on infrastructure problems (warning + exit 0), so a missing
# ref or an unreadable board never wedges a commit.
# Status-transparent on the pass path: the first line captures whatever the
# surrounding hook last ran (e.g. the boardctl-wrapped body's own guard),
# and the last line re-emits it (nonzero stays nonzero) so a trailing
# `exit $?` still reports the body's own result instead of this block's.
_board_status_guard_prev_status=$?
_board_status_guard_reject=0
if [ -n "$(git diff --cached --name-only -- .coding-hermes/board/tasks.jsonl)" ]; then
    _board_status_guard_root="$(git rev-parse --show-toplevel 2>/dev/null)"
    _board_status_guard_script="$_board_status_guard_root/scripts/board_status_guard.py"
    if [ -n "$_board_status_guard_root" ] && [ -f "$_board_status_guard_script" ]; then
        if [ -x "$_board_status_guard_root/.venv/bin/python" ]; then
            _board_status_guard_py="$_board_status_guard_root/.venv/bin/python"
        else
            _board_status_guard_py="python3"
        fi
        "$_board_status_guard_py" "$_board_status_guard_script" \
            || _board_status_guard_reject=1
    else
        echo "board-status-guard: skipped (guard script not found)" >&2
    fi
fi
if [ "$_board_status_guard_reject" -ne 0 ]; then
    echo "board-status-guard: commit rejected (a board row status was lowered)" >&2
    exit 1
fi
[ "$_board_status_guard_prev_status" -eq 0 ]
"""
    + HOOK_MARKER_END
    + "\n"
)


def warn(message: str) -> None:
    """Warnings go to stderr; the guard stays fail-open on every one."""
    print(f"board-status-guard: WARNING {message}", file=sys.stderr)


def run_git(args: list[str], cwd: Path | None) -> subprocess.CompletedProcess[bytes]:
    """Run git and return the raw CompletedProcess (never raises)."""
    return subprocess.run(
        ["git", *args],
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        check=False,
    )


def repo_root() -> Path | None:
    """Top of the current checkout (None outside a repo / on failure)."""
    proc = run_git(["rev-parse", "--show-toplevel"], cwd=None)
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.decode("utf-8", "replace").strip())


def load_statuses(text: str, source: str) -> dict[str, str]:
    """id -> status for every well-formed row.

    Malformed lines, non-object rows, missing ids and status strings outside
    the rank table are skipped with a note on stderr -- never guessed.
    """
    statuses: dict[str, str] = {}
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            warn(f"{source}: line {line_no}: malformed JSON ({exc.msg}); row skipped")
            continue
        if not isinstance(row, dict):
            warn(f"{source}: line {line_no}: row is not a JSON object; row skipped")
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id.strip():
            warn(f"{source}: line {line_no}: missing/blank id; row skipped")
            continue
        status = row.get("status")
        if not isinstance(status, str) or status not in STATUS_RANK:
            warn(
                f"{source}: row {row_id}: status {status!r} not in the rank "
                f"table {sorted(STATUS_RANK)}; row skipped"
            )
            continue
        statuses[row_id] = status
    return statuses


def load_base_statuses(
    base: str, board_rel: str, cwd: Path | None
) -> dict[str, str] | None:
    """Baseline id -> status from ``git show base:board_rel``.

    Returns None (after a warning) on any infrastructure problem -- the
    caller fail-opens instead of wedging the commit.
    """
    proc = run_git(["show", f"{base}:{board_rel}"], cwd=cwd)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        reason = detail[-1] if detail else f"exit code {proc.returncode}"
        warn(
            f"cannot read base board from {base}:{board_rel} ({reason}); "
            "check skipped (fail-open)"
        )
        return None
    try:
        text = proc.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        warn(
            f"base board from {base}:{board_rel} is not valid UTF-8 ({exc}); "
            "check skipped (fail-open)"
        )
        return None
    return load_statuses(text, f"base {base}:{board_rel}")


def find_lowerings(
    new: dict[str, str], base: dict[str, str]
) -> list[tuple[str, str, str]]:
    """(id, base status, new status) for every shared id whose rank dropped."""
    lowerings: list[tuple[str, str, str]] = []
    for row_id in sorted(set(new) & set(base)):
        old = base[row_id]
        if STATUS_RANK[new[row_id]] < STATUS_RANK[old]:
            lowerings.append((row_id, old, new[row_id]))
    return lowerings


def run_guard(args: argparse.Namespace) -> int:
    """Compare the working-tree board against the base ref's board."""
    root = repo_root()
    board = (
        Path(args.board)
        if args.board is not None
        else (root or REPO_ROOT) / DEFAULT_BOARD_RELATIVE
    )
    try:
        board_text = board.read_text(encoding="utf-8")
    except OSError as exc:
        warn(
            f"cannot read working-tree board {board} ({exc}); check skipped (fail-open)"
        )
        return EXIT_OK
    except UnicodeDecodeError as exc:
        warn(
            f"working-tree board {board} is not valid UTF-8 ({exc}); "
            "check skipped (fail-open)"
        )
        return EXIT_OK

    new_statuses = load_statuses(board_text, f"board {board}")

    if root is not None:
        board_rel = os.path.relpath(board.resolve(), root.resolve())
        if board_rel.startswith(os.pardir):
            warn(
                f"board {board} lives outside the repo; base comparison "
                "skipped (fail-open)"
            )
            return EXIT_OK
    else:
        board_rel = str(DEFAULT_BOARD_RELATIVE)
    base_statuses = load_base_statuses(args.base, board_rel.replace(os.sep, "/"), root)
    if base_statuses is None:
        return EXIT_OK  # warning already printed by the loader

    shared = set(new_statuses) & set(base_statuses)
    new_only = len(set(new_statuses) - set(base_statuses))
    base_only = len(set(base_statuses) - set(new_statuses))
    lowerings = find_lowerings(new_statuses, base_statuses)

    for row_id, old, new_status in lowerings:
        print(f"{row_id}: status lowered {old} -> {new_status} (base {args.base})")
    if lowerings:
        print(
            f"board-status-guard: {len(lowerings)} lowering violation(s) over "
            f"{len(shared)} shared id(s) vs base {args.base}"
        )
        return EXIT_LOWERED
    print(
        f"board-status-guard: ok — {len(shared)} shared id(s), {new_only} new "
        f"row(s), {base_only} row(s) gone from the new board; 0 lowering "
        f"violation(s) vs base {args.base}"
    )
    return EXIT_OK


# boardctl chain markers (BT-054-R): the wrapped original body ends at a
# lone ")" whose next line captures its status, followed by a marked
# epilogue and a final exit.
BOARDCTL_EPILOGUE_MARKER = "# board-lint epilogue (managed by boardctl install)"
BOARDCTL_STATUS_CAPTURE = "boardctl_lint_existing_status=$?"
# A hook line that terminates execution: `exit`, `exit 0`, `exit "$var"`.
TERMINATING_EXIT = re.compile(r"^exit(\b|$)")


def hook_insert_line_index(lines: list[str]) -> int | None:
    """Line index (0-based) before which the guard block must be inserted.

    First match wins; None means "no structured placement -- append at the
    end". Rules (module docstring, --install-hook): inside a boardctl chain
    the block goes before the wrapped body's terminating exit (or immediately
    before the closing ")" when the body ends without one); otherwise it goes
    before a plain hook's terminating final exit; else append.
    """
    # (a) boardctl chain: a signal line directly preceded by a lone ")".
    for i, line in enumerate(lines):
        stripped = line.strip()
        chained = stripped.startswith(BOARDCTL_EPILOGUE_MARKER) or (
            stripped == BOARDCTL_STATUS_CAPTURE
        )
        if not (chained and i > 0 and lines[i - 1].strip() == ")"):
            continue
        close_idx = i - 1
        # Last non-blank statement of the wrapped body: when it is an exit,
        # the block must go BEFORE it or that exit strands the block.
        for j in range(close_idx - 1, -1, -1):
            if lines[j].strip():
                if TERMINATING_EXIT.match(lines[j].strip()):
                    return j
                break
        return close_idx
    # (b) plain hook whose last non-blank line is a terminating exit.
    for j in range(len(lines) - 1, -1, -1):
        if lines[j].strip():
            if TERMINATING_EXIT.match(lines[j].strip()):
                return j
            break
    # (c) append at the end.
    return None


def insert_guard_block(existing: str) -> str:
    """Return ``existing`` with HOOK_BLOCK placed per hook_insert_line_index."""
    lines = existing.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    idx = hook_insert_line_index([line.rstrip("\r\n") for line in lines])
    if idx is None:
        # (c) append at the end, exactly as before the placement rules.
        return "".join(lines) + "\n" + HOOK_BLOCK.lstrip("\n")
    lines[idx:idx] = HOOK_BLOCK.lstrip("\n").splitlines(keepends=True)
    return "".join(lines)


def install_hook() -> int:
    """Install the marked guard block into the pre-commit hook (idempotent).

    The block is placed where it actually runs -- inside a boardctl chain's
    wrapped-body subshell (before the body's terminating exit, else before
    the closing ")"), before a plain hook's terminating final exit, or
    appended at the end otherwise (hook_insert_line_index).
    """
    proc = run_git(["rev-parse", "--git-path", "hooks/pre-commit"], cwd=None)
    if proc.returncode != 0:
        print(
            "board-status-guard: not inside a git repository; cannot locate "
            "the pre-commit hook",
            file=sys.stderr,
        )
        return EXIT_ERROR
    hook = Path(proc.stdout.decode("utf-8", "replace").strip())
    if not hook.is_absolute():
        hook = Path.cwd() / hook

    existing = ""
    if hook.exists():
        existing = hook.read_text(encoding="utf-8", errors="replace")
    if HOOK_MARKER in existing:
        print(f"board-status-guard: block already installed in {hook}; no change")
        return EXIT_OK

    if existing:
        content = insert_guard_block(existing)
    else:
        content = "#!/bin/sh\n\n" + HOOK_BLOCK.lstrip("\n")
    hook.parent.mkdir(parents=True, exist_ok=True)
    try:
        hook.write_text(content, encoding="utf-8")
        hook.chmod(0o755)
    except OSError as exc:
        print(f"board-status-guard: cannot write {hook} ({exc})", file=sys.stderr)
        return EXIT_ERROR
    print(f"board-status-guard: installed pre-commit block in {hook}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Refuse commits that lower a .coding-hermes board row status "
            "relative to a base ref."
        )
    )
    parser.add_argument(
        "--board",
        default=None,
        help="working-tree board path (default: <repo>/"
        + str(DEFAULT_BOARD_RELATIVE)
        + ")",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="git ref holding the baseline board (default: origin/main)",
    )
    parser.add_argument(
        "--install-hook",
        action="store_true",
        help=(
            "append the guard block to the pre-commit hook (idempotent); "
            "ignores --board/--base"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.install_hook:
        return install_hook()
    return run_guard(args)


if __name__ == "__main__":
    sys.exit(main())
