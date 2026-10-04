"""DOC-8 — pins for docs/capability-matrix.md (the per-host capability matrix).

The matrix states what terminal-jail delivers per enforcement layer per launch
shape / host class, with every cell marked enforced / degraded / unavailable
(and an explicit ``unknown (not measured on this host)`` for cells nobody
measured). These are DOC pins, not behavior probes: they read the file and
assert the load-bearing strings — the probe commands that reproduce the read,
the six layer rows, and the measured numbers — so an edit cannot drift the
numbers silently. The runtime behavior itself is verified live by the repo's
probes (``scripts/pidns-capability-probe.py``, ``scripts/fs-isolation-probe.py``)
and the backend battery (``plugin/test_backend_parity.py``).

Two pins guard the cross-document contract with the shared per-layer matrix
(``tests/test_composed_doc.py`` / ``docs/composed-deployment.md`` §3): the
2026-10-01 snapshot numbers (bwrap 5, ``unshare --user`` 1084, container 4)
must appear in BOTH pages and must agree, and the worked-example page must
point at that shared matrix.

Follows the docs-pinning pattern of ``tests/test_composed_doc.py``.
"""

from __future__ import annotations

import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = PROJECT_ROOT / "docs" / "capability-matrix.md"
COMPOSED_DOC = PROJECT_ROOT / "docs" / "composed-deployment.md"
README = PROJECT_ROOT / "README.md"

# The probe commands that produce the matrix — named with their real invocation.
_PROBE_COMMANDS = (
    "python3 scripts/pidns-capability-probe.py",
    "python3 scripts/fs-isolation-probe.py",
)

# The six enforcement-layer rows the matrix must carry (the DOC-8 brief's rows).
_LAYER_ROWS = (
    "PID namespace",
    "Identity / env scrub",
    "Private `/proc`",
    "Filesystem isolation",
    "seccomp",
    "egress",
)

# Strings the matrix may never lose: the measured identities.
_PINNED_STRINGS = (
    "/proc/1 = bwrap",
    "/proc/1 = systemd",
    "USER=nobody",
    "HOME=/nonexistent",
    "kernel.apparmor_restrict_unprivileged_userns",
    "jail_layer=platform",
    "proc_view=platform-owned",
)

# The launch-shape columns of the matrix header row.
_COLUMNS = ("bwrap backend", "unshare (bare)", "unshare --user", "composed")

# The honest-unknown vocabulary: cells nobody measured must say exactly this.
_UNKNOWN_CELL = "unknown (not measured on this host)"

# The Ubuntu AppArmor case, stated with remediation (DOC-8 acceptance 3).
_APPARMOR_CLAIM = "unavailable on Ubuntu 24.04+ by default"
_REMEDIATION_SYSCTL = "sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"

# The shared 2026-10-01 board snapshot: /proc entry counts per shape, with the
# row-identity conventions used in both pages. bwrap = private procfs,
# 1084 = the host view under unshare --user, 4 = the container's own view.
# In this page the counts are written "<n> numeric PID entries" / "<n> entries";
# in composed-deployment.md §3 they are written 'entry count **<n>**'.
_SNAPSHOT = {
    "bwrap": ("**5**", r"entry count \*\*5\*\*"),
    "unshare --user": ("**1084**", r"entry count \*\*1084\*\*"),
    "container": ("**4**", r"entry count \*\*4\*\*"),
}


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
    row_re = re.compile(
        r"^\|\s*\*\*(?:PID namespace|Identity / env scrub|Private `/proc`|"
        r"Filesystem isolation|seccomp|egress)\*\*",
        re.MULTILINE,
    )
    found = row_re.findall(doc)
    assert len(found) == 6, f"matrix must have exactly six layer rows, got {found}"
    for layer in _LAYER_ROWS:
        assert layer in doc, f"missing enforcement-layer row: {layer}"


def test_matrix_carries_the_four_launch_shape_columns() -> None:
    doc = _doc_text()
    header = re.search(r"^\| Enforcement layer \|.*$", doc, re.MULTILINE)
    assert header is not None, "matrix header row missing"
    for column in _COLUMNS:
        assert column in header.group(0), f"launch-shape column missing: {column!r}"


def test_matrix_pins_key_strings() -> None:
    doc = _doc_text()
    for pinned in _PINNED_STRINGS:
        assert pinned in doc, f"pinned string missing from the matrix: {pinned!r}"


