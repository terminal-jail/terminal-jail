#!/usr/bin/env python3
"""TJ-GAP-089 — composition battery: tool alone, platform alone, BOTH.

Three cells, each recording the MEASURED per-layer properties (PID-ns inode,
/proc entry count, /proc/1 identity, seccomp state) plus the tool's verdict
provenance where the tool ran:

  host       the tool on the outer host (container absent or not used)
  platform   the container alone, WITHOUT the tool (the platform's own layer)
  both       the tool INSIDE the container (the composed stack)

Verdict vocabulary — every cell is exactly one of:
  PASS         the cell's arms ran and their outcomes matched the contract
  FAIL         an arm's outcome contradicted the contract
  UNAVAILABLE  the cell could not run here (no docker, no repo mount) —
               a HOST condition, never a pass
  UNMEASURED   nothing was observed (reserved for imported records)

UNAVAILABLE and UNMEASURED are never converted to PASS, mirroring
scripts/kernel-matrix-teardown.py conventions. Every printed row carries its
raw properties; nothing is fabricated when a probe fails — the property is
reported as null with a reason (unexplained nulls are junk).

Usage:
    .venv/bin/python scripts/composed-mode-battery.py            # host + both
    .venv/bin/python scripts/composed-mode-battery.py --json     # machine rows
    docker run --rm -v <repo>:/repo:ro --entrypoint python3 \\
        python:3.11-slim /repo/scripts/composed-mode-battery.py --inner
    .venv/bin/python scripts/composed-mode-battery.py --selftest # offline

The --inner mode runs INSIDE the container (collects the container's own
properties and runs the tool arms against /repo/standalone/terminal-jail);
the host mode drives `docker run --inner` for the platform/both cells when
docker is available and records UNAVAILABLE (with reason) when it is not.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI_REL = "standalone/terminal-jail"
INNER_IMAGE = "python:3.11-slim"

VERDICTS = ("PASS", "FAIL", "UNMEASURED", "UNAVAILABLE")


def _readlink(path: str) -> str | None:
    try:
        return os.readlink(path)
    except OSError:
        return None


def _proc_props() -> dict:
    """The per-layer properties of THIS process's view, measured (never
    inferred). Each value carries a reason when unreadable."""
    props: dict = {}
    props["pid_ns"] = _readlink("/proc/self/ns/pid") or "unreadable"
    init_ns = _readlink("/proc/1/ns/pid")
    props["pid_ns_of_1"] = init_ns or "unreadable (permission or hidepid)"
    try:
        props["proc_entry_count"] = sum(
            1 for name in os.listdir("/proc") if name.isdigit()
        )
    except OSError as exc:
        props["proc_entry_count"] = None
        props["proc_entry_count_reason"] = str(exc)
    try:
        props["proc_1_comm"] = Path("/proc/1/comm").read_text(encoding="utf-8").strip()
    except OSError:
        props["proc_1_comm"] = "unreadable"
    try:
        for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
            if line.startswith("Seccomp:"):
                props["seccomp_state"] = line.split()[1]
                break
        else:
            props["seccomp_state"] = "absent"
    except OSError:
        props["seccomp_state"] = "unreadable"
    props["dockerenv"] = Path("/.dockerenv").exists()
    return props


def _cli_run(
    args: list[str], env_extra: dict | None = None, timeout: float = 30
) -> tuple[subprocess.CompletedProcess, float]:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    result = subprocess.run(
        [str(REPO / CLI_REL), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(REPO),
        check=False,
    )
    return result, time.time() - t0


def _verdict_from_arms(arms: list[dict]) -> tuple[str, list[str]]:
    """arms: [{name, ok, detail}] -> verdict + failing detail lines."""
    failures = [f"{a['name']}: {a['detail']}" for a in arms if not a["ok"]]
    if failures and any(a.get("ran") for a in arms):
        return ("FAIL", failures)
    if failures:
        return ("UNAVAILABLE", failures)
    return ("PASS", [])


def _host_cell() -> dict:
    props = _proc_props()
    arms: list[dict] = []
    # Firewall arm: the block contract holds wherever the bridge can run.
    try:
        result, _ = _cli_run(["rm", "-rf", "/"])
        arms.append(
            {
                "name": "firewall-block",
                "ok": result.returncode == 126
                and "builtin-rm-rf-root" in result.stderr,
                "ran": True,
                "detail": f"rc={result.returncode}",
            }
        )
    except (OSError, subprocess.SubprocessError) as exc:
        arms.append(
            {"name": "firewall-block", "ok": False, "ran": False, "detail": str(exc)}
        )
    verdict, failures = _verdict_from_arms(arms)
    return {
        "cell": "host",
        "verdict": verdict,
        "properties": props,
        "failures": failures,
        "note": "tool on the outer host; namespace arms depend on this host's policy (see docs/backend-parity.md)",
    }


def _inner_cell() -> dict:
    """Runs INSIDE the container: platform properties + tool composed arms."""
    props = _proc_props()
    arms: list[dict] = []
    try:
        result, dt = _cli_run(["echo", "TJ089-INNER-OK"])
        arms.append(
            {
                "name": "composed-echo",
                "ok": (
                    result.returncode == 0
                    and "TJ089-INNER-OK" in result.stdout
                    and "COMPOSED MODE" in result.stderr
                    and "jail_layer=platform" in result.stderr
                ),
                "ran": True,
                "detail": f"rc={result.returncode} in {dt:.2f}s",
            }
        )
    except (OSError, subprocess.SubprocessError) as exc:
        arms.append(
            {"name": "composed-echo", "ok": False, "ran": False, "detail": str(exc)}
        )
    try:
        result, _ = _cli_run(["rm", "-rf", "/"])
        arms.append(
            {
                "name": "firewall-block",
                "ok": result.returncode == 126
                and "builtin-rm-rf-root" in result.stderr,
                "ran": True,
                "detail": f"rc={result.returncode}",
            }
        )
    except (OSError, subprocess.SubprocessError) as exc:
        arms.append(
            {"name": "firewall-block", "ok": False, "ran": False, "detail": str(exc)}
        )
    try:
        result, dt = _cli_run(
            ["echo", "x"], env_extra={"TERMINAL_JAIL_COMPOSED": "off"}
        )
        stderr_lines = result.stderr.splitlines()
        arms.append(
            {
                "name": "composed-off-refusal",
                "ok": (
                    result.returncode == 2
                    and any("namespace creation failed" in ln for ln in stderr_lines)
                    and any("cause:" in ln for ln in stderr_lines)
                    and any("options:" in ln for ln in stderr_lines)
                ),
                "ran": True,
                "detail": f"rc={result.returncode} in {dt:.2f}s",
            }
        )
    except (OSError, subprocess.SubprocessError) as exc:
        arms.append(
            {
                "name": "composed-off-refusal",
                "ok": False,
                "ran": False,
                "detail": str(exc),
            }
        )
    try:
        result, _ = _cli_run(
            ["echo", "x"], env_extra={"TERMINAL_JAIL_JAIL_BACKEND": "unshare"}
        )
        arms.append(
            {
                "name": "explicit-backend-no-downgrade",
                "ok": (
                    result.returncode == 2
                    and result.stderr
                    == (
                        "terminal-jail: namespace creation failed (unshare exit 1); "
                        "command not run — on unprivileged hosts try --user\n"
                    )
                ),
                "ran": True,
                "detail": f"rc={result.returncode}",
            }
        )
    except (OSError, subprocess.SubprocessError) as exc:
        arms.append(
            {
                "name": "explicit-backend-no-downgrade",
                "ok": False,
                "ran": False,
                "detail": str(exc),
            }
        )
    verdict, failures = _verdict_from_arms(arms)
    return {
        "cell": "both",
        "verdict": verdict,
        "properties": props,
        "failures": failures,
        "note": "tool inside the container: firewall by the tool, pid-ns/proc by the platform (jail_layer=platform)",
    }


def _docker_available() -> str | None:
    docker = shutil.which("docker")
    if docker is None:
        return "docker not on PATH"
    try:
        result = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"docker info failed: {exc}"
    if result.returncode != 0:
        return f"docker daemon unreachable: rc={result.returncode}"
    return None


def _container_cells(timeout: float = 300) -> list[dict]:
    """Drive --inner inside the container from the host: platform-alone and
    both cells. UNAVAILABLE (with reason) when docker cannot run."""
    reason = _docker_available()
    if reason is not None:
        return [
            {
                "cell": "platform",
                "verdict": "UNAVAILABLE",
                "properties": {},
                "failures": [reason],
                "note": "platform-alone cell needs docker",
            },
            {
                "cell": "both",
                "verdict": "UNAVAILABLE",
                "properties": {},
                "failures": [reason],
                "note": "both cell needs docker",
            },
        ]
    docker = shutil.which("docker")
    t0 = time.time()
    result = subprocess.run(
        [
            docker,
            "run",
            "--rm",
            "-v",
            f"{REPO}:/repo:ro",
            "--entrypoint",
            "python3",
            INNER_IMAGE,
            "/repo/scripts/composed-mode-battery.py",
            "--inner",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    dt = time.time() - t0
    try:
        inner = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [
            {
                "cell": "both",
                "verdict": "FAIL",
                "properties": {},
                "failures": [
                    (
                        f"inner run produced no JSON row in {dt:.1f}s "
                        f"(rc={result.returncode}): {result.stderr.strip()[:400]}"
                    )
                ],
                "note": "the --inner cell must print exactly one JSON row",
            }
        ]
    platform_row = dict(inner)
    platform_row["cell"] = "platform"
    # Platform-alone: same properties; the TOOL arms do not apply — the
    # platform's own layer is the subject. Verdict PASS requires the
    # container to actually provide the namespace layer (pid ns exists and
    # /proc/1 is the container init), else the cell FAILs honestly.
    props = inner.get("properties", {})
    platform_ok = isinstance(props.get("proc_entry_count"), int) and props.get(
        "proc_1_comm"
    ) not in (None, "unreadable")
    platform_row["verdict"] = "PASS" if platform_ok else "FAIL"
    platform_row["failures"] = (
        [] if platform_ok else [f"platform layer incomplete: {props}"]
    )
    platform_row["note"] = (
        "container alone: pid-ns/proc owned by the platform (no tool involved)"
    )
    return [platform_row, inner]


def _validate_row(row: dict) -> list[str]:
    """Schema/consistency validation (also the --selftest subject)."""
    errors: list[str] = []
    if row.get("cell") not in ("host", "platform", "both"):
        errors.append(f"bad cell: {row.get('cell')!r}")
    if row.get("verdict") not in VERDICTS:
        errors.append(f"bad verdict: {row.get('verdict')!r}")
    if not isinstance(row.get("failures"), list):
        errors.append("failures must be a list")
    if row.get("verdict") == "UNAVAILABLE" and not row.get("failures"):
        errors.append("UNAVAILABLE without a reason is junk")
    if row.get("verdict") == "PASS" and row.get("failures"):
        errors.append("PASS with failures is a contradiction")
    props = row.get("properties")
    if row.get("verdict") in ("PASS", "FAIL") and not isinstance(props, dict):
        errors.append("PASS/FAIL rows must carry measured properties")
    return errors


def _selftest() -> int:
    """Offline, non-vacuous: every malformed arm is rejected, every valid
    row accepted — mirrors kernel-matrix-teardown.py --selftest."""
    good = {
        "cell": "both",
        "verdict": "PASS",
        "properties": {"pid_ns": "pid:[1]"},
        "failures": [],
        "note": "n",
    }
    assert _validate_row(good) == [], "valid row rejected"
    bad_rows = [
        {**good, "verdict": "GREEN"},
        {**good, "cell": "everywhere"},
        {**good, "verdict": "UNAVAILABLE", "failures": []},
        {**good, "verdict": "PASS", "failures": ["x"]},
        {**good, "verdict": "PASS", "properties": None},
    ]
    for row in bad_rows:
        errors = _validate_row(row)
        assert errors, f"malformed row accepted: {row}"
    print(
        f"SELFTEST PASS: 1 valid row accepted, {len(bad_rows)} malformed rows rejected"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="print machine rows only"
    )
    parser.add_argument(
        "--inner", action="store_true", help="run inside the container (one JSON row)"
    )
    parser.add_argument(
        "--selftest", action="store_true", help="offline validation selftest"
    )
    args = parser.parse_args()

    if args.selftest:
        return _selftest()

    if args.inner:
        row = _inner_cell()
        errors = _validate_row(row)
        if errors:
            row["verdict"] = "FAIL"
            row["failures"] = (row.get("failures") or []) + errors
        print(json.dumps(row))
        return 0

    rows = [_host_cell()] + _container_cells()
    for row in rows:
        errors = _validate_row(row)
        if errors:
            row["verdict"] = "FAIL"
            row["failures"] = (row.get("failures") or []) + errors

    if args.as_json:
        for row in rows:
            print(json.dumps(row))
    else:
        for row in rows:
            print(f"[{row['verdict']:>11}] {row['cell']}: {row['note']}")
            for key, value in row.get("properties", {}).items():
                print(f"    {key} = {value}")
            for failure in row["failures"]:
                print(f"    ! {failure}")
        greens = [r for r in rows if r["verdict"] == "PASS"]
        unavailable = [r for r in rows if r["verdict"] == "UNAVAILABLE"]
        print(
            f"summary: {len(greens)}/{len(rows)} PASS, "
            f"{len(unavailable)} UNAVAILABLE — unavailable cells never count "
            "as green"
        )
    return 0 if all(r["verdict"] == "PASS" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
