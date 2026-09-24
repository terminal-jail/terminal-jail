#!/usr/bin/env python3
"""Classify, per host, which staged systemd directives it accepts AND enforces.

TJ-GAP-052. specs/systemd.md ships the gateway hardening drop-in as a
lightweight baseline (4 active directives) and stages the stronger profile
commented out in systemd/90-terminal-jail-hardening.conf, because those
directives "require per-host verification" and must be verified "on the actual
target, not only in a development container". This probe performs that
verification using ONLY throwaway transient units: it launches each directive
with `systemd-run --wait --collect`, has the payload observe its own
sandbox state, and classifies the observation.

Verdicts (one per directive):

- ENFORCED:      systemd accepted the directive AND the payload observed the
                 effect (e.g. NoNewPrivs: 1, pids.max == 256, /usr read-only).
- NOT_ENFORCED:  the unit ran but the effect was NOT observed; the evidence
                 line records what was observed instead. A directive that is
                 pre-restricted on the host anyway (baseline == with-directive
                 behaviour) is classified NOT_ENFORCED-with-note via its
                 evidence, because the directive adds nothing there.
- UNSUPPORTED:   systemd rejected the directive at load (stderr matches
                 "Unknown assignment" / "Unknown lvalue" / "Failed to load").
                 CloseOnExec=true is the shipped negative control:
                 specs/systemd.md documents it as NOT a valid service
                 hardening directive, so it must classify UNSUPPORTED
                 (NOT_ENFORCED if a manager somehow accepts it, UNKNOWN on
                 other failures) — never ENFORCED.
- UNKNOWN:       systemd-run is missing, the run timed out, the scope is
                 unavailable, or the evidence could not be interpreted.

Scope selection (--scope): "user" probes through the caller's systemd user
manager; "system" probes through the system manager via `sudo -n systemd-run`
(passwordless sudo only — never prompts). "auto" (default) prefers the user
scope and falls back to the system scope only when the user manager is
unavailable; auto never silently requires sudo.

LIVE FINDING (verified on karaHermes-mde-7840hs, 2026-09-15): the user scope
under-enforces mount-namespace directives. ProtectHome=true and
ProtectSystem=strict are accepted but leave /home visible and / writable in
the user scope while the system scope hides the home and makes the root mount
read-only; ProtectProc=invisible (hidepid) and ProtectControlGroups=true
(read-only cgroup mount) likewise only take effect in the system scope.
Accept-but-not-enforce in user scope is a real host property this probe
surfaces, not a probe bug.

Always exits 0: this is a classifier for operators and docs, not a gate.

Safety contract (grep-verifiable):
- Only throwaway TRANSIENT units: every run uses --wait --collect and a unique
  unit name (tj-probe-<pid>-<random>), so parallel runs never collide and
  nothing persists after the run.
- The gateway service unit is never referenced or manipulated in any way; no
  systemctl verb of any kind is used.
- Nothing is written under system-configuration directories; no drop-in is
  installed; the manager is never asked to reload anything.
- The only filesystem write in any payload is one probe file inside a
  tempfile.mkdtemp() directory (ReadWritePaths/ProtectSystem probe), removed
  afterwards.
- No shell-string execution with interpolated host data: argv lists only.

Usage:
    python3 scripts/systemd-directive-probe.py              # plain text
    python3 scripts/systemd-directive-probe.py --json       # machine-readable
    python3 scripts/systemd-directive-probe.py --scope system --directive ProtectHome
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import string
import subprocess
import sys
import tempfile
from collections.abc import Callable

# Rejection markers: systemd prints these when it refuses a directive at load.
_REJECT_MARKERS = ("Unknown assignment", "Unknown lvalue", "Failed to load")
_UNIT_PREFIX = "tj-probe"


def _uniq_unit() -> str:
    """A unique transient-unit name so parallel probes never collide."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{_UNIT_PREFIX}-{os.getpid()}-{suffix}"


# ── payload evidence helpers ───────────────────────────────────────────

_CGDIR = "/sys/fs/cgroup$(cat /proc/self/cgroup | cut -d: -f3)"

