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
  commit while allowing a raising one, inside its tmp repo.

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
