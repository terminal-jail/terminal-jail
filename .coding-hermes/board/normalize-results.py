#!/usr/bin/env python3
"""Normalize free-form guard_result/ci_result to closed vocabulary.

Preserves original prose in foreman_note. Line-preserving: only rewrites rows that change.
"""

import json
import re
from pathlib import Path

BOARD = Path(__file__).parent / "tasks.jsonl"


def normalize_guard(val):
    if not val or not isinstance(val, str):
        return val
    v = val.strip()
    vu = v.upper()
    if vu in {"PASS", "FAIL", "SKIP"}:
        return v
    if "FAIL" in vu and "DEGRADED" not in vu:
        return "FAIL"
    if "PASS" in vu:
        return "PASS"
    if re.match(r"^\d+/\d+$", v.strip()):
        return "PASS"
    if "SKIP" in vu or "SKIPPED" in vu:
        return "SKIP"
    if "N/A" in vu or "NOT APPLICABLE" in vu:
        return "SKIP"
    return v


def normalize_ci(val):
    if not val or not isinstance(val, str):
        return val
    v = val.strip()
    vu = v.upper()
    if vu in {"GREEN", "RED", "SKIP"}:
        return v
    if "FAIL" in vu or vu == "RED":
        return "RED"
    if "GREEN" in vu or "SUCCESS" in vu or vu == "PASS":
        return "GREEN"
    if any(
        x in vu
        for x in (
            "PENDING",
            "UNVERIFIED",
            "IN_PROGRESS",
            "IN PROGRESS",
            "N/A",
            "NOT APPLICABLE",
        )
    ):
        return "SKIP"
    return v


def main():
    lines = BOARD.read_text().splitlines()
    changed = 0
    new_lines = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            new_lines.append(line)
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue

        modified = False
        orig_guard = row.get("guard_result")
        orig_ci = row.get("ci_result")

        if orig_guard and isinstance(orig_guard, str):
            new_guard = normalize_guard(orig_guard)
            if new_guard != orig_guard:
                note = row.get("foreman_note") or ""
                suffix = f"orig guard_result: {orig_guard}"
                if note:
                    note += "; " + suffix
                else:
                    note = suffix
                row["foreman_note"] = note
                row["guard_result"] = new_guard
                modified = True
                print(
                    f"L{i} {row.get('id', '?')}: guard '{orig_guard}' -> '{new_guard}'"
                )

        if orig_ci and isinstance(orig_ci, str):
            new_ci = normalize_ci(orig_ci)
            if new_ci != orig_ci:
                note = row.get("foreman_note") or ""
                suffix = f"orig ci_result: {orig_ci}"
                if note:
                    note += "; " + suffix
                else:
                    note = suffix
                row["foreman_note"] = note
                row["ci_result"] = new_ci
                modified = True
                print(f"L{i} {row.get('id', '?')}: ci '{orig_ci}' -> '{new_ci}'")

        if modified:
            changed += 1
            new_lines.append(json.dumps(row, ensure_ascii=False))
        else:
            new_lines.append(line)

    if changed > 0:
        BOARD.write_text("\n".join(new_lines) + "\n")
        print(f"\nNormalized {changed} rows")
    else:
        print("\nNo changes needed")


if __name__ == "__main__":
    main()
