"""Tests for scripts/board_status_guard.py (QA-TERMINAL-JAIL-26).

This board has repeatedly lost state when a stale checkout committed a board
snapshot that RE-OPENED already-closed rows (complete -> pending). These
tests pin the status-lowering guard's contract against throwaway git repos
built in tmp_path:

- a lowered status (complete -> pending) is REFUSED (exit 1), naming the
  row id and both statuses; raised statuses (pending->blocked,
  pending->complete), equal statuses, brand-new ids and unknown status
  strings all PASS (exit 0, unknown statuses skipped with a stderr note);
- infrastructure problems fail OPEN with a warning on stderr (missing base
  ref, malformed JSONL line on either side) -- the guard must never wedge
  a commit;
- --install-hook is idempotent (two runs leave exactly one guard block,
  the hook stays executable) and the installed hook refuses a lowering
  commit while allowing a raising one, inside its tmp repo;
- the block is PLACED where it actually runs: before a hook's terminating
  final `exit`, and inside a boardctl-chained hook's wrapped-body subshell
  (before the body's own terminating exit / the closing `)`) -- appended
  after either exit the block would be unreachable dead code.

Tests never touch the real board or the real hook: the canonical checkout's
hooks live in a shared common git dir, so the hook wiring is exercised only
inside tmp repos.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GUARD_SCRIPT = PROJECT_ROOT / "scripts" / "board_status_guard.py"
BOARD_RELATIVE = Path(".coding-hermes") / "board" / "tasks.jsonl"
HOOK_MARKER = "# >>> board status-lowering guard"


# -- helpers ---------------------------------------------------------


def git_env() -> dict[str, str]:
    """Hermetic git environment: no ambient GIT_* state, no user config."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return env


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env=git_env(),
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"git {args} failed rc={proc.returncode}: {proc.stderr.strip()}"
        )
    return proc


def commit_author_args() -> list[str]:
    """Identity flags so a commit works without any ambient git config."""
    return [
        "-c",
        "user.email=guard-test@example.invalid",
        "-c",
        "user.name=guard-test",
    ]


def write_board(repo: Path, rows: list[dict[str, str]]) -> None:
    path = repo / BOARD_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, *commit_author_args(), "commit", "-q", "-m", message)


