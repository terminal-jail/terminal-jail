"""Docs-pin enforcement for documented tag-installer instructions (RELEASE-TJ-030).

The Tier-2 judge on RELEASE-TJ-030 (verdict b836590c) uncovered exactly one
uncovered failure path: a documentation edit could add a tag-checkout
installer command with NO explicit ``TERMINAL_JAIL_VERSION`` pin and still
pass the release-cut validation and the regression suite. install.sh pin
parity (tag == installer default) is enforced elsewhere; nothing scanned the
docs that TELL operators how to install from a tag.

This module adds that scan, deliberately narrow:

- Only FENCED code blocks in the documented instruction surfaces
  (``docs/releasing.md``, ``docs/quickstart.md``,
  ``docs/deploy-to-karahermes.md``) are scanned — never prose, release
  notes, or blockquotes.
- A "tag installer instruction" is a non-comment ``install.sh`` invocation
  line inside a fence that also carries a ``git checkout|switch ... vX.Y.Z``
  tag checkout, or an invocation line that itself references a release tag
  (e.g. a ``releases/download/vX.Y.Z`` URL), or an invocation in a fence
  whose *preceding paragraph* declares a tag checkout (see below).
- Preceding paragraph rule: the prose between the previous fence's closing
  line (or the start of the file) and this fence's opening line, trimmed to
  its LAST blank-line-separated paragraph — i.e. walking back from the
  opening fence, skip blank lines, then take the contiguous run of
  non-blank lines. Deterministic and narrow: nothing further away than that
  one paragraph is ever consulted (no whole-file prose scans).
  When that paragraph says ``tag checkout`` (case-insensitive) or carries a
  ``git checkout|switch ... vX.Y.Z`` line, the fence's install.sh
  invocations are tag installer instructions even without an in-fence tag
  reference — the prose is what makes the instruction a tag checkout.
- Every such instruction must carry ``TERMINAL_JAIL_VERSION=`` on its own
  line or on an immediately adjacent line of the same block.

Fail-closed by construction: an empty scan (docs missing, fences gone, or
zero tag-installer instructions found) is rc=2 — parser drift, not a pass.
"""

from __future__ import annotations

import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

DOC_PATHS = [
    PROJECT_ROOT / "docs" / "releasing.md",
    PROJECT_ROOT / "docs" / "quickstart.md",
    PROJECT_ROOT / "docs" / "deploy-to-karahermes.md",
]

# A tag checkout inside the same fence makes every install.sh invocation
# there a "tag installer instruction".
TAG_CHECKOUT_RE = re.compile(r"git\s+(?:checkout|switch)\b[^\n]*\bv\d+(?:\.\d+)+")
# The prose phrase "tag checkout" (case-insensitive) in the paragraph
# immediately preceding a fence declares that fence's installers to be
# tag-checkout instructions.
PROSE_TAG_CHECKOUT_RE = re.compile(r"tag\s+checkout", re.IGNORECASE)
# A release tag referenced by the invocation line itself (URL or arg).
TAG_REF_RE = re.compile(r"\bv\d+(?:\.\d+)+")
INSTALL_LINE_RE = re.compile(r"\binstall\.sh\b")
PIN_RE = re.compile(r"TERMINAL_JAIL_VERSION=")

RC_OK = 0
RC_VIOLATION = 1
RC_EMPTY_SCAN = 2


def _iter_fenced_blocks(
    lines: list[str],
) -> list[tuple[int, list[tuple[int, str]], int | None]]:
    """Yield fenced code blocks as (open_lineno, [(lineno, text), ...], close_lineno).

    ``close_lineno`` is None for an unterminated final fence (still scanned,
    fail-closed).
    """
    blocks: list[tuple[int, list[tuple[int, str]], int | None]] = []
    current: list[tuple[int, str]] | None = None  # None == outside any fence
    open_lineno = 0
    for lineno, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            if current is not None:
                blocks.append((open_lineno, current, lineno))
                current = None
            else:
                open_lineno = lineno
                current = []  # opening fence
            continue
        if current is not None:
            current.append((lineno, line))
    if current is not None:  # unterminated fence: still scanned (fail-closed)
        blocks.append((open_lineno, current, None))
    return blocks


