#!/usr/bin/env python3
"""Interruptor resident bridge — AF_UNIX daemon serving the verdict contract.

TJ-GAP-084. The one-shot bridge (``interruptor_bridge.py``) pays a full
Python interpreter start per verdict (~65 ms p50 measured 2026-09-27); a
resident daemon amortizes that to a socket round-trip (single-digit ms).

Protocol (SAME contract as the one-shot bridge):
  Client connects to the AF_UNIX socket, sends ONE JSON line:
      {"command": "<shell command>"}
  and receives ONE JSON line:
      {"action": "allow"|"block"|"modify", "command": "...",
       "modified": "...", "rule_id": "...", "reason": "...",
       "layer": "engine"|"yaml"|"user"|"pack"|null}

Error envelopes are MODE-AWARE exactly like the one-shot bridge
(REVIEW-TJ-008 / TJ-GAP-070): in enforce mode any transport/parse/engine
failure answers ``action: block`` with ``rule_id: "[bridge-error]"``;
in warn mode the fail-open allow-with-warning envelope is preserved.

Socket safety (pre-verified mechanism, corpus TJ-GAP-084):
  A raw ``socket.bind`` on an AF_UNIX path creates the inode as
  ``0o777 & ~umask`` — group/world-writable under common umasks, i.e. an
  unauthenticated verb surface for other local users. The daemon therefore
  ``os.chmod(sock_path, 0o600)`` IMMEDIATELY after bind, BEFORE the accept
  loop, and REFUSES TO SERVE (fail-closed) if the chmod fails.

No TCP listener anywhere: AF_UNIX only. "0 grep hits for listener" must
stay true — the property is pinned, not assumed: see
``plugin/test_resident_bridge.py::TestNoTcpListener``. The transport
choice itself (decision table, measured numbers, and how to run either
transport) lives in README.md §"Choosing a bridge transport: one-shot vs
resident (TJ-GAP-084)".

Client mode (``--sock PATH --client --command "..."`` or command on stdin):
  On transport failure the client does NOT answer with a verdict of its
  own — it exits 3 with a stderr note so the caller can fall back to the
  one-shot bridge. With ``--fallback`` (or env
  TERMINAL_JAIL_BRIDGE_FALLBACK=1) the client instead evaluates through
  the one-shot path in-process, so a resident-transport failure can never
  become an allow in enforce mode either way.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import signal
import socket
import sys
from collections.abc import Callable
from pathlib import Path

# Same sys.path bootstrap as the one-shot bridge (works from plugin/ or standalone/).
_resident_file = Path(__file__).resolve()
_project_root = _resident_file.parent.parent.parent  # terminal-jail repo root
_plugin_dir = _project_root / "plugin"
if str(_plugin_dir) not in sys.path:
    sys.path.insert(0, str(_plugin_dir))

DEFAULT_SOCK_DIR = Path.home() / ".local" / "run" / "terminal-jail"
DEFAULT_SOCK_PATH = DEFAULT_SOCK_DIR / "interruptor.sock"
ENV_SOCK = "TERMINAL_JAIL_BRIDGE_SOCK"

# Exit code used by client mode to signal "resident transport failed —
# fall back to the one-shot bridge". Deliberately distinct from 0 (verdict
# delivered) and 1 (generic error).
_EXIT_FALLBACK = 3

# TJ-GAP-097 shutdown state. The SIGTERM/SIGINT handler sets these BEFORE it
# closes the listening socket, so the accept loop can distinguish an OSError
# caused by our own teardown from a transient accept() error worth retrying.
# The daemon is single-threaded (signal handlers run in the main thread), so
# plain module state needs no locking.
_shutting_down = False
_shutdown_signum = 0


def _sock_path() -> Path:
    raw = os.environ.get(ENV_SOCK, "") or str(DEFAULT_SOCK_PATH)
    return Path(raw)


def _bridge_module():
    """Import the one-shot bridge module under either invocation shape."""
    try:
        from terminal_jail import (  # noqa: PLC0415
            interruptor_bridge as bridge,  # type: ignore[attr-defined]
        )
    except ImportError:
        import interruptor_bridge as bridge  # type: ignore[no-redef]  # noqa: PLC0415
    return bridge


def _mode() -> str:
    """Same mode resolution as the one-shot bridge's ``_current_mode``."""
    return _bridge_module()._current_mode()


