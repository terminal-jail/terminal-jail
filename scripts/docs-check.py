#!/usr/bin/env python3
"""README docs check for terminal-jail (README-5): fences + pinned commands.

Nothing else in CI reads README.md (verified 2026-10-27: the "Drift guards"
job runs rule-catalog / yaml-mirror-parity / rules-drift / backend-parity /
kernel-matrix-teardown; none of them touches README.md), so README rot —
stale fences, broken quickstart commands — shipped undetected. This script
is the missing guard. Stdlib only.

CHECK 1 — fenced-block balance in README.md
    A line starting with ``` at COLUMN 0 toggles a fenced block (this is
    how the README writes fences). The fence-line count must be even and
    no block may be open at EOF; on failure the opening line number of the
    unclosed block is reported.

CHECK 2 — pinned read-only README commands
    Executes the PINNED_COMMANDS list (data: one dict per command with an
    `argv` list — extend it when a README audit pins new commands) from
    the repo root with a bounded timeout, and fails on any non-zero exit.
    The bridge pin additionally requires exactly one stdout line that
    json-parses with action == "allow" and a non-null rule_id.
    Pins are deliberately read-only and CI-safe: no unprivileged PID
    namespaces, no bubblewrap, no root, no network, no writable install
    dir — a stock CI runner passes them all.

ESCAPE HATCH
    Set TERMINAL_JAIL_DOCS_CHECK_SKIP_COMMANDS=1 (or true/yes/on, any
    case) to skip CHECK 2 ONLY — CHECK 1 is always enforced. Intended for
    local runs in sandboxes where the pinned commands cannot execute; CI
    never sets it.

CLI
    docs-check.py [--readme PATH]    # default: <repo root>/README.md

Negative controls, without editing this file or the real README:
  * fence control: point --readme at a mutated COPY of the README;
  * command control: import this module and call
    run_pinned_commands(commands=[{"id": ..., "argv": ["false"]}]).

Exit 0 only if every enforced check passes; exit 1 otherwise, with one
self-explaining PASS/FAIL line per check (and per pinned command).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

COMMAND_TIMEOUT_S = 60

BRIDGE_STDIN = '{"command": "ls -la"}\n'

# Data structure, not code: a future README audit extends this list.
# Keys: id (display name), argv (required), stdin (optional),
# expect (optional bridge-verdict assertions).
PINNED_COMMANDS = [
    {
        "id": "terminal-jail --version",
        "argv": ["./standalone/terminal-jail", "--version"],
    },
    {
        "id": "terminal-jail --help",
        "argv": ["./standalone/terminal-jail", "--help"],
    },
    {
        "id": "rule-catalog --check",
        "argv": ["python3", "scripts/rule-catalog.py", "--check"],
    },
    {
        "id": "interruptor_bridge benign verdict",
        "argv": ["python3", "plugin/terminal_jail/interruptor_bridge.py"],
        "stdin": BRIDGE_STDIN,
        "expect": {"stdout_lines": 1, "action": "allow", "rule_id_not_null": True},
    },
]


def check_fence_balance(readme: Path) -> tuple[bool, str]:
    """Toggle-count ^``` fence lines; name the unclosed block on failure."""
    try:
        lines = readme.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return False, f"[FAIL] fenced-block balance: cannot read {readme}: {exc}"
    open_at: int | None = None
    fence_lines = 0
    for no, line in enumerate(lines, start=1):
        if line.startswith("```"):
            fence_lines += 1
            open_at = no if open_at is None else None
    if open_at is None:
        blocks = fence_lines // 2
        return True, (
            f"[PASS] fenced-block balance: {fence_lines} fence lines "
            f"({blocks} blocks), all closed"
        )
    return False, (
        f"[FAIL] fenced-block balance: {fence_lines} fence lines is odd; "
        f"block opened at line {open_at} of {readme} is never closed "
        f"(EOF inside a fence)"
    )


