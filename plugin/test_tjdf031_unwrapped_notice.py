"""The deploy shim must never exec unwrapped SILENTLY (TJ-DF-031).

``standalone/terminal-jail-sh`` wraps shell invocations with the interruptor
firewall + jail (namespace/seccomp) — but only when it has a command string
(``-c``). The login/interactive form (``-lic`` with no command string, the
command text arriving on stdin) has nothing to evaluate, so the shim execs an
UNWRAPPED /bin/bash: no firewall, no namespace, no seccomp. The behavior
stays (login shells are interactive by design) but it must never be SILENT:
the shim prints a one-line stderr notice before that exec.

This module pins the contract:
- the empty-cmd path prints the ``running unwrapped`` notice on stderr;
- the ``-c`` wrapped path does NOT print it (stderr stays free of the notice
  — the jail's own warnings, e.g. filesystem-isolation degradation, are
  unrelated and may still appear);
- the behavior is documented next to the setpriv-degradation note in
  docs/deploy-to-karahermes.md and in the shim's header comment block.

Behavior probes run the shim directly (subprocess with captured streams).
No PATH stub is needed: the empty-cmd path touches only /bin/bash, and the
``-c`` arm distinguishes HOST degradation (namespace-denial markers) from a
real contract break, mirroring the HOST-DEGRADED-PIDNS idiom of
test_standalone_cli.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHIM = PROJECT_ROOT / "standalone" / "terminal-jail-sh"
DEPLOY_DOC = PROJECT_ROOT / "docs" / "deploy-to-karahermes.md"

# Grep-stable marker mandated by TJ-DF-031 (must never change wording).
NOTICE_MARKER = "running unwrapped"


def _shim_path() -> Path:
    assert SHIM.exists(), f"deploy shim not found: {SHIM}"
    return SHIM


def _run_shim(args: list[str], stdin_text: str) -> subprocess.CompletedProcess[str]:
    """Run the shim with both stdio streams captured."""
    return subprocess.run(
        [str(_shim_path()), *args],
        cwd=str(PROJECT_ROOT),
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _host_denies_namespaces(stderr: str) -> bool:
    """Markers of a host refusing the jail launch (namespace/privilege
    denial) — distinct from a contract break on the wrapped path."""
    lowered = stderr.lower()
    return (
        "permission denied" in lowered
        or "operation not permitted" in lowered
        or "user namespace" in lowered
        or "no filesystem isolation" in lowered
    )


# ── Behavior: the notice ───────────────────────────────────────────────────


def test_empty_command_login_shell_prints_notice() -> None:
    """``-lic`` with no command string prints the unwrapped-exec notice on
    stderr, then still execs the (unwrapped) shell reading stdin."""
    result = _run_shim(["-lic"], stdin_text="echo tj031-empty-cmd-ran; exit\n")
    assert NOTICE_MARKER in result.stderr, (
        "empty-cmd login-shell path must print the unwrapped-exec notice "
        f"on stderr; got: {result.stderr!r}"
    )
    assert "terminal-jail:" in result.stderr, result.stderr
    # Exactly one notice line — not a multi-line screed.
    notice_lines = [
        line for line in result.stderr.splitlines() if NOTICE_MARKER in line
    ]
    assert len(notice_lines) == 1, result.stderr
    # The unwrapped bash still ran and consumed the stdin command.
    assert "tj031-empty-cmd-ran" in result.stdout, result.stdout


def test_wrapped_c_path_does_not_print_notice() -> None:
    """``-c "cmd"`` goes through the jail and never prints the notice."""
    result = _run_shim(["-c", "echo tj031-wrapped-c-ran"], stdin_text="ignored\n")
    assert NOTICE_MARKER not in result.stderr, result.stderr
    if result.returncode != 0 and _host_denies_namespaces(result.stderr):
        pytest.skip(
            "HOST-DEGRADED: host refused the jail launch — wrapped-path "
            "behavior not verifiable here, but the notice-absence assertion "
            "above already held"
        )
    assert "tj031-wrapped-c-ran" in result.stdout, result.stdout


# ── Docs pins: the behavior must be documented, adjacent to setpriv ────────


def test_docs_pin_empty_command_behavior_documented() -> None:
    """deploy-to-karahermes.md documents the empty-cmd behavior right after
    the setpriv-degradation note (Step 2), including the notice text and the
    only-``-c``-is-jailed rule."""
    doc = DEPLOY_DOC.read_text(encoding="utf-8")
    assert "running unwrapped (no firewall, no namespace)" in doc, (
        "deploy doc must quote the exact notice text"
    )
    assert "UNWRAPPED" in doc
    assert "form is jailed" in doc
    setpriv_pos = doc.index("On hosts without `setpriv` it degrades gracefully")
    notice_pos = doc.index("no command string")
    assert setpriv_pos < notice_pos < setpriv_pos + 1000, (
        "empty-cmd note must sit adjacent to (immediately after) the "
        "setpriv-degradation note in Step 2"
    )


def test_shim_header_documents_empty_command_exception() -> None:
    """The shim's own header comment block states the unwrapped-exec
    exception and its task provenance."""
    header = SHIM.read_text(encoding="utf-8")[:1600]
    assert "UNWRAPPED" in header
    assert "no interruptor firewall, no namespace, no seccomp" in header
    assert "TJ-DF-031" in header