def _envelope_transport_error(reason: str) -> dict:
    """Mirror of the one-shot bridge's mode-aware transport-error envelope."""
    if _mode() == "warn":
        return {
            "action": "allow",
            "command": "",
            "modified": None,
            "rule_id": None,
            "reason": f"[bridge-error] {reason} — fail-open: allowing command (warn mode)",
            "layer": None,
        }
    return {
        "action": "block",
        "command": "",
        "modified": None,
        "rule_id": "[bridge-error]",
        "reason": f"[bridge-error] {reason} — fail-closed: blocking command (enforce mode)",
        "layer": None,
    }


def _envelope_engine_error(detail: str) -> dict:
    """Mirror of the one-shot bridge's fail-closed engine-error envelope."""
    return {
        "action": "block",
        "command": "",
        "modified": None,
        "rule_id": "[bridge-error]",
        "reason": f"[bridge-error] {detail} — fail-closed: blocking command (enforce mode)",
        "layer": None,
    }


def evaluate_payload(payload: object) -> dict:
    """Evaluate one parsed request object into a verdict dict.

    Shares the engine and the envelope shapes with the one-shot bridge so
    the two transports stay verdict-parity (test_resident_bridge.py).
    """
    if not isinstance(payload, dict):
        return _envelope_transport_error(
            f"payload must be a JSON object, got {type(payload).__name__}"
        )
    if "command" not in payload:
        return _envelope_transport_error("missing 'command' key")
    command = payload["command"]
    if not isinstance(command, str):
        return _envelope_transport_error("command field must be a string")

    try:
        from terminal_jail.interruptor import (  # noqa: PLC0415
            intercept,  # type: ignore[import-not-found]
        )
    except ImportError:
        return _envelope_transport_error("interruptor engine not importable")

    try:
        result = intercept(command)
    except Exception as exc:  # noqa: BLE001 — engine failure must fail CLOSED
        return _envelope_engine_error(f"{type(exc).__name__}: {exc}")

    return {
        "action": result.action,
        "command": result.command,
        "modified": result.modified,
        "rule_id": result.rule_id,
        "reason": result.reason,
        "layer": getattr(result, "layer", None),
    }


def _reset_shutdown_state() -> None:
    """Clear the TJ-GAP-097 shutdown marker for a fresh ``serve()``."""
    global _shutting_down, _shutdown_signum
    _shutting_down = False
    _shutdown_signum = 0


def _listener_gone(exc: OSError, server: socket.socket) -> bool:
    """True when ``exc`` means the LISTENER is gone, not "retry the accept".

    Three independent witnesses, any one of which is conclusive:
      * the shutdown marker — our own signal handler already closed it;
      * ``EBADF`` — the descriptor the kernel was asked about no longer exists;
      * ``fileno() == -1`` — the socket object itself is closed.
    Anything else (EINTR, ECONNABORTED, ENOMEM, ...) is transient.
    """
    if _shutting_down:
        return True
    if exc.errno == errno.EBADF:
        return True
    try:
        return server.fileno() == -1
    except OSError:
        return True


