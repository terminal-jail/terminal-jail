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

REVIEW-TJ-015 — per-verdict structured log on stderr:

  For EVERY verdict the bridge emits — the engine's allow/block/modify and
  both ``[bridge-error]`` envelope paths (enforce and warn) — one compact
  JSON line is written to STDERR, right before the stdout verdict line:

    {"ts": "<ISO-8601 UTC>", "event": "verdict", "action": "block",
     "rule_id": "builtin-curl-pipe-shell", "layer": "yaml",
     "command_sha256": "<first 16 hex chars of sha256(command)>"}

  The raw command text NEVER reaches the log — only its sha256 prefix
  (commands can contain secrets). The error envelopes are logged too, with
  their ``rule_id`` (``[bridge-error]``, or ``null`` in the warn-mode
  fail-open envelope) and the sha256 of the empty string when no command
  was captured, so an operator can count "no rule matched" versus "rule
  matched". The line goes to stderr ONLY: stdout is the verdict protocol
  (the wrapper captures it through a pipeline — anything else on stdout
  corrupts it). Default ON; ``TERMINAL_JAIL_VERDICT_LOG`` set to
  ``0``/``off``/``false`` (any case — the repo-wide falsy spelling,
  mirroring ``TERMINAL_JAIL_LANDLOCK`` in standalone/terminal-jail)
  disables it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
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


_VERDICT_LOG_DISABLED_SPELLINGS = frozenset(
    {"0", "off", "false", "OFF", "FALSE", "Off", "False"}
)


def _verdict_log_enabled() -> bool:
    """TERMINAL_JAIL_VERDICT_LOG gates the per-verdict stderr log line.

    Default ON. The falsy spellings mirror the repo-wide pattern
    (``TERMINAL_JAIL_LANDLOCK`` case handling in standalone/terminal-jail):
    0/off/false in any case disables; anything else (unset included) leaves
    the log on.
    """
    raw = os.environ.get("TERMINAL_JAIL_VERDICT_LOG")
    return raw is None or raw not in _VERDICT_LOG_DISABLED_SPELLINGS


def _log_verdict(
    action: str, rule_id: str | None, layer: str | None, command: str
) -> None:
    """Emit the one-line per-verdict structured log (REVIEW-TJ-015).

    One compact JSON line to STDERR — never stdout, which is the verdict
    protocol the wrapper captures through a pipeline. The command appears
    ONLY as the first 16 hex chars of its sha256: command lines can carry
    secrets (tokens, passwords) and must never reach a log. The ``ts`` is
    ISO-8601 UTC; ``event`` is the constant ``"verdict"``.
    """
    if not _verdict_log_enabled():
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "verdict",
        "action": action,
        "rule_id": rule_id,
        "layer": layer,
        "command_sha256": hashlib.sha256(command.encode()).hexdigest()[:16],
    }
    sys.stderr.write(json.dumps(entry, separators=(",", ":")) + "\n")
    sys.stderr.flush()


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

    _log_verdict(
        result.action,
        result.rule_id,
        getattr(result, "layer", None),
        command,
    )
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
        # REVIEW-TJ-015: warn-mode envelope is logged too — a null rule_id
        # still records the event so an operator can count "no rule matched"
        # (allow with a null rule_id) versus "rule matched".
        _log_verdict(response["action"], response["rule_id"], None, "")
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
        _log_verdict(response["action"], response["rule_id"], None, "")
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
    # REVIEW-TJ-015: the engine-failure envelope is a verdict too — log it.
    _log_verdict(response["action"], response["rule_id"], None, "")
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
