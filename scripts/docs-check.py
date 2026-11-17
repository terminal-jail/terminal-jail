#!/usr/bin/env python3
"""Docs check for terminal-jail (README-5, TJ-DF-067): README fences, version,
pinned commands, and the quarterly-review §3 standalone-CLI checklist.

Nothing else in CI reads README.md (verified 2026-10-27: the "Drift guards"
job runs rule-catalog / yaml-mirror-parity / rules-drift / backend-parity /
kernel-matrix-teardown; none of them touches README.md), so README rot —
stale fences, broken quickstart commands — shipped undetected. This script
is the missing guard. docs/quarterly-review.md §3 was the same hole on the
release-checklist side (TJ-DF-067: five CLI lines nobody could pass, executed
by nothing), so CHECK 4 now runs that checklist straight out of the document.
Stdlib only.

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

CHECK 4 — quarterly-review §3 standalone-CLI checklist
    Extracts every `- [ ]` line of docs/quarterly-review.md section 3
    ("Standalone CLI"), takes the FIRST inline-code span of the line as its
    argv, and executes it from the repo root. The DOCUMENT is the source of
    truth: the checker keeps no second copy of the command, so a checklist
    line cannot drift from what CI actually runs. Each command must exit 0,
    be registered in QUARTERLY_EXPECT (the table stating what the line
    CLAIMS: usage text, version string, printed isolation marker), and
    satisfy that claim. A command that is missing from the table fails
    loudly instead of passing on exit status alone — "it happens to exit 0"
    is exactly how the stale `--` invocations survived.

    Unlike CHECK 2 these commands DO use namespaces, so they cannot be
    promised passable on every runner. Two honest non-pass classes are
    reported as SKIP with the reason, never as PASS (same doctrine as
    scripts/kernel-matrix-teardown.py --gate): the wrapper refusing for an
    environment reason (exit 2 + "command not run" — no namespaces on this
    host, isolation never silently downgraded), and a per-entry
    `skip_if_stderr_contains` marker (composed mode, where --seccomp is
    documented as NOT applied by this tool). When every line skips, the check
    says so: "0 of N commands could be verified on this host".

ESCAPE HATCH
    Set TERMINAL_JAIL_DOCS_CHECK_SKIP_COMMANDS=1 (or true/yes/on, any
    case) to skip CHECK 3 and CHECK 4 ONLY — CHECK 1 and CHECK 2 are always
    enforced. Intended for local runs in sandboxes where the pinned commands
    cannot execute; CI never sets it.

CLI
    docs-check.py [--readme PATH] [--quarterly PATH]
                   # defaults: <repo root>/README.md, docs/quarterly-review.md

Negative controls, without editing this file or the real docs:
  * fence control: point --readme at a mutated COPY of the README;
  * command control: import this module and call
    run_pinned_commands(commands=[{"id": ..., "argv": ["false"]}]);
  * checklist control: point --quarterly at a COPY of the quarterly review
    with a stale invocation reinserted into §3 (e.g. `-- echo hello`, which
    the wrapper answers with rc 127 "command not found").

Exit 0 only if every enforced check passes; exit 1 otherwise, with one
self-explaining PASS/FAIL line per check (and per pinned command).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

COMMAND_TIMEOUT_S = 60

VERSION_LITERAL_RE = re.compile(r"v?[0-9]+[.][0-9]+[.][0-9]+")

BRIDGE_STDIN = '{"command": "ls -la"}\n'

QUARTERLY_DOC = REPO_ROOT / "docs" / "quarterly-review.md"

#: §3 of the quarterly review is the standalone-CLI checklist (TJ-DF-067).
QUARTERLY_SECTION_RE = re.compile(r"^##\s+3\.\s+Standalone CLI\b")
SECTION_HEADING_RE = re.compile(r"^##\s+")
CHECKBOX_RE = re.compile(r"^\s*-\s+\[ \]\s+(?P<body>.*)$")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")

#: Only the wrapper is ever executed from the checklist. A line naming any
#: other program is refused before it runs: the document is editable by hand
#: and this check must never become a way to execute an arbitrary command in
#: CI just by adding a bullet.
QUARTERLY_WRAPPER = "./standalone/terminal-jail"

#: The wrapper's documented fail-closed refusal: exit 2 plus this marker
#: means "command not run" because the host cannot provide the isolation, an
#: environment limit rather than a doc regression (never silently downgraded,
#: see standalone/terminal-jail and scripts/kernel-matrix-teardown.py --gate).
WRAPPER_REFUSAL_RC = 2
WRAPPER_REFUSAL_MARKER = "command not run"

#: TJ-DF-067: what each docs/quarterly-review.md §3 line CLAIMS, keyed by the
#: exact command text the document shows. A checklist command absent from this
#: table fails CHECK 4 instead of passing on exit status alone — the stale
#: `-- echo hello` lines this table replaced either failed outright (rc 127) or
#: exited 0 for the wrong reason (`--seccomp -- echo hello`: the loader, not
#: the wrapper, ate the `--`), so nothing ever tested a claim.
#: Keys: stdout_equals (one line, `{version}` rendering the pyproject
#: version), stdout_contains (all substrings), stdout_one_of (exact match
#: against a set), skip_if_stderr_contains (documented degradation markers).
QUARTERLY_EXPECT = {
    "./standalone/terminal-jail --help": {
        "stdout_contains": ["Usage:", "--user", "--seccomp"],
    },
    "./standalone/terminal-jail --version": {
        "stdout_equals": "terminal-jail {version}",
    },
    "./standalone/terminal-jail echo hello": {"stdout_contains": ["hello"]},
    "./standalone/terminal-jail --user printenv TERMINAL_JAIL_FS_ISOLATION": {
        "stdout_one_of": ["mapped", "degraded"],
    },
    "./standalone/terminal-jail --seccomp printenv TERMINAL_JAIL_SECCOMP": {
        "stdout_equals": "1",
        "skip_if_stderr_contains": ["seccomp filter is NOT applied in composed mode"],
    },
    "./standalone/terminal-jail --user --seccomp echo hello": {
        "stdout_contains": ["hello"],
    },
}

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


def check_version_cell(
    readme: Path, pyproject: Path = REPO_ROOT / "pyproject.toml"
) -> tuple[bool, str]:
    """Reject hard-coded README Version-cell values that differ from pyproject."""
    try:
        version = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"][
            "version"
        ]
        lines = readme.read_text(encoding="utf-8").splitlines()
    except (
        KeyError,
        OSError,
        TypeError,
        UnicodeDecodeError,
        tomllib.TOMLDecodeError,
    ) as exc:
        return False, f"[FAIL] README Version cell: cannot read version sources: {exc}"

    version_lines = [line for line in lines if line.startswith("| **Version** |")]
    if len(version_lines) != 1:
        return False, (
            "[FAIL] README Version cell: expected exactly one "
            f"Version row, found {len(version_lines)}"
        )

    expected = f"v{version}"
    literals = VERSION_LITERAL_RE.findall(version_lines[0])
    stale = sorted(
        {literal for literal in literals if literal.removeprefix("v") != version}
    )
    if stale:
        return False, (
            f"[FAIL] README Version cell: pyproject.toml says {expected}; "
            f"README contains stale version(s): {', '.join(stale)}"
        )
    if literals:
        return True, f"[PASS] README Version cell matches pyproject.toml ({expected})"
    return True, "[PASS] README Version cell has no hard-coded version literal"


def _first_line(proc: subprocess.CompletedProcess[str]) -> str:
    for stream in (proc.stdout, proc.stderr):
        if stream and stream.strip():
            return stream.strip().splitlines()[0]
    return "(no output)"


def _diagnostic_line(proc: subprocess.CompletedProcess[str]) -> str:
    """The wrapper's own error line: verdict JSON first, real diagnosis last."""
    lines = [ln.strip() for ln in (proc.stderr or "").splitlines() if ln.strip()]
    lines = [ln for ln in lines if not ln.startswith("{")]
    return lines[-1] if lines else _first_line(proc)


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


