#!/usr/bin/env python3
"""TJ-DF-037 — kernel-matrix orphan-teardown harness (current-host live cell
plus an import path for external raw evidence).

Scope, stated honestly: this harness measures the orphan-teardown contract
(bwrap ``--die-with-parent`` / unshare ``--kill-child=SIGKILL``) **on the
kernel it runs on**. A multi-kernel claim requires cells recorded from at
least three real kernels and imported here; the current-host run alone is
never a matrix, and a cell whose kernel is not this host's kernel is never
executed or fabricated by this script.

Why TJ-DF-037 exists: scripts/backend-parity-battery.py cells 3/4 measure the
current host only, and docs/backend-parity.md recorded dev-kernel rows without
a committed multi-kernel runner or record format. TJ-DF-027 observed unshare
orphan teardown failing on fresh Debian 13.7 (kernel 6.12.107) while bwrap
passed there — an EXTERNAL cell whose raw output lives outside this repo;
until that raw output is imported, this repo's matrix row for that kernel
stays UNMEASURED. Nothing in this script or its docs may upgrade it.

Verdict vocabulary — every cell is exactly one of:
  PASS        the payload disappeared after the wrapper's SIGKILL within the
              teardown budget (survival_seconds recorded)
  FAIL        the payload survived the whole budget (orphan), or the
              harness's own evidence contradicts the row
  UNMEASURED  nothing was observed: imported/unavailable state without live
              data (survival_seconds and exit_code are null)
  UNAVAILABLE the backend could not be launched on this host (wrapper
              failed closed: missing binary, probe failure) — a HOST or
              BACKEND condition, never a pass

UNMEASURED and UNAVAILABLE are never converted to PASS, by construction: the
classifier requires observed evidence for PASS/FAIL and rejects anything
else.

Usage:
    # Live cell: measure both backends on THIS host (the only execution mode).
    .venv/bin/python scripts/kernel-matrix-teardown.py
    .venv/bin/python scripts/kernel-matrix-teardown.py --json     # machine rows
    .venv/bin/python scripts/kernel-matrix-teardown.py --raw      # + raw evidence blocks

    # Import external raw results (schema below) — pure parsing/classification,
    # no network, no remote execution:
    .venv/bin/python scripts/kernel-matrix-teardown.py --import cell-6.12.107.json

    # Offline, non-vacuous selftest of the parser/validator (no jail, no
    # network): runs every malformed arm through validate_row and proves each
    # is rejected; fails loudly if a malformed arm is accepted or a valid
    # row is rejected:
    .venv/bin/python scripts/kernel-matrix-teardown.py --selftest

Imported-file schema (v1) — one JSON object:
    {"rows": [row, ...]}   # rows required, non-empty

    row = {
      "kernel": str,              # non-empty `uname -r` string (required)
      "backend": "bwrap"|"unshare",  # exactly one of the two (required)
      "verdict": "PASS"|"FAIL"|"UNMEASURED"|"UNAVAILABLE",  # (required)
      "survival_seconds": float|null,  # >= 0; null when no live data
      "exit_code": int|null,           # wrapper exit code; null when no live data
      "captured": str,            # non-empty capture timestamp string (required)
      "evidence": str,            # non-empty raw evidence text (required)
    }

Consistency rules enforced by validate_row (rejections are rejections, never
repairs):
  - PASS/FAIL rows MUST carry a numeric survival_seconds >= 0 and an int
    exit_code (a claimed verdict without observed numbers is malformed);
  - UNMEASURED/UNAVAILABLE rows MUST carry survival_seconds = null and
    exit_code = null (a no-data row claiming numbers is malformed);
  - kernel, captured, evidence must be non-empty strings;
  - backend and verdict must be from the vocabulary above;
  - FAIL rows must carry a reason string in evidence (non-empty, already
    required) — the raw output itself is the evidence.

Matrix summary semantics (never a green matrix from one host):
  - cells on this host's kernel that this script measured  -> MEASURED
  - cells imported from other kernels with PASS/FAIL        -> MEASURED (external)
  - every kernel named in the matrix needs BOTH backends; a kernel with only
    one backend row is reported as an INCOMPLETE kernel (both rows required);
  - the summary line names how many DISTINCT kernels have a COMPLETE pair of
    MEASURED cells — the matrix is green for teardown only if that count is
    >= 3 AND every measured cell is PASS. One host can never satisfy this.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = PROJECT_ROOT / "standalone" / "terminal-jail"

LAUNCH_WAIT = 10.0  # seconds to wait for the sleep payload to appear
TEARDOWN_BUDGET = 15.0  # seconds a payload may survive the wrapper's death
PROC_POLL = 0.02  # /proc poll granularity

BACKENDS = ("bwrap", "unshare")
VERDICTS = ("PASS", "FAIL", "UNMEASURED", "UNAVAILABLE")
LIVE_VERDICTS = ("PASS", "FAIL")
MIN_KERNELS_FOR_MATRIX = 3


# ── row validation (shared by import and by the live run) ──────────────────


def validate_row(row: object) -> tuple[dict | None, str]:
    """Return (canonical_row, "") when row is a valid matrix cell, else
    (None, reason). Malformed input is rejected, never repaired."""
    if not isinstance(row, dict):
        return None, "row is not a JSON object"
    for field in ("kernel", "backend", "verdict", "captured", "evidence"):
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            return None, f"field {field!r} must be a non-empty string"
    if row["backend"] not in BACKENDS:
        return None, f"backend {row['backend']!r} not in {list(BACKENDS)}"
    if row["verdict"] not in VERDICTS:
        return None, f"verdict {row['verdict']!r} not in {list(VERDICTS)}"
    survival = row.get("survival_seconds")
    exit_code = row.get("exit_code")
    if row["verdict"] in LIVE_VERDICTS:
        if not isinstance(survival, (int, float)) or isinstance(survival, bool):
            return None, (
                f"verdict {row['verdict']} requires a numeric "
                f"survival_seconds, got {survival!r}"
            )
        if survival < 0:
            return None, f"survival_seconds must be >= 0, got {survival!r}"
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            return None, (
                f"verdict {row['verdict']} requires an integer exit_code, "
                f"got {exit_code!r}"
            )
    else:
        if survival is not None:
            return None, (
                f"verdict {row['verdict']} must carry survival_seconds=null, "
                f"got {survival!r}"
            )
        if exit_code is not None:
            return None, (
                f"verdict {row['verdict']} must carry exit_code=null, got {exit_code!r}"
            )
    canonical = {
        "kernel": row["kernel"].strip(),
        "backend": row["backend"],
        "verdict": row["verdict"],
        "survival_seconds": (
            float(survival) if row["verdict"] in LIVE_VERDICTS else None
        ),
        "exit_code": exit_code if row["verdict"] in LIVE_VERDICTS else None,
        "captured": row["captured"].strip(),
        "evidence": row["evidence"],
    }
    return canonical, ""


def load_import(path: pathlib.Path) -> tuple[list[dict], list[str]]:
    """Parse an imported evidence file; return (valid_rows, rejection_reasons).
    Malformed rows never enter the matrix — they are reported."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"{path.name}: unreadable JSON: {exc}"]
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        return [], [f"{path.name}: top-level object must carry a 'rows' array"]
    rows: list[dict] = []
    rejections: list[str] = []
    for index, raw in enumerate(payload["rows"]):
        row, reason = validate_row(raw)
        if row is None:
            rejections.append(f"{path.name}: rows[{index}]: {reason}")
        else:
            rows.append(row)
    if not rows and not rejections:
        rejections.append(f"{path.name}: 'rows' array is empty")
    return rows, rejections


