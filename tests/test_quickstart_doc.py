"""TJ-GAP-090 — pins docs/quickstart.md as stranger-executable.

The quickstart is the first page a fresh host reads: every command in it must
be copy-pasteable with no placeholder the reader has to invent (no
``<your-user>``, no ``<PATH>``, no ``{your_org}``), and it must state the host
capability requirements — PID-NS ``FULL`` for bare-mode containment,
FS-isolation ``FULL`` for the mapped-user-namespace filesystem layer —
together with what happens when a host does not meet them (degraded warnings;
bare mode exits 2 fail-closed, TJ-GAP-034). The install command the doc
teaches is proven valid live: ``install.sh --help`` must exit 0.

These are DOC pins, not behavior probes: the runtime behavior stays verified
by ``scripts/pidns-capability-probe.py`` / ``scripts/fs-isolation-probe.py``
and the backend battery. Follows the docs-pinning pattern of
``tests/test_capability_matrix_doc.py``.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = PROJECT_ROOT / "docs" / "quickstart.md"
INSTALL = PROJECT_ROOT / "install.sh"

# A placeholder is an angle-bracket token, a {snake_case} brace token, or an
# ALL-CAPS YOUR_ prefix. The quickstart must not need any of them: a stranger
# pastes the commands verbatim.
_PLACEHOLDER_RE = re.compile(r"<[a-z-]+>|\{[a-z_]+\}|YOUR_|<PATH>")

# The capability vocabulary the page must carry (probe layer names, either
# the uppercase tokens or the probe-script prefixes).
_CAPABILITY_RE = re.compile(r"PID-NS|FS-isolation|pidns|fs-isolation")


def test_quickstart_exists() -> None:
    assert DOC.is_file(), "docs/quickstart.md is missing"


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _fenced_commands() -> list[str]:
    """Every fenced block that carries shell commands (bash/console/sh)."""
    return re.findall(r"```(?:bash|console|sh)\n(.*?)```", _doc_text(), re.DOTALL)


def _inline_prompts() -> list[str]:
    """Inline ``$ `` command prompts in prose (fences dropped first)."""
    unfenced = re.sub(r"```.*?```", "", _doc_text(), flags=re.DOTALL)
    return re.findall(r"^\$\s+(.+)$", unfenced, re.MULTILINE)


def test_fenced_command_blocks_are_present() -> None:
    """Guard against fence-parsing rot: the page teaches ~28 bash blocks."""
    assert len(_fenced_commands()) >= 5, (
        "expected the install/verify/probe bash blocks; fence parsing rotted"
    )


def test_no_placeholders_anywhere() -> None:
    """Acceptance 1: zero placeholder-shaped tokens in the whole page."""
    text = _doc_text()
    hits = [
        (text.count("\n", 0, m.start()) + 1, m.group(0))
        for m in _PLACEHOLDER_RE.finditer(text)
    ]
    assert not hits, f"placeholders remain in docs/quickstart.md: {hits}"


def test_fenced_commands_have_no_placeholders() -> None:
    for block in _fenced_commands():
        assert not _PLACEHOLDER_RE.search(block), (
            f"placeholder inside a fenced command block: {block!r}"
        )


def test_inline_prompts_have_no_placeholders() -> None:
    for prompt in _inline_prompts():
        assert not _PLACEHOLDER_RE.search(prompt), (
            f"placeholder in an inline $ prompt: {prompt!r}"
        )


def test_doc_states_capability_requirements() -> None:
    """Acceptance 2 + the not-met outcomes, in so many words."""
    text = _doc_text()
    assert len(_CAPABILITY_RE.findall(text)) >= 2, (
        "the capability layers (pidns / fs-isolation) must be named"
    )
    # The probes themselves, by their real script names.
    assert "scripts/pidns-capability-probe.py" in text
    assert "scripts/fs-isolation-probe.py" in text
    # Bare mode without PID-NS: exit 2, fail-closed (TJ-GAP-034).
    assert "exit 2" in text, "bare-mode DEGRADED outcome (exit 2) must be stated"
    assert "TJ-GAP-034" in text, "the fail-closed contract must be cited"
    # --user degradation when FS-isolation is unavailable.
    assert "no filesystem isolation" in text, (
        "the --user degradation warning must be stated"
    )


def test_install_help_exits_zero() -> None:
    """The install command the doc teaches is valid: --help exits 0."""
    proc = subprocess.run(
        [str(INSTALL), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"install.sh --help rc={proc.returncode}: {proc.stderr[:400]}"
    )
    assert "Usage" in proc.stdout, "expected the usage banner on --help"
