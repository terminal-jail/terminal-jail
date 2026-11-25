"""TJ-DF-077: a pinned loader must not mask the payload interpreter."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

WRAPPER = Path(__file__).resolve().parent.parent / "standalone" / "terminal-jail"


@pytest.mark.parametrize(
    ("pin", "covered", "expected"),
    [("/usr/bin/python3", False, 2), ("", False, 2), ("", True, 0)],
)
def test_payload_interpreter_preflight(tmp_path, pin, covered, expected):
    # Execute the actual shell preflight with a deterministic tier probe. The
    # PATH interpreter is a distinct executable from the pinned loader; the
    # probe simulates whether that interpreter can start within the fs tier.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    interpreter = bin_dir / "python3"
    interpreter.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    interpreter.chmod(0o755)
    source = WRAPPER.read_text(encoding="utf-8")
    helpers = source[
        source.index("_tj_modify_tier_head() {") : source.index(
            "_tj_launch_composed() {"
        )
    ]
    script = (
        helpers
        + """
_tj_modify_tier_head_startable() {
    [ "$1" = /usr/bin/python3 ] || [ "$COVERED" = yes ]
}
CMD_STR="unshare --user bash -c 'python3 /opt/landlock-loader.py -- python3 payload.py'"
MODIFIED_COMMAND=python3
_tj_modify_tier_head_prepare
printf 'PREFLIGHT_PASSED\\n'
"""
    )
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "COVERED": "yes" if covered else "no",
        "TERMINAL_JAIL_PYTHON": pin,
    }
    result = subprocess.run(
        ["/bin/bash", "-c", script],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == expected, result.stderr
    if expected == 2:
        assert "auto-sandbox modify unavailable" in result.stderr
        assert "python3" in result.stderr
        assert str(interpreter) in result.stderr
        assert "command not run" in result.stderr
    else:
        assert "PREFLIGHT_PASSED" in result.stdout