# payload: single /bin/sh -c string. Reference implementations follow the
# live-verified facts in the task brief (TJ-GAP-052); ProtectProc,
# ProtectControlGroups and ProtectSystem observe /proc/self/mountinfo instead
# of writing to host paths.
_PAYLOADS: dict[str, tuple[str | None, str]] = {
    "ProtectProc": (
        "ProtectProc=invisible",
        'echo PROC_$(grep " /proc " /proc/self/mountinfo | head -1)',
    ),
    "NoNewPrivileges": (
        "NoNewPrivileges=true",
        "echo NoNewPrivs_$(grep NoNewPrivs /proc/self/status | awk '{print $2}')",
    ),
    "ProtectControlGroups": (
        "ProtectControlGroups=true",
        'awk \'$5=="/sys/fs/cgroup" {print "CGOPTS_"$6}\' /proc/self/mountinfo | head -1',
    ),
    "TasksMax": (
        "TasksMax=256",
        f"echo PIDS_MAX_$(cat {_CGDIR}/pids.max)",
    ),
    "PrivateUsers": (
        "PrivateUsers=true",
        "cat /proc/self/uid_map; echo EUID_$(id -u)",
    ),
    "RestrictNamespaces": (
        "RestrictNamespaces=true",
        "unshare --user --pid true 2>/dev/null; echo RNS_RC=$?",
    ),
    "CapabilityBoundingSet": (
        "CapabilityBoundingSet=",
        "echo CAPBND_$(grep CapBnd /proc/self/status | awk '{print $2}')",
    ),
    "RestrictAddressFamilies": (
        "RestrictAddressFamilies=~AF_INET AF_INET6 AF_NETLINK",
        # AF_UNIX is the negative control inside the payload: it must stay
        # creatable, proving the deny-list (not a broken interpreter) is what
        # refused AF_INET.
        (
            'python3 -c "import socket; socket.socket(socket.AF_UNIX)"; '
            "echo UNIX_RC=$?; "
            'python3 -c "import socket; socket.socket(socket.AF_INET)" 2>/dev/null; '
            "echo INET_RC=$?; "
            'python3 -c "import socket; socket.socket(socket.AF_UNIX)" 2>/dev/null '
            "&& echo RAF_UNIX_OK"
        ),
    ),
    "ProtectSystem": (
        "ProtectSystem=strict",
        # Observe mount options, do not WRITE to /usr: test -w is false for
        # any non-root caller even without the directive.
        (
            'awk \'$5=="/" {print "ROOT_OPTS_"$6} $5=="/usr" {print "USR_OPTS_"$6}\' '
            "/proc/self/mountinfo"
        ),
    ),
    "ProtectHome": (
        "ProtectHome=true",
        'test -e "$HOME" && echo HOME_VISIBLE || echo HOME_HIDDEN',
    ),
    "MemoryMax": (
        "MemoryMax=1G",
        f"echo MEM_MAX_$(cat {_CGDIR}/memory.max)",
    ),
    # CloseOnExec=true: the negative control. specs/systemd.md documents it as
    # NOT a valid service-hardening directive; a correct manager rejects it at
    # load ("Unknown assignment") and this probe must classify UNSUPPORTED.
    "CloseOnExec": (
        "CloseOnExec=true",
        "true",
    ),
}

_ALL_DIRECTIVES = [
    "ProtectProc",
    "NoNewPrivileges",
    "ProtectControlGroups",
    "TasksMax",
    "PrivateUsers",
    "RestrictNamespaces",
    "CapabilityBoundingSet",
    "RestrictAddressFamilies",
    "ProtectSystem",
    "ProtectHome",
    "MemoryMax",
    "ReadWritePaths",
    "CloseOnExec",
]


# ── verdict parsing ────────────────────────────────────────────────────


def _field(stdout: str, prefix: str) -> str | None:
    """First line of stdout carrying `prefix`, stripped of the prefix."""
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


# Each judge receives the run's stdout/stderr/returncode and the scope used,
# and returns (verdict, evidence). Judged against the live-verified facts:
# system scope must classify the profile's directives ENFORCED; user scope
# honestly reports under-enforcement (ProtectHome etc.).
_Judge = Callable[[str, str, int, str], tuple[str, str]]


