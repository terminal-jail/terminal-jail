#!/usr/bin/env python3
"""Interruptor JSON bridge — stdin/stdout protocol for the bash CLI wrapper.

Protocol:
  Read one JSON line from stdin:  {"command": "<shell command>"}
  Write one JSON line to stdout:  {"action": "allow"|"block"|"modify",
                                   "command": "...", "modified": "...",
                                   "rule_id": "...", "reason": "..."}

The bridge imports the interruptor engine and must work regardless of
whether it is invoked from the plugin/ or standalone/ directory.
It adds the project root (parent of the directory containing this file's
package) to sys.path so that ``from terminal_jail.interruptor import …``
resolves correctly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the plugin/ parent is on sys.path so that ``terminal_jail``
# (the top-level package) is importable regardless of cwd.
_bridge_file = Path(__file__).resolve()
_project_root = _bridge_file.parent.parent.parent  # terminal-jail repo root
_plugin_dir = _project_root / "plugin"
if str(_plugin_dir) not in sys.path:
    sys.path.insert(0, str(_plugin_dir))


def main() -> None:
    """Read command from stdin, evaluate through interruptor, write JSON to stdout."""
    try:
        raw = sys.stdin.readline()
    except (OSError, KeyboardInterrupt):
        _emit_fail_open("unable to read stdin")
        return

    if not raw:
        _emit_fail_open("empty stdin")
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _emit_fail_open("invalid JSON on stdin")
        return

    if not isinstance(payload, dict):
        _emit_fail_open(f"payload must be a JSON object, got {type(payload).__name__}")
        return

    if "command" not in payload:
        _emit_fail_open("missing 'command' key")
        return

    command = payload["command"]
    if not isinstance(command, str):
        _emit_fail_open("command field must be a string")
        return

    # Import the engine (lazy — after path setup above).
    try:
        from terminal_jail.interruptor import (
            intercept,  # type: ignore[import-not-found]
        )
    except ImportError:
        _emit_fail_open("interruptor engine not importable")
        return

    try:
        result = intercept(command)
    except Exception:  # noqa: BLE001 — fail-open: allow command to not brick the shell
        _emit_fail_open("interrupt() raised an exception")
        return

    response = {
        "action": result.action,
        "command": result.command,
        "modified": result.modified,
        "rule_id": result.rule_id,
        "reason": result.reason,
    }
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _emit_fail_open(reason: str) -> None:
    """Fail-open: allow the command through so the shell isn't bricked."""
    response = {
        "action": "allow",
        "command": "",
        "modified": None,
        "rule_id": None,
        "reason": f"[bridge-error] {reason} — fail-open: allowing command",
    }
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
