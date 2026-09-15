"""User-namespace launch flags shared by the wrapper contract and the engine.

TJ-DF-015: `unshare --user` WITHOUT a uid mapping is an unmapped-namespace
illusion — the process displays uid 65534 but keeps the caller's underlying
kuid for DAC, so it can still read the caller's mode-600 files and create
files in their home. Real filesystem isolation requires a MAPPED namespace:

    unshare --user --map-users=65534:<subuid_start>:1 \
            --map-groups=65534:<subgid_start>:1 -S 65534 -G 65534 ...

`-S`/`-G` (util-linux setuid/setgid inside the entered namespace, no
intermediate exec) are required: an intermediate setpriv exec clears the
namespace capability set and the mapping write fails on AppArmor hosts.

Some hosts (e.g. Ubuntu with the stock `unprivileged_userns` AppArmor
profile) deny setuid/setgid inside unprivileged user namespaces, so the
mapped launch cannot be created by an unprivileged caller no matter how it
is spelled. This module mirrors the standalone wrapper's preflight: probe
the mapped launch once per process; use it when it works, fall back to the
legacy mapping-less flags (PID namespace + env scrub only) with a LOUD
degradation otherwise. The wrapper's probe script is
``scripts/fs-isolation-probe.py``.

TERMINAL_JAIL_UID_MAP=0|off|false forces the legacy mapping-less mode in
both the wrapper and this helper (parity).
"""

from __future__ import annotations

import os
import subprocess

# nobody/nogroup inside the namespace.
NOBODY_UID = 65534
NOBODY_GID = 65534

# Fallback subordinate-ID range start when /etc/subuid|/etc/subgid have no
# entry for the calling user (only meaningful if the preflight then passes).
DEFAULT_SUBID_START = 100000

# Legacy mapping-less flags: the historical TJ-DF-015-era launch. Identity
# display only — NO filesystem isolation (see module docstring).
LEGACY_USER_FLAGS = (
    "--user --pid --fork --kill-child=SIGKILL"
)

# Mapped-launch template. The bash wrapper assembles the identical string
# (its --kill-child token comes from adjacent string literals there — do not
# inline that literal in the wrapper). Parity is pinned by test_userns.py.
_MAPPED_FLAGS_TEMPLATE = (
    "--user"
    " --map-users={nobody_uid}:{subuid_start}:1"
    " --map-groups={nobody_gid}:{subgid_start}:1"
    " -S {nobody_uid} -G {nobody_gid}"
    " --pid --fork --kill-child=SIGKILL"
)

_PREFIX_SUFFIX = " bash -c "

# One probe per process: the host's namespace policy does not change
# mid-process, and the bridge runs one process per evaluated command.
_DECISION: str | None = None


def uid_map_disabled() -> bool:
    """True when TERMINAL_JAIL_UID_MAP forces the legacy mode."""
    return os.environ.get("TERMINAL_JAIL_UID_MAP", "").strip().lower() in (
        "0",
        "off",
        "false",
    )


def _read_subid_start(path: str, username: str) -> int | None:
    """Read the subordinate-ID range start for username (first match)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                fields = line.strip().split(":")
                if len(fields) >= 2 and fields[0] == username:
                    try:
                        return int(fields[1])
                    except ValueError:
                        return None
    except OSError:
        return None
    return None


def subid_range_start(username: str | None = None) -> tuple[int, int]:
    """(subuid_start, subgid_start) for the calling user.

    Falls back to DEFAULT_SUBID_START per value when the file is absent,
    unreadable, or has no entry for the user. Callers must still preflight
    the resulting flags before trusting them.
    """
    if username is None:
        try:
            import pwd

            username = pwd.getpwuid(os.geteuid()).pw_name
        except (ImportError, KeyError):
            username = ""
    subuid = _read_subid_start("/etc/subuid", username)
    subgid = _read_subid_start("/etc/subgid", username)
    return (
        subuid if subuid is not None else DEFAULT_SUBID_START,
        subgid if subgid is not None else DEFAULT_SUBID_START,
    )


def mapped_user_flags(
    subuid_start: int | None = None, subgid_start: int | None = None
) -> str:
    """The mapped launch flag string (single source of truth for parity)."""
    if subuid_start is None or subgid_start is None:
        d_uid, d_gid = subid_range_start()
        subuid_start = subuid_start if subuid_start is not None else d_uid
        subgid_start = subgid_start if subgid_start is not None else d_gid
    return _MAPPED_FLAGS_TEMPLATE.format(
        nobody_uid=NOBODY_UID,
        nobody_gid=NOBODY_GID,
        subuid_start=subuid_start,
        subgid_start=subgid_start,
    )


def legacy_user_flags() -> str:
    """The legacy mapping-less flag string."""
    return LEGACY_USER_FLAGS


def mapped_launch_ok(flags: str | None = None) -> bool:
    """Preflight the mapped launch exactly like the wrapper does.

    Runs ``unshare <mapped flags> true`` — the probe result is
    representative because the flags are identical to the real launch.
    """
    if flags is None:
        flags = mapped_user_flags()
    try:
        result = subprocess.run(
            ["unshare", *flags.split(), "true"],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def unshare_prefix() -> str:
    """The unshare prefix for auto-sandbox/modify rewrites.

    Mapped prefix when the host permits the mapped launch (and
    TERMINAL_JAIL_UID_MAP does not disable it), legacy prefix otherwise.
    Cached for the process lifetime — mirrors the wrapper's one preflight.
    """
    global _DECISION
    if _DECISION is None:
        if uid_map_disabled() or not mapped_launch_ok():
            _DECISION = f"unshare {LEGACY_USER_FLAGS}{_PREFIX_SUFFIX}"
        else:
            _DECISION = f"unshare {mapped_user_flags()}{_PREFIX_SUFFIX}"
    return _DECISION
