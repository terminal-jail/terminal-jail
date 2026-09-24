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
is spelled.

DF-TERMINAL-JAIL-15 — creatable is not usable. The mapped launch is NOT a
transparent rewrite: under that mapping the payload's host uid is the
caller's SUBUID (e.g. 100000), so DAC denies the caller's own repository and
HOME and an auto-sandboxed command silently loses the file it was given.
Namespace creation is therefore only the FIRST preflight;
`mapped_file_access_ok()` proves the property a transparent rewrite depends
on, by running inside the candidate launch and requiring the payload to read
a caller-owned mode-600 probe file it just wrote AND to write a probe file
in the caller's current working directory. `unshare_prefix()` returns the
mapped prefix only when both hold; otherwise it keeps the legacy
mapping-less flags (PID namespace + env scrub only) and — when the mapped
launch IS creatable and merely breaks the property — prints one LOUD
warning naming the degradation, its cause and the way out. The mapped launch
remains the explicit hard-isolation path (`terminal-jail --user`), where it
is preflighted exactly as before; the wrapper's probe script is
``scripts/fs-isolation-probe.py``.

TERMINAL_JAIL_UID_MAP=0|off|false forces the legacy mapping-less mode in
both the wrapper and this helper (parity) and silences the engine's
degradation warning.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable

# nobody/nogroup inside the namespace.
NOBODY_UID = 65534
NOBODY_GID = 65534

# Fallback subordinate-ID range start when /etc/subuid|/etc/subgid have no
# entry for the calling user (only meaningful if the preflight then passes).
DEFAULT_SUBID_START = 100000

# Legacy mapping-less flags: the historical TJ-DF-015-era launch. Identity
# display only — NO filesystem isolation (see module docstring).
LEGACY_USER_FLAGS = "--user --pid --fork --kill-child=SIGKILL"

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

# Probe budgets. A preflight that can hang is worse than no preflight: both
# probes are bounded and a timeout counts as FAILURE (fall back to legacy).
_PROBE_TIMEOUT = 15
_PROPERTY_TIMEOUT = 15

# The exact last line the property payload prints when BOTH file-access
# checks succeeded (read_rc=0: caller-owned mode-600 file readable;
# write_rc=0: probe file created in the caller's cwd), and the marker of the
# documented DF-TERMINAL-JAIL-15 capable-host case where BOTH are denied.
_PROPERTY_MARKER = "read_rc=0 write_rc=0"
_PROPERTY_DENIED_MARKER = "read_rc=1 write_rc=1"

# How a launch argv is executed. `_LAUNCH_RUNNER` is the test seam that lets
# a test simulate a host shape (namespace creation OK, file access broken)
# without owning a capable host; an explicit `runner=` argument overrides it
# per call. A runner returns the completed process, or None when the launch
# could not be run at all (missing binary, timeout, any launch error).
LaunchRunner = Callable[[list[str], int], subprocess.CompletedProcess[str] | None]
_LAUNCH_RUNNER: LaunchRunner | None = None


def _run_launch(
    argv: list[str], timeout: int, runner: LaunchRunner | None = None
) -> subprocess.CompletedProcess[str] | None:
    """Run one launch argv, bounded by timeout; None when it did not run.

    OSError (unshare missing) and SubprocessError (TimeoutExpired included)
    both mean "this launch cannot be trusted", which callers read as FAIL.
    """
    if runner is None:
        runner = _LAUNCH_RUNNER
    try:
        if runner is not None:
            return runner(argv, timeout)
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


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


def mapped_launch_ok(
    flags: str | None = None, *, runner: LaunchRunner | None = None
) -> bool:
    """Can this host CREATE the mapped launch? (first preflight only)

    Runs ``unshare <mapped flags> true`` — the probe result is
    representative because the flags are identical to the real launch.

    DF-TERMINAL-JAIL-15: this proves namespace creation and NOTHING about
    whether the payload can still reach the caller's files. A transparent
    rewrite must also pass `mapped_file_access_ok()`.
    """
    if flags is None:
        flags = mapped_user_flags()
    result = _run_launch(["unshare", *flags.split(), "true"], _PROBE_TIMEOUT, runner)
    return result is not None and result.returncode == 0


def _property_payload(secret_path: str, target_path: str) -> str:
    """Payload run INSIDE the candidate launch (fetches no external state).

    (a) read a caller-owned mode-600 file, (b) create a probe file in the
    caller's current working directory. Both outcomes are reported on one
    final line so the caller can assert them exactly.
    """
    return (
        f"cat {shlex.quote(secret_path)} >/dev/null 2>&1; read_rc=$?; "
        f"echo terminal-jail-file-access-probe > {shlex.quote(target_path)} "
        f"2>/dev/null; write_rc=$?; "
        f'echo "read_rc=$read_rc write_rc=$write_rc"'
    )


