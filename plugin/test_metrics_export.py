"""Tests for scripts/metrics-export.py (AUDIT-07)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METRICS_SCRIPT = PROJECT_ROOT / "scripts" / "metrics-export.py"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the metrics-export script and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(METRICS_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT),
    )


# ── JSON output tests ──────────────────────────────────────────────


def test_json_output_is_valid_json():
    """--json produces valid JSON to stdout."""
    result = run_script("--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, dict)


def test_json_output_required_fields():
    """JSON output contains all required fields from Metrics + derived fields."""
    result = run_script("--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)

    # Raw metrics fields
    assert "commands_wrapped" in data
    assert "commands_passed_disabled" in data
    assert "commands_passed_no_unshare" in data
    assert "jail_crashes" in data
    assert "byte_budget_rejections" in data
    assert "wrap_time_ns_total" in data
    assert "wrap_count" in data
    assert "perf_regression_alert_count" in data

    # Derived fields
    assert "total_commands_observed" in data
    assert "wrap_rate" in data
    assert "crash_rate" in data
    assert "wrap_avg_ns" in data

    # Metadata
    assert "timestamp" in data
    assert "project" in data
    assert "version" in data


def test_json_output_field_types():
    """JSON output fields have correct types."""
    result = run_script("--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)

    # All counter fields are ints
    int_fields = [
        "commands_wrapped",
        "commands_passed_disabled",
        "commands_passed_no_unshare",
        "jail_crashes",
        "byte_budget_rejections",
        "wrap_time_ns_total",
        "wrap_count",
        "perf_regression_alert_count",
        "total_commands_observed",
        "wrap_avg_ns",
    ]
    for field in int_fields:
        assert isinstance(data[field], int), (
            f"{field} should be int, got {type(data[field])}"
        )

    # Rate fields are floats
    assert isinstance(data["wrap_rate"], float)
    assert isinstance(data["crash_rate"], float)

    # Metadata fields
    assert isinstance(data["timestamp"], str)
    assert data["project"] == "terminal-jail"
    assert data["version"] == "1.2.0"


def test_json_derived_values_with_zeros():
    """Derived fields are zero/safe when all counters are zero."""
    result = run_script("--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)

    assert data["total_commands_observed"] == 0
    assert data["wrap_rate"] == 0.0
    assert data["crash_rate"] == 0.0
    assert data["wrap_avg_ns"] == 0


def test_json_timestamp_is_iso8601():
    """Timestamp is a valid ISO-8601 string with UTC timezone."""
    result = run_script("--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)

    ts = data["timestamp"]
    assert "T" in ts
    assert "+" in ts or "Z" in ts


# ── Human-readable output tests ────────────────────────────────────


def test_human_output_no_json_flag():
    """Without --json, script produces human-readable summary to stdout."""
    result = run_script()
    assert result.returncode == 0

    assert "===" in result.stdout
    assert "terminal-jail metrics" in result.stdout
    assert "commands_wrapped" in result.stdout
    assert "wrap_rate" in result.stdout
    assert "crash_rate" in result.stdout


def test_human_output_does_not_contain_json():
    """Without --json, stdout is NOT valid JSON."""
    result = run_script()
    assert result.returncode == 0

    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)


def test_human_output_has_all_sections():
    """Human output includes all metrics sections."""
    result = run_script()
    assert result.returncode == 0

    expected = [
        "timestamp",
        "commands_wrapped",
        "commands_passed_disabled",
        "commands_passed_no_unshare",
        "jail_crashes",
        "byte_budget_rejections",
        "perf_regression_alerts",
        "wrap_avg_ns",
        "total_observed",
        "wrap_rate",
        "crash_rate",
    ]
    for field in expected:
        assert field in result.stdout, f"Missing field in human output: {field}"


# ── --reset flag tests ─────────────────────────────────────────────


def test_reset_flag_resets_counters():
    """--reset --json exports then resets counters to zero."""
    # First, verify reset works: run with --reset --json
    result1 = run_script("--reset", "--json")
    assert result1.returncode == 0

    # After reset, a second run should show all zeros
    result2 = run_script("--json")
    assert result2.returncode == 0
    data2 = json.loads(result2.stdout)

    assert data2["commands_wrapped"] == 0
    assert data2["commands_passed_disabled"] == 0
    assert data2["jail_crashes"] == 0
    assert data2["byte_budget_rejections"] == 0
    assert data2["wrap_count"] == 0
    assert data2["wrap_time_ns_total"] == 0


def test_reset_with_human_output():
    """--reset works with human-readable output (no --json)."""
    result = run_script("--reset")
    assert result.returncode == 0
    assert "===" in result.stdout

    # After reset, verify counters are zero
    result2 = run_script("--json")
    data = json.loads(result2.stdout)
    assert data["commands_wrapped"] == 0


def test_reset_then_json_shows_zeros():
    """After --reset, subsequent --json shows all zero counters."""
    # Reset
    run_script("--reset")

    # Then export
    result = run_script("--json")
    data = json.loads(result.stdout)

    assert data["commands_wrapped"] == 0
    assert data["commands_passed_disabled"] == 0
    assert data["commands_passed_no_unshare"] == 0
    assert data["jail_crashes"] == 0
    assert data["byte_budget_rejections"] == 0
    assert data["wrap_time_ns_total"] == 0
    assert data["wrap_count"] == 0
    assert data["perf_regression_alert_count"] == 0
    assert data["total_commands_observed"] == 0


# ── Error path tests ───────────────────────────────────────────────


def test_missing_plugin_import_error():
    """Script reports error when get_metrics import raises ImportError."""
    # Run the script via a wrapper that simulates ImportError
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import sys
import builtins
original_import = builtins.__import__

def blocking_import(name, *args, **kwargs):
    if name == 'plugin.terminal_jail.plugin' or name.startswith('plugin'):
        raise ImportError("Simulated missing plugin: " + name)
    return original_import(name, *args, **kwargs)

builtins.__import__ = blocking_import
sys.path.insert(0, "{PROJECT_ROOT}")
exec(open("{METRICS_SCRIPT}").read())
""",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode != 0