def _preceding_paragraph(
    lines: list[str], open_lineno: int, prev_close_lineno: int | None
) -> str:
    """The last blank-line-separated paragraph before an opening fence.

    Window: strictly between the previous fence's closing line (or the start
    of the file) and the opening fence — the previous block's content is
    never consulted. Rule: walking back from the opening fence, skip blank
    lines, then take the contiguous run of non-blank lines. Deterministic;
    an all-blank window yields "" (no prose trigger possible).
    """
    window_start = prev_close_lineno or 0
    prose = lines[window_start : open_lineno - 1]
    paragraph: list[str] = []
    for line in reversed(prose):
        if not line.strip():
            if paragraph:
                break
            continue
        paragraph.append(line)
    paragraph.reverse()
    return "\n".join(paragraph)


def scan_tag_installer_pins(paths: list[pathlib.Path]) -> tuple[int, list[str], int]:
    """Scan docs for unpinned tag-installer instructions.

    Returns ``(rc, violations, n_instructions)``: rc 0 when at least one tag
    installer instruction was found and all carry an explicit pin, rc 1 with
    named ``<file>:<line>`` violations otherwise, rc 2 when the scan found no
    tag-installer instruction at all (empty scan must never read as a pass).
    """
    violations: list[str] = []
    n_instructions = 0
    for path in paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        prev_close: int | None = None
        for open_lineno, block, close_lineno in _iter_fenced_blocks(lines):
            has_tag_checkout = any(TAG_CHECKOUT_RE.search(text) for _, text in block)
            preceding = _preceding_paragraph(lines, open_lineno, prev_close)
            prose_declares_tag_checkout = bool(
                PROSE_TAG_CHECKOUT_RE.search(preceding)
                or TAG_CHECKOUT_RE.search(preceding)
            )
            for lineno, text in block:
                stripped = text.strip()
                if stripped.startswith("#") or not INSTALL_LINE_RE.search(text):
                    continue
                if not (
                    has_tag_checkout
                    or prose_declares_tag_checkout
                    or TAG_REF_RE.search(text)
                ):
                    continue
                n_instructions += 1
                adjacent = [t for ln, t in block if abs(ln - lineno) == 1]
                if not any(PIN_RE.search(t) for t in [text, *adjacent]):
                    violations.append(
                        f"{path.name}:{lineno}: tag-checkout installer instruction "
                        f"lacks an explicit TERMINAL_JAIL_VERSION= pin: {stripped}"
                    )
            prev_close = close_lineno if close_lineno is not None else open_lineno
    if violations:
        rc = RC_VIOLATION
    elif n_instructions == 0:
        rc = RC_EMPTY_SCAN
    else:
        rc = RC_OK
    return rc, violations, n_instructions


def test_documented_tag_installer_instructions_are_pinned() -> None:
    """GREEN arm (real docs): every documented tag installer carries a pin.

    Fails closed: zero scanned instructions is a named failure (parser drift),
    never a silent pass.
    """
    for doc in DOC_PATHS:
        assert doc.is_file(), f"documented instruction surface missing: {doc}"
    rc, violations, n = scan_tag_installer_pins(DOC_PATHS)
    assert n >= 1, (
        "fail-closed: the scan found NO tag-installer instructions in "
        f"{[p.name for p in DOC_PATHS]} — the parser has drifted or the docs "
        "no longer document tag installs; this is a failure, not a pass"
    )
    assert rc == RC_OK, "unpinned documented tag-installer instructions:\n" + "\n".join(
        violations
    )


def test_unpinned_tag_installer_in_mutated_copy_is_named(tmp_path) -> None:
    """RED arm (mutated COPY only — no tracked doc is edited here).

    A copy of the deploy doc gains an unpinned ``git checkout v9.9.8`` +
    ``./install.sh`` instruction; the same scanner must report rc != 0 and
    name the violating file and line.
    """
    source = DOC_PATHS[2]
    mutated = tmp_path / source.name
    original = source.read_text(encoding="utf-8")
    injected = "\n```bash\ngit checkout --detach v9.9.8\n./install.sh\n```\n"
    mutated.write_text(original + injected, encoding="utf-8")

    # Premise: the tracked original itself scans clean, so the only reason
    # the copy can fail is the injected instruction.
    rc_before, _, _ = scan_tag_installer_pins([source])
    assert rc_before == RC_OK, "premise broken: the tracked deploy doc must scan clean"

    rc, violations, n = scan_tag_installer_pins([mutated])
    assert rc != RC_OK, "the injected unpinned tag installer must be reported"
    assert n >= 1, "the injected instruction must be counted as a tag installer"
    assert violations, "the scan must name the violation, not fail silently"

    mutated_lines = (original + injected).splitlines()
    injected_lineno = max(
        i for i, line in enumerate(mutated_lines, 1) if line == "./install.sh"
    )
    expected_marker = f"{mutated.name}:{injected_lineno}"
    assert any(expected_marker in v for v in violations), violations
    assert any("TERMINAL_JAIL_VERSION" in v for v in violations), violations