def _first_line(proc: subprocess.CompletedProcess[str]) -> str:
    for stream in (proc.stdout, proc.stderr):
        if stream and stream.strip():
            return stream.strip().splitlines()[0]
    return "(no output)"


def _validate_expectation(
    expect: dict, proc: subprocess.CompletedProcess[str], display: str
) -> tuple[bool, list[str]]:
    """Check bridge-verdict expectations: one JSON stdout line, allow, rule."""
    ok = True
    msgs: list[str] = []
    out_lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    want_lines = expect.get("stdout_lines")
    if want_lines is not None and len(out_lines) != want_lines:
        ok = False
        msgs.append(
            f"[FAIL] {display}: expected exactly {want_lines} stdout "
            f"line(s), got {len(out_lines)}"
        )
    verdict = None
    if out_lines:
        try:
            verdict = json.loads(out_lines[0])
        except json.JSONDecodeError as exc:
            ok = False
            msgs.append(
                f"[FAIL] {display}: first stdout line does not json-parse: {exc}"
            )
    else:
        ok = False
        msgs.append(f"[FAIL] {display}: no stdout to parse")
    if verdict is not None:
        want_action = expect.get("action")
        if want_action is not None and verdict.get("action") != want_action:
            ok = False
            msgs.append(
                f"[FAIL] {display}: expected action={want_action!r}, "
                f"got {verdict.get('action')!r}"
            )
        if expect.get("rule_id_not_null") and verdict.get("rule_id") is None:
            ok = False
            msgs.append(f"[FAIL] {display}: rule_id is null (expected a deciding rule)")
    return ok, msgs


def run_pinned_commands(
    commands: list[dict] | None = None, cwd: Path | None = None
) -> tuple[bool, list[str]]:
    """Run pinned read-only commands; return (all_ok, one message per line)."""
    commands = PINNED_COMMANDS if commands is None else commands
    cwd = REPO_ROOT if cwd is None else cwd
    all_ok = True
    messages: list[str] = []
    for spec in commands:
        argv = spec["argv"]
        display = shlex.join(argv)
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd),
                input=spec.get("stdin"),
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            all_ok = False
            messages.append(f"[FAIL] {display} -> TIMEOUT after {COMMAND_TIMEOUT_S}s")
            continue
        except OSError as exc:
            all_ok = False
            messages.append(f"[FAIL] {display} -> could not exec: {exc}")
            continue
        failed = proc.returncode != 0
        messages.append(
            f"[{'FAIL' if failed else 'PASS'}] {display} -> "
            f"rc={proc.returncode} | first line: {_first_line(proc)}"
        )
        if not failed and "expect" in spec:
            exp_ok, exp_msgs = _validate_expectation(spec["expect"], proc, display)
            messages.extend(exp_msgs)
            failed = failed or not exp_ok
        all_ok = all_ok and not failed
    return all_ok, messages


def skip_commands_requested() -> bool:
    raw = os.environ.get("TERMINAL_JAIL_DOCS_CHECK_SKIP_COMMANDS", "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="README docs check: fenced-block balance + pinned commands."
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=REPO_ROOT / "README.md",
        help="README to check (default: <repo root>/README.md)",
    )
    args = parser.parse_args(argv)

    all_ok = True

    fence_ok, fence_msg = check_fence_balance(args.readme)
    print(f"docs-check[check1] {fence_msg}")
    all_ok = all_ok and fence_ok

    if skip_commands_requested():
        print(
            "docs-check[check2] [SKIP] pinned commands skipped "
            "(TERMINAL_JAIL_DOCS_CHECK_SKIP_COMMANDS is set); "
            "check 1 remains enforced"
        )
    else:
        cmds_ok, cmd_msgs = run_pinned_commands()
        for msg in cmd_msgs:
            print(f"docs-check[check2] {msg}")
        status = "PASS" if cmds_ok else "FAIL"
        print(
            f"docs-check[check2] [{status}] pinned commands "
            f"({len(PINNED_COMMANDS)} pinned)"
        )
        all_ok = all_ok and cmds_ok

    print(f"docs-check: overall {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
