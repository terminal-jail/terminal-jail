#!/usr/bin/env python3
"""Bridge round-trip benchmark: one-shot vs resident (TJ-GAP-084).

Measures the wall-clock cost of obtaining ONE verdict through each
transport, same payloads, same engine. Bounded and laptop-friendly.

Usage:
    python3 scripts/bench_bridge.py [--n 50] [--json]

Sizes: a small command ("ls -la") and 8 KB / 20 KB argument payloads
(the latter padded with a long comment tail so the JSON envelope is the
variable, not the engine path).

Ceiling (cost guard): one-shot p50 must stay below 200 ms. A silent
regression (e.g. interpreter start bloat, import creep) fails the run.
The resident daemon's own cost is reported but not gated here — the
hard gate is "one-shot must not get slower".
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugin"
_BRIDGE = _PLUGIN_DIR / "terminal_jail" / "interruptor_bridge.py"
_RESIDENT = _PLUGIN_DIR / "terminal_jail" / "interruptor_resident.py"

_ONE_SHOT_P50_CEILING_MS = 200.0


def _payload(command: str) -> bytes:
    return (json.dumps({"command": command}) + "\n").encode()


def _padded(base: str, size_bytes: int) -> str:
    """Pad a command with a trailing comment so the JSON line is ~size_bytes."""
    pad_needed = size_bytes - len(json.dumps({"command": base})) - 1
    if pad_needed <= 0:
        return base
    filler = "#" * pad_needed
    return f"{base} {filler}"


def bench_oneshot(command: str, n: int) -> list[float]:
    """Latency of one full subprocess bridge invocation (interpreter start included)."""
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run(
            [sys.executable, str(_BRIDGE)],
            input=_payload(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=True,
        )
        times.append((time.perf_counter() - t0) * 1000.0)
    return times


def _start_resident(sock_path: Path) -> subprocess.Popen:
    env = dict(os.environ)
    env.pop("TERMINAL_JAIL_INTERRUPTOR_MODE", None)
    proc = subprocess.Popen(
        [sys.executable, str(_RESIDENT), "--serve", "--sock", str(sock_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    deadline = time.time() + 10.0
    while time.time() < deadline:
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.connect(str(sock_path))
            probe.close()
            return proc
        except OSError:
            time.sleep(0.05)
    proc.kill()
    raise RuntimeError("resident daemon never became ready")


def bench_resident(sock_path: Path, command: str, n: int) -> list[float]:
    times = []
    for _ in range(n):
        client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.settimeout(10.0)
        client_sock.connect(str(sock_path))
        t0 = time.perf_counter()
        client_sock.sendall(_payload(command))
        buf = b""
        while b"\n" not in buf:
            chunk = client_sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        times.append((time.perf_counter() - t0) * 1000.0)
        client_sock.close()
        assert buf and b'"action"' in buf
    return times


def _stats(times: list[float]) -> dict:
    ordered = sorted(times)
    n = len(ordered)
    return {
        "n": n,
        "p50_ms": round(ordered[int(n * 0.50) - 1 if n >= 2 else 0], 2),
        "p99_ms": round(ordered[min(n - 1, int(n * 0.99) - 1 if n >= 2 else 0)], 2),
        "mean_ms": round(statistics.fmean(ordered), 2),
        "max_ms": round(ordered[-1], 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--n", type=int, default=50, help="iterations per cell (default 50)"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    n = args.n

    with tempfile.TemporaryDirectory(prefix="tj-bench-") as td:
        sock = Path(td) / "bench.sock"
        daemon = _start_resident(sock)
        try:
            cells = []
            for label, base in (
                ("small (ls -la)", "ls -la"),
                ("8 KB", _padded("ls -la", 8192)),
                ("20 KB", _padded("ls -la", 20480)),
            ):
                one = bench_oneshot(base, n)
                res = bench_resident(sock, base, n)
                cells.append((label, _stats(one), _stats(res)))
        finally:
            daemon.kill()

    if args.json:
        print(
            json.dumps(
                {
                    "cells": [
                        {"payload": lbl, "one_shot": a, "resident": b}
                        for lbl, a, b in cells
                    ]
                }
            )
        )
    else:
        host = os.uname()
        print(
            f"Bridge round-trip benchmark — host: {host.nodename} ({sys.platform}, "
            f"{host.machine}), python {sys.version.split()[0]}, n={n}/cell"
        )
        print(
            "Method: wall-clock per verdict; one-shot = full subprocess (interpreter start included),"
        )
        print(
            "resident = connect+send+recv on AF_UNIX against a warm daemon. Same engine, same payloads."
        )
        print()
        print(
            f"{'payload':<16} {'one-shot p50':>13} {'p99':>10} {'resident p50':>13} {'p99':>10} {'speedup':>8}"
        )
        for label, one, res in cells:
            speedup = one["p50_ms"] / res["p50_ms"] if res["p50_ms"] else 0
            print(
                f"{label:<16} {one['p50_ms']:>10.1f}ms {one['p99_ms']:>8.1f}ms "
                f"{res['p50_ms']:>10.1f}ms {res['p99_ms']:>8.1f}ms {speedup:>7.1f}x"
            )

    # Cost guard: one-shot p50 must not silently degrade.
    worst = max(a["p50_ms"] for _, a, _ in cells)
    if worst >= _ONE_SHOT_P50_CEILING_MS:
        print(
            f"FAIL: one-shot p50 {worst:.1f}ms >= ceiling {_ONE_SHOT_P50_CEILING_MS:.0f}ms "
            f"— silent degradation (TJ-GAP-084 cost guard)",
            file=sys.stderr,
        )
        return 1
    print(
        f"\nCost guard OK: worst one-shot p50 {worst:.1f}ms < {_ONE_SHOT_P50_CEILING_MS:.0f}ms ceiling."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