def init_repo(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    """Throwaway repo with `rows` committed and pinned as origin/main."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write_board(repo, rows)
    commit_all(repo, "baseline board")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def run_guard(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repo),
    )


def run_install(repo: Path) -> subprocess.CompletedProcess[str]:
    return run_guard(repo, "--install-hook")


def install_script_copy(repo: Path) -> None:
    """The installed hook runs <repo>/scripts/board_status_guard.py."""
    (repo / "scripts").mkdir(exist_ok=True)
    shutil.copy2(GUARD_SCRIPT, repo / "scripts" / "board_status_guard.py")


def hook_path(repo: Path) -> Path:
    out = git(repo, "rev-parse", "--git-path", "hooks/pre-commit").stdout.strip()
    hook = Path(out)
    if not hook.is_absolute():
        hook = repo / hook
    return hook


# -- guard verdicts --------------------------------------------------


def test_lowering_refused(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, [{"id": "QA-T-1", "status": "complete"}])
    write_board(repo, [{"id": "QA-T-1", "status": "pending"}])
    result = run_guard(repo)
    assert result.returncode == 1
    assert (
        "QA-T-1: status lowered complete -> pending (base origin/main)" in result.stdout
    )
    assert "1 lowering violation" in result.stdout


def test_raises_pass(tmp_path: Path) -> None:
    repo = init_repo(
        tmp_path,
        [
            {"id": "QA-T-1", "status": "pending"},
            {"id": "QA-T-2", "status": "pending"},
        ],
    )
    write_board(
        repo,
        [
            {"id": "QA-T-1", "status": "blocked"},
            {"id": "QA-T-2", "status": "complete"},
        ],
    )
    result = run_guard(repo)
    assert result.returncode == 0
    assert "0 lowering violation" in result.stdout


def test_equal_status_and_new_row_pass(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, [{"id": "QA-T-1", "status": "blocked"}])
    write_board(
        repo,
        [
            {"id": "QA-T-1", "status": "blocked"},
            {"id": "QA-T-NEW", "status": "pending"},
        ],
    )
    result = run_guard(repo)
    assert result.returncode == 0
    assert "0 lowering violation" in result.stdout


def test_unknown_status_not_refused(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, [{"id": "QA-T-1", "status": "pending"}])
    # Unknown status in the NEW board: never guessed, skipped with a note.
    write_board(
        repo,
        [
            {"id": "QA-T-1", "status": "pending"},
            {"id": "QA-T-2", "status": "in_progress"},
        ],
    )
    result = run_guard(repo)
    assert result.returncode == 0
    assert "in_progress" in result.stderr
    # Unknown status in the BASE: also skipped -- guessing a rank could
    # invent a lowering that does not exist.
    write_board(
        repo,
        [
            {"id": "QA-T-1", "status": "complete"},
            {"id": "QA-T-2", "status": "in_progress"},
        ],
    )
    commit_all(repo, "baseline with unknown status")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    write_board(
        repo,
        [
            {"id": "QA-T-1", "status": "complete"},
            {"id": "QA-T-2", "status": "complete"},
        ],
    )
    result = run_guard(repo)
    assert result.returncode == 0
    assert "in_progress" in result.stderr


# -- fail-open arms --------------------------------------------------


def test_missing_base_fails_open(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, [{"id": "QA-T-1", "status": "pending"}])
    write_board(repo, [{"id": "QA-T-1", "status": "complete"}])
    result = run_guard(repo, "--base", "refs/heads/does-not-exist")
    assert result.returncode == 0
    assert "WARNING" in result.stderr


def test_corrupt_line_fails_open(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, [{"id": "QA-T-1", "status": "pending"}])
    # Corrupt line in the NEW board: the corrupt row is skipped, not a veto.
    path = repo / BOARD_RELATIVE
    path.write_text(
        json.dumps({"id": "QA-T-1", "status": "complete"}) + "\nnot-json{{{\n",
        encoding="utf-8",
    )
    result = run_guard(repo)
    assert result.returncode == 0
    assert "malformed JSON" in result.stderr
    # Corrupt line in the BASE: same fail-open treatment.
    path.write_text(
        "garbage line {{{\n" + json.dumps({"id": "QA-T-1", "status": "pending"}) + "\n",
        encoding="utf-8",
    )
    commit_all(repo, "corrupt baseline board")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    write_board(repo, [{"id": "QA-T-1", "status": "pending"}])
    result = run_guard(repo)
    assert result.returncode == 0
    assert "malformed JSON" in result.stderr


# -- --install-hook --------------------------------------------------


def test_install_hook_idempotent(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, [{"id": "QA-T-1", "status": "pending"}])
    install_script_copy(repo)
    hook = hook_path(repo)
    assert not hook.exists()

    first = run_install(repo)
    assert first.returncode == 0, first.stderr
    assert hook.exists()
    content = hook.read_text(encoding="utf-8")
    assert content.count(HOOK_MARKER) == 1
    assert os.access(hook, os.X_OK)

    second = run_install(repo)
    assert second.returncode == 0, second.stderr
    assert hook.read_text(encoding="utf-8") == content
    assert hook.read_text(encoding="utf-8").count(HOOK_MARKER) == 1


def test_installed_hook_refuses_lowering_allows_raising(tmp_path: Path) -> None:
    repo = init_repo(
        tmp_path,
        [
            {"id": "QA-T-DONE", "status": "complete"},
            {"id": "QA-T-OPEN", "status": "pending"},
        ],
    )
    install_script_copy(repo)
    assert run_install(repo).returncode == 0

    # Lowering commit: refused by the installed hook, HEAD does not move.
    write_board(
        repo,
        [
            {"id": "QA-T-DONE", "status": "pending"},
            {"id": "QA-T-OPEN", "status": "pending"},
        ],
    )
    git(repo, "add", "-A")
    refused = git(
        repo, *commit_author_args(), "commit", "-q", "-m", "reopen", check=False
    )
    combined = refused.stdout + refused.stderr
    assert refused.returncode != 0, combined
    assert "QA-T-DONE" in combined
    assert "status lowered complete -> pending" in combined
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"

    # Raising commit: the same hook lets it through.
    write_board(
        repo,
        [
            {"id": "QA-T-DONE", "status": "complete"},
            {"id": "QA-T-OPEN", "status": "blocked"},
        ],
    )
    git(repo, "add", "-A")
    allowed = git(
        repo, *commit_author_args(), "commit", "-q", "-m", "raise", check=False
    )
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "2"


# -- --install-hook placement ----------------------------------------
#
# The real canonical hook is boardctl-chained (BT-054-R): the original body
# runs inside a subshell `( ... )` whose LAST statement is an explicit
# `exit $?`, followed by a status capture line, a marked epilogue, and a
# final exit. A guard block appended at the end of the file — or inserted
# after any of those exits — is unreachable dead code, so a lowering commit
# would sail through. These tests pin the placement for both shapes.


def write_hook(repo: Path, body: str) -> Path:
    """Install `body` as the repo's pre-commit hook (executable)."""
    hook = hook_path(repo)
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(body, encoding="utf-8")
    hook.chmod(0o755)
    return hook


def try_commit(repo: Path, message: str) -> subprocess.CompletedProcess[str]:
    """git add -A + commit WITHOUT check, so hook refusals are observable."""
    git(repo, "add", "-A")
    return git(repo, *commit_author_args(), "commit", "-q", "-m", message, check=False)


LEGACY_EXIT_HOOK = """#!/bin/sh
# legacy body: a plain hook that terminates with an explicit exit.
echo "legacy hook body ran"
exit 0
"""

# Faithful miniature of the boardctl chain shape, including the wrapped
# body's own terminating `exit $?` (the real canonical hook ends the
# subshell exactly this way).
BOARDCTL_CHAIN_HOOK = """#!/bin/sh
# boardctl-chained hook: original body wrapped in a subshell, then epilogue.
(
    echo "wrapped original body ran"
    exit $?
)
boardctl_lint_existing_status=$?
# board-lint epilogue (managed by boardctl install): both statuses honored.
if [ "$boardctl_lint_existing_status" -ne 0 ]; then
    exit "$boardctl_lint_existing_status"
fi
exit 0
"""


def test_installed_hook_runs_before_terminating_exit(tmp_path: Path) -> None:
    repo = init_repo(
        tmp_path,
        [
            {"id": "QA-T-DONE", "status": "complete"},
            {"id": "QA-T-OPEN", "status": "pending"},
        ],
    )
    install_script_copy(repo)
    hook = write_hook(repo, LEGACY_EXIT_HOOK)

    assert run_install(repo).returncode == 0
    content = hook.read_text(encoding="utf-8")
    assert content.count(HOOK_MARKER) == 1
    # The block must precede the terminating exit, not dangle after it.
    assert content.index(HOOK_MARKER) < content.index("\nexit 0\n")

    # Lowering commit: the hook runs the guard BEFORE its own exit, and the
    # guard's exit 1 refuses the commit.
    write_board(
        repo,
        [
            {"id": "QA-T-DONE", "status": "pending"},
            {"id": "QA-T-OPEN", "status": "pending"},
        ],
    )
    refused = try_commit(repo, "reopen")
    combined = refused.stdout + refused.stderr
    assert refused.returncode != 0, combined
    assert "QA-T-DONE" in combined
    assert "status lowered complete -> pending" in combined
    # The legacy body still ran, ahead of the guard block.
    assert "legacy hook body ran" in combined
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"

    # Raising commit: the guard passes and the hook's own exit 0 wins.
    write_board(
        repo,
        [
            {"id": "QA-T-DONE", "status": "complete"},
            {"id": "QA-T-OPEN", "status": "blocked"},
        ],
    )
    allowed = try_commit(repo, "raise open row")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "legacy hook body ran" in allowed.stdout + allowed.stderr
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "2"


def test_installed_hook_runs_inside_boardctl_chain_subshell(tmp_path: Path) -> None:
    repo = init_repo(
        tmp_path,
        [
            {"id": "QA-T-DONE", "status": "complete"},
            {"id": "QA-T-OPEN", "status": "pending"},
        ],
    )
    install_script_copy(repo)
    hook = write_hook(repo, BOARDCTL_CHAIN_HOOK)

    assert run_install(repo).returncode == 0
    content = hook.read_text(encoding="utf-8")
    assert content.count(HOOK_MARKER) == 1
    # The block sits INSIDE the subshell: before the closing ')', before the
    # status capture line and epilogue -- and before the wrapped body's own
    # terminating `exit $?`, which would otherwise strand it (dead code).
    marker_at = content.index(HOOK_MARKER)
    paren_at = content.index("\n)")
    capture_at = content.index("boardctl_lint_existing_status=$?")
    assert marker_at < paren_at < capture_at
    assert marker_at < content.index("\n    exit $?")

    # Lowering: the guard runs inside the subshell; its exit 1 only leaves
    # the subshell, propagates into boardctl_lint_existing_status, and the
    # epilogue's final exit refuses the commit.
    write_board(
        repo,
        [
            {"id": "QA-T-DONE", "status": "pending"},
            {"id": "QA-T-OPEN", "status": "pending"},
        ],
    )
    refused = try_commit(repo, "reopen")
    combined = refused.stdout + refused.stderr
    assert refused.returncode != 0, combined
    assert "QA-T-DONE" in combined
    assert "status lowered complete -> pending" in combined
    assert "wrapped original body ran" in combined
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"

    # Raising: guard passes, the wrapped body's own exit 0 stands.
    write_board(
        repo,
        [
            {"id": "QA-T-DONE", "status": "complete"},
            {"id": "QA-T-OPEN", "status": "blocked"},
        ],
    )
    allowed = try_commit(repo, "raise open row")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "wrapped original body ran" in allowed.stdout + allowed.stderr
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "2"


def test_install_hook_idempotent_on_both_hook_shapes(tmp_path: Path) -> None:
    for name, body in (
        ("legacy-exit", LEGACY_EXIT_HOOK),
        ("boardctl-chain", BOARDCTL_CHAIN_HOOK),
    ):
        root = tmp_path / name
        root.mkdir()
        repo = init_repo(root, [{"id": "QA-T-DONE", "status": "complete"}])
        install_script_copy(repo)
        hook = write_hook(repo, body)

        assert run_install(repo).returncode == 0
        first = hook.read_text(encoding="utf-8")
        assert first.count(HOOK_MARKER) == 1

        assert run_install(repo).returncode == 0
        second = hook.read_text(encoding="utf-8")
        assert second == first
        assert second.count(HOOK_MARKER) == 1


def test_chain_hook_keeps_wrapped_body_failure(tmp_path: Path) -> None:
    """Insertion must not mask the wrapped body's own failure.

    The real chained hook ends its subshell with `exit $?`. A block that
    passes but leaves $? = 0 would turn a failing gitreins guard into an
    allowed commit, so the block re-emits the captured status on its pass
    path: nonzero stays nonzero, and the epilogue still refuses.
    """
    repo = init_repo(tmp_path, [{"id": "QA-T-DONE", "status": "complete"}])
    install_script_copy(repo)
    body = """#!/bin/sh
(
    echo "wrapped body failing on purpose"
    false
    exit $?
)
boardctl_lint_existing_status=$?
# board-lint epilogue (managed by boardctl install).
if [ "$boardctl_lint_existing_status" -ne 0 ]; then
    exit "$boardctl_lint_existing_status"
fi
exit 0
"""
    hook = write_hook(repo, body)
    assert run_install(repo).returncode == 0
    assert hook.read_text(encoding="utf-8").count(HOOK_MARKER) == 1

    # The BOARD side is clean (new row only, no lowering): the guard passes,
    # so any refusal must come from the wrapped body's own `exit $?`.
    write_board(
        repo,
        [
            {"id": "QA-T-DONE", "status": "complete"},
            {"id": "QA-T-NEW", "status": "pending"},
        ],
    )
    refused = try_commit(repo, "new row, body fails")
    combined = refused.stdout + refused.stderr
    assert refused.returncode != 0, combined
    assert "wrapped body failing on purpose" in combined
    assert "0 lowering violation" in combined
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"
