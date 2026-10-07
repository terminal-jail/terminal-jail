"""TJ-GAP-086 — pinned argument-size latency ceiling.

Runs the committed benchmark's measurement function
(``scripts/arg_size_benchmark.py``) in-process against the real
bridge/engine verdict path and fails if any pinned p50 ceiling is
exceeded.

The ceilings are a GENEROUS MULTIPLE of the measured curve so CI/VM
jitter does not flake. Measured on the reference host
(karaHermes-mde-7840hs, 2026-10-07, engine p50 by payload size, from
scripts/arg_size_benchmark.py's pinned table):

    small  ~2.2 ms   8 KB ~21.8 ms   20 KB ~51.7 ms

Headroom factor: **20x** per cell. That is deliberate — this test pins
"suddenly 20x slower" (a lost prefilter, a quadratic path, a stall-sized
input reaching the engine), not "10% slower", which belongs to trend
dashboards, not a unit gate. The one-shot/subprocess transport cost
(interpreter start, ~65-190 ms) is deliberately NOT pinned here: that
shape is scripts/bench_bridge.py's 200 ms cost guard (TJ-GAP-084), and a
unit test that pins process-start latency flakes on loaded CI runners.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BENCH = _PROJECT_ROOT / "scripts" / "arg_size_benchmark.py"

_spec = importlib.util.spec_from_file_location("tj_arg_size_benchmark", _BENCH)
assert _spec is not None and _spec.loader is not None
bench = importlib.util.module_from_spec(_spec)
sys.modules["tj_arg_size_benchmark"] = bench
_spec.loader.exec_module(bench)

HEADROOM_FACTOR = 20.0  # see module docstring — jitter-proof by design

PINNED_P50_CEILINGS_MS = {
    label: round(max(measured_ms, bench._MEASURED_ENGINE_FLOOR_MS) * HEADROOM_FACTOR, 1)
    for label, measured_ms in bench.MEASURED_ENGINE_P50_MS.items()
}


def test_pin_matches_benchmark_cells() -> None:
    """The pinned table covers exactly the benchmark's cells — never stale."""
    assert set(PINNED_P50_CEILINGS_MS) == {label for label, _ in bench.BENCH_CELLS}
    # and the pins are derived from measured numbers, not vibes
    assert set(bench.MEASURED_ENGINE_P50_MS) == {
        label for label, _ in bench.BENCH_CELLS
    }


@pytest.mark.parametrize(
    "label", [label for label, _size in bench.BENCH_CELLS], ids=str
)
def test_engine_p50_under_pinned_ceiling(label: str) -> None:
    """p50 at each payload size stays under the pinned generous ceiling.

    Ceiling = 20x the documented measurement (module docstring). A failure
    means the curve moved by an order of magnitude — a real regression
    (a lost prefilter, a quadratic path), not VM jitter.
    """
    result = bench.measure_cell(label, n=bench.CEILING_TEST_N)
    ceiling = PINNED_P50_CEILINGS_MS[label]
    assert result["p50_ms"] < ceiling, (
        f"{label}: engine p50 {result['p50_ms']:.1f}ms >= pinned ceiling "
        f"{ceiling:.1f}ms ({HEADROOM_FACTOR:.0f}x the documented measurement) "
        f"— argument-size latency regression (TJ-GAP-086)"
    )
