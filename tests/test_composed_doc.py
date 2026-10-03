"""DOC-9 — pins for docs/composed-deployment.md (the shared per-layer matrix).

The composed-stack page carries the contract for running terminal-jail INSIDE
an outer containment layer (a bunker-agent container, or any OCI container),
including the SHARED per-layer guarantee matrix whose numbers must match the
platform repository's copy (bunker ``DOC-043``). These are DOC pins, not
behavior probes: they read the file and assert the load-bearing strings so an
edit cannot drift the numbers silently. The runtime contract itself is verified
live by ``tests/test_composed_mode.py`` and the committed measurer
``scripts/composed-mode-battery.py``.

Follows the docs-pinning pattern of ``plugin/test_tjdf042_warn_docs_pin.py``
(read the file, assert the exact claims) and the layout of
``tests/test_composed_mode.py``.
"""

from __future__ import annotations

import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = PROJECT_ROOT / "docs" / "composed-deployment.md"
README = PROJECT_ROOT / "README.md"

# The five required sections (deliverable a–e).
_SECTIONS = (
    "## 1. The three configurations",
    "## 2. Composed quickstart",
    "## 3. Shared per-layer guarantee matrix",
    "## 4. Per-layer attribution warnings",
    "## 5. Cross-links and pinning",
)

# Strings the matrix may never lose: the frozen audit numbers and identities.
_PINNED_STRINGS = (
    "1084",  # host /proc view under unshare --user (measured 2026-10-01)
    "/proc/1 = bwrap",  # private-procfs ownership under the bwrap backend
    "exit 126",  # the tool's block exit code
    "rule_id builtin-rm-rf-root",  # block provenance
    "GAP-179",  # bunker counterpart: private /proc ownership
    "DOC-043",  # bunker counterpart: the platform-side copy of the matrix
)

# The three layers of the composed stack, each a matrix row.
_LAYER_ROWS = ("LAYER 1", "LAYER 2", "LAYER 3")


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_composed_doc_exists_with_all_sections() -> None:
    assert DOC.is_file(), "docs/composed-deployment.md is missing"
    doc = _doc_text()
    for heading in _SECTIONS:
        assert heading in doc, f"missing section: {heading}"


def test_matrix_pins_key_strings() -> None:
    doc = _doc_text()
    for pinned in _PINNED_STRINGS:
        assert pinned in doc, f"pinned string missing from the matrix: {pinned!r}"


def test_matrix_carries_the_three_layer_rows() -> None:
    doc = _doc_text()
    for layer in _LAYER_ROWS:
        assert layer in doc, f"missing layer row: {layer}"
    # The rows must live in the markdown table (each starts with "| **LAYER").
    row_re = re.compile(r"^\|\s*\*\*LAYER [123]\b", re.MULTILINE)
    assert len(row_re.findall(doc)) == 3, "matrix must have exactly three layer rows"


def test_matrix_carries_the_frozen_numbers() -> None:
    """The 4/5/1084 counts, the capability/seccomp states, the scrub."""
    doc = _doc_text()
    for value in (
        "CapEff 00000000a80425fb",  # container capability set, bit 21 clear
        "Seccomp: 2",  # container outer profile / --seccomp filter
        "HOME=/nonexistent",  # --user identity scrub
        "USER=nobody",
        "jail_layer=platform",  # composed mode adds no inner namespace
    ):
        assert value in doc, f"matrix lost a measured value: {value!r}"
    # The frozen /proc counts, all inside the matrix numbering.
    assert re.search(r"entry count \*\*4\*\*", doc), "container /proc count 4"
    assert re.search(r"entry count \*\*5\*\*", doc), "bwrap /proc count 5"
    assert re.search(r"entry count \*\*1084\*\*", doc), "host /proc count 1084"


def test_matrix_dates_the_unreverified_numbers() -> None:
    """Any snapshot value must carry its measurement date, per the brief."""
    doc = _doc_text()
    for count in ("4", "5", "1084"):
        annotated = f"entry count **{count}** `(measured 2026-10-01)`"
        assert annotated in doc, f"/proc count {count} must carry (measured 2026-10-01)"


def test_matrix_names_the_platform_copy_and_identical_numbers() -> None:
    """Cross-repo contract: the bunker copy (DOC-043) carries identical numbers."""
    doc = _doc_text()
    assert "DOC-043" in doc
    assert "identical" in doc, "the identical-numbers requirement must be stated"
    assert "one source of truth" in doc


def test_readme_links_the_composed_page() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "docs/composed-deployment.md" in readme
    assert (
        "See [docs/composed-deployment.md](docs/composed-deployment.md) for the "
        "full composed deployment guide and shared per-layer guarantee matrix."
        in readme
    ), "README must carry the exact one-line link"
