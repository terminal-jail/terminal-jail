#!/usr/bin/env python3
"""Classify whether this host can run bare-mode PID-namespace containment.

The E2E battery uses this probe to label each run FULL or DEGRADED
(TJ-GAP-042): a battery must never report ALL GREEN without having actually
verified the PID-namespace layer.

- FULL: bare mode (./standalone/terminal-jail true) succeeds — the host can
  create the PID namespace, so bare-mode containment tests actually run.
- DEGRADED: bare mode exits 2 with the wrapper's degradation message
  (TJ-GAP-034 fail-closed contract naming --user); the host refuses
  unprivileged PID namespace creation and bare-mode tests must skip.
- UNKNOWN: anything else (missing wrapper, timeouts, unexpected output).
- JAIL-AWARE: the probe detected that IT is itself running under a
  terminal-jail launch (DF-TERMINAL-JAIL-18) — the env markers the wrapper
  exports into a jailed process, or a multi-value NSpid in /proc/self/status
  (the auto-sandbox modify path exports no env markers). A nested bare-mode
  launch cannot work from inside an existing PID namespace, so the probe
  short-circuits to this verdict instead of attempting the launch and
  delivering its failure as a misleading classification. Direct-run
  guidance is printed for the full outer-host classification.

Always exits 0: this is a classifier for the battery, not a gate.

Usage:
    python3 scripts/pidns-capability-probe.py
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CLI = _PROJECT_ROOT / "standalone" / "terminal-jail"

# The fail-closed degradation message (TJ-GAP-034) names the fallback.
_DEGRADATION_MARKERS = ("namespace creation failed", "try --user")

# DF-TERMINAL-JAIL-18: env markers the wrapper exports INTO a jailed process
# (TERMINAL_JAIL_FS_ISOLATION on --user launches, TERMINAL_JAIL_SECCOMP under
# --seccomp). The auto-sandbox (modify) path exports none of them, so env
# alone cannot detect that launch shape — the NSpid signal below covers it.
_JAIL_ENV_MARKERS = ("TERMINAL_JAIL_FS_ISOLATION", "TERMINAL_JAIL_SECCOMP")


def _nspid_values() -> list[str]:
    """The NSpid values from /proc/self/status.

    Exactly one value when this process sits in the init PID namespace (a
    direct, unjailed run); two or more (outer pid + inner pid) when the
    process is inside a PID namespace — the signature of every terminal-jail
    launch shape, including auto-sandbox modify which leaves no env marker.
    Test seam: tests monkeypatch this to simulate both contexts offline.
    """
    try:
        with open("/proc/self/status", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("NSpid:"):
                    return line.split()[1:]
    except OSError:
        pass
    return []


def _inside_terminal_jail() -> bool:
    """True when this probe is itself running under a terminal-jail launch."""
    for marker in _JAIL_ENV_MARKERS:
        if os.environ.get(marker):
            return True
    return len(_nspid_values()) > 1


def _jail_aware_verdict() -> str:
    """Honest classification when the probe runs under its own jail."""
    signals: list[str] = []
    markers = [m for m in _JAIL_ENV_MARKERS if os.environ.get(m)]
    if markers:
        signals.append("jail env markers present: " + ", ".join(markers))
    nspid = _nspid_values()
    if len(nspid) > 1:
        signals.append("multi-value NSpid in /proc/self/status: " + " ".join(nspid))
    detail = "; ".join(signals) if signals else "jail detected"
    return (
        "JAIL-AWARE: this probe is itself running inside a terminal-jail "
        f"launch ({detail}), so its nested "
        f"bare-mode launch ({_CLI.name} true) cannot work here — unshare "
        "cannot create a child namespace from inside an existing PID "
        "namespace, and attempting it only produced a hang whose failure "
        "was delivered as if it were a host classification. The surrounding "
        "launch demonstrably created its own PID namespace: this process is "
        "running inside it. For the full classification of the outer host "
        "run the probe directly, outside the jail: "
        "python3 scripts/pidns-capability-probe.py"
    )


def _classify() -> str:
    # DF-TERMINAL-JAIL-18: when the probe itself is jailed, the nested
    # bare-mode launch below cannot succeed — short-circuit to an honest
    # jail-aware verdict instead of delivering the launch's failure as a
    # host classification. Direct (unjailed) runs never reach this.
    if _inside_terminal_jail():
        return _jail_aware_verdict()
    try:
        result = subprocess.run(
            [str(_CLI), "true"],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        return f"UNKNOWN: {_CLI} not found"
    except subprocess.TimeoutExpired:
        return "UNKNOWN: probe timed out after 15s"

    if result.returncode == 0:
        return "FULL"
    if result.returncode == 2 and any(
        marker in result.stderr for marker in _DEGRADATION_MARKERS
    ):
        return "DEGRADED"
    return f"UNKNOWN: rc={result.returncode}, stderr={result.stderr.strip()!r}"


def main() -> None:
    print(_classify())


if __name__ == "__main__":
    main()
