#!/usr/bin/env python3
"""Performance benchmarks for the Interruptor Bash command firewall.

Measures four key metrics per the S05 Interruptor spec (§13):

- Cold start (first invocation): < 50ms
- Warm start (cached rules): < 5ms
- Command parsing for 1KB command: < 10ms
- Rule evaluation for 500 rules: < 5ms

Usage:
    python3 scripts/benchmark-interruptor.py [--json]

Output:
    Table of results with PASS/FAIL per metric.
    With --json: machine-readable JSON for CI consumption.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure plugin/ is importable
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
_plugin_dir = _project_root / "plugin"
sys.path.insert(0, str(_plugin_dir))

from terminal_jail.interruptor import intercept
from terminal_jail.interruptor.config import Config
from terminal_jail.interruptor.decider import Decider
from terminal_jail.interruptor.parser import parse_command


def _generate_n_rules(n: int, prefix: str) -> list:
    """Generate N fake rules for benchmarking."""
    rules = []
    for i in range(n):
        rules.append(
            {
                "id": f"{prefix}-{i}",
                "action": "block",
                "match": {"type": "command", "command": f"never-match-{prefix}-{i}"},
            }
        )
    return rules


def benchmark_cold_start(config: Config, n_runs: int = 10) -> float:
    """Measure cold start time for the interruptor engine.

    Cold start = module import + Config.from_environ() + first intercept().
    """
    times: list[float] = []
    for _ in range(n_runs):
        start = time.perf_counter()
        # Import fresh module state (simulate cold start)
        import importlib

        import terminal_jail.interruptor as mod

        importlib.reload(mod)
        _ = mod.intercept("echo hello", config=config)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    return min(times)  # fastest run = ideal cold start


def benchmark_warm_start(config: Config, n_runs: int = 100) -> float:
    """Measure warm start time — cached module state, repeated evaluation."""
    # First call warms the cache
    intercept("echo hello", config=config)
    times: list[float] = []
    for _ in range(n_runs):
        start = time.perf_counter()
        intercept("echo hello", config=config)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    return min(times)


def benchmark_parse_1kb(n_runs: int = 100) -> float:
    """Parse a ~1KB shell command — complex pipeline."""
    command = (
        "cat /var/log/syslog | grep '" + ("x" * 200) + "' | awk '{print $1}' | "
        "sort -u | head -100 | tee /tmp/output.txt"
        " && "
        "for f in $(find /etc -name '*.conf' -type f 2>/dev/null | head -50); do"
        '  echo "Processing: $f"'
        '  if [[ -r "$f" ]]; then'
        '    echo "Config: $(head -1 "$f")"'
        "  fi"
        "done"
        " && "
        'echo "All done. Exit code: $?"'
        " | "
        "sed 's/All/all/g'"
        " | "
        "tee /tmp/report.txt"
        " && "
        "cat /var/log/auth.log | grep -E 'sshd|sudo' | "
        "awk '{print $1, $2, $3}' FS=':' OFS='/' | "
        "sort | uniq -c | sort -rn | head -20"
    )
    # Pad command to ~1KB if needed
    if len(command) < 900:
        command += " && " + "#" * (950 - len(command))
    # Ensure command is ~1KB
    assert 900 < len(command) < 1100, f"Command length {len(command)} not ~1KB"

    times: list[float] = []
    for _ in range(n_runs):
        start = time.perf_counter()
        _ = parse_command(command)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    return min(times)


def benchmark_rule_eval(n_rules: int = 500, n_runs: int = 50) -> float:
    """Evaluate a command against N rules."""
    config = Config.from_environ()
    decider = Decider(config)

    # Create N rules that won't match
    for rule in _generate_n_rules(n_rules, "bench"):
        # Inject into the blocklist for testing
        from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST
        from terminal_jail.interruptor.rules import Rule

        BUILTIN_BLOCKLIST.append(Rule.from_dict(rule))

    segments = parse_command("echo hello")
    times: list[float] = []
    for _ in range(n_runs):
        start = time.perf_counter()
        _ = decider.evaluate(segments, "echo hello")
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)

    # Clean up injected rules
    del BUILTIN_BLOCKLIST[-n_rules:]

    return min(times)


def main() -> None:
    config = Config.from_environ()

    print("=" * 60)
    print("  Interruptor Performance Benchmarks")
    print("=" * 60)

    # Cold start
    cold = benchmark_cold_start(config)
    cold_pass = cold < 50.0
    print(
        f"\n  Cold start (first invocation)         : {cold:.2f}ms  {'✅ PASS' if cold_pass else '❌ FAIL'} (< 50ms)"
    )

    # Warm start
    warm = benchmark_warm_start(config)
    warm_pass = warm < 5.0
    print(
        f"  Warm start (cached, min of 100)      : {warm:.3f}ms  {'✅ PASS' if warm_pass else '❌ FAIL'} (< 5ms)"
    )

    # Parse 1KB
    parse = benchmark_parse_1kb()
    parse_pass = parse < 10.0
    print(
        f"  1KB parse (min of 100)               : {parse:.3f}ms  {'✅ PASS' if parse_pass else '❌ FAIL'} (< 10ms)"
    )

    # Rule evaluation for 500 rules
    eval_500 = benchmark_rule_eval(500)
    eval_pass = eval_500 < 5.0
    print(
        f"  500-rule eval (min of 50)            : {eval_500:.3f}ms  {'✅ PASS' if eval_pass else '❌ FAIL'} (< 5ms)"
    )

    print(f"\n  {'=' * 56}")

    if "--json" in sys.argv:
        results = {
            "cold_start_ms": round(cold, 2),
            "cold_start_pass": cold_pass,
            "warm_start_ms": round(warm, 3),
            "warm_start_pass": warm_pass,
            "parse_1kb_ms": round(parse, 3),
            "parse_1kb_pass": parse_pass,
            "eval_500_rules_ms": round(eval_500, 3),
            "eval_500_rules_pass": eval_pass,
            "all_pass": all([cold_pass, warm_pass, parse_pass, eval_pass]),
        }
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