def _property_observation(
    flags: str | None = None,
    *,
    cwd: str | None = None,
    runner: LaunchRunner | None = None,
) -> str:
    """Run the property payload inside the candidate launch.

    Returns the payload's final marker line, or "" when the launch produced
    none (it never started, timed out, exited non-zero, or printed nothing)
    — so a caller can name the cause it OBSERVED instead of assuming one.
    """
    if flags is None:
        flags = mapped_user_flags()
    workdir = os.getcwd() if cwd is None else str(cwd)
    probe_dir = tempfile.mkdtemp(prefix="tj-fsaccess-")
    secret = os.path.join(probe_dir, "caller-600")
    target = os.path.join(workdir, f".tj-fsaccess-probe-{os.getpid()}")
    try:
        with open(secret, "w", encoding="utf-8") as handle:
            handle.write("terminal-jail file-access probe\n")
        os.chmod(secret, 0o600)
        result = _run_launch(
            [
                "unshare",
                *flags.split(),
                "bash",
                "-c",
                _property_payload(secret, target),
            ],
            _PROPERTY_TIMEOUT,
            runner,
        )
        if result is None or result.returncode != 0:
            return ""
        lines = (result.stdout or "").strip().splitlines()
        return lines[-1] if lines else ""
    except OSError:
        return ""
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)
        try:
            os.unlink(target)
        except OSError:
            pass


def mapped_file_access_ok(
    flags: str | None = None,
    *,
    cwd: str | None = None,
    runner: LaunchRunner | None = None,
) -> bool:
    """Does the candidate launch PRESERVE the caller's file access?

    The property that matters for a transparent rewrite: inside the launch
    the payload must be able to (a) read a caller-owned probe file the
    caller just created with mode 600 and (b) write a probe file in the
    caller's current working directory. Namespace creation alone is not
    evidence for either (DF-TERMINAL-JAIL-15: under the mapped launch the
    payload's host uid is the caller's subuid, so DAC denies both).

    Bounded and fail-closed: any launch error, non-zero exit, unexpected
    output or timeout scores as NOT usable. `cwd` defaults to the caller's
    current directory; `runner` overrides `_LAUNCH_RUNNER` for tests.
    """
    return _property_observation(flags, cwd=cwd, runner=runner) == _PROPERTY_MARKER


def _degradation_warning(observed: str) -> str:
    """One line naming the degradation, its cause and the way out.

    Same shape as the wrapper's warnings (standalone/terminal-jail): the
    leading `terminal-jail: WARNING: no filesystem isolation` marker is the
    one users and tests already look for. The cause is stated from the
    OBSERVED marker: the mapped launch that denies the caller's files reports
    `read_rc=1 write_rc=1` (the documented DF-TERMINAL-JAIL-15 capable-host
    case); any other marker is reported verbatim rather than attributed to
    the uid mapping.
    """
    subuid_start, subgid_start = subid_range_start()
    if observed == _PROPERTY_DENIED_MARKER:
        cause = (
            "the payload started through it cannot read the caller's own files"
            f" — its host uid becomes the subordinate uid {subuid_start}, so"
            " DAC denies the caller's repository and HOME"
        )
    else:
        cause = (
            "the file-access probe inside it did not report"
            f" {_PROPERTY_MARKER!r} (observed {observed or 'no marker'!r}): a"
            " usable launch must let the payload read a caller-owned mode-600"
            " file and write a probe file in the caller's current directory"
        )
    return (
        "terminal-jail: WARNING: no filesystem isolation — the transparent "
        "auto-sandbox fell back to the mapping-less PID namespace"
        f" ({LEGACY_USER_FLAGS}): this host CAN create the uid-mapped launch"
        f" ({mapped_user_flags(subuid_start, subgid_start)}), but"
        f" {cause} — an auto-sandboxed rewrite must never break the caller's"
        " file access (DF-TERMINAL-JAIL-15). Set"
        " TERMINAL_JAIL_UID_MAP=0 to make this mapping-less mode the explicit"
        " choice (it is also what silences this warning); use"
        " `terminal-jail --user` where the mapped hard-isolation launch is"
        " wanted; classify the host with scripts/fs-isolation-probe.py"
    )


def unshare_prefix() -> str:
    """The unshare prefix for auto-sandbox/modify rewrites.

    Selected on a PROVEN property, never on namespace creation alone
    (DF-TERMINAL-JAIL-15): the mapped launch is used only when the host can
    create it AND a payload launched that way can still read the caller's
    mode-600 files and write in the caller's cwd. Otherwise the legacy
    mapping-less prefix is used; when the mapped launch is creatable but
    fails the property, one loud warning names the degradation and the way
    out. TERMINAL_JAIL_UID_MAP=0|off|false still forces legacy. Cached for
    the process lifetime — mirrors the wrapper's one preflight.
    """
    global _DECISION
    if _DECISION is None:
        legacy = f"unshare {LEGACY_USER_FLAGS}{_PREFIX_SUFFIX}"
        observed: str | None = None
        if not uid_map_disabled() and mapped_launch_ok():
            observed = _property_observation()
        if observed == _PROPERTY_MARKER:
            _DECISION = f"unshare {mapped_user_flags()}{_PREFIX_SUFFIX}"
        else:
            if observed is not None:
                # Creatable but not file-access preserving: degrade LOUDLY,
                # naming the marker that was actually observed.
                print(_degradation_warning(observed), file=sys.stderr)
            _DECISION = legacy
    return _DECISION
