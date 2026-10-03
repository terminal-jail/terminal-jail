"""Docs-contract pin for the ``warn`` action runtime contract (TJ-DF-042).

docs/quickstart.md §3b2 documents what ``action: warn`` does at verdict time.
This module pins the load-bearing sentences so the contract cannot rot
silently: warn prints to stderr, the command still executes, nothing pauses
or prompts, the exit code is the command's own, and the warn-mode downgrade
provenance note is present. Follows the docs-pinning pattern of
test_docs_state_bubblewrap_packaging_boundary in test_packaging.py
(read the file, assert the exact claims).

These are DOC pins, not behavior probes: the runtime contract itself is
verified live (bridge verdict + wrapper stderr + exit codes) and quoted in
the doc's "Observed live" block.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUICKSTART = PROJECT_ROOT / "docs" / "quickstart.md"

_MD_EMPHASIS_RE = re.compile(r"(\*\*|__|`)")


def _plain_markdown(text: str) -> str:
    """Strip markdown emphasis/inline-code markers so claims assert as prose."""
    return _MD_EMPHASIS_RE.sub("", text)


def _section(text: str) -> str:
    """The 3b2 warn-action section only — later rewrites elsewhere must not
    be able to satisfy (or break) these pins."""
    start = text.index("### 3b2. The warn action (runtime contract)")
    ends = [idx for idx in (text.find("### 3c.", start),) if idx != -1]
    assert ends, "section 3c not found after 3b2 — doc structure drifted"
    return text[start : min(ends)]


def test_docs_pin_warn_action_section_exists() -> None:
    """TJ-DF-042: quickstart.md carries a warn-action runtime-contract section."""
    doc = _plain_markdown(QUICKSTART.read_text(encoding="utf-8"))
    assert "### 3b2. The warn action (runtime contract)" in doc


def test_docs_pin_warn_prints_to_stderr() -> None:
    """TJ-DF-042: the doc states the warning goes to stderr."""
    section = _section(_plain_markdown(QUICKSTART.read_text(encoding="utf-8")))
    assert "to stderr" in section, "doc must state warn prints to stderr"
    # And the concrete line shape the wrapper emits (em-dash separator).
    assert "WARNING — would have blocked:" in section


def test_docs_pin_warn_command_still_executes() -> None:
    """TJ-DF-042: the doc states the command runs after the warning."""
    section = _section(_plain_markdown(QUICKSTART.read_text(encoding="utf-8")))
    assert "the command still" in section
    assert "executes" in section
    # The downgrade arm too: block-under-warn-mode also runs.
    assert "the command runs" in section


def test_docs_pin_warn_no_pause_no_prompt() -> None:
    """TJ-DF-042: the doc states nothing pauses and nothing waits for input."""
    section = _section(_plain_markdown(QUICKSTART.read_text(encoding="utf-8")))
    assert "nothing pauses" in section
    assert "nothing waits for" in section
    assert "no confirmation is requested" in section


def test_docs_pin_warn_exit_code_is_the_commands_own() -> None:
    """TJ-DF-042: the doc states the exit code is the command's own."""
    section = _section(_plain_markdown(QUICKSTART.read_text(encoding="utf-8")))
    assert "exit code is the command's own" in section
    # And the enforcement contrast that makes the contract meaningful.
    assert "exit 126" in section


def test_docs_pin_warn_mode_downgrade_provenance() -> None:
    """TJ-DF-042: the doc carries the warn-mode downgrade provenance note."""
    section = _section(_plain_markdown(QUICKSTART.read_text(encoding="utf-8")))
    assert "[WARN MODE] Would have blocked:" in section
    # The downgrade's provenance must be stated, not just the prefix: a block
    # under warn mode yields rule_id null BECAUSE no rule decided to allow.
    assert "no rule decided to allow" in section, (
        "downgrade provenance (rule_id null because no rule decided) missing"
    )
    # TJ-DF-012 rule-level warn: the allow verdict names the warn rule itself.
    assert "would have blocked: <the rule's block_message>" in section
    assert "naming the warn rule" in section
    assert "TJ-DF-012" in section


def test_docs_pin_warn_is_per_command_and_bridge_action_field() -> None:
    """TJ-DF-042: per-command semantics + the bridge action-field caveat."""
    section = _section(_plain_markdown(QUICKSTART.read_text(encoding="utf-8")))
    assert "per command" in section
    # Consumers must not expect action "warn" on the wire — the verdict is an
    # allow whose warning rides in reason.
    assert "never says warn" in section
