#!/usr/bin/env python3
"""Classify whether this host can run the Landlock filesystem tier.

TJ-GAP-082: the kernel-enforced filesystem tier for hosts where the
uid-mapped user namespace (TJ-DF-015) is unavailable. Landlock needs NO
user namespace and NO privileges — but the kernel must expose the LSM and
the ABI, and the tier must actually ENFORCE (not merely create a ruleset):
an applied Landlock domain is an allowlist model, so the probe proves the
property exactly like the tier does — inside a throwaway domain that
handles all FS rights and grants NOTHING, reading a caller-owned mode-600
fixture file must fail EACCES.

Verdicts:
- FULL: ABI present AND ruleset creation works AND the denied read was
  actually denied (kernel-enforced).
- DEGRADED: Landlock unusable, with the diagnosed cause (LSM not loaded,
  ABI absent, unknown architecture, syscall refusal) and a remediation
  pointer.
- UNKNOWN: probe error.

Also reports the highest Landlock ABI the kernel supports (max supported
via landlock_create_ruleset with LANDLOCK_CREATE_RULESET_VERSION).

Always exits 0: this is a classifier, like pidns-capability-probe.py and
fs-isolation-probe.py.

Usage:
    python3 scripts/landlock-capability-probe.py [--json]
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import json
import os
import platform
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Keep the syscall/ABI table in step with the engine module without
# importing it (the probe must run standalone, like the other probes).
_SYSCALL_NR: dict[str, tuple[int, int, int]] = {
    "x86_64": (444, 445, 446),
    "aarch64": (444, 445, 446),
}
LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
LANDLOCK_RULE_PATH_BENEATH = 1
_FS_ACCESS_BITS = tuple(1 << bit for bit in range(13))

_ETC_LSM = Path("/sys/kernel/security/lsm")


@dataclass
class ProbeResult:
    verdict: str
    abi_version: int = 0
    lsm_loaded: bool = False
    ruleset_ok: bool = False
    restrict_ok: bool = False
    enforcement: str = "not-tested"  # denied|allowed|not-tested
    cause: str = ""
    remediation: str = ""
    details: list[str] = field(default_factory=list)


def _libc() -> ctypes.CDLL | None:
    try:
        libc_name = ctypes.util.find_library("c") or "libc.so.6"
        return ctypes.CDLL(libc_name, use_errno=True)
    except OSError:
        return None


def _syscall(libc: ctypes.CDLL, nr: int, a: int = 0, b: int = 0, c: int = 0) -> int:
    fn = libc.syscall
    fn.argtypes = [ctypes.c_long] * 7
    fn.restype = ctypes.c_long
    return fn(nr, a, b, c, 0, 0, 0)


def _lsm_list() -> str:
    try:
        return _ETC_LSM.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _abi(libc: ctypes.CDLL | None) -> int:
    if libc is None:
        return 0
    numbers = _SYSCALL_NR.get(platform.machine())
    if numbers is None:
        return 0
    rv = _syscall(libc, numbers[0], 0, 0, LANDLOCK_CREATE_RULESET_VERSION)
    return rv if rv >= 1 else 0


class _RulesetAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


def _classify() -> ProbeResult:
    result = ProbeResult(verdict="UNKNOWN")
    machine = platform.machine()
    if machine not in _SYSCALL_NR:
        result.verdict = "DEGRADED"
        result.cause = f"unsupported architecture {machine}"
        result.remediation = (
            "add the generic syscall numbers for this architecture "
            "(linux/landlock.h lists 444-446 on every arch with the generic table)"
        )
        return result

    result.lsm_loaded = "landlock" in _lsm_list().split(",")

    libc = _libc()
    if libc is None:
        result.verdict = "DEGRADED"
        result.cause = "libc not loadable via ctypes"
        result.remediation = "run on a host with a working libc"
        return result

    result.abi_version = _abi(libc)
    if result.abi_version < 1:
        result.verdict = "DEGRADED"
        result.cause = (
            f"Landlock ABI absent (landlock_create_ruleset returned "
            f"{result.abi_version}; LSM list: "
            f"{_lsm_list() or 'unreadable'}{' — landlock NOT in the LSM list' if result.lsm_loaded is False else ''})"
        )
        result.remediation = (
            "boot a kernel with CONFIG_SECURITY_LANDLOCK=y and add 'landlock' "
            "to the lsm= boot parameter (or the LSM list), then re-probe"
        )
        return result

    # The mode-600 fixture is created BEFORE restrict_self — the domain is
    # allowlist-shaped, so anything created after it (temp dir, file)
    # would itself be denied (the probe's first run died exactly there).
    tmp = tempfile.mkdtemp(prefix="tj-landlock-probe-")
    secret = os.path.join(tmp, "secret600")
    with open(secret, "w", encoding="utf-8") as handle:
        handle.write("terminal-jail landlock probe\n")
    os.chmod(secret, 0o600)

    # Ruleset creation: handle ALL FS rights, grant NOTHING — the empty
    # allowlist domain is the probe's throwaway jail (also proves the
    # tier's exact creation path).
    attr = _RulesetAttr(sum(_FS_ACCESS_BITS))
    ctypes.set_errno(0)
    fd = _syscall(
        libc, _SYSCALL_NR[machine][0], ctypes.addressof(attr), ctypes.sizeof(attr), 0
    )
    if fd < 0:
        code = ctypes.get_errno()
        result.verdict = "DEGRADED"
        result.cause = (
            f"landlock_create_ruleset failed: {os.strerror(code)} (errno {code})"
        )
        result.remediation = (
            "check dmesg for landlock errors; verify the kernel was built "
            "with CONFIG_SECURITY_LANDLOCK=y"
        )
        _cleanup_tmp(tmp)
        return result
    result.ruleset_ok = True

    # PR_SET_NO_NEW_PRIVS, then landlock_restrict_self.
    prctl = libc.prctl
    prctl.restype = ctypes.c_int
    prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    ctypes.set_errno(0)
    if prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        code = ctypes.get_errno()
        os.close(fd)
        result.verdict = "DEGRADED"
        result.cause = f"PR_SET_NO_NEW_PRIVS failed: {os.strerror(code)} (errno {code})"
        result.remediation = "no_new_privs must be settable by an unprivileged caller"
        _cleanup_tmp(tmp)
        return result

    ctypes.set_errno(0)
    rv = _syscall(libc, _SYSCALL_NR[machine][2], fd, 0)
    if rv != 0:
        code = ctypes.get_errno()
        os.close(fd)
        result.verdict = "DEGRADED"
        result.cause = (
            f"landlock_restrict_self failed: {os.strerror(code)} (errno {code})"
        )
        result.remediation = (
            "restrict_self requires PR_SET_NO_NEW_PRIVS and a created ruleset"
        )
        _cleanup_tmp(tmp)
        return result
    result.restrict_ok = True
    os.close(fd)

    # PROPERTY proof (the TJ-DF-015 lesson: preflight the property, not a
    # proxy): inside the applied zero-grant domain, the pre-created
    # caller-owned mode-600 file must be DENIED (EACCES).
    try:
        try:
            with open(secret, "rb") as handle:
                handle.read(1)
            result.enforcement = "allowed"
            result.verdict = "DEGRADED"
            result.cause = (
                "ruleset created and restrict_self succeeded but the denied "
                "read was NOT denied — enforcement unproven"
            )
            result.remediation = (
                "this shape should not exist; report it with the probe "
                "output to the terminal-jail maintainers"
            )
        except PermissionError:
            result.enforcement = "denied"
            result.verdict = "FULL"
            result.details.append(
                "mode-600 read under the zero-grant domain denied EACCES"
            )
        except OSError as exc:
            result.enforcement = "unknown"
            result.verdict = "DEGRADED"
            result.cause = f"probe read failed with unexpected errno: {exc}"
            result.remediation = "inspect the fixture path and permissions"
    finally:
        _cleanup_tmp(tmp)
    return result


def _cleanup_tmp(tmp: str) -> None:
    try:
        for name in os.listdir(tmp):
            try:
                os.unlink(os.path.join(tmp, name))
            except OSError:
                pass
        os.rmdir(tmp)
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Landlock filesystem-tier capability classifier (always exits 0)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print one JSON object instead of the text report",
    )
    args = parser.parse_args()

    result = _classify()

    if args.json:
        print(
            json.dumps(
                {
                    "verdict": result.verdict,
                    "abi_version": result.abi_version,
                    "lsm_loaded": result.lsm_loaded,
                    "ruleset_ok": result.ruleset_ok,
                    "restrict_ok": result.restrict_ok,
                    "enforcement": result.enforcement,
                    "cause": result.cause,
                    "remediation": result.remediation,
                    "details": result.details,
                }
            )
        )
        return

    print(f"Landlock capability probe: {result.verdict}")
    print(f"  ABI version (max supported): {result.abi_version}")
    print(f"  landlock in /sys/kernel/security/lsm: {result.lsm_loaded}")
    print(f"  ruleset creation: {'ok' if result.ruleset_ok else 'failed'}")
    print(f"  restrict_self: {'ok' if result.restrict_ok else 'failed'}")
    print(f"  enforcement (mode-600 read under empty domain): {result.enforcement}")
    if result.cause:
        print(f"  cause: {result.cause}")
    if result.remediation:
        print(f"  remediation: {result.remediation}")
    for detail in result.details:
        print(f"  - {detail}")


if __name__ == "__main__":
    main()
