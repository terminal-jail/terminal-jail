"""REVIEW-TJ-009 — pins for the bwrap signal-reach boundary.

docs/backend-parity.md carries a "Signal reach boundary (bwrap private
/proc)" section and scripts/backend-parity-battery.py carries cell 10, the
live probe that re-measures the boundary on whatever host it runs on. These
are DOC/BATTERY pins, not behavior probes: they read the files and assert the
load-bearing strings and the cell registration so an edit cannot drift the
boundary silently. The runtime contract is measured live by the battery cell
itself (never by these tests — cell 10 launches bwrap and is a battery
concern, and these pins must stay cheap, offline, and host-independent).

Follows the docs-pinning pattern of ``tests/test_composed_doc.py`` (read the
file, assert the exact claims) and the importlib load of
``tests/test_kernel_matrix_teardown.py``.

The boundary pinned here (measured on the evidence host, bwrap 0.11.1 /
kernel 7.0.0-31):

- ``kill -0 1`` succeeds inside the private-/proc jail but is
  NAMESPACE-INTERNAL: /proc/1 in the jail is the bwrap reaper (known limit
  (b)), so the success says nothing about the host;
- the PID namespace is NOT shared with the host (``--unshare-pid`` creates a
  new one — ns ids differ); a live host pid is ESRCH from inside and the
  host process survives a TERM sent from inside;
- the premise as filed ("the payload CAN still signal host processes via
  their host PIDs") is recorded as DISPROVEN, and the section must keep
  saying so rather than over-claiming containment or reaching.
"""

from __future__ import annotations

import importlib.util
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = PROJECT_ROOT / "docs" / "backend-parity.md"
BATTERY = PROJECT_ROOT / "scripts" / "backend-parity-battery.py"

SECTION_HEADING = "## Signal reach boundary (bwrap private /proc) — REVIEW-TJ-009"

# Strings the section may never lose: the premise command + its measured
# output, and the three measured arms of the boundary.
_PINNED_DOC_STRINGS = (
    # the premise command, quoted verbatim (the direct --ro-bind shape)
    "--ro-bind /usr /usr",
    "--unshare-pid",
    "kill -0 1 && echo CAN-SIGNAL-PID1",
    "CAN-SIGNAL-PID1",
    # /proc/1 identity inside the jail (the namespace-internal explanation)
    "pid 1 in that jail is bwrap's own reaper",
    # the ns identity measurement (not shared)
    "pid:[4026531836]",
    # the live host-pid arm (ESRCH, process survives)
    "ESRCH",
    # the boundary statements
    "namespace-internal",
    "cannot\n   signal host processes by host PID",
    "Visibility is not reachability",
    # honest attribution + cross references
    "DISPROVEN",
    "TJ-GAP-088",
    "known limit (b)",
    "known limit (c)",
    "known limit (e)",
    "battery cell 10",
)

# The battery cell must keep the premise marker and the reach verdicts so the
# probe keeps REPORTING reality on every host.
_PINNED_BATTERY_STRINGS = (
    "10 signal reach — bwrap private /proc (REVIEW-TJ-009)",
    "CAN-SIGNAL-PID1",
    "ESRCH-HOSTPID",
    "TERM-FAILED",
    "_signal_reach_cell()",
    "REVIEW-TJ-009",
)


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _load_battery_module():
    spec = importlib.util.spec_from_file_location("backend_parity_battery", BATTERY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_signal_reach_section_exists() -> None:
    assert DOC.is_file(), "docs/backend-parity.md is missing"
    doc = _doc_text()
    assert SECTION_HEADING in doc, f"missing section: {SECTION_HEADING!r}"


def test_signal_reach_section_pins_the_measured_claims() -> None:
    doc = _doc_text()
    section = doc.split(SECTION_HEADING, 1)[1]
    for pinned in _PINNED_DOC_STRINGS:
        assert pinned in section, f"pinned string missing from the section: {pinned!r}"


def test_battery_registers_the_signal_reach_cell() -> None:
    module = _load_battery_module()
    # Registration is structural: the cell function exists, is used by
    # collect_cells (source-level pin — calling collect_cells would RUN the
    # probes), and the pinned strings survive in the module source.
    source = BATTERY.read_text(encoding="utf-8")
    assert callable(getattr(module, "_signal_reach_cell", None))
    for pinned in _PINNED_BATTERY_STRINGS:
        assert pinned in source, f"pinned string missing from the battery: {pinned!r}"
    import inspect

    collect_source = inspect.getsource(module.collect_cells)
    assert "_signal_reach_cell()" in collect_source, (
        "collect_cells must register the signal-reach cell"
    )


def test_battery_cell_verdict_vocabulary_unchanged() -> None:
    """The new cell must speak the house vocabulary, not invent one."""
    module = _load_battery_module()
    assert getattr(module, "VOCABULARY", ()) == (
        "SAME",
        "DIFFERS",
        "KNOWN-LIMIT",
        "FAIL-CLOSED-PROVEN",
    )


def test_doc_does_not_overclaim_host_reach() -> None:
    """Negative pin: the over-claim the premise carried must never appear as
    an UNQUALIFIED statement. The quoted premise itself ("the payload CAN
    still signal host processes via their host PIDs") is allowed exactly
    once — as the thing being disproven — and the disproven verdict must sit
    next to it."""
    doc = _doc_text()
    section = doc.split(SECTION_HEADING, 1)[1]
    section = section.split("## Kernel-matrix teardown status", 1)[0]
    flat = " ".join(section.split())
    overclaim = "the payload CAN still signal host processes via their host PIDs"
    count = flat.count(overclaim)
    assert count <= 1, (
        f"the over-claim appears {count}x — it is only allowed as the single "
        "quoted premise"
    )
    if count == 1:
        assert "DISPROVEN" in flat, (
            "the quoted premise must carry its disproven verdict"
        )
    assert "PID namespace is SHARED with the host" not in flat
