#!/usr/bin/env python3
"""Classify whether `terminal-jail --user` gets REAL filesystem isolation.

TJ-DF-015: `unshare --user` without a uid mapping is an unmapped-namespace
illusion — `id` displays 65534 but the process keeps the caller's underlying
kuid, so mode-600 files stay readable and home files stay writable. Real
isolation requires a MAPPED launch:

    unshare --user --map-users=65534:<subuid_start>:1 \\
            --map-groups=65534:<subgid_start>:1 -S 65534 -G 65534 ...

This probe actually exercises that launch in a throwaway namespace and runs
two acceptance checks INSIDE it:

  (1) read a caller-owned mode-600 temp file,
  (2) create a file in the caller's HOME.

Both must fail (EACCES/EPERM) for FULL; any success is DEGRADED. On
degradation the likely cause is diagnosed in order: missing
newuidmap/newgidmap; no /etc/subuid|/etc/subgid entry for the caller; the
mapped launch failing while the legacy one succeeds (uid-mapping denied —
the AppArmor `unprivileged_userns` setuid/setgid denial is named when the
error text matches, and kernel.apparmor_restrict_unprivileged_userns is
reported when readable).

Always exits 0: this is a classifier, like pidns-capability-probe.py.

JAIL-AWARE verdict (DF-TERMINAL-JAIL-18): when the probe detects that IT is
itself running under a terminal-jail launch (the env markers the wrapper
exports into a jailed process, or a multi-value NSpid in /proc/self/status —
the auto-sandbox modify path exports no env markers), it does not attempt
the nested mapped launch: unshare cannot create the child namespace the
probe needs from inside an existing one, and on this shape the probe's
chmod of its mode-600 fixture fails with EINVAL before any check runs,
which was delivered as a misleading UNKNOWN. Instead it reports the
wrapper-observed isolation state (TERMINAL_JAIL_FS_ISOLATION when the
surrounding launch exported it) with an explicit caveat that this is the
wrapper's preflight observation, not this probe's own classification, and
prints guidance to run the probe directly for the full outer-host verdict.

Usage:
    python3 scripts/fs-isolation-probe.py
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

NOBODY = 65534
DEFAULT_SUBID_START = 100000

# DF-TERMINAL-JAIL-18: env markers the wrapper exports INTO a jailed process
# (TERMINAL_JAIL_FS_ISOLATION on --user launches, TERMINAL_JAIL_SECCOMP under
# --seccomp). The auto-sandbox (modify) path exports none of them, so env
# alone cannot detect that launch shape — the NSpid signal below covers it.
_JAIL_ENV_MARKERS = ("TERMINAL_JAIL_FS_ISOLATION", "TERMINAL_JAIL_SECCOMP")


def _nspid_values() -> list[str]:
    """The NSpid values from /proc/self/status.

    Exactly one value when this process sits in the init PID namespace (a
    direct, unjailed run); two or more (outer pid + inner pid) when the
    process is inside a PID namespace — the signature of every terminal-jail
    launch shape, including auto-sandbox modify which leaves no env marker.
    Test seam: tests monkeypatch this to simulate both contexts offline.
    """
    try:
        with open("/proc/self/status", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("NSpid:"):
                    return line.split()[1:]
    except OSError:
        pass
    return []


def _inside_terminal_jail() -> bool:
    """True when this probe is itself running under a terminal-jail launch."""
    for marker in _JAIL_ENV_MARKERS:
        if os.environ.get(marker):
            return True
    return len(_nspid_values()) > 1


def _jail_aware_verdict() -> str:
    """Honest classification when the probe runs under its own jail.

    Reports the wrapper-observed filesystem-isolation state when the
    surrounding launch exported it (TERMINAL_JAIL_FS_ISOLATION), always
    with the explicit caveat that this is the wrapper's preflight
    observation — never this probe's own classification.
    """
    signals: list[str] = []
    markers = [m for m in _JAIL_ENV_MARKERS if os.environ.get(m)]
    if markers:
        signals.append("jail env markers present: " + ", ".join(markers))
    nspid_vals = _nspid_values()
    if len(nspid_vals) > 1:
        signals.append(
            "multi-value NSpid in /proc/self/status: " + " ".join(nspid_vals)
        )
    detail = "; ".join(signals) if signals else "jail detected"
    base = (
        "JAIL-AWARE: this probe is itself running inside a terminal-jail "
        f"launch ({detail}), so its nested "
        "mapped launch cannot work here — unshare cannot create the child "
        "namespace the probe needs from inside an existing one. What follows "
        "is the wrapper-observed isolation state of the surrounding launch, "
        "NOT a host classification by this probe."
    )
    observed = os.environ.get("TERMINAL_JAIL_FS_ISOLATION")
    if observed == "mapped":
        return base + (
            " The surrounding launch reports real filesystem isolation"
            " (uid-mapped user namespace, TERMINAL_JAIL_FS_ISOLATION=mapped)."
            " For the full classification of the outer host run the probe"
            " directly, outside the jail: python3 scripts/fs-isolation-probe.py"
        )
    if observed == "degraded":
        return base + (
            " The surrounding launch reports NO filesystem isolation"
            " (mapping-less user namespace, TERMINAL_JAIL_FS_ISOLATION=degraded)."
            " For the full classification of the outer host run the probe"
            " directly, outside the jail: python3 scripts/fs-isolation-probe.py"
        )
    return base + (
        " The surrounding launch exported no TERMINAL_JAIL_FS_ISOLATION"
        " marker (e.g. the auto-sandbox path), so no wrapper-observed"
        " isolation state is available here. For the full classification of"
        " the outer host run the probe directly, outside the jail:"
        " python3 scripts/fs-isolation-probe.py"
    )


def _subid_start(path: Path, username: str) -> int | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            fields = line.strip().split(":")
            if len(fields) >= 2 and fields[0] == username:
                try:
                    return int(fields[1])
                except ValueError:
                    return None
    except OSError:
        return None
    return None


def _mapped_flags() -> str:
    username = ""
    try:
        import pwd

        username = pwd.getpwuid(os.geteuid()).pw_name
    except (ImportError, KeyError):
        pass
    subuid = _subid_start(Path("/etc/subuid"), username) or DEFAULT_SUBID_START
    subgid = _subid_start(Path("/etc/subgid"), username) or DEFAULT_SUBID_START
    return (
        f"--user --map-users={NOBODY}:{subuid}:1"
        f" --map-groups={NOBODY}:{subgid}:1"
        f" -S {NOBODY} -G {NOBODY} --pid --fork"
    )


_LEGACY_FLAGS = "--user --pid --fork"


def _run_unshare(flags: str, payload: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["unshare", *flags.split(), "bash", "-c", payload],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _diagnose(mapped: subprocess.CompletedProcess[str], legacy_rc: int) -> str:
    causes: list[str] = []
    for helper in ("/usr/bin/newuidmap", "/usr/bin/newgidmap"):
        if not Path(helper).exists():
            causes.append(f"missing {helper}")
    import pwd

    try:
        username = pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        username = ""
    if username and _subid_start(Path("/etc/subuid"), username) is None:
        causes.append(f"no /etc/subuid entry for {username!r}")
    if _subid_start(Path("/etc/subgid"), username) is None:
        causes.append(f"no /etc/subgid entry for {username!r}")
    err = (mapped.stderr or "").strip()
    if legacy_rc == 0 and mapped.returncode != 0:
        cause = "uid-mapping denied: mapped launch failed while the legacy one succeeded"
        lowered = err.lower()
        if "setuid" in lowered:
            cause += (
                " (kernel denies setuid inside unprivileged user namespaces — "
                "AppArmor profile 'unprivileged_userns')"
            )
        elif "setgid" in lowered or "setgroups" in lowered:
            # setgroups() requires CAP_SETGID — the same denied capability.
            cause += (
                " (kernel denies setgid/setgroups inside unprivileged user "
                "namespaces — AppArmor profile 'unprivileged_userns')"
            )
        elif "uid_map" in lowered or "write failed" in lowered:
            cause += " (writing the uid map was denied)"
        try:
            sysctl = subprocess.run(
                ["sysctl", "-n", "kernel.apparmor_restrict_unprivileged_userns"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if sysctl.returncode == 0:
                cause += f" [kernel.apparmor_restrict_unprivileged_userns={sysctl.stdout.strip()}]"
        except (OSError, subprocess.SubprocessError):
            pass
        causes.append(cause)
    remediation = (
        "remediation: as root, `sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` "
        "or add an AppArmor exception for the launcher, or install newuidmap/newgidmap "
        "plus /etc/subuid|/etc/subgid ranges for the calling user"
    )
    if causes:
        return "causes: " + "; ".join(causes) + ". " + remediation
    return (
        f"causes: mapped launch failed unexpectedly (rc={mapped.returncode}, "
        f"stderr={err!r}). " + remediation
    )


def _classify() -> str:
    # DF-TERMINAL-JAIL-18: when the probe itself is jailed, the nested
    # mapped launch below cannot succeed — short-circuit to the honest
    # jail-aware verdict (wrapper-observed state + direct-run guidance)
    # instead of delivering the nested launch's failure as a host
    # classification. Direct (unjailed) runs never reach this.
    if _inside_terminal_jail():
        return _jail_aware_verdict()
    tmp = Path(tempfile.mkdtemp(prefix="tj-fsiso-"))
    secret_file = tmp / "secret600"
    try:
        secret_file.write_text("terminal-jail fs-isolation probe\n", encoding="utf-8")
        os.chmod(secret_file, 0o600)
        os.chown(secret_file, os.geteuid(), os.getegid())
        home = Path(os.environ.get("HOME", str(tmp)))
        home_probe = home / f".tj-fsiso-probe-{os.getpid()}"
        payload = (
            f"cat '{secret_file}' >/dev/null 2>&1; read_rc=$?; "
            f"touch '{home_probe}' >/dev/null 2>&1; write_rc=$?; "
            f"echo \"read_rc=$read_rc write_rc=$write_rc\""
        )

        mapped = _run_unshare(_mapped_flags(), payload)
        last_line = (mapped.stdout or "").strip().splitlines()[-1:] or [""]
        if mapped.returncode == 0 and last_line[0] == "read_rc=0 write_rc=0":
            # The namespace never came up with a mapping — the payload ran in
            # the caller's own context. Not FULL even though rc==0.
            return "DEGRADED: mapped launch produced no isolation " + _diagnose(mapped, -1)
        if mapped.returncode == 0 and last_line[0] == "read_rc=1 write_rc=1":
            return "FULL: uid-mapped user namespace denies caller-owned 600 reads and home writes"
        if mapped.returncode == 0:
            return (
                "DEGRADED: partial isolation "
                f"({last_line[0]!r}); " + _diagnose(mapped, -1)
            )
        legacy = _run_unshare(_LEGACY_FLAGS, "true")
        return (
            f"DEGRADED: mapped launch failed (rc={mapped.returncode}, "
            f"stderr={(mapped.stderr or '').strip()!r}); " + _diagnose(mapped, legacy.returncode)
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"UNKNOWN: probe error: {exc}"
    finally:
        try:
            for p in tmp.iterdir():
                p.unlink()
            tmp.rmdir()
        except OSError:
            pass
        home_probe = Path(os.environ.get("HOME", "/tmp")) / f".tj-fsiso-probe-{os.getpid()}"
        try:
            home_probe.unlink()
        except OSError:
            pass


def main() -> None:
    print(_classify())


if __name__ == "__main__":
    main()