def pyproject_version(path: Path = REPO_ROOT / "pyproject.toml") -> str:
    """Project version from pyproject.toml — the value the docs must match."""
    return str(tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"])


def _quarterly_section_lines(doc: Path) -> list[str]:
    """Body lines of the "## 3. Standalone CLI" section (heading excluded)."""
    lines = doc.read_text(encoding="utf-8").splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if QUARTERLY_SECTION_RE.match(line):
            start = index + 1
            break
    if start is None:
        raise ValueError(f"no '## 3. Standalone CLI' section in {doc}")
    body: list[str] = []
    for line in lines[start:]:
        if SECTION_HEADING_RE.match(line):
            break
        body.append(line)
    return body


def quarterly_commands(doc: Path | None = None) -> list[str]:
    """Commands the §3 checklist asks a reviewer to run, in document order.

    The FIRST inline-code span of each `- [ ]` line is its command. A
    checklist line with no command span raises: an item nobody can execute is
    the rot this check exists to catch, so it must not be skipped silently.
    """
    doc = QUARTERLY_DOC if doc is None else doc
    commands: list[str] = []
    for line in _quarterly_section_lines(doc):
        match = CHECKBOX_RE.match(line)
        if match is None:
            continue
        span = INLINE_CODE_RE.search(match.group("body"))
        if span is None:
            raise ValueError(
                f"checklist line carries no inline-code command: {line.strip()!r}"
            )
        commands.append(span.group(1).strip())
    return commands


def _validate_quarterly_expectation(
    expect: dict, proc: subprocess.CompletedProcess[str], display: str, version: str
) -> tuple[bool, str]:
    """Compare a checklist command's stdout with what its line claims."""
    stdout = proc.stdout or ""
    out = stdout.strip()
    want_equals = expect.get("stdout_equals")
    if want_equals is not None:
        want = want_equals.format(version=version)
        if out != want:
            return False, f"[FAIL] {display}: expected stdout {want!r}, got {out!r}"
    for needle in expect.get("stdout_contains", ()):
        if needle not in stdout:
            return False, f"[FAIL] {display}: stdout is missing {needle!r}"
    one_of = expect.get("stdout_one_of")
    if one_of is not None and out not in one_of:
        return False, f"[FAIL] {display}: expected stdout one of {one_of}, got {out!r}"
    return True, f"[PASS] {display} -> rc=0 | stdout: {_first_line(proc)}"


def check_quarterly_cli(doc: Path | None = None) -> tuple[bool, list[str]]:
    """Run every §3 checklist command and assert the claim its line makes."""
    doc = QUARTERLY_DOC if doc is None else doc
    try:
        commands = quarterly_commands(doc)
        version = pyproject_version()
    except (
        KeyError,
        OSError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        tomllib.TOMLDecodeError,
    ) as exc:
        return False, [f"[FAIL] quarterly §3 CLI checklist: cannot read inputs: {exc}"]
    if not commands:
        return False, [
            f"[FAIL] quarterly §3 CLI checklist: no '- [ ]' command lines in {doc}"
        ]

    all_ok = True
    verified = 0
    messages: list[str] = []
    for command in commands:
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            all_ok = False
            messages.append(f"[FAIL] {command}: cannot parse as argv: {exc}")
            continue
        if not argv or argv[0] != QUARTERLY_WRAPPER:
            all_ok = False
            messages.append(
                f"[FAIL] {command}: §3 executes only {QUARTERLY_WRAPPER} "
                "invocations; this line was NOT run"
            )
            continue
        try:
            proc = subprocess.run(
                argv,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            all_ok = False
            messages.append(f"[FAIL] {command} -> TIMEOUT after {COMMAND_TIMEOUT_S}s")
            continue
        except OSError as exc:
            all_ok = False
            messages.append(f"[FAIL] {command} -> could not exec: {exc}")
            continue

        stderr = proc.stderr or ""
        if proc.returncode == WRAPPER_REFUSAL_RC and WRAPPER_REFUSAL_MARKER in stderr:
            messages.append(
                f"[SKIP] {command} -> rc={proc.returncode}, the wrapper refused to "
                f"run it (environment, not a doc regression): "
                f"{_diagnostic_line(proc)}"
            )
            continue
        if proc.returncode != 0:
            all_ok = False
            messages.append(
                f"[FAIL] {command} -> rc={proc.returncode} | "
                f"first line: {_diagnostic_line(proc)}"
            )
            continue
        expect = QUARTERLY_EXPECT.get(command)
        if expect is None:
            all_ok = False
            messages.append(
                f"[FAIL] {command}: exits 0 but is not registered in "
                "QUARTERLY_EXPECT, so the claim its line makes is unchecked"
            )
            continue
        marker = next(
            (m for m in expect.get("skip_if_stderr_contains", ()) if m in stderr),
            None,
        )
        if marker is not None:
            messages.append(
                f"[SKIP] {command} -> documented degradation ({marker}); "
                f"not counted as PASS: {_first_line(proc)}"
            )
            continue
        ok, message = _validate_quarterly_expectation(expect, proc, command, version)
        all_ok = all_ok and ok
        verified += 1
        messages.append(message)
    if verified == 0:
        messages.append(
            f"[SKIP] 0 of {len(commands)} quarterly §3 commands could be verified on "
            "this host — a skip is never coverage"
        )
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
    parser.add_argument(
        "--quarterly",
        type=Path,
        default=QUARTERLY_DOC,
        help="quarterly review to check (default: <repo root>/docs/quarterly-review.md)",
    )
    args = parser.parse_args(argv)

    all_ok = True

    fence_ok, fence_msg = check_fence_balance(args.readme)
    print(f"docs-check[check1] {fence_msg}")
    all_ok = all_ok and fence_ok

    version_ok, version_msg = check_version_cell(args.readme)
    print(f"docs-check[check2] {version_msg}")
    all_ok = all_ok and version_ok

    if skip_commands_requested():
        print(
            "docs-check[check3] [SKIP] pinned commands skipped "
            "(TERMINAL_JAIL_DOCS_CHECK_SKIP_COMMANDS is set); "
            "check 1 remains enforced"
        )
        print(
            "docs-check[check4] [SKIP] quarterly §3 CLI checklist skipped "
            "(TERMINAL_JAIL_DOCS_CHECK_SKIP_COMMANDS is set); "
            "checks 1 and 2 remain enforced"
        )
    else:
        cmds_ok, cmd_msgs = run_pinned_commands()
        for msg in cmd_msgs:
            print(f"docs-check[check3] {msg}")
        status = "PASS" if cmds_ok else "FAIL"
        print(
            f"docs-check[check3] [{status}] pinned commands "
            f"({len(PINNED_COMMANDS)} pinned)"
        )
        all_ok = all_ok and cmds_ok

        quarterly_ok, quarterly_msgs = check_quarterly_cli(args.quarterly)
        for msg in quarterly_msgs:
            print(f"docs-check[check4] {msg}")
        status = "PASS" if quarterly_ok else "FAIL"
        print(f"docs-check[check4] [{status}] quarterly-review §3 CLI checklist")
        all_ok = all_ok and quarterly_ok

    print(f"docs-check: overall {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
