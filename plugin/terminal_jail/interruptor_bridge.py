#!/usr/bin/env python3
"""Interruptor JSON bridge — stdin/stdout protocol for the bash CLI wrapper.

Protocol:
  Read one JSON line from stdin:  {"command": "<shell command>"}
  Write one JSON line to stdout:  {"action": "allow"|"block"|"modify",
                                   "command": "...", "modified": "...",
                                   "rule_id": "...", "reason": "...",
                                   "layer": "engine"|"yaml"|"user"|"pack"|null}

``layer`` (TJ-GAP-085) names the rule source that decided the verdict —
an engine builtin constant, the shipped YAML mirror, an operator rule,
or an installed rule pack — and is ``null`` on the error envelopes
(where no rule decided anything).

The bridge imports the interruptor engine and must work regardless of
whether it is invoked from the plugin/ or standalone/ directory.
It adds the project root (parent of the directory containing this file's
package) to sys.path so that ``from terminal_jail.interruptor import …``
resolves correctly.

REVIEW-TJ-008 — transport-level failure envelopes are mode-aware:

  ch:trace row=REVIEW-TJ-008
           evidence=plugin/test_bridge_fail_closed.py::TestTransportEnvelopeModeAware
           witness=none:bridge-level unit seam (wrapper enforcement pinned by
           the existing [bridge-error] wrapper rule, standalone/terminal-jail)

  In enforce mode (the default) a transport-level failure — stdin read
  failure, empty stdin, invalid JSON, a payload that is not a JSON object,
  a missing/non-string ``command`` key, or the engine not importable — used
  to answer the fail-open ALLOW envelope, so a broken bridge silently
  allowed every command. It now answers the same envelope the engine
  failure path uses: ``action: block`` with ``rule_id: "[bridge-error]"``
  and a reason naming the transport cause. The bridge still exits 0 so the
  wrapper (which captures stdout through a pipeline) receives the verdict
  JSON; the wrapper's existing rule — any ``[bridge-error]`` reason blocks
  in enforce mode (exit 126) and warns-and-runs in warn mode — turns it
  into the enforcement decision (TJ-GAP-070 shape, REVIEW-TJ-008 scope).

  In warn mode the fail-open envelope remains, documented: warn means the
  operator has explicitly accepted unguarded execution, and warn mode must
  never block anything — so the envelope degrades to allow-with-warning
  (``action: allow``, reason ``[bridge-error] … — fail-open: allowing
  command (warn mode)``).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure the plugin/ parent is on sys.path so that ``terminal_jail``
# (the top-level package) is importable regardless of cwd.
_bridge_file = Path(__file__).resolve()
_project_root = _bridge_file.parent.parent.parent  # terminal-jail repo root
_plugin_dir = _project_root / "plugin"
if str(_plugin_dir) not in sys.path:
    sys.path.insert(0, str(_plugin_dir))


def _current_mode() -> str:
    """The interruptor mode the bridge enforces its error envelopes under.

    Resolved from the same environment variable the engine and the wrapper
    read (``TERMINAL_JAIL_INTERRUPTOR_MODE``), with the same default
    (``enforce``), the same invalid-value fallback, and (when the engine is
    importable) the same normalization as ``Config`` — a misspelled value
    must not disable the fail-closed default. ``disabled`` mode is mapped to
    the warn-mode envelope: in disabled mode the wrapper never invokes the
    bridge at all, so an invocation that still arrives has no standing to
    block anything.

    The env value is read BEFORE the ``Config`` import attempt and the
    import failure falls back to a self-contained normalization: this probe
    runs exactly when the transport is already broken (including an engine
    that cannot be imported, e.g. ``sys.modules["terminal_jail.interruptor"]
    = None``), so the probe itself must never raise.
    """
    raw = os.environ.get("TERMINAL_JAIL_INTERRUPTOR_MODE", "") or "enforce"
    valid_modes = ("enforce", "warn", "disabled")  # mirrors Config.VALID_MODES
    try:
        from terminal_jail.interruptor.config import (  # noqa: PLC0415
            Config,
        )

        mode = Config(mode=raw).mode
    except Exception:  # noqa: BLE001 — the probe must never raise
        # Same fallback rule as Config.__init__: anything outside the
        # vocabulary means enforce (fail-closed default).
        mode = raw if raw in valid_modes else "enforce"
    # Disabled mode degrades to the warn envelope: the wrapper never invokes
    # the bridge in disabled mode, so an invocation that still arrives has no
    # standing to block anything.
    return "warn" if mode == "disabled" else mode


def main() -> None:
    """Read command from stdin, evaluate through interruptor, write JSON to stdout."""
    try:
        raw = sys.stdin.readline()
    except (OSError, KeyboardInterrupt):
        _emit_transport_error("unable to read stdin")
        return

    if not raw:
        _emit_transport_error("empty stdin")
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _emit_transport_error("invalid JSON on stdin")
        return

    if not isinstance(payload, dict):
        _emit_transport_error(
            f"payload must be a JSON object, got {type(payload).__name__}"
        )
        return

    if "command" not in payload:
        _emit_transport_error("missing 'command' key")
        return

    command = payload["command"]
    if not isinstance(command, str):
        _emit_transport_error("command field must be a string")
        return

    # Import the engine (lazy — after path setup above).
    try:
        from terminal_jail.interruptor import (
            intercept,  # type: ignore[import-not-found]
        )
    except ImportError:
        _emit_transport_error("interruptor engine not importable")
        return

    try:
        result = intercept(command)
    except Exception as exc:  # noqa: BLE001 — engine failure must fail CLOSED
        # TJ-GAP-070: an exception raised HERE is an engine-evaluation failure,
        # not a transport failure. The only thing that used to reach this
        # branch was a fail-open allow carrying a [bridge-error] reason — and
        # the wrapper never inspected the reason, so enforce mode ran the
        # command with ZERO protection (reproduced with a user rule file
        # carrying `priority: not-a-number`, which explodes inside
        # RuleSet._sort). A security tool that silently stops protecting is
        # worse than none: emit a BLOCKING verdict instead. Since
        # REVIEW-TJ-008 the same is true of the stdin/transport paths below
        # (read failure, empty stdin, invalid JSON, non-dict payload,
        # missing/non-string command, engine ImportError) — see
        # ``_emit_transport_error``.
        _emit_fail_closed(f"{type(exc).__name__}: {exc}")
        return

    response = {
        "action": result.action,
        "command": result.command,
        "modified": result.modified,
        "rule_id": result.rule_id,
        "reason": result.reason,
        "layer": getattr(result, "layer", None),
    }
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _emit_transport_error(reason: str) -> None:
    """Transport-level failure (REVIEW-TJ-008): block in enforce, warn-open otherwise.

    Covers stdin unreadable, empty stdin, invalid JSON, non-dict payload,
    missing/non-string ``command``, and the engine not importable — every
    failure that prevents the request from REACHING the engine.

    In enforce mode (the default) this fails CLOSED (REVIEW-TJ-008): the
    verdict is the same blocking ``[bridge-error]`` envelope the
    engine-evaluation path emits (TJ-GAP-070), with the transport cause in
    the reason. The historical rationale for allowing here — a host shell
    calls this bridge before every command, so blocking would brick the
    shell — is the wrapper's escape hatch, not the bridge's: the wrapper
    surfaces this verdict as its ``interruptor-verdict-unusable``-style
    block box in enforce mode and degrades to a loud unguarded-execution
    warning in warn mode. A broken bridge must never look like a silent
    allow again.

    In warn mode the fail-open envelope REMAINS, by design: warn means the
    operator explicitly accepted unguarded execution, and warn mode never
    blocks — the envelope degrades to allow-with-warning, still naming the
    transport cause in ``reason``.
    """
    mode = _current_mode()
    if mode == "warn":
        response = {
            "action": "allow",
            "command": "",
            "modified": None,
            "rule_id": None,
            "reason": f"[bridge-error] {reason} — fail-open: allowing command (warn mode)",
            "layer": None,
        }
    else:
        response = {
            "action": "block",
            "command": "",
            "modified": None,
            "rule_id": "[bridge-error]",
            "reason": (
                f"[bridge-error] {reason} — fail-closed: blocking command (enforce mode)"
            ),
            "layer": None,
        }
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _emit_fail_closed(detail: str) -> None:
    """Fail-closed: block the command because the engine could not decide.

    Used when ``intercept()`` raises (TJ-GAP-070). The verdict is a normal
    BLOCK — same ``action``/``rule_id`` shape the engine itself emits for a
    matched block rule — so the wrapper's existing block path handles it, and
    the ``rule_id`` sentinel ``[bridge-error]`` plus the reason prefix identify
    it as an engine failure rather than a policy match. The wrapper ALSO checks
    the reason prefix, so this verdict blocks even if the bridge's python is
    old enough to have emitted the fail-open form.
    """
    response = {
        "action": "block",
        "command": "",
        "modified": None,
        "rule_id": "[bridge-error]",
        "reason": (
            f"[bridge-error] {detail} — fail-closed: blocking command (enforce mode)"
        ),
        "layer": None,
    }
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
