#!/usr/bin/env python3
"""Export terminal-jail metrics as JSON for DuckBrain ingestion (T7.5).

Usage:
    python3 scripts/metrics-export.py           # human-readable summary
    python3 scripts/metrics-export.py --json    # JSON for DuckBrain / automation
    python3 scripts/metrics-export.py --reset   # dump JSON then reset counters
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure the plugin package is importable from the project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from plugin.terminal_jail.plugin import (
    get_metrics,
    reset_metrics,
)


def _metrics_to_dict() -> dict:
    """Convert the Metrics dataclass to a plain dict with a timestamp."""
    m = get_metrics()
    d = dataclasses.asdict(m)
    d["timestamp"] = datetime.now(UTC).isoformat()
    d["project"] = "terminal-jail"
    d["version"] = "1.1.0"
    # Derived fields for dashboarding
    total_commands = (
        m.commands_wrapped
        + m.commands_wrapped_user_ns
        + m.commands_passed_disabled
        + m.commands_passed_no_unshare
    )
    d["total_commands_observed"] = total_commands
    d["wrap_rate"] = m.commands_wrapped / total_commands if total_commands > 0 else 0.0
    d["crash_rate"] = m.jail_crashes / total_commands if total_commands > 0 else 0.0
    if m.wrap_count > 0:
        d["wrap_avg_ns"] = m.wrap_time_ns_total // m.wrap_count
    else:
        d["wrap_avg_ns"] = 0
    return d


def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal-Jail metrics exporter")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--reset", action="store_true", help="Reset counters after export"
    )
    args = parser.parse_args()

    data = _metrics_to_dict()

    if args.json:
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        # Human-readable summary
        print("=== terminal-jail metrics ===")
        print(f"  timestamp:                {data['timestamp']}")
        print(f"  commands_wrapped:         {data['commands_wrapped']}")
        print(f"  commands_wrapped_user_ns: {data['commands_wrapped_user_ns']}")
        print(f"  commands_passed_disabled: {data['commands_passed_disabled']}")
        print(f"  commands_passed_no_unshare: {data['commands_passed_no_unshare']}")
        print(f"  jail_crashes:             {data['jail_crashes']}")
        print(f"  byte_budget_rejections:   {data['byte_budget_rejections']}")
        print(f"  perf_regression_alerts:   {data['perf_regression_alert_count']}")
        print(f"  wrap_avg_ns:              {data['wrap_avg_ns']}")
        print(f"  total_observed:           {data['total_commands_observed']}")
        print(f"  wrap_rate:                {data['wrap_rate']:.4f}")
        print(f"  crash_rate:               {data['crash_rate']:.4f}")

    if args.reset:
        reset_metrics()


if __name__ == "__main__":
    main()
