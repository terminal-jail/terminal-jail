"""TJ-DF-037 — regression tests for the kernel-matrix teardown harness.

scripts/kernel-matrix-teardown.py is the committed runner/record format for
the orphan-teardown kernel matrix (docs/backend-parity.md). These tests pin
its DURABLE contracts, host-independent where possible:

- parsing/validation: a row missing or carrying malformed kernel / backend /
  verdict / survival / exit fields is REJECTED, never repaired or defaulted;
- an UNAVAILABLE (or UNMEASURED) cell can never be classified PASS: the
  validator refuses a no-data row that claims observed numbers, and the
  matrix summary refuses to count such a cell towards a green matrix;
- both backend rows are required: a kernel with only one backend's row is an
  incomplete kernel and can never make the matrix green;
- the matrix needs >= 3 kernels: one host (or two) is never green — the
  non-vacuity guard against "single-host run == matrix proof";
- the live current-host harness (subprocess) emits the required fields for
  both backends and never reports matrix green from its single host;
- the --selftest mode is itself non-vacuous (exit 0, PASS banner).

None of these tests require a second kernel, a remote host, or a network.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
HARNESS = PROJECT_ROOT / "scripts" / "kernel-matrix-teardown.py"
VERDICTS = ("PASS", "FAIL", "UNMEASURED", "UNAVAILABLE")
BACKENDS = ("bwrap", "unshare")
REQUIRED_FIELDS = (
    "kernel",
    "backend",
    "verdict",
    "survival_seconds",
    "exit_code",
    "captured",
    "evidence",
)


def _load_harness():
    spec = importlib.util.spec_from_file_location("kernel_matrix_teardown", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    return _load_harness()


def _valid_row(**overrides):
    row = {
        "kernel": "6.12.107",
        "backend": "unshare",
        "verdict": "FAIL",
        "survival_seconds": 15.0,
        "exit_code": -9,
        "captured": "2026-09-25T10:00:00+0000",
        "evidence": "ORPHAN: payload 1234 survived the wrapper's SIGKILL",
    }
    row.update(overrides)
    return row


# ── validation: valid rows ──────────────────────────────────────────────────


def test_valid_live_rows_accepted_and_canonicalized(harness) -> None:
    for verdict, survival in (("PASS", 0.021), ("FAIL", 15.0)):
        row, reason = harness.validate_row(
            _valid_row(verdict=verdict, survival_seconds=survival, exit_code=0)
        )
        assert row is not None, reason
        assert row["survival_seconds"] == survival
        assert isinstance(row["survival_seconds"], float)
        assert row["exit_code"] == 0


def test_valid_no_data_rows_accepted(harness) -> None:
    for verdict in ("UNMEASURED", "UNAVAILABLE"):
        row, reason = harness.validate_row(
            _valid_row(verdict=verdict, survival_seconds=None, exit_code=None)
        )
        assert row is not None, reason
        assert row["survival_seconds"] is None and row["exit_code"] is None


# ── validation: malformed / missing fields are rejected ────────────────────


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_field_rejected(harness, field) -> None:
    row = _valid_row()
    del row[field]
    canonical, reason = harness.validate_row(row)
    assert canonical is None
    assert field in reason


@pytest.mark.parametrize(
    "overrides",
    [
        {"kernel": ""},
        {"kernel": "   "},
        {"captured": ""},
        {"evidence": ""},
        {"evidence": "   "},
        {"backend": "bubblewrap"},
        {"backend": ""},
        {"backend": 123},
        {"verdict": "GREEN"},
        {"verdict": "pass"},  # vocabulary is case-sensitive
        {"verdict": ""},
    ],
)
def test_malformed_identity_fields_rejected(harness, overrides) -> None:
    canonical, reason = harness.validate_row(_valid_row(**overrides))
    assert canonical is None, overrides
    assert reason


@pytest.mark.parametrize(
    "overrides",
    [
        {"verdict": "PASS", "survival_seconds": None},
        {"verdict": "PASS", "survival_seconds": "0.021"},  # string, not number
        {"verdict": "PASS", "survival_seconds": -0.5},  # negative survival
        {"verdict": "PASS", "survival_seconds": True},  # bool is not a number
        {"verdict": "PASS", "exit_code": None},
        {"verdict": "PASS", "exit_code": "0"},  # string, not int
        {"verdict": "PASS", "exit_code": 1.5},  # float, not int
        {"verdict": "FAIL", "survival_seconds": None},
        {"verdict": "FAIL", "exit_code": None},
    ],
)
def test_live_verdict_without_observed_numbers_rejected(harness, overrides) -> None:
    """A claimed PASS/FAIL without observed survival/exit numbers is malformed
    — evidence-less verdicts can never enter the matrix."""
    canonical, reason = harness.validate_row(_valid_row(**overrides))
    assert canonical is None, overrides
    assert reason


@pytest.mark.parametrize(
    "overrides",
    [
        {"verdict": "UNAVAILABLE", "survival_seconds": 0.5, "exit_code": None},
        {"verdict": "UNAVAILABLE", "survival_seconds": None, "exit_code": 2},
        {"verdict": "UNMEASURED", "survival_seconds": 0.0, "exit_code": 0},
    ],
)
def test_no_data_verdict_claiming_numbers_rejected(harness, overrides) -> None:
    canonical, _reason = harness.validate_row(_valid_row(**overrides))
    assert canonical is None, overrides


@pytest.mark.parametrize("row", [None, [], "PASS", 42])
def test_non_object_row_rejected(harness, row) -> None:
    canonical, reason = harness.validate_row(row)
    assert canonical is None
    assert reason


# ── an UNAVAILABLE cell can never be classified PASS ────────────────────────


def test_unavailable_cannot_become_pass_via_validator(harness) -> None:
    """The only route from UNAVAILABLE to PASS would be rewriting the verdict
    while keeping numbers; the validator refuses any no-data row that carries
    observed numbers, and refuses unknown verdicts entirely."""
    for verdict in ("UNAVAILABLE", "UNMEASURED"):
        with_numbers = _valid_row(verdict=verdict, survival_seconds=0.01, exit_code=0)
        canonical, _ = harness.validate_row(with_numbers)
        assert canonical is None
        # and a re-labelled cell is not a valid row of either vocabulary
        canonical, _ = harness.validate_row(
            _valid_row(verdict="UNAVAILABLE", survival_seconds=0.01, exit_code=0)
        )
        assert canonical is None


def test_unavailable_cells_never_make_a_kernel_complete(harness) -> None:
    rows = [
        _valid_row(
            kernel="6.12.107",
            backend="bwrap",
            verdict="UNAVAILABLE",
            survival_seconds=None,
            exit_code=None,
        ),
        _valid_row(
            kernel="6.12.107",
            backend="unshare",
            verdict="PASS",
            survival_seconds=0.02,
            exit_code=0,
        ),
        # a second complete PASS kernel to prove the UNAVAILABLE cell is what
        # blocks green (mutation control for the summary)
        _valid_row(
            kernel="7.0.0-31-generic",
            backend="bwrap",
            verdict="PASS",
            survival_seconds=0.02,
            exit_code=0,
        ),
        _valid_row(
            kernel="7.0.0-31-generic",
            backend="unshare",
            verdict="PASS",
            survival_seconds=0.02,
            exit_code=0,
        ),
    ]
    summary = harness.matrix_summary([harness.validate_row(r)[0] for r in rows])
    assert "6.12.107" not in summary["kernels_with_complete_measured_pair"]
    assert summary["matrix_green"] is False
    assert any("6.12.107" in item for item in summary["incomplete_kernels"])


# ── both backend rows are required ──────────────────────────────────────────


def test_kernel_with_one_backend_is_incomplete(harness) -> None:
    rows = [
        _valid_row(
            kernel="6.12.107",
            backend="unshare",
            verdict="PASS",
            survival_seconds=0.02,
            exit_code=0,
        ),
    ]
    summary = harness.matrix_summary([harness.validate_row(r)[0] for r in rows])
    assert summary["kernels_with_complete_measured_pair"] == []
    assert summary["matrix_green"] is False
    assert summary["incomplete_kernels"], summary


def test_matrix_green_requires_three_kernels(harness) -> None:
    def pair(kernel):
        return [
            _valid_row(
                kernel=kernel,
                backend="bwrap",
                verdict="PASS",
                survival_seconds=0.02,
                exit_code=0,
            ),
            _valid_row(
                kernel=kernel,
                backend="unshare",
                verdict="PASS",
                survival_seconds=0.02,
                exit_code=0,
            ),
        ]

    two_kernels = pair("6.12.107") + pair("6.1.0")
    summary = harness.matrix_summary([harness.validate_row(r)[0] for r in two_kernels])
    assert summary["matrix_green"] is False, (
        "two kernels must never read as a green matrix"
    )
    summary = harness.matrix_summary(
        [harness.validate_row(r)[0] for r in two_kernels + pair("7.0.0-31-generic")]
    )
    assert summary["matrix_green"] is True
    # matrix_summary sorts kernel names
    assert summary["kernels_with_complete_measured_pair"] == sorted(
        ["6.12.107", "6.1.0", "7.0.0-31-generic"]
    )


def test_single_fail_cell_blocks_green(harness) -> None:
    def rows_for(kernel, unshare_verdict):
        return [
            _valid_row(
                kernel=kernel,
                backend="bwrap",
                verdict="PASS",
                survival_seconds=0.02,
                exit_code=0,
            ),
            _valid_row(
                kernel=kernel,
                backend="unshare",
                verdict=unshare_verdict,
                survival_seconds=0.02 if unshare_verdict == "PASS" else 15.0,
                exit_code=0 if unshare_verdict == "PASS" else -9,
            ),
        ]

    rows = (
        rows_for("6.12.107", "FAIL")
        + rows_for("6.1.0", "PASS")
        + rows_for("7.0.0-31-generic", "PASS")
    )
    summary = harness.matrix_summary([harness.validate_row(r)[0] for r in rows])
    assert summary["matrix_green"] is False
    assert {"kernel": "6.12.107", "backend": "unshare"} in summary["failures"]


# ── the import path ─────────────────────────────────────────────────────────


def test_load_import_splits_valid_rows_from_rejections(harness, tmp_path) -> None:
    good = _valid_row()
    bad = _valid_row(kernel="")
    payload = {"rows": [good, bad, {"kernel": "9.9.9"}]}  # last: missing fields
    path = tmp_path / "cell-external.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    rows, rejections = harness.load_import(path)
    assert len(rows) == 1 and rows[0]["kernel"] == "6.12.107"
    assert len(rejections) == 2
    assert any("rows[1]" in r for r in rejections)
    assert any("rows[2]" in r for r in rejections)


def test_load_import_rejects_unreadable_and_empty(harness, tmp_path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    rows, rejections = harness.load_import(broken)
    assert rows == [] and len(rejections) == 1

    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"rows": []}), encoding="utf-8")
    rows, rejections = harness.load_import(empty)
    assert rows == [] and rejections

    wrongshape = tmp_path / "shape.json"
    wrongshape.write_text(json.dumps([_valid_row()]), encoding="utf-8")
    rows, rejections = harness.load_import(wrongshape)
    assert rows == [] and rejections


# ── the live current-host harness (subprocess) ──────────────────────────────


def _run_harness(*args: str, timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HARNESS), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


@pytest.mark.integration
def test_live_harness_json_rows_have_required_fields() -> None:
    result = _run_harness("--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    rows = payload["rows"]
    assert len(rows) == 2, f"expected one row per backend, got {rows}"
    backends = sorted(row["backend"] for row in rows)
    assert backends == sorted(BACKENDS)
    for row in rows:
        for field in REQUIRED_FIELDS:
            assert field in row, row
        assert row["verdict"] in VERDICTS, row
        assert isinstance(row["kernel"], str) and row["kernel"], row
        assert isinstance(row["captured"], str) and row["captured"], row
        assert isinstance(row["evidence"], str) and row["evidence"], row
        if row["verdict"] in ("PASS", "FAIL"):
            assert isinstance(row["survival_seconds"], (int, float))
            assert isinstance(row["exit_code"], int)
        else:
            # UNMEASURED/UNAVAILABLE: no observed numbers, and the raw
            # evidence names the host/backend condition
            assert row["survival_seconds"] is None
            assert row["exit_code"] is None
    summary = payload["summary"]
    assert summary["matrix_green"] is False, (
        "a single-host run must never report the matrix green"
    )
    assert summary["kernels_with_complete_measured_pair"] in (
        [],
        [payload["this_host_kernel"]],
    )
    assert payload["import_rejections"] == []


@pytest.mark.integration
def test_live_harness_imports_external_rows_and_reports_matrix_honestly(
    tmp_path,
) -> None:
    """Two synthetic foreign-kernel PASS cells (recorded elsewhere) merge in
    WITHOUT executing anything for them; the matrix stays not-green at two
    complete kernels — proving the >=3-kernel rule on the real output path."""
    foreign = {
        "rows": [
            {
                "kernel": "6.6.87",
                "backend": "bwrap",
                "verdict": "PASS",
                "survival_seconds": 0.02,
                "exit_code": 0,
                "captured": "2026-09-25T10:00:00+0000",
                "evidence": "captured on the 6.6.87 host; raw output attached",
            },
            {
                "kernel": "6.6.87",
                "backend": "unshare",
                "verdict": "PASS",
                "survival_seconds": 0.02,
                "exit_code": 0,
                "captured": "2026-09-25T10:00:00+0000",
                "evidence": "captured on the 6.6.87 host; raw output attached",
            },
        ]
    }
    path = tmp_path / "cell-6.6.87.json"
    path.write_text(json.dumps(foreign), encoding="utf-8")
    result = _run_harness("--json", "--import", str(path))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    kernels = {row["kernel"] for row in payload["rows"]}
    assert "6.6.87" in kernels, "imported cell must appear verbatim"
    assert payload["this_host_kernel"] in kernels
    assert payload["import_rejections"] == []
    assert payload["summary"]["matrix_green"] is False, (
        "two complete kernels (one of them synthetic-imported) must not read "
        "as a green matrix"
    )
    complete = payload["summary"]["kernels_with_complete_measured_pair"]
    assert len(complete) == 2 and "6.6.87" in complete


def test_selftest_mode_is_non_vacuous() -> None:
    result = _run_harness("--selftest")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SELFTEST PASS" in result.stdout


@pytest.mark.integration
def test_harness_human_mode_names_the_host_condition() -> None:
    """Human mode prints the kernel, per-backend rows, and an explicit
    not-green summary; it never prints MATRIX GREEN for this single host."""
    result = _run_harness()
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "kernel-matrix orphan teardown" in out
    assert "MATRIX NOT GREEN" in out
    assert "MATRIX GREEN" not in out.replace("MATRIX NOT GREEN", "")
    for backend in BACKENDS:
        assert backend in out


# ── TJ-DF-043 gate: the classifier arms (offline, non-vacuous) ──────────────


def test_gate_pass_on_current_host_pass_cell(harness, monkeypatch) -> None:
    this = harness.host_kernel()
    verdict, reason = harness.gate_verdict(
        [
            harness.validate_row(
                _valid_row(
                    kernel=this,
                    backend="unshare",
                    verdict="PASS",
                    survival_seconds=0.02,
                    exit_code=-9,
                )
            )[0]
        ]
    )
    assert verdict == "PASS", reason
    assert "teardown held" in reason


def test_gate_fail_on_current_host_fail_cell(harness, monkeypatch) -> None:
    this = harness.host_kernel()
    verdict, reason = harness.gate_verdict(
        [
            harness.validate_row(
                _valid_row(
                    kernel=this,
                    backend="unshare",
                    verdict="FAIL",
                    survival_seconds=15.0,
                    exit_code=-9,
                )
            )[0]
        ]
    )
    assert verdict == "FAIL"
    assert "orphan observed" in reason
    assert "TJ-DF-043" in reason


def test_gate_ignores_foreign_kernel_rows(harness) -> None:
    """A FAIL cell from ANOTHER kernel must never fail THIS host's gate
    (and a foreign PASS must never pass it either — no live row here)."""
    verdict, reason = harness.gate_verdict(
        [
            harness.validate_row(
                _valid_row(
                    kernel="0.0.1-not-this-host",
                    verdict="FAIL",
                )
            )[0]
        ]
    )
    assert verdict == "SKIP", reason
    assert "fail" in reason.lower() or "no live cell" in reason


def test_gate_skip_on_unavailable_cell(harness) -> None:
    """UNAVAILABLE carries no numbers by schema: an unlaunchable wrapper
    produces no payload and no orphan — SKIP, never FAIL, never PASS."""
    this = harness.host_kernel()
    verdict, reason = harness.gate_verdict(
        [
            harness.validate_row(
                _valid_row(
                    kernel=this,
                    backend="unshare",
                    verdict="UNAVAILABLE",
                    survival_seconds=None,
                    exit_code=None,
                )
            )[0]
        ]
    )
    assert verdict == "SKIP", reason


def test_gate_fail_on_partial_pass_with_fail(harness) -> None:
    """A FAIL cell next to a PASS cell is still FAIL (any orphan counts)."""
    this = harness.host_kernel()
    rows = [
        harness.validate_row(
            _valid_row(
                kernel=this,
                backend="unshare",
                verdict="FAIL",
                survival_seconds=15.0,
                exit_code=-9,
            )
        )[0],
        harness.validate_row(
            _valid_row(
                kernel=this,
                backend="bwrap",
                verdict="PASS",
                survival_seconds=0.02,
                exit_code=-9,
            )
        )[0],
    ]
    verdict, reason = harness.gate_verdict(rows)
    assert verdict == "FAIL"
    assert "unshare" in reason


def test_gate_mutation_control_reason_tracks_the_cell(harness) -> None:
    """Non-vacuity: flip the cell's verdict and the gate's verdict follows."""
    this = harness.host_kernel()
    pass_row = harness.validate_row(
        _valid_row(
            kernel=this,
            backend="unshare",
            verdict="PASS",
            survival_seconds=0.02,
            exit_code=-9,
        )
    )[0]
    fail_row = dict(pass_row, verdict="FAIL", survival_seconds=15.0)
    assert harness.gate_verdict([pass_row])[0] == "PASS"
    assert harness.gate_verdict([fail_row])[0] == "FAIL"