def _accept_loop(
    server: socket.socket, handle: Callable[[socket.socket], None]
) -> None:
    """Accept one connection at a time; return only when the listener is dead.

    Every iteration MUST make progress. ``accept()`` on a CLOSED listener
    raises ``OSError`` forever, so treating every ``OSError`` as transient is
    an infinite busy loop — that is TJ-GAP-097, where the daemon ignored its
    own SIGTERM and sat at 100% CPU (``State: R``, 7:45 CPU in 7:47 of wall
    time, py-spy parked in ``accept``) while its caller waited out a timeout.

    A dead listener therefore ENDS the loop: with the shutdown marker set the
    exit code is the signal's ``128 + signum`` (the property the signal cells
    assert); without it the daemon can serve nothing, so it exits non-zero
    instead of pretending it shut down cleanly. Genuine transient errors
    still ``continue`` — the retry is narrowed, not deleted.
    """
    while True:
        try:
            conn, _ = server.accept()
        except OSError as exc:
            if not _listener_gone(exc, server):
                continue
            if _shutting_down:
                raise SystemExit(128 + _shutdown_signum) from None
            print(
                "[resident-bridge] listening socket closed under the accept "
                "loop — stopping (cannot serve without a listener)",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
        handle(conn)


def serve(sock_path: Path) -> None:
    """Bind, chmod 0o600 (fail-closed), then serve the accept loop forever."""
    sock_path.parent.mkdir(parents=True, exist_ok=True)

    # Stale-socket handling: if the path exists we probe it. A LIVE socket
    # (connect succeeds) means another daemon owns it — refuse to start.
    # A dead path (connect refused / not a socket) is unlinked and rebound.
    if sock_path.exists():
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(1.0)
        try:
            probe.connect(str(sock_path))
        except OSError:
            probe.close()
            try:
                sock_path.unlink()
            except OSError as exc:
                print(
                    f"[resident-bridge] cannot remove stale socket "
                    f"{sock_path}: {exc} — refusing to start",
                    file=sys.stderr,
                )
                raise SystemExit(1) from None
        else:
            probe.close()
            print(
                f"[resident-bridge] socket {sock_path} is live and owned by "
                f"another process — refusing to start",
                file=sys.stderr,
            )
            raise SystemExit(1)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(sock_path))
    except OSError as exc:
        # QA-TERMINAL-JAIL-22: name the unix(7) sun_path limit (108 bytes
        # including the NUL) so a deep socket path is diagnosable from the
        # startup error alone. Fail-closed either way (exit 1, no serve).
        if exc.errno == errno.ENAMETOOLONG:
            print(
                f"[resident-bridge] bind failed: AF_UNIX path too long: "
                f"{sock_path} ({len(os.fsencode(str(sock_path)))} bytes; "
                f"sun_path limit is 108 bytes) — use a shorter socket path",
                file=sys.stderr,
            )
        else:
            print(f"[resident-bridge] bind failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    # FAIL-CLOSED permission fix (pre-verified mechanism): a bare bind
    # creates the inode as 0o777 & ~umask; tighten to owner-only BEFORE
    # accepting anything. If this fails, unlink and refuse to serve.
    try:
        os.chmod(sock_path, 0o600)
    except OSError as exc:
        server.close()
        try:
            sock_path.unlink()
        except OSError:
            pass
        print(
            f"[resident-bridge] chmod 0o600 on {sock_path} failed: {exc} "
            f"— fail-closed: refusing to serve",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    # TJ-REVIEW-073: install signal handlers before exposing the listening
    # socket. The handler performs the same idempotent cleanup as finally so
    # termination is safe even while accept() or a client request is blocked.
    def _cleanup() -> None:
        server.close()
        try:
            sock_path.unlink()
        except OSError:
            pass

    def _clean_exit(signum: int, _frame: object) -> None:
        # TJ-GAP-097: mark BEFORE closing. Once the listener is closed the
        # blocked accept() reports EBADF/EINTR on every retry, so the loop has
        # to read that error as "we are shutting down" — not as transient.
        global _shutting_down, _shutdown_signum
        _shutting_down = True
        _shutdown_signum = signum
        _cleanup()
        raise SystemExit(128 + signum)

    # A previous serve() in the same process must not be able to abort this
    # one through a leftover marker.
    _reset_shutdown_state()
    prev_term = signal.signal(signal.SIGTERM, _clean_exit)
    prev_int = signal.signal(signal.SIGINT, _clean_exit)
    server.listen(16)
    print(f"[resident-bridge] serving on {sock_path} (mode={_mode()})", file=sys.stderr)
    try:
        _accept_loop(server, _serve_connection)
    finally:
        signal.signal(signal.SIGTERM, prev_term)
        signal.signal(signal.SIGINT, prev_int)
        _cleanup()


def _serve_connection(conn: socket.socket) -> None:
    """One request per connection: read a line, answer a line, close."""
    try:
        conn.settimeout(10.0)
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(65536)
            if not chunk:
                break
            buf += chunk
        line = buf.split(b"\n", 1)[0].decode("utf-8", errors="replace")
        if not line.strip():
            response = _envelope_transport_error("empty request line")
        else:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                response = _envelope_transport_error("invalid JSON on request line")
            else:
                response = evaluate_payload(payload)
        data = (json.dumps(response) + "\n").encode("utf-8")
        conn.sendall(data)
    except OSError:
        pass  # client hung up mid-request; nothing to answer
    finally:
        try:
            conn.close()
        except OSError:
            pass


def client(sock_path: Path, command: str | None, fallback: bool) -> int:
    """Send one command, print the verdict line, exit 0.

    Transport failure: print nothing on stdout, note on stderr, exit 3 —
    the caller falls back to the one-shot bridge. With ``fallback=True``
    the one-shot path runs in-process instead, so enforce mode still gets
    a fail-closed verdict from a real engine evaluation.
    """
    try:
        client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.settimeout(10.0)
        client_sock.connect(str(sock_path))
    except OSError as exc:
        print(
            f"[resident-bridge] cannot reach {sock_path}: {exc} "
            f"{'— falling back to one-shot bridge' if fallback else '— caller must fall back to one-shot bridge'}",
            file=sys.stderr,
        )
        if fallback:
            return _one_shot_fallback(command)
        return _EXIT_FALLBACK

    try:
        payload = {
            "command": command
            if command is not None
            else sys.stdin.readline().rstrip("\n")
        }
        client_sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = client_sock.recv(65536)
            if not chunk:
                break
            buf += chunk
    except OSError as exc:
        print(
            f"[resident-bridge] transport error talking to {sock_path}: {exc} "
            f"{'— falling back to one-shot bridge' if fallback else '— caller must fall back to one-shot bridge'}",
            file=sys.stderr,
        )
        if fallback:
            return _one_shot_fallback(command)
        return _EXIT_FALLBACK
    finally:
        try:
            client_sock.close()
        except OSError:
            pass

    if not buf:
        print(
            "[resident-bridge] empty response from daemon — caller must fall back "
            "to one-shot bridge",
            file=sys.stderr,
        )
        if fallback:
            return _one_shot_fallback(command)
        return _EXIT_FALLBACK

    line = buf.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    try:
        verdict = json.loads(line)
        if not isinstance(verdict, dict) or "action" not in verdict:
            raise ValueError("response is not a verdict object")
    except ValueError:
        print(
            "[resident-bridge] malformed response from daemon — caller must fall "
            "back to one-shot bridge",
            file=sys.stderr,
        )
        if fallback:
            return _one_shot_fallback(command)
        return _EXIT_FALLBACK

    sys.stdout.write(json.dumps(verdict) + "\n")
    sys.stdout.flush()
    return 0


def _one_shot_fallback(command: str | None) -> int:
    """Run the one-shot bridge in-process (REVIEW-TJ-008 envelopes intact)."""
    import io  # noqa: PLC0415
    from contextlib import redirect_stderr, redirect_stdout  # noqa: PLC0415

    from interruptor_resident import _bridge_module  # noqa: PLC0415

    bridge_main = _bridge_module().main

    if command is None:
        bridge_main()  # reads real stdin
        return 0
    out, err = io.StringIO(), io.StringIO()
    fake_stdin = io.StringIO(json.dumps({"command": command}) + "\n")
    real_stdin = sys.stdin
    sys.stdin = fake_stdin  # type: ignore[assignment]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            bridge_main()
    finally:
        sys.stdin = real_stdin  # type: ignore[assignment]
    sys.stdout.write(out.getvalue())
    sys.stdout.flush()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true", help="run as a resident daemon")
    parser.add_argument(
        "--client", action="store_true", help="send one command and print the verdict"
    )
    parser.add_argument(
        "--sock",
        type=str,
        default=None,
        help=f"socket path (default: ${ENV_SOCK} or {DEFAULT_SOCK_PATH})",
    )
    parser.add_argument(
        "--command", type=str, default=None, help="command to evaluate (client mode)"
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="client mode: on transport failure evaluate through the one-shot bridge in-process",
    )
    args = parser.parse_args()

    sock_path = Path(args.sock) if args.sock else _sock_path()
    if args.serve:
        serve(sock_path)
        return
    if args.client or args.command is not None:
        raise SystemExit(client(sock_path, args.command, args.fallback))
    # Default when invoked with neither flag and stdin is a TTY: show usage.
    parser.print_help()
    raise SystemExit(2)


if __name__ == "__main__":
    main()