def test_matrix_pins_the_measured_numbers() -> None:
    doc = _doc_text()
    # The 2026-10-03 re-measurement: host view 1175 vs host 1173 under unshare --user.
    assert "**1175**" in doc and "1173" in doc, (
        "the 2026-10-03 host-view counts (1175 vs 1173) are missing"
    )
    # The 2026-10-01 snapshot counts, with their row identities.
    assert "**5**" in doc, "bwrap /proc entry count 5 (2026-10-01 snapshot)"
    assert "**1084**" in doc, "unshare --user host /proc count 1084 (2026-10-01)"
    assert "**4**" in doc, "container /proc entry count 4"
    # Both procfs owners must be named (bwrap's fresh procfs vs the host view).
    assert "/proc/1 = bwrap" in doc and "/proc/1 = systemd" in doc


def test_snapshot_numbers_agree_with_the_shared_matrix() -> None:
    """The 2026-10-01 snapshot (bwrap 5 / 1084 / 4) must appear in BOTH pages.

    This is the DOC-8 numbers cross-check: the capability matrix reuses the
    shared per-layer matrix's numbers (docs/composed-deployment.md §3), so a
    change to one copy without the other must fail here.
    """
    ours = _doc_text()
    theirs = COMPOSED_DOC.read_text(encoding="utf-8")
    for shape, (ours_form, theirs_re) in _SNAPSHOT.items():
        assert ours_form in ours, (
            f"{shape}: count {ours_form} missing from the matrix page"
        )
        assert re.search(theirs_re, theirs), (
            f"{shape}: composed-deployment.md lost its pinned count ({theirs_re})"
        )
    # The matrix page must state its relationship to the shared matrix.
    assert "docs/composed-deployment.md" in ours, (
        "the matrix page must link the shared per-layer matrix"
    )


def test_every_cell_state_vocabulary_present() -> None:
    """The enforced/degraded/unavailable vocabulary and the honest unknown."""
    doc = _doc_text()
    for state in ("**enforced**", "**degraded", "**unavailable**"):
        assert state in doc, f"state vocabulary missing from the matrix: {state!r}"
    assert _UNKNOWN_CELL in doc, (
        "unmeasured cells must say 'unknown (not measured on this host)'"
    )
    for marketing in ("seamless", "bulletproof", "military-grade", "enterprise-grade"):
        assert marketing not in doc.lower(), (
            f"marketing language in the matrix: {marketing!r}"
        )


def test_ubuntu_apparmor_case_with_remediation() -> None:
    doc = _doc_text()
    assert _APPARMOR_CLAIM in doc, "the Ubuntu AppArmor default must be stated"
    assert _REMEDIATION_SYSCTL in doc, "remediation must name the sysctl"
    # The worked-example host facts.
    assert "Ubuntu 26.04.1 LTS" in doc
    assert "7.0.0-31" in doc


def test_worked_example_quotes_real_probe_output() -> None:
    """The page must quote the probes' real verdicts for this host."""
    doc = _doc_text()
    assert re.search(r"^FULL$", doc, re.MULTILINE), "pidns probe verdict FULL"
    assert "DEGRADED: mapped launch failed" in doc, "fs probe verdict DEGRADED"
    assert "setgroups failed: Operation not permitted" in doc, (
        "the diagnosed cause must be quoted"
    )


def test_every_command_is_copy_pasteable() -> None:
    """DOC-8 requirement: no placeholder inside a fenced console/bash block.

    The worked-example prose uses '…' to stand for a payload and says so in
    the sentence introducing the table; fenced blocks must not carry it.
    """
    doc = _doc_text()
    fence_re = re.compile(r"```(?:bash|console|sh|text)?\n(.*?)```", re.DOTALL)
    for block in fence_re.findall(doc):
        assert "…" not in block, (
            f"placeholder ellipsis inside a fenced block: {block!r}"
        )
        assert "<" not in block.replace("kill-child=SIGKILL", ""), (
            f"angle-bracket placeholder inside a fenced block: {block!r}"
        )


def test_readme_links_the_capability_matrix() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "docs/capability-matrix.md" in readme, "README must link the matrix page"
    assert "### What containment do I actually get on MY host?" in readme, (
        "README must carry the host-capability section"
    )
    # The README section must name both probes so the reader can run them.
    for command in _PROBE_COMMANDS:
        assert command in readme, (
            f"README host-capability section lost a probe: {command!r}"
        )
