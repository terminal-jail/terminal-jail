"""DOC-8 — pins for docs/capability-matrix.md (the per-host capability matrix).

The matrix states what terminal-jail delivers per enforcement layer per host
class / backend, with every cell marked enforced / degraded / unavailable (plus
the explicit ``unknown (not measured on this host)`` for cells nobody
measured). These are DOC pins, not behavior probes: they read the file and
assert the load-bearing strings — the probe commands that reproduce the read,
the six layer rows, and the measured numbers (the 2026-10-01 board snapshot
and the 2026-10-03 re-measurement) — so an edit cannot drift the numbers
silently. The runtime behavior itself is verified live by the repo's probes
(``scripts/pidns-capability-probe.py``, ``scripts/fs-isolation-probe.py``) and
the backend battery (``tests/test_backend_parity.py``).

Follows the docs-pinning pattern of ``tests/test_composed_doc.py``.
"""

from __future__ import annotations

import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = PROJECT_ROOT / "docs" / "capability-matrix.md"
README = PROJECT_ROOT / "README.md"

# The probe commands that produce the matrix — named with their real invocation.
_PROBE_COMMANDS = (
    "python3 scripts/pidns-capability-probe.py",
    "python3 scripts/fs-isolation-probe.py",
)

# The six enforcement-layer rows the matrix must carry.
_LAYER_ROWS = (
    "PID namespace",
    "Identity / env scrub",
    "Private `/proc`",
    "Filesystem isolation",
    "seccomp",
    "egress",
)

# Strings the matrix may never lose: the measured identities and counts.
# 2026-10-01 board snapshot: bwrap 5 /proc entries; unshare --user 1084
# entries with /proc/1 = systemd. 2026-10-03 re-measurement (numeric PID
# dirs): bwrap 4 entries; unshare --user 1175 vs host 1173.
_PINNED_STRINGS = (
    "/proc/1 = bwrap",
    "/proc/1 = systemd",
    "USER=nobody",
    "HOME=/nonexistent",
    "kernel.apparmor_restrict_unprivileged_userns",
)

_PINNED_NUMBERS = ("5", "1084", "4", "1175", "1173", "65534")

# The honest-unknown vocabulary: cells nobody measured must say exactly this.
_UNKNOWN_CELL = "unknown (not measured on this host)"

# The Ubuntu AppArmor case, stated with remediation.
_APPARMOR_CLAIM = "unavailable on Ubuntu 24.04+ by default"
_REMEDIATION_SYSCTL = "sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_capability_matrix_doc_exists() -> None:
    assert DOC.is_file(), "docs/capability-matrix.md is missing"


def test_doc_names_both_probe_commands() -> None:
    doc = _doc_text()
    for command in _PROBE_COMMANDS:
        assert command in doc, (
            f"probe command missing from the matrix page: {command!r}"
        )


def test_matrix_carries_all_six_layer_rows() -> None:
    doc = _doc_text()
    for layer in _LAYER_ROWS:
        assert layer in doc, f"missing enforcement-layer row: {layer}"
    # The rows must live in the markdown table (each starts with "| **").
    row_re = re.compile(
        r"^\|\s*\*\*(?:PID namespace|Identity / env scrub|Private `/proc`|"
        r"Filesystem isolation|seccomp|egress)\*\*",
        re.MULTILINE,
    )
    assert len(row_re.findall(doc)) == 6, "matrix must have exactly six layer rows"


def test_matrix_carries_the_four_host_columns() -> None:
    """Every launch-shape column must appear in the header row."""
    doc = _doc_text()
    header = re.search(r"^\| Enforcement layer \|.*$", doc, re.MULTILINE)
    assert header is not None, "matrix header row missing"
    for column in ("bwrap", "unshare (bare)", "unshare --user", "composed"):
        assert column in header.group(0), (
            f"host column missing from the matrix: {column!r}"
        )


def test_matrix_pins_key_strings() -> None:
    doc = _doc_text()
    for pinned in _PINNED_STRINGS:
        assert pinned in doc, f"pinned string missing from the matrix: {pinned!r}"


def test_matrix_pins_the_measured_numbers() -> None:
    doc = _doc_text()
    for number in _PINNED_NUMBERS:
        assert number in doc, f"measured number missing from the matrix: {number!r}"
    # The measured identities of the two procfs views, with their owners.
    assert re.search(r"\*\*5\*\*.*entries|entries.*\*\*5\*\*", doc), (
        "bwrap /proc entry count 5 (2026-10-01 snapshot)"
    )
    assert re.search(r"\*\*1084\*\*.*entries|entries.*\*\*1084\*\*", doc), (
        "unshare --user /proc entry count 1084 (2026-10-01 snapshot)"
    )
    assert "bwrap" in doc and "systemd" in doc, (
        "both procfs owners (bwrap, systemd) must be named"
    )


def test_every_cell_state_vocabulary_present() -> None:
    """The enforced/degraded/unavailable vocabulary must be used, and the
    honest-unknown string must appear for unmeasured cells."""
    doc = _doc_text()
    for state in ("**enforced**", "**degraded", "**unavailable**"):
        assert state in doc, f"state vocabulary missing from the matrix: {state!r}"
    assert _UNKNOWN_CELL in doc, (
        "unmeasured cells must say 'unknown (not measured on this host)'"
    )
    # The worktable must not be dressed up: no marketing language.
    for marketing in ("seamless", "bulletproof", "military-grade", "enterprise-grade"):
        assert marketing not in doc.lower(), (
            f"marketing language in the matrix: {marketing!r}"
        )


def test_ubuntu_apparmor_case_with_remediation() -> None:
    doc = _doc_text()
    assert _APPARMOR_CLAIM in doc, "the Ubuntu AppArmor default must be stated"
    assert _REMEDIATION_SYSCTL in doc, "remediation must name the sysctl"
    # The worked-example host facts.
    assert "Ubuntu 26.04" in doc
    assert "7.0.0-31" in doc


def test_worked_example_quotes_real_probe_output() -> None:
    """The page must quote the probes' real verdicts for this host."""
    doc = _doc_text()
    assert re.search(r"^\s*FULL\s*$", doc, re.MULTILINE), "pidns probe verdict FULL"
    assert "DEGRADED: mapped launch failed" in doc, "fs probe verdict DEGRADED"
    assert "setgroups failed: Operation not permitted" in doc, (
        "the diagnosed cause must be quoted"
    )


def test_readme_links_the_capability_matrix() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "docs/capability-matrix.md" in readme
    assert "### What containment do I get on MY host?" in readme, (
        "README must carry the host-capability section"
    )
    # The README section must name both probes so the reader can run them.
    for command in _PROBE_COMMANDS:
        assert command in readme, (
            f"README host-capability context lost a probe: {command!r}"
        )
