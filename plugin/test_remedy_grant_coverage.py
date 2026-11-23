"""TJ-REVIEW-077 — the auto-sandbox modify refusal must not recommend a bare
absolute interpreter path.

The old remedy text told the operator to "point TERMINAL_JAIL_PYTHON at an
interpreter the payload can read (e.g. /usr/bin/python3)". On Ubuntu
24.x-class hosts that path may dereference to a HOME-baked uv toolchain the
filesystem tier's grant set does not cover (measured 2026-11-22), so the
advice sent the operator in circles. The remedy now states the actual
criterion — the interpreter must live under a prefix the filesystem tier's
grant set covers — and names the uv dereference hazard, keeping the
``TERMINAL_JAIL_LANDLOCK=0`` escape hatch and the README "Graceful
Degradation" pointer.

Source-level assertion over BOTH carriers of the message (the standalone
wrapper and its byte-identical bundled mirror; byte identity itself is
pinned by ``test_packaging_wheel.py``). Neither carrier may carry the old
advice, and both must carry the grant-coverage condition. README.md and the
grant-derivation comment in ``landlock.py`` are aligned to the same framing
and guarded here too.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.standalone_cli

CARRIERS = (
    PROJECT_ROOT / "standalone" / "terminal-jail",
    PROJECT_ROOT / "plugin" / "terminal_jail" / "_bundled" / "terminal-jail",
)

# The refusal echo whose remedy segment changed (one line in each carrier;
# anchored past "so" so the earlier interruptor-python box banner ("Fix:
# point TERMINAL_JAIL_PYTHON at an executable python") cannot match).
REFUSAL_ANCHOR = "so point TERMINAL_JAIL_PYTHON at"

# Stable substrings the new remedy introduces (AC 3's named condition).
GRANT_COVERAGE_CLAUSE = "under a prefix the filesystem tier's grant set covers"
UV_DEREF_WARNING = "HOME-baked uv toolchain"

# The old advice, in the exact advisory shape the text used to carry.
OLD_ADVICE = "e.g. /usr/bin/python3"


def _refusal_line(carrier: Path) -> str:
    """The single wrapper line carrying the modify-unavailable remedy."""
    for line in carrier.read_text(encoding="utf-8").splitlines():
        if REFUSAL_ANCHOR in line:
            return line
    raise AssertionError(
        f"{carrier}: no refusal remedy line matching {REFUSAL_ANCHOR!r}"
    )


@pytest.mark.parametrize(
    "carrier", CARRIERS, ids=lambda p: str(p.relative_to(PROJECT_ROOT))
)
class TestModifyRefusalRemedy:
    def test_no_bare_absolute_interpreter_advice(self, carrier: Path) -> None:
        """The old "(e.g. /usr/bin/python3)" recommendation is gone, and no
        path-exemplar advice of any kind remains in the remedy line."""
        line = _refusal_line(carrier)
        assert OLD_ADVICE not in line
        assert "e.g. /" not in line

    def test_names_the_grant_coverage_condition(self, carrier: Path) -> None:
        """The remedy states the real criterion: the interpreter must live
        under a prefix the filesystem tier's grant set covers, and warns
        that /usr/bin/python3 may dereference into a HOME-baked uv
        toolchain the grant does not cover (the measured failure)."""
        line = _refusal_line(carrier)
        assert GRANT_COVERAGE_CLAUSE in line
        assert UV_DEREF_WARNING in line

    def test_keeps_the_escape_hatch_and_readme_pointer(self, carrier: Path) -> None:
        """The degraded-mode escape hatch and the README pointer survive."""
        line = _refusal_line(carrier)
        assert "TERMINAL_JAIL_LANDLOCK=0" in line
        assert "Graceful Degradation" in line


def test_readme_does_not_recommend_the_bare_path() -> None:
    """README "Graceful Degradation" aligns with the grant-coverage framing."""
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "TERMINAL_JAIL_PYTHON=/usr/bin/python3" not in readme
    assert GRANT_COVERAGE_CLAUSE in readme
    assert UV_DEREF_WARNING in readme


def test_landlock_comment_frames_grant_coverage() -> None:
    """The grant-derivation comment judges coverage per prefix and names the
    uv dereference hazard instead of pointing at the bare absolute path."""
    source = (
        PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor" / "landlock.py"
    ).read_text(encoding="utf-8")
    assert "(often outside HOME, e.g. /usr/bin/python3)" not in source
    assert "Coverage is judged per prefix" in source
    assert UV_DEREF_WARNING in source