def test_script_as_module_produces_same_output():
    """Running as `python3 -m scripts.metrics_export` or via script produces consistent behavior.

    Note: The script uses `if __name__ == '__main__'` so direct execution is the
    intended path. This test verifies the script file is syntactically loadable
    as a module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("metrics_export", str(METRICS_SCRIPT))
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Verify it loads without error
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main")
    assert hasattr(mod, "_metrics_to_dict")


# ── Derived calculation tests ──────────────────────────────────────


def test_wrap_rate_calculation():
    """wrap_rate = commands_wrapped / total_commands_observed."""
    result = run_script("--reset", "--json")  # reset to zero first
    # With all zeros, wrap_rate should be 0.0
    data = json.loads(result.stdout)
    assert data["wrap_rate"] == 0.0
    assert data["crash_rate"] == 0.0


def test_total_commands_observed_formula():
    """total_commands_observed = wrapped + passed_disabled + passed_no_unshare."""
    result = run_script("--json")
    data = json.loads(result.stdout)
    total = (
        data["commands_wrapped"]
        + data["commands_passed_disabled"]
        + data["commands_passed_no_unshare"]
    )
    assert data["total_commands_observed"] == total


def test_wrap_avg_ns_zero_when_no_wraps():
    """wrap_avg_ns is 0 when wrap_count is 0 (no division by zero)."""
    result = run_script("--reset", "--json")
    data = json.loads(result.stdout)
    assert data["wrap_count"] == 0
    assert data["wrap_avg_ns"] == 0


def test_json_output_machine_readable_no_stderr_on_success():
    """Successful --json run produces NO stderr output."""
    result = run_script("--json")
    assert result.returncode == 0
    assert result.stderr == "" or result.stderr is None


# ── Edge case: running from different directories ──────────────────


def test_runs_from_project_root():
    """Script runs successfully when cwd is project root."""
    result = subprocess.run(
        [sys.executable, str(METRICS_SCRIPT), "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["project"] == "terminal-jail"


def test_runs_from_scripts_directory():
    """Script runs successfully when cwd is scripts/."""
    result = subprocess.run(
        [sys.executable, "metrics-export.py", "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT / "scripts"),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["project"] == "terminal-jail"


# ── Repeated execution idempotency ─────────────────────────────────


def test_repeated_json_output_consistent_structure():
    """Running --json twice produces the same set of keys."""
    result1 = run_script("--json")
    result2 = run_script("--json")
    keys1 = set(json.loads(result1.stdout).keys())
    keys2 = set(json.loads(result2.stdout).keys())
    assert keys1 == keys2


def test_json_indent_is_2():
    """JSON output uses 2-space indentation."""
    result = run_script("--json")
    lines = result.stdout.split("\n")
    indented_lines = [
        line for line in lines if line.startswith("  ") and not line.startswith("    ")
    ]
    assert len(indented_lines) > 0, "Expected 2-space indented lines in JSON output"
