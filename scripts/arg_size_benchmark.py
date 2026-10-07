#!/usr/bin/env python3
"""Argument-size latency benchmark for the interruptor bridge/engine path.

TJ-GAP-086. Bounded and laptop-friendly: in-process (no network, no
subprocess spawn per sample), a few seconds wall clock at the defaults.
It measures the REAL verdict path — the same ``intercept()`` engine call
the one-shot bridge (``plugin/terminal_jail/interruptor_bridge.py``) and
the resident daemon both make — at a small, an 8 KB, and a 20 KB
argument, and prints one table.

The base command is deliberately RULE-INERT (``echo …``) and the rule
directories are pinned to an EMPTY temp dir for the measurement (the
same reproducibility mechanism docs/quickstart.md §3a2 uses for its
transcripts): no auto-sandbox MODIFY verdict, no shell-outs, no operator
policy in the loop — the numbers are the builtins-only engine cost, the
same on every host shape. (An unpinned run inherits whatever the
operator's rules.d re-arms; transport shapes — interpreter start,
socket round-trip — are measured separately by scripts/bench_bridge.py.)

Why argument size matters (measured 2026-09-27, fresh clone, n=200/cell):
engine cost grows LINEARLY with argument size — ~2.2 ms p50 for an
ordinary command vs ~21.8 ms at 8 KB and ~51.7 ms at 20 KB. There is no
maximum argument size anywhere in the product: the bridge is documented
as having no length bound (docs/quickstart.md §3a2), so a host evaluating
stall-sized (MB-scale) arguments pays this curve linearly. See README
"Environment variables and limits" for the stated budget.

Usage:
    .venv/bin/python scripts/arg_size_benchmark.py [--n 100] [--json]
    [--ceiling-check]

Exit code is 0 unless ``--ceiling-check`` is passed and a p50 exceeds the
pinned ceiling (20x the measured pins — the same pins
tests/test_arg_size_ceiling.py asserts). The test imports ``measure_cell``
directly instead of running this file, so CI does not need the flag.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Repo-checkout bootstrap: make the plugin/ package importable regardless
# of cwd (same pattern as scripts/bench_bridge.py).
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
_plugin_dir = _project_root / "plugin"
sys.path.insert(0, str(_plugin_dir))

# ── Pinned constants ────────────────────────────────────────────────────────
# MEASURED_ENGINE_P50_MS documents the curve this benchmark re-measures;
# the ceiling test derives its pins from these numbers x a stated headroom
# factor (see tests/test_arg_size_ceiling.py docstring). Update BOTH files
# together after a re-measurement.

BENCH_CELLS: tuple[tuple[str, int], ...] = (
    ("small (echo)", 11),
    ("8 KB", 8192),
    ("20 KB", 20480),
)

MEASURED_ENGINE_P50_MS: dict[str, float] = {
    "small (echo)": 2.2,
    "8 KB": 21.8,
    "20 KB": 51.7,
}

CEILING_TEST_N = 30  # per-cell iterations the ceiling test runs (seconds)

# Floor for the engine path: even a tiny command costs ~2 ms in-process.
_MEASURED_ENGINE_FLOOR_MS = 2.0

# Headroom factor shared with the ceiling test's pins.
CEILING_HEADROOM = 20.0

ENV_RULES_DIR = "TERMINAL_JAIL_INTERRUPTOR_RULES_DIR"
ENV_USER_RULES_DIR = "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR"

_BASE_COMMAND = "echo hello"  # rule-inert: no auto-sandbox, no shell-outs

_pinned_dir: str | None = None


def _empty_rules_dir() -> str:
    """One empty rules dir, shared by every cell, cleaned at process exit."""
    global _pinned_dir
    if _pinned_dir is None:
        _pinned_dir = tempfile.mkdtemp(prefix="tj-arg-bench-rules-")
        atexit.register(shutil.rmtree, _pinned_dir, ignore_errors=True)
    return _pinned_dir


def _padded(base: str, size_bytes: int) -> str:
    """Pad a command with a trailing comment so the string is ~size_bytes.

    The pad is a benign payload (no rule literal present) so every sample
    measures the linear parse/scan cost, never a block-rule short-circuit.
    Constructed in Python — no huge literal ever reaches a shell.
    """
    if size_bytes <= len(base):
        return base
    pad_needed = size_bytes - len(base) - 1
    return f"{base} {'#' * pad_needed}"


def measure_cell(label: str, n: int = 100) -> dict:
    """One benchmark cell: n intercept() evaluations at this cell's size.

    Returns {label, bytes, n, p50_ms, p99_ms, mean_ms}. Raises KeyError on
    an unknown label so a stale pin fails loudly instead of silently
    dropping a cell. The operator's rules.d is OUT of the loop: both rule
    directory env vars are pinned to an empty temp dir for the loop (the
    engine reads them per call) and restored after it, so the measured
    curve is builtins-only and host-independent.
    """
    sizes = dict(BENCH_CELLS)
    command = _padded(_BASE_COMMAND, sizes[label])
    from terminal_jail.interruptor import intercept

    saved = {k: os.environ.get(k) for k in (ENV_RULES_DIR, ENV_USER_RULES_DIR)}
    empty = _empty_rules_dir()
    os.environ[ENV_RULES_DIR] = empty
    os.environ[ENV_USER_RULES_DIR] = empty
    try:
        intercept(command)  # warm-up: rule load + imports out of the samples
        times_ms = []
        for _ in range(n):
            t0 = time.perf_counter()
            intercept(command)
            times_ms.append((time.perf_counter() - t0) * 1000.0)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    ordered = sorted(times_ms)
    count = len(ordered)
    return {
        "label": label,
        "bytes": len(command.encode()),
        "n": count,
        "p50_ms": round(ordered[count // 2], 2),
        "p99_ms": round(ordered[min(count - 1, int(count * 0.99))], 2),
        "mean_ms": round(statistics.fmean(ordered), 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=100, help="iterations per cell")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--ceiling-check",
        action="store_true",
        help="exit 1 if any p50 exceeds the pinned ceiling (20x the measured "
        "pins; same pins tests/test_arg_size_ceiling.py asserts)",
    )
    args = parser.parse_args(argv)

    host = ""
    if not args.json:
        import platform

        host = f"host: {platform.node()} ({sys.platform}), python {sys.version.split()[0]}, "

    results = [measure_cell(label, n=args.n) for label, _size in BENCH_CELLS]

    if args.json:
        print(json.dumps({"cells": results}))
    else:
        print(
            f"Argument-size latency benchmark — {host}n={args.n}/cell, "
            "in-process intercept() (the bridge/engine verdict path, builtins-only: "
            "rule dirs pinned empty for the run); wall clock per verdict, "
            "subprocess-transport overhead not included "
            "(scripts/bench_bridge.py measures that shape)."
        )
        print()
        print(f"{'payload':<16} {'bytes':>8} {'p50':>10} {'p99':>10} {'mean':>10}")
        for r in results:
            print(
                f"{r['label']:<16} {r['bytes']:>8} {r['p50_ms']:>9.1f}ms "
                f"{r['p99_ms']:>9.1f}ms {r['mean_ms']:>9.1f}ms"
            )
        print()
        print(
            "Cost is linear in argument size; inputs above the enforced "
            "maximum are refused before evaluation (see README, "
            "'Environment variables and limits')."
        )

    if args.ceiling_check:
        failures = []
        for r in results:
            measured = MEASURED_ENGINE_P50_MS.get(r["label"])
            if measured is None:
                failures.append(f"{r['label']}: no pinned measurement")
                continue
            reference = max(measured, _MEASURED_ENGINE_FLOOR_MS)
            if r["p50_ms"] >= reference * CEILING_HEADROOM:
                failures.append(
                    f"{r['label']}: p50 {r['p50_ms']:.1f}ms >= "
                    f"{CEILING_HEADROOM:.0f}x pin ({reference:.1f}ms measured)"
                )
        if failures:
            print("CEILING FAIL: " + "; ".join(failures), file=sys.stderr)
            return 1
        print(
            f"ceiling check OK ({CEILING_HEADROOM:.0f}x pins, "
            "see tests/test_arg_size_ceiling.py)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