def test_unpinned_quickstart_tag_instruction_in_mutated_copy_is_named(tmp_path) -> None:
    """RED arm #2: the tag-checkout fence loses only its pin token.

    docs/quickstart.md documents a tag-checkout install in a fence whose
    in-fence text carries NO ``git checkout v...`` line and whose invocation
    line carries no tag reference — only the PROSE paragraph before the fence
    declares it a tag checkout ("A **tag checkout's** installer is the case
    that bites..."). Verdict 9c7127c2 demonstrated a false green here: with
    the pre-prose-aware scanner, deleting ``TERMINAL_JAIL_VERSION=1.3.4``
    from that fence left the scan green. With the prose rule the same
    mutation must be named.
    """
    source = DOC_PATHS[1]  # docs/quickstart.md
    mutated = tmp_path / source.name
    original = source.read_text(encoding="utf-8")

    pinned_lines = [
        i
        for i, line in enumerate(original.splitlines(), 1)
        if "TERMINAL_JAIL_VERSION=1.3.4" in line
    ]
    # Premise: the documented tag-checkout instruction is exactly one pinned
    # line, and the untouched copy scans clean.
    assert len(pinned_lines) == 1, (
        f"expected exactly one 1.3.4-pinned line, got {pinned_lines}"
    )
    pinned_lineno = pinned_lines[0]
    rc_before, _, _ = scan_tag_installer_pins([source])
    assert rc_before == RC_OK, (
        "premise broken: the tracked quickstart doc must scan clean"
    )

    mutated_lines = original.splitlines()
    mutated_lines[pinned_lineno - 1] = mutated_lines[pinned_lineno - 1].replace(
        "TERMINAL_JAIL_VERSION=1.3.4 ", ""
    )
    mutated.write_text("\n".join(mutated_lines) + "\n", encoding="utf-8")

    rc, violations, n = scan_tag_installer_pins([mutated])
    assert rc != RC_OK, "the pin-less tag-checkout instruction must be reported"
    assert n >= 1, "the prose-declared tag-checkout instruction must be counted"
    assert violations, "the scan must name the violation, not fail silently"
    expected_marker = f"{mutated.name}:{pinned_lineno}"
    assert any(expected_marker in v for v in violations), violations
    assert any("TERMINAL_JAIL_VERSION" in v for v in violations), violations


def test_prose_and_non_tag_installers_are_not_flagged(tmp_path) -> None:
    """Narrowness control: prose-style surfaces must not false-positive.

    A release-notes-style copy (unfenced prose mentioning a tag and
    install.sh) and a fenced block installing from the current checkout with
    no tag checkout anywhere must both scan clean.
    """
    prose = tmp_path / "release-notes.md"
    prose.write_text(
        "# Release notes v1.3.4\n\n"
        "Fixed the installer. Run `./install.sh` from tag v1.3.4 to get it.\n",
        encoding="utf-8",
    )
    checkout_install = tmp_path / "quickstart-like.md"
    checkout_install.write_text(
        "```bash\ngit clone https://github.com/terminal-jail/terminal-jail.git\n"
        "cd terminal-jail\n./install.sh\n```\n",
        encoding="utf-8",
    )
    rc, violations, n = scan_tag_installer_pins([prose, checkout_install])
    assert violations == [], (
        "narrowness breach: prose or non-tag installers were flagged"
    )
    assert rc in (RC_OK, RC_EMPTY_SCAN), rc
    assert n == 0, "no tag-checkout installer instruction exists in either fixture"