def _judge_no_new_privs(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    value = _field(out, "NoNewPrivs_")
    if value is None:
        return "UNKNOWN", f"no NoNewPrivs evidence (rc={rc}, stderr={err.strip()!r})"
    if value == "1":
        return "ENFORCED", "NoNewPrivs: 1"
    return "NOT_ENFORCED", f"observed NoNewPrivs: {value} ({scope} scope)"


def _judge_tasks_max(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    value = _field(out, "PIDS_MAX_")
    if value is None:
        return "UNKNOWN", f"no pids.max evidence (rc={rc}, stderr={err.strip()!r})"
    if value == "256":
        return "ENFORCED", "pids.max = 256"
    return "NOT_ENFORCED", f"observed pids.max = {value}, requested 256 ({scope} scope)"


def _judge_memory_max(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    value = _field(out, "MEM_MAX_")
    if value is None:
        return "UNKNOWN", f"no memory.max evidence (rc={rc}, stderr={err.strip()!r})"
    if value == "1073741824":
        return "ENFORCED", "memory.max = 1073741824 (1G)"
    return "NOT_ENFORCED", (
        f"observed memory.max = {value}, requested 1073741824 ({scope} scope)"
    )


def _judge_private_users(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    # uid_map rows are space-indented; strip before testing the first char.
    lines = [
        ln.split() for ln in out.splitlines() if ln.strip() and ln.strip()[0].isdigit()
    ]
    euid = _field(out, "EUID_")
    if not lines:
        return "UNKNOWN", f"no uid_map evidence (rc={rc}, stderr={err.strip()!r})"
    first = lines[0]
    if len(first) == 3 and first[0] == "0" and first[1] == "0" and int(first[2]) > 1:
        # Unmapped identity range: the namespace never applied a mapping.
        return "NOT_ENFORCED", (
            f"observed uid_map '{' '.join(first)}' (unmapped, euid={euid}) "
            f"({scope} scope)"
        )
    return "ENFORCED", f"uid_map '{' '.join(first)}' (euid={euid})"


def _judge_restrict_namespaces(
    out: str, err: str, rc: int, scope: str
) -> tuple[str, str]:
    observed = _field(out, "RNS_RC=")
    if observed is None:
        return "UNKNOWN", f"no unshare evidence (rc={rc}, stderr={err.strip()!r})"
    if observed != "0":
        return "ENFORCED", f"unshare --user --pid denied (rc={observed})"
    return "NOT_ENFORCED", f"observed unshare --user --pid rc=0 ({scope} scope)"


def _judge_capability_bounding(
    out: str, err: str, rc: int, scope: str
) -> tuple[str, str]:
    value = _field(out, "CAPBND_")
    if value is not None:
        if set(value) == {"0"}:
            return "ENFORCED", "CapBnd: 0000000000000000"
        return "NOT_ENFORCED", f"observed CapBnd: {value} ({scope} scope)"
    # User-scope managers often kill the unit instead: status=218/CAPABILITIES.
    blob = (err or "") + (out or "")
    if "218/CAPABILITIES" in blob or "CAPABILITIES" in blob:
        return "NOT_ENFORCED", (
            f"unit died with status 218/CAPABILITIES before producing evidence "
            f"({scope} scope); bounding set not observable in this scope"
        )
    return "UNKNOWN", f"no CapBnd evidence (rc={rc}, stderr={err.strip()!r})"


def _judge_address_families(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    unix_rc = _field(out, "UNIX_RC=")
    inet_rc = _field(out, "INET_RC=")
    if inet_rc is None:
        return "UNKNOWN", f"no socket evidence (rc={rc}, stderr={err.strip()!r})"
    if "RAF_UNIX_OK" not in out:
        return "UNKNOWN", (
            "AF_UNIX control failed — payload interpreter broken, no verdict"
        )
    if inet_rc != "0":
        return (
            "ENFORCED",
            f"AF_INET socket denied (rc={inet_rc}); AF_UNIX ok (rc={unix_rc})",
        )
    return "NOT_ENFORCED", (
        f"observed AF_INET socket allowed (rc=0), deny-list not applied ({scope} scope)"
    )


def _judge_protect_proc(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    line = _field(out, "PROC_")
    if line is None:
        return (
            "UNKNOWN",
            f"no /proc mountinfo evidence (rc={rc}, stderr={err.strip()!r})",
        )
    if "hidepid=invisible" in line:
        return "ENFORCED", f"/proc mount: {line}"
    return "NOT_ENFORCED", (
        f"observed /proc mount without hidepid ({scope} scope): {line}"
    )


def _judge_protect_control_groups(
    out: str, err: str, rc: int, scope: str
) -> tuple[str, str]:
    opts = _field(out, "CGOPTS_")
    if opts is None:
        return (
            "UNKNOWN",
            f"no cgroup mountinfo evidence (rc={rc}, stderr={err.strip()!r})",
        )
    if "ro" in opts.split(","):
        return "ENFORCED", f"/sys/fs/cgroup mounted read-only ({opts})"
    return "NOT_ENFORCED", (f"observed writable cgroup mount ({scope} scope): {opts}")


def _judge_protect_system(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    root = _field(out, "ROOT_OPTS_")
    usr = _field(out, "USR_OPTS_")
    if root is None and usr is None:
        return "UNKNOWN", f"no mountinfo evidence (rc={rc}, stderr={err.strip()!r})"
    root_ro = root is not None and "ro" in root.split(",")
    usr_ro = usr is not None and "ro" in usr.split(",")
    if root_ro or usr_ro:
        detail = f"root mount opts={root}" + (f", /usr opts={usr}" if usr else "")
        return "ENFORCED", f"/ and /usr read-only under strict: {detail}"
    return "NOT_ENFORCED", (
        f"observed writable filesystem under strict ({scope} scope): "
        f"root opts={root}, /usr opts={usr}"
    )


def _judge_protect_home(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    token = (
        "HOME_HIDDEN"
        if "HOME_HIDDEN" in out
        else ("HOME_VISIBLE" if "HOME_VISIBLE" in out else None)
    )
    if token is None:
        return (
            "UNKNOWN",
            f"no home-visibility evidence (rc={rc}, stderr={err.strip()!r})",
        )
    if token == "HOME_HIDDEN":
        return "ENFORCED", "$HOME not visible inside the unit"
    return "NOT_ENFORCED", (
        f"observed $HOME VISIBLE inside the unit ({scope} scope) — user "
        f"managers cannot bind-mount over /home; system scope enforces this"
    )


def _judge_carve_out(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    if "TMP_WRITE_OK" in out:
        return "ENFORCED", "ReadWritePaths carve-out writable inside read-only unit"
    if "TMP_WRITE_FAIL" in out:
        return "NOT_ENFORCED", (
            f"observed ReadWritePaths carve-out NOT writable ({scope} scope)"
        )
    return "UNKNOWN", f"no carve-out evidence (rc={rc}, stderr={err.strip()!r})"


def _judge_close_on_exec(out: str, err: str, rc: int, scope: str) -> tuple[str, str]:
    # Reached only when the manager ACCEPTED the directive (a non-rejecting
    # manager). It is still not a hardening control, so this must never be
    # ENFORCED; accept-but-inert is honestly NOT_ENFORCED.
    return "NOT_ENFORCED", (
        f"manager accepted CloseOnExec=true (rc={rc}) but it is not a valid "
        f"service-hardening directive (specs/systemd.md negative control)"
    )


_JUDGES: dict[str, _Judge] = {
    "ProtectProc": _judge_protect_proc,
    "NoNewPrivileges": _judge_no_new_privs,
    "ProtectControlGroups": _judge_protect_control_groups,
    "TasksMax": _judge_tasks_max,
    "PrivateUsers": _judge_private_users,
    "RestrictNamespaces": _judge_restrict_namespaces,
    "CapabilityBoundingSet": _judge_capability_bounding,
    "RestrictAddressFamilies": _judge_address_families,
    "ProtectSystem": _judge_protect_system,
    "ProtectHome": _judge_protect_home,
    "MemoryMax": _judge_memory_max,
    "CloseOnExec": _judge_close_on_exec,
}


# ── probe engine ───────────────────────────────────────────────────────


class _Run:
    """Result of one transient-unit launch."""

    def __init__(self, stdout: str, stderr: str, returncode: int):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _launch(
    systemd_run: str,
    scope: str,
    props: list[str],
    payload: str,
    timeout: int,
) -> _Run | None:
    """Launch ONE throwaway transient unit. Returns None on timeout."""
    argv = []
    if scope == "system":
        # sudo -n: passwordless only — validated by the caller beforehand.
        argv += ["sudo", "-n"]
    argv.append(systemd_run)
    if scope == "user":
        argv.append("--user")
    # --pipe: payload stdout/stderr come back on OUR streams (without it they
    # go to the journal). --wait --collect: reap and garbage-collect the unit.
    argv += ["--pipe", "--wait", "--collect", f"--unit={_uniq_unit()}"]
    for prop in props:
        argv += ["-p", prop]
    argv += ["/bin/sh", "-c", payload]
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    return _Run(result.stdout or "", result.stderr or "", result.returncode)


def _rejected_at_load(run: _Run) -> bool:
    return any(marker in run.stderr for marker in _REJECT_MARKERS)


def _probe_one(
    name: str,
    systemd_run: str,
    scope: str,
    timeout: int,
) -> tuple[str, str]:
    if name == "ReadWritePaths":
        return _probe_read_write_paths(systemd_run, scope, timeout)
    payload = _PAYLOADS[name][1]
    run = _launch(systemd_run, scope, [_PAYLOADS[name][0]], payload, timeout)
    if run is None:
        return "UNKNOWN", f"transient unit timed out after {timeout}s"
    if _rejected_at_load(run):
        first = run.stderr.strip().splitlines()[0]
        if name == "CloseOnExec":
            return "UNSUPPORTED", (
                f"{first!r} — rejected at load (negative control per "
                f"specs/systemd.md: not a valid service-hardening directive)"
            )
        return "UNSUPPORTED", f"rejected at load: {first!r}"
    return _JUDGES[name](run.stdout, run.stderr, run.returncode, scope)


def _probe_read_write_paths(
    systemd_run: str,
    scope: str,
    timeout: int,
) -> tuple[str, str]:
    """Probe ReadWritePaths= together with ProtectSystem=strict.

    Creates one temp dir (the ONLY filesystem write this probe performs in a
    payload), asks the unit to write a probe file into it, and removes the
    directory afterwards.
    """
    tmp = tempfile.mkdtemp(prefix="tj-probe-rwp-")
    try:
        props = ["ProtectSystem=strict", f"ReadWritePaths={tmp}"]
        payload = (
            f"echo PROBE > '{tmp}/write-test' 2>/dev/null"
            " && echo TMP_WRITE_OK || echo TMP_WRITE_FAIL"
        )
        run = _launch(systemd_run, scope, props, payload, timeout)
        if run is None:
            return "UNKNOWN", f"transient unit timed out after {timeout}s"
        if _rejected_at_load(run):
            return (
                "UNSUPPORTED",
                f"rejected at load: {run.stderr.strip().splitlines()[0]!r}",
            )
        return _judge_carve_out(run.stdout, run.stderr, run.returncode, scope)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _resolve_scope(requested: str, systemd_run: str) -> tuple[str, str | None]:
    """Pick the manager to probe. Returns (scope, note-or-None).

    auto prefers the user scope and falls back to system ONLY when the user
    manager is genuinely unavailable — auto must never silently require sudo.
    """
    if requested != "auto":
        return requested, None
    probe = _launch(systemd_run, "user", [], "true", timeout=15)
    if probe is not None and probe.returncode == 0:
        return "user", None
    detail = "unavailable"
    if probe is not None:
        first = probe.stderr.strip().splitlines()
        detail = first[0] if first else f"rc={probe.returncode}"
    return "system", f"user scope unavailable ({detail}); fell back to system scope"


# ── CLI ────────────────────────────────────────────────────────────────


def probe_directives(
    directives: list[str],
    systemd_run: str,
    scope_req: str,
    timeout: int,
) -> tuple[list[dict[str, str]], str | None]:
    """Classify each requested directive. Returns (records, scope-note)."""
    records: list[dict[str, str]] = []
    note: str | None = None

    if not os.path.isfile(systemd_run) or not os.access(systemd_run, os.X_OK):
        for name in directives:
            records.append(
                {
                    "directive": name,
                    "value": _PAYLOADS[name][0],
                    "scope": "none",
                    "verdict": "UNKNOWN",
                    "evidence": f"systemd-run not found at {systemd_run!r}",
                }
            )
        return records, None

    scope, note = _resolve_scope(scope_req, systemd_run)
    if scope == "system":
        # sudo -n: passwordless only. If sudo would prompt, the scope is
        # unavailable — auto never escalates interactively.
        sudo = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if sudo.returncode != 0:
            for name in directives:
                records.append(
                    {
                        "directive": name,
                        "value": _PAYLOADS[name][0],
                        "scope": "none",
                        "verdict": "UNKNOWN",
                        "evidence": (
                            "system scope unavailable: passwordless sudo refused "
                            f"({(sudo.stderr or sudo.stdout).strip()!r})"
                        ),
                    }
                )
            return records, note

    for name in directives:
        if name == "ReadWritePaths":
            value_str = "ReadWritePaths=<tempdir>"
        else:
            value_str = _PAYLOADS[name][0]
        verdict, evidence = _probe_one(name, systemd_run, scope, timeout)
        records.append(
            {
                "directive": name,
                "value": value_str,
                "scope": scope,
                "verdict": verdict,
                "evidence": evidence,
            }
        )
    return records, note


def _scope_argv(scope: str) -> list[str]:
    """Prefix for reporting which manager each unit ran under."""
    return ["sudo -n"] if scope == "system" else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-host classifier for staged systemd directives "
        "(throwaway transient units only; always exits 0).",
        epilog="Verdicts: ENFORCED / NOT_ENFORCED / UNSUPPORTED / UNKNOWN "
        "(see module docstring). Scope auto prefers the user manager and "
        "never silently requires sudo.",
    )
    parser.add_argument(
        "--systemd-run",
        default="/usr/bin/systemd-run",
        help="path to the systemd-run binary (default: %(default)s; override "
        "for offline tests)",
    )
    parser.add_argument(
        "--scope",
        choices=("user", "system", "auto"),
        default="auto",
        help="which manager to probe (default: auto = user first, system "
        "fallback only when the user manager is unavailable)",
    )
    parser.add_argument(
        "--directive",
        action="append",
        choices=_ALL_DIRECTIVES,
        dest="directives",
        help="restrict the probe to one directive (repeatable; default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a JSON report on stdout (nothing else on stdout)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="per-directive timeout in seconds (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    directives = args.directives if args.directives else _ALL_DIRECTIVES
    records, note = probe_directives(
        directives, args.systemd_run, args.scope, args.timeout
    )
    scope = records[0]["scope"] if records else "none"

    counts = {v: 0 for v in ("ENFORCED", "NOT_ENFORCED", "UNSUPPORTED", "UNKNOWN")}
    for record in records:
        counts[record["verdict"]] += 1

    if args.json:
        report = {
            "scope": scope,
            "summary": {
                "total": len(records),
                **counts,
            },
            "records": records,
        }
        if note:
            report["note"] = note
        print(json.dumps(report, indent=2))
        return 0

    for record in records:
        prefix = " ".join(_scope_argv(record["scope"]))
        location = (
            f" ({prefix} {record['scope']})" if prefix else f" ({record['scope']})"
        )
        print(
            f"{record['verdict']:<13} {record['value']}{location}: {record['evidence']}"
        )
    print(
        f"SUMMARY: scope={scope} enforced={counts['ENFORCED']} "
        f"not_enforced={counts['NOT_ENFORCED']} "
        f"unsupported={counts['UNSUPPORTED']} unknown={counts['UNKNOWN']} "
        f"of={len(records)}"
    )
    if note:
        print(f"NOTE: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
