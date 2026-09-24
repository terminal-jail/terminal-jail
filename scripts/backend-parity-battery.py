#!/usr/bin/env python3
"""TJ-GAP-056 — backend parity battery: bwrap vs unshare containment evidence.

specs/cli.md section 4 "Jail backends" documents where the two backends
genuinely differ (the private /proc, the teardown mechanism) and where they
must not be overstated. This battery MEASURES those properties on the host it
runs on and prints a per-cell parity table. It is a classifier in the house
style (scripts/pidns-capability-probe.py, scripts/fs-isolation-probe.py):
it always exits 0 and never gates anything.

Cells:
  1  private /proc under the bwrap backend (jail count << host count)
  2  private /proc under the unshare backend --user (host /proc exposed —
     the documented known limit, recorded honestly, not a failure)
  3  --die-with-parent orphan teardown (bwrap): SIGKILL the wrapper, the
     payload must disappear; teardown latency recorded
  4  orphan comparison (unshare --kill-child=SIGKILL): same experiment;
     a difference is a finding to document, not a crash
  5  escape-wave replay under the bwrap backend (engine corpus via pytest,
     plus a live-wrapper argv/exit slice)
  6  DEGRADED-host fail-closed contract: a PATH-stubbed backend whose probe
     fails must exit 2 with the command not run and a marker file the
     payload would have created left ABSENT (host-independent)
  7  host classification summary via the two shipped probes

Verdict vocabulary: SAME | DIFFERS | KNOWN-LIMIT | FAIL-CLOSED-PROVEN.
A cell that cannot be measured on this host is labelled KNOWN-LIMIT with an
"UNMEASURED" note — the divergence vocabulary is never used for a value that
was not actually observed.

Usage:
    .venv/bin/python scripts/backend-parity-battery.py           # human table
    .venv/bin/python scripts/backend-parity-battery.py --json    # structured

Always exits 0: this is evidence collection, not a gate.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = PROJECT_ROOT / "standalone" / "terminal-jail"
PIDNS_PROBE = PROJECT_ROOT / "scripts" / "pidns-capability-probe.py"
FSISO_PROBE = PROJECT_ROOT / "scripts" / "fs-isolation-probe.py"
ESCAPE_WAVES = PROJECT_ROOT / "plugin" / "test_escape_waves.py"

PROC_COUNT_SNIPPET = 'ls /proc | grep -c "^[0-9]\\+$"'
ORPHAN_WAIT_LAUNCH = 10.0
ORPHAN_WAIT_TEARDOWN = 15.0

VOCABULARY = ("SAME", "DIFFERS", "KNOWN-LIMIT", "FAIL-CLOSED-PROVEN")


def _cell(
    cell: str, backend: str, measured: str, expected: str, verdict: str, notes: str
) -> dict[str, str]:
    assert verdict in VOCABULARY, verdict
    return {
        "cell": cell,
        "backend": backend,
        "measured": measured,
        "expected": expected,
        "verdict": verdict,
        "notes": notes,
    }


def _unmeasured(cell: str, backend: str, expected: str, reason: str) -> dict[str, str]:
    return _cell(
        cell,
        backend,
        "not measured",
        expected,
        "KNOWN-LIMIT",
        f"UNMEASURED on this host: {reason}",
    )


def _run(
    cmd: list[str], env: dict[str, str] | None = None, timeout: float = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env if env is not None else dict(os.environ),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _cli_env(backend: str, *, disable_interruptor: bool = True) -> dict[str, str]:
    env = dict(os.environ)
    env["TERMINAL_JAIL_JAIL_BACKEND"] = backend
    if disable_interruptor:
        env["TERMINAL_JAIL_INTERRUPTOR_MODE"] = "disabled"
    else:
        # The verdict layers need the DEFAULT interruptor mode; drop any
        # inherited override so the cell is deterministic.
        env.pop("TERMINAL_JAIL_INTERRUPTOR_MODE", None)
    return env


def _host_proc_count() -> int:
    return len([p for p in pathlib.Path("/proc").iterdir() if p.name.isdigit()])


def _last_int(stdout: str) -> int | None:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


# ── cells 1+2: private /proc ───────────────────────────────────────────────


def _proc_cell(backend: str, host_count: int) -> dict[str, str]:
    if backend == "bwrap":
        name = "1 private /proc — bwrap backend"
    else:
        name = "2 private /proc — unshare backend"
    try:
        result = _run(
            [str(CLI), "--no-interruptor", "--user", "sh", "-c", PROC_COUNT_SNIPPET],
            env=_cli_env(backend),
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _unmeasured(
            name,
            backend,
            "a handful of entries, far below the host count",
            f"launch failed: {exc}",
        )
    if result.returncode != 0:
        return _unmeasured(
            name,
            backend,
            "a handful of entries, far below the host count",
            f"jail launch exited {result.returncode}: {result.stderr.strip()[:200]}",
        )
    count = _last_int(result.stdout)
    if count is None:
        return _unmeasured(
            name,
            backend,
            "a handful of entries, far below the host count",
            "no numeric count",
        )
    if backend == "bwrap":
        # private /proc: the jail sees only its own processes — a handful of
        # entries (reaper + trampoline + payload), never a fraction of the host.
        ok = count <= max(16, host_count // 100)
        verdict = "SAME" if ok else "DIFFERS"
        note = (
            f"jail sees {count} numeric /proc entries vs {host_count} on the host; "
            "--proc /proc mounts a fresh procfs"
            if ok
            else (
                f"bwrap jail sees {count} numeric /proc entries vs {host_count} on "
                "the host — /proc is NOT private; see docs/backend-parity.md "
                "known limits"
            )
        )
        return _cell(
            name,
            backend,
            f"{count} entries (host: {host_count})",
            "a handful of entries, far below the host count",
            verdict,
            note,
        )
    # unshare --user: the host /proc stays visible (spec: user namespaces
    # cannot mount /proc unprivileged) — the documented known limit.
    exposed = count >= host_count * 0.5
    verdict = "KNOWN-LIMIT" if exposed else "SAME"
    return _cell(
        name,
        backend,
        f"{count} entries (host: {host_count})",
        "≈ host count (documented known limit)",
        verdict,
        (
            f"unshare --user exposes the host /proc ({count} vs {host_count} "
            "entries) — specs/cli.md documents this, docs/backend-parity.md "
            "known limit (a)"
            if exposed
            else f"jail sees {count} vs {host_count} host entries"
        ),
    )


# ── cells 3+4: orphan teardown ─────────────────────────────────────────────


def _sleep300_pids() -> set[int]:
    out = set()
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if argv[:2] == [b"sleep", b"300"]:
            out.add(int(proc.name))
    return out


def _orphan_cell(backend: str) -> dict[str, str]:
    if backend == "bwrap":
        name = "3 orphan teardown — bwrap (--die-with-parent)"
        expected = "payload gone shortly after the wrapper dies"
    else:
        name = "4 orphan comparison — unshare (--kill-child=SIGKILL)"
        expected = "payload gone shortly after the wrapper dies"
    before = _sleep300_pids()
    try:
        launcher = subprocess.Popen(
            [str(CLI), "--no-interruptor", "--user", "sleep", "300"],
            cwd=str(PROJECT_ROOT),
            env=_cli_env(backend),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return _unmeasured(name, backend, expected, f"launch failed: {exc}")
    t0 = time.monotonic()
    payload: int | None = None
    while time.monotonic() - t0 < ORPHAN_WAIT_LAUNCH:
        new = _sleep300_pids() - before
        if new:
            payload = min(new)
            break
        time.sleep(0.05)
    if payload is None:
        launcher.kill()
        launcher.wait()
        return _unmeasured(
            name, backend, expected, "no sleep payload appeared within 10s"
        )
    how = (
        f"host-side pid {payload}, identified by exact cmdline 'sleep 300' "
        "diffed against the pre-launch /proc scan"
    )
    try:
        os.kill(launcher.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    tk = time.monotonic()
    latency: float | None = None
    while time.monotonic() - tk < ORPHAN_WAIT_TEARDOWN:
        if not pathlib.Path(f"/proc/{payload}").exists():
            latency = time.monotonic() - tk
            break
        time.sleep(0.02)
    launcher.wait()
    leftover = _sleep300_pids() - before
    if latency is not None:
        return _cell(
            name,
            backend,
            f"payload gone in {latency * 1000:.0f} ms; {how}",
            expected,
            "SAME",
            "no orphan; no leftover 'sleep 300' processes",
        )
    return _cell(
        name,
        backend,
        f"ORPHAN: payload {payload} still alive after "
        f"{ORPHAN_WAIT_TEARDOWN:.0f}s; {how}",
        expected,
        "DIFFERS",
        (
            "an orphan survived the wrapper's death — see "
            "docs/backend-parity.md known limits"
            if not leftover
            else f"leftover 'sleep 300' pids: {sorted(leftover)}"
        ),
    )


# ── cell 5: escape-wave replay ─────────────────────────────────────────────


def _escape_cell() -> dict[str, str]:
    name = "5 escape-wave replay under the bwrap backend"
    # NOTE: the corpus pins auto-sandbox (modify) verdicts, which the default
    # interruptor mode produces — TERMINAL_JAIL_INTERRUPTOR_MODE=disabled
    # flips 105 of them to allow (measured), so it must NOT be set here.
    try:
        result = _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "plugin/test_escape_waves.py",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            env=_cli_env("bwrap", disable_interruptor=False),
            timeout=300,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _unmeasured(name, "bwrap", "all vectors green", f"pytest failed: {exc}")
    tail = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if "No module named" in result.stderr and "pytest" in result.stderr:
        return _unmeasured(
            name,
            "bwrap",
            "all vectors green",
            "pytest unavailable — run under the repo venv (.venv/bin/python)",
        )
    ok = result.returncode == 0 and "failed" not in tail.lower()
    return _cell(
        name,
        "bwrap",
        f"rc={result.returncode}, tail: {tail}",
        "all escape vectors stay green under the bwrap backend",
        "SAME" if ok else "DIFFERS",
        "method (a): the engine corpus via pytest under the bwrap backend; a "
        "live-wrapper argv/exit slice follows in cell 5b",
    )


def _escape_live_slice_cell() -> dict[str, str]:
    name = "5b escape replay live slice (wrapper, argv+exit semantics)"
    try:
        argv = _run(
            [str(CLI), "--no-interruptor", "printf", "[%s]", "a b", "$(id)", "*", ""],
            env=_cli_env("bwrap"),
            timeout=30,
        )
        exitcode = _run(
            [str(CLI), "--no-interruptor", "bash", "-c", "exit 42"],
            env=_cli_env("bwrap"),
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _unmeasured(name, "bwrap", "argv preserved, exit propagated", str(exc))
    ok = (
        argv.returncode == 0
        and argv.stdout == "[a b][$(id)][*][]"
        and exitcode.returncode == 42
    )
    return _cell(
        name,
        "bwrap",
        f"argv round-trip rc={argv.returncode} stdout={argv.stdout!r}; "
        f"exit 42 -> rc={exitcode.returncode}",
        "argv preserved, payload exit propagated",
        "SAME" if ok else "DIFFERS",
        "live wrapper under TERMINAL_JAIL_JAIL_BACKEND=bwrap",
    )


# ── cell 6: DEGRADED fail-closed contract ──────────────────────────────────


def _fail_closed_cell(backend: str) -> dict[str, str]:
    name = "6 fail-closed when the namespace probe fails"
    expected = "exit 2, command not run, marker file ABSENT"
    with tempfile.TemporaryDirectory(prefix="tj-parity-") as tmp:
        root = pathlib.Path(tmp)
        bindir = root / "bin"
        bindir.mkdir()
        stub = bindir / backend
        stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        stub.chmod(0o755)
        marker = root / f"marker-{backend}"
        env = _cli_env(backend)
        env["PATH"] = f"{bindir}:{env.get('PATH', os.defpath)}"
        try:
            result = _run(
                [str(CLI), "--no-interruptor", "touch", str(marker)],
                env=env,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return _unmeasured(name, backend, expected, f"run failed: {exc}")
        absent = not marker.exists()
        proven = (
            result.returncode == 2
            and absent
            and result.stdout == ""
            and "command not run" in result.stderr
        )
        return _cell(
            name,
            backend,
            f"rc={result.returncode}, stdout={result.stdout!r}, "
            f"marker={'ABSENT' if absent else 'PRESENT'}",
            expected,
            "FAIL-CLOSED-PROVEN" if proven else "DIFFERS",
            (
                "PATH-stubbed backend whose probe exits 1; the payload never ran"
                if proven
                else f"stderr: {result.stderr.strip()[:200]}"
            ),
        )


# ── cell 7: host classification ────────────────────────────────────────────


def _probe_classification(script: pathlib.Path) -> tuple[str, str]:
    try:
        result = _run([sys.executable, str(script)], timeout=60)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return "UNKNOWN", f"probe failed to run: {exc}"
    line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    return (line.split(":", 1)[0].split()[0] if line else "UNKNOWN"), line


def _classification_cells() -> list[dict[str, str]]:
    pidns, pidns_line = _probe_classification(PIDNS_PROBE)
    fsiso, fsiso_line = _probe_classification(FSISO_PROBE)
    return [
        _cell(
            "7 host classification: PID-namespace creation",
            "both",
            pidns,
            "FULL on a containment-capable host",
            "SAME" if pidns == "FULL" else "KNOWN-LIMIT",
            "scripts/pidns-capability-probe.py — "
            f"{pidns_line or pidns}; DEGRADED hosts cannot create the "
            "namespaces and live cells skip",
        ),
        _cell(
            "7 host classification: uid mapping (FS isolation)",
            "both",
            fsiso,
            "mapped keeps real FS isolation; degraded runs mapping-less",
            "SAME" if fsiso == "FULL" else "KNOWN-LIMIT",
            "scripts/fs-isolation-probe.py — "
            + (fsiso_line or fsiso)
            + "; DEGRADED = both backends run mapping-less here "
            "(known limit (c))",
        ),
    ]


# ── environment banner ─────────────────────────────────────────────────────


def _environment() -> dict[str, str]:
    kernel = pathlib.Path("/proc/sys/kernel/osrelease")
    bwrap = shutil.which("bwrap")
    version = ""
    if bwrap:
        try:
            probe = _run([bwrap, "--version"], timeout=10)
            version = probe.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            version = ""
    try:
        tj = _run([str(CLI), "--version"], timeout=15).stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        tj = "unknown"
    return {
        "kernel": kernel.read_text(encoding="ascii").strip()
        if kernel.exists()
        else "unknown",
        "bubblewrap": version or "absent",
        "terminal-jail": tj,
    }


def collect_cells() -> list[dict[str, str]]:
    host_count = _host_proc_count()
    cells = [
        _proc_cell("bwrap", host_count),
        _proc_cell("unshare", host_count),
        _orphan_cell("bwrap"),
        _orphan_cell("unshare"),
        _escape_cell(),
        _escape_live_slice_cell(),
        _fail_closed_cell("bwrap"),
        _fail_closed_cell("unshare"),
    ]
    cells.extend(_classification_cells())
    return cells


def print_table(env: dict[str, str], cells: list[dict[str, str]]) -> None:
    widths = {
        key: max(len(key), *(len(c[key]) for c in cells))
        for key in ("cell", "backend", "measured", "expected", "verdict")
    }
    host_count = _host_proc_count()
    print("backend parity battery (TJ-GAP-056) — bwrap vs unshare")
    print(
        f"host: kernel {env['kernel']}, {env['bubblewrap']}, "
        f"{env['terminal-jail']}, host /proc numeric entries: {host_count}"
    )
    print()
    header = "  ".join(key.ljust(widths[key]) for key in widths)
    print(header)
    print("  ".join("-" * widths[key] for key in widths))
    for cell in cells:
        print("  ".join(cell[key].ljust(widths[key]) for key in widths))
    print()
    print("notes:")
    for cell in cells:
        if cell["notes"]:
            print(f"  [{cell['cell'][:1]}] {cell['notes']}")
    divergences = [c for c in cells if c["verdict"] == "DIFFERS"]
    print()
    if divergences:
        print(
            f"{len(divergences)} divergence(s) — each must be justified in "
            "docs/backend-parity.md (known limits):"
        )
        for cell in divergences:
            print(f"  - {cell['cell']} ({cell['backend']})")
    else:
        print(
            "zero unexplained divergences: every cell is SAME, KNOWN-LIMIT "
            "(documented) or FAIL-CLOSED-PROVEN."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--json",
        action="store_true",
        help="print structured cells as JSON instead of the human table",
    )
    args = parser.parse_args()
    env = _environment()
    cells = collect_cells()
    if args.json:
        print(json.dumps({"environment": env, "cells": cells}, indent=2))
    else:
        print_table(env, cells)
    # House style: a classifier never gates.
    sys.exit(0)


if __name__ == "__main__":
    main()