# ── the current-host live cell ──────────────────────────────────────────────


def host_kernel() -> str:
    try:
        return (
            pathlib.Path("/proc/sys/kernel/osrelease")
            .read_text(encoding="ascii")
            .strip()
        )
    except OSError:
        return "unknown"


def _sleep300_pids() -> set[int]:
    out: set[int] = set()
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


def _cli_env(backend: str) -> dict[str, str]:
    env = dict(os.environ)
    env["TERMINAL_JAIL_JAIL_BACKEND"] = backend
    env["TERMINAL_JAIL_INTERRUPTOR_MODE"] = "disabled"
    return env


def _measured_row(
    backend: str,
    *,
    verdict: str,
    survival: float | None,
    exit_code: int | None,
    evidence: str,
) -> dict:
    row = {
        "kernel": host_kernel(),
        "backend": backend,
        "verdict": verdict,
        "survival_seconds": survival,
        "exit_code": exit_code,
        "captured": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "evidence": evidence,
    }
    canonical, reason = validate_row(row)
    assert canonical is not None, f"harness produced an invalid row: {reason}"
    return canonical


def run_backend_cell(backend: str) -> dict:
    """Measure one backend's orphan teardown on THIS host. Never guesses: a
    launch failure is UNAVAILABLE, a surviving payload is FAIL."""
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
        return _measured_row(
            backend,
            verdict="UNAVAILABLE",
            survival=None,
            exit_code=None,
            evidence=f"launcher could not start: {exc}",
        )
    payload: int | None = None
    t0 = time.monotonic()
    while time.monotonic() - t0 < LAUNCH_WAIT:
        new = _sleep300_pids() - before
        if new:
            payload = min(new)
            break
        time.sleep(0.05)
    if payload is None:
        launcher.kill()
        launcher.wait()
        return _measured_row(
            backend,
            verdict="UNAVAILABLE",
            survival=None,
            exit_code=launcher.returncode,
            evidence=(
                f"no 'sleep 300' payload appeared within {LAUNCH_WAIT:.0f}s; "
                "wrapper exited without launching the jail"
            ),
        )
    try:
        os.kill(launcher.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    tk = time.monotonic()
    survival: float | None = None
    while time.monotonic() - tk < TEARDOWN_BUDGET:
        if not pathlib.Path(f"/proc/{payload}").exists():
            survival = time.monotonic() - tk
            break
        time.sleep(PROC_POLL)
    launcher.wait()
    exit_code = launcher.returncode
    if survival is not None:
        return _measured_row(
            backend,
            verdict="PASS",
            survival=survival,
            exit_code=exit_code,
            evidence=(
                f"wrapper pid {launcher.pid} SIGKILLed; payload pid {payload} "
                f"(cmdline 'sleep 300', host-side, diffed against the "
                f"pre-launch /proc scan) disappeared in {survival * 1000:.0f} ms"
            ),
        )
    leftover = _sleep300_pids() - before
    try:
        # cleanup, not the contract: do not leave an orphan behind
        os.kill(payload, signal.SIGKILL)
    except ProcessLookupError:
        pass
    note = (
        f"leftover 'sleep 300' pids after cleanup: {sorted(leftover)}"
        if leftover
        else "payload reaped during cleanup"
    )
    return _measured_row(
        backend,
        verdict="FAIL",
        survival=TEARDOWN_BUDGET,
        exit_code=exit_code,
        evidence=(
            f"ORPHAN: payload pid {payload} survived the wrapper's SIGKILL "
            f"for the full {TEARDOWN_BUDGET:.0f}s budget; {note}"
        ),
    )


# ── matrix assembly (current-host rows + imported rows) ────────────────────


def matrix_summary(rows: list[dict]) -> dict:
    by_kernel: dict[str, dict[str, dict]] = {}
    for row in rows:
        by_kernel.setdefault(row["kernel"], {})[row["backend"]] = row
    complete_kernels: list[str] = []
    incomplete: list[str] = []
    failures: list[dict] = []
    for kernel in sorted(by_kernel):
        pair = by_kernel[kernel]
        missing = [b for b in BACKENDS if b not in pair]
        if missing:
            incomplete.append(f"{kernel} (missing: {', '.join(missing)})")
            continue
        measured = all(pair[b]["verdict"] in LIVE_VERDICTS for b in BACKENDS)
        if not measured:
            incomplete.append(f"{kernel} (cell not measured on the real kernel)")
            continue
        complete_kernels.append(kernel)
        for backend in BACKENDS:
            if pair[backend]["verdict"] == "FAIL":
                failures.append({"kernel": kernel, "backend": backend})
    return {
        "kernels_with_complete_measured_pair": complete_kernels,
        "incomplete_kernels": incomplete,
        "failures": failures,
        "matrix_green": (
            len(complete_kernels) >= MIN_KERNELS_FOR_MATRIX and not failures
        ),
        "min_kernels_required": MIN_KERNELS_FOR_MATRIX,
    }


# ── output ──────────────────────────────────────────────────────────────────


def _fmt_survival(row: dict) -> str:
    if row["survival_seconds"] is None:
        return "n/a"
    return f"{row['survival_seconds'] * 1000:.0f} ms"


def _fmt_exit(row: dict) -> str:
    return "n/a" if row["exit_code"] is None else str(row["exit_code"])


def print_human(rows: list[dict], summary: dict, *, show_raw: bool) -> None:
    this_kernel = host_kernel()
    print("kernel-matrix orphan teardown (TJ-DF-037)")
    print(
        f"this host: kernel {this_kernel}; rows below are MEASURED only for "
        "this kernel — other kernels appear only if imported"
    )
    print()
    header = (
        f"{'kernel':<16} {'backend':<8} {'verdict':<12} "
        f"{'survival':>10} {'exit':>5}  captured"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        marker = " (this host)" if row["kernel"] == this_kernel else ""
        print(
            f"{row['kernel']:<16} {row['backend']:<8} {row['verdict']:<12} "
            f"{_fmt_survival(row):>10} {_fmt_exit(row):>5}  "
            f"{row['captured']}{marker}"
        )
    print()
    print("summary:")
    complete = summary["kernels_with_complete_measured_pair"]
    print(
        f"  kernels with a complete measured bwrap+unshare pair: "
        f"{len(complete)}{': ' + ', '.join(complete) if complete else ''}"
    )
    for item in summary["incomplete_kernels"]:
        print(f"  incomplete kernel: {item}")
    for failure in summary["failures"]:
        print(
            f"  FAIL cell: {failure['kernel']} / {failure['backend']} — "
            "orphan survived; see docs/backend-parity.md"
        )
    if summary["matrix_green"]:
        print(
            f"  MATRIX GREEN for orphan teardown "
            f"(>= {summary['min_kernels_required']} kernels, all cells PASS)"
        )
    else:
        print(
            f"  MATRIX NOT GREEN: {len(complete)} complete kernel(s) "
            f"(need >= {summary['min_kernels_required']}) — a single-host run "
            "is never a matrix; import external cells for the other kernels"
        )
    if show_raw:
        print()
        print("raw evidence:")
        for row in rows:
            print(f"--- [{row['kernel']} / {row['backend']} / {row['verdict']}]")
            for line in row["evidence"].splitlines() or [""]:
                print(f"  {line}")


# ── TJ-DF-043 gate (CI cell) ────────────────────────────────────────────────


def gate_verdict(rows: list[dict]) -> tuple[str, str]:
    """TJ-DF-043 CI gate over live current-host rows.

    Returns (verdict, reason) with verdict exactly one of:
      PASS   every live current-host cell is PASS — teardown held here;
      FAIL   at least one live current-host cell is FAIL (an orphan was
             OBSERVED on this host — the containment defect is live);
      SKIP   no live current-host cell could launch (wrapper fail-closed:
             no namespaces, missing binaries — a HOST condition, and an
             unlaunchable wrapper cannot produce an orphan).

    A row from another kernel can never gate this host: only rows whose
    kernel equals host_kernel() are considered, and UNMEASURED/UNAVAILABLE
    rows carry no observed evidence by schema (validate_row enforces the
    nulls), so they classify as SKIP evidence, never as PASS.
    """
    this = host_kernel()
    live = [r for r in rows if r["kernel"] == this]
    if not live:
        return "SKIP", (
            f"no live cell for this host's kernel {this}: the wrapper failed "
            "closed (namespaces unavailable/absent binaries) — an unlaunchable "
            "wrapper produces no payload and no orphan; nothing to gate here"
        )
    failures = [r for r in live if r["verdict"] == "FAIL"]
    if failures:
        names = ", ".join(sorted({r["backend"] for r in failures}))
        return "FAIL", (
            f"orphan observed on this host ({this}): backend(s) {names} "
            "survived the wrapper's SIGKILL past the budget — TJ-DF-043 "
            "containment defect is LIVE here"
        )
    passing = [r for r in live if r["verdict"] == "PASS"]
    if len(passing) != len(live):
        return "SKIP", (
            f"current-host cells present but not all measured "
            f"({len(passing)}/{len(live)} PASS; the rest UNAVAILABLE/UNMEASURED) "
            "— no orphan was observed, but teardown was not fully proven either"
        )
    times = ", ".join(
        f"{r['backend']}={r['survival_seconds'] * 1000:.0f} ms" for r in passing
    )
    return "PASS", f"teardown held on {this} ({times})"


def run_gate() -> int:
    """Exit semantics of the TJ-DF-043 gate (the ONE gating surface):

    0 = PASS (teardown held) or SKIP (wrapper fail-closed on this host —
        recorded honestly, never counted as a pass);
    1 = FAIL (an orphan was observed: the defect is live on this kernel).
    """
    row = run_backend_cell("unshare")
    verdict, reason = gate_verdict([row])
    print(f"TJ-DF-043 teardown gate: {verdict} — {reason}")
    if verdict == "FAIL":
        print(f"  cell: {json.dumps(row)}", file=sys.stderr)
        return 1
    return 0


# ── offline, non-vacuous selftest ───────────────────────────────────────────

_VALID_ROW = {
    "kernel": "6.12.107",
    "backend": "unshare",
    "verdict": "FAIL",
    "survival_seconds": 15.0,
    "exit_code": -9,
    "captured": "2026-09-25T10:00:00+0000",
    "evidence": "ORPHAN: payload survived the wrapper's SIGKILL",
}

# One malformed arm per rule validate_row enforces; every arm MUST be
# rejected. mutation-control for the validator: if any arm is accepted (or
# the valid row rejected) the selftest exits 1 — a silent validator can
# never ship.
_MALFORMED_ARMS: list[dict] = [
    {**_VALID_ROW, "kernel": ""},
    {**_VALID_ROW, "kernel": None},
    {**_VALID_ROW, "kernel": "   "},
    {**_VALID_ROW, "backend": "bubblewrap"},
    {**_VALID_ROW, "backend": ""},
    {**_VALID_ROW, "verdict": "GREEN"},
    {**_VALID_ROW, "verdict": ""},
    # a claimed PASS without observed numbers
    {**_VALID_ROW, "verdict": "PASS", "survival_seconds": None},
    {**_VALID_ROW, "verdict": "PASS", "survival_seconds": "0.02"},
    {**_VALID_ROW, "verdict": "PASS", "survival_seconds": -1.0},
    {**_VALID_ROW, "verdict": "PASS", "exit_code": None},
    {**_VALID_ROW, "verdict": "PASS", "exit_code": "0"},
    # a no-data row that claims numbers
    {**_VALID_ROW, "verdict": "UNAVAILABLE", "survival_seconds": 0.5},
    {**_VALID_ROW, "verdict": "UNMEASURED", "exit_code": 0},
    {**_VALID_ROW, "verdict": "UNMEASURED", "survival_seconds": None, "exit_code": 3},
    {**_VALID_ROW, "captured": ""},
    {**_VALID_ROW, "evidence": ""},
    {**_VALID_ROW, "evidence": None},
]


def run_selftest() -> int:
    failures: list[str] = []
    row, reason = validate_row(_VALID_ROW)
    if row is None:
        failures.append(f"valid control row rejected: {reason}")
    for index, arm in enumerate(_MALFORMED_ARMS):
        row, reason = validate_row(arm)
        if row is not None:
            failures.append(f"arm {index} ACCEPTED but must be rejected: {arm!r}")
    # UNAVAILABLE can never be classified PASS: the validator refuses any
    # UNAVAILABLE row that carries live numbers, and the classifier only
    # emits PASS from an observed payload disappearance — prove the first
    # half here (the second half is the live cell's construction).
    unavailable_with_numbers = {
        **_VALID_ROW,
        "verdict": "UNAVAILABLE",
        "survival_seconds": 0.01,
        "exit_code": 0,
    }
    row, reason = validate_row(unavailable_with_numbers)
    if row is not None:
        failures.append("UNAVAILABLE row with numbers was accepted")
    if failures:
        print("SELFTEST FAIL:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(
        f"SELFTEST PASS: valid control accepted; {len(_MALFORMED_ARMS)} malformed arms rejected; UNAVAILABLE-with-numbers rejected"
    )
    return 0


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "This script executes ONLY on the host it runs on; it never "
            "pretends to execute a remote kernel. Attach external kernels "
            "via --import with raw output captured on that kernel."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable rows (JSON) instead of the human table",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="human mode: also print each row's raw evidence block",
    )
    parser.add_argument(
        "--import",
        dest="import_file",
        type=pathlib.Path,
        metavar="FILE",
        help=(
            "import external raw results (v1 schema, see --help header) and "
            "merge them into the matrix view; no remote execution happens"
        ),
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="offline parser/validator selftest (no jail launched)",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help=(
            "TJ-DF-043 CI gate: measure the unshare backend's orphan teardown "
            "on THIS host; exit 1 only when an orphan is OBSERVED, 0 on PASS "
            "or on an honest fail-closed SKIP (no namespaces/binary here)"
        ),
    )
    args = parser.parse_args()

    if args.selftest:
        return run_selftest()
    if args.gate:
        return run_gate()

    rejections: list[str] = []
    rows: list[dict] = []
    if args.import_file is not None:
        imported, rejections = load_import(args.import_file)
        rows.extend(imported)

    this_kernel = host_kernel()
    live_rows = [r for r in rows if r["kernel"] == this_kernel]
    for backend in BACKENDS:
        if not any(r["backend"] == backend for r in live_rows):
            rows.append(run_backend_cell(backend))
    # keep a deterministic order: kernel, then bwrap before unshare
    rows.sort(key=lambda r: (r["kernel"], BACKENDS.index(r["backend"])))
    summary = matrix_summary(rows)

    if rejections:
        for rejection in rejections:
            print(f"REJECTED: {rejection}", file=sys.stderr)
    if args.json:
        print(
            json.dumps(
                {
                    "this_host_kernel": this_kernel,
                    "rows": rows,
                    "import_rejections": rejections,
                    "summary": summary,
                },
                indent=2,
            )
        )
    else:
        print_human(rows, summary, show_raw=args.raw)
        if rejections:
            print(f"\n{len(rejections)} imported row(s) REJECTED (see stderr)")
    # House style (backend-parity-battery.py): a classifier never gates —
    # always exit 0; read the verdicts, not the exit status.
    return 0


if __name__ == "__main__":
    sys.exit(main())
