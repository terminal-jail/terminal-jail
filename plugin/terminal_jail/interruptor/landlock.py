"""Landlock filesystem-isolation tier (TJ-GAP-082).

A kernel-enforced deny tier for hosts where the uid-mapped user namespace
(TJ-DF-015) is unavailable — e.g. Ubuntu with the stock AppArmor
``unprivileged_userns`` profile denying setuid/setgroups inside the
namespace, where ``unshare_prefix()`` must fall back mapping-less and the
payload keeps the caller's kuid for DAC. Landlock needs NO user namespace
and NO privileges: any unprivileged process can restrict ITSELF.

What the tier enforces (kernel-side, inherited by the payload and every
descendant — Landlock restrictions survive exec and cannot be undone by
the process or a less-privileged child):

- DENIES read access to credential surfaces: ``~/.ssh``, ``~/.gnupg``,
  ``~/.config/terminal-jail`` (the tier's own policy store), ``~/.hermes``,
  ``~/.git-credentials``, ``~/.config/git/credentials``, ``~/.netrc``,
  ``~/.aws``, ``~/.kube``, ``~/.docker``, ``~/.password-store``, other
  users' home directories, ``/root``, and — since Landlock is an
  ALLOWLIST model — every path not explicitly granted.
- DENIES writes everywhere except the working tree, the temp directories
  (``/tmp``, ``/var/tmp``, ``$TMPDIR``), ``~/.cache`` and ``/dev``.

Landlock is allowlist-shaped: a ruleset DECLares which access types it
handles, and everything NOT covered by an added rule is denied. The tier
grants a read-only runner set (system mounts, the loader/nss/release-file
paths under /etc, DNS resolver state, the home allowlist: shell rc files,
``~/.cargo``, ``~/.rustup``, ``~/.nvm``, ``~/go/pkg/mod``,
``~/.local/{bin,lib,share,pipx}``, ``~/.config/fish``, git config) and a
read-write set (workdir, temp dirs, ``~/.cache``, ``/dev`` — so
``/dev/null`` and ``/dev/shm`` keep working). Denied subtrees are added as
explicit zero-access rules so they stay denied even under the workdir or
a granted parent (deeper rule wins).

NOT handled (documented boundary): ``LANDLOCK_ACCESS_FS_REFER`` (ABI 2).
Without it a cross-hierarchy rename is still checked against the SOURCE
hierarchy, so moving a file OUT of a denied tree fails there (the denied
tree grants no REMOVE_* right); a hardlink made inside the workdir to a
denied file is still evaluated against the denied hierarchy on every
access, so the read stays denied. The tier therefore holds without REFER.

PREFLIGHT LESSON (TJ-DF-015/TJ-DF-018, applied): creatable is not
enforced. ``apply()`` proves the PROPERTY after ``landlock_restrict_self``
— it reads a caller-owned mode-600 probe file under a denied root in
THIS process and requires EACCES. Any other outcome raises
``LandlockError`` and the caller degrades LOUDLY (one warning naming the
cause; behavior unchanged). The tier is silent on success.

Knobs: ``TERMINAL_JAIL_LANDLOCK=0|off|false`` disables the tier entirely
(truthy/other values follow the repo-wide truthy/falsy pattern used by
``TERMINAL_JAIL_SECCOMP``). ``sandbox_prefix()`` is the single-sourced
engine seam: decider.py composes ``unshare_prefix()`` with it exactly
once, the same way it consumes ``unshare_prefix()``.

Implementation: ctypes against the kernel syscalls (no python-landlock
dependency), mirroring plugin/terminal_jail/seccomp.py's constraints —
stdlib only, arch allowlist (x86_64/aarch64 share the generic syscall
numbers 444-446), graceful degradation by the caller. The standalone
pre-exec entry point is ``standalone/landlock-loader.py``.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import importlib.util
import logging
import os
import platform
import shlex
import stat
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field

LOGGER: logging.Logger = logging.getLogger("terminal_jail")

# --- Environment ----------------------------------------------------------

ENV_VAR = "TERMINAL_JAIL_LANDLOCK"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"", "0", "false", "no", "off"})


def landlock_enabled_from_environment() -> bool:
    """Parse ``TERMINAL_JAIL_LANDLOCK`` (default ENABLED).

    The default is on because the tier is deny-path hardening: on a host
    without Landlock it is a no-op, and where Landlock exists it only
    removes access the brief's threat model denies anyway. Unset and
    truthy values enable; ``0/off/false`` forces it off; an unrecognised
    value disables it (fail-closed, same as
    ``seccomp_enabled_from_environment``).
    """
    raw = os.environ.get(ENV_VAR)
    if raw is None:
        return True  # unset: the tier is on by default
    value = raw.strip().lower()
    if value == "" or value in _FALSY:
        return False
    if value in _TRUTHY:
        return True
    LOGGER.warning(
        "terminal-jail: unrecognised value %r for %s; disabling the "
        "Landlock filesystem tier",
        raw,
        ENV_VAR,
    )
    return False


# --- Kernel ABI (ctypes; linux/landlock.h) --------------------------------

# The generic syscall table (x86_64 and aarch64 both): arches outside this
# table raise LandlockUnsupportedError (same posture as seccomp.py).
_SYSCALL_NR: dict[str, tuple[int, int, int]] = {
    # (landlock_create_ruleset, landlock_add_rule, landlock_restrict_self)
    "x86_64": (444, 445, 446),
    "aarch64": (444, 445, 446),
}

LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
LANDLOCK_RULE_PATH_BENEATH = 1

# FS access bits (linux/landlock.h). Bits 0-12 exist since ABI 1; REFER
# (1<<13, ABI 2) and TRUNCATE (1<<14, ABI 3) are deliberately NOT handled
# (see the module docstring's boundary note) — one mask, no ABI branching.
LANDLOCK_ACCESS_FS_EXECUTE = 1 << 0
LANDLOCK_ACCESS_FS_WRITE_FILE = 1 << 1
LANDLOCK_ACCESS_FS_READ_FILE = 1 << 2
LANDLOCK_ACCESS_FS_READ_DIR = 1 << 3
LANDLOCK_ACCESS_FS_REMOVE_DIR = 1 << 4
LANDLOCK_ACCESS_FS_REMOVE_FILE = 1 << 5
LANDLOCK_ACCESS_FS_MAKE_CHAR = 1 << 6
LANDLOCK_ACCESS_FS_MAKE_DIR = 1 << 7
LANDLOCK_ACCESS_FS_MAKE_REG = 1 << 8
LANDLOCK_ACCESS_FS_MAKE_SOCK = 1 << 9
LANDLOCK_ACCESS_FS_MAKE_FIFO = 1 << 10
LANDLOCK_ACCESS_FS_MAKE_BLOCK = 1 << 11
LANDLOCK_ACCESS_FS_MAKE_SYM = 1 << 12

HANDLED_ACCESS_FS = (
    LANDLOCK_ACCESS_FS_EXECUTE
    | LANDLOCK_ACCESS_FS_WRITE_FILE
    | LANDLOCK_ACCESS_FS_READ_FILE
    | LANDLOCK_ACCESS_FS_READ_DIR
    | LANDLOCK_ACCESS_FS_REMOVE_DIR
    | LANDLOCK_ACCESS_FS_REMOVE_FILE
    | LANDLOCK_ACCESS_FS_MAKE_CHAR
    | LANDLOCK_ACCESS_FS_MAKE_DIR
    | LANDLOCK_ACCESS_FS_MAKE_REG
    | LANDLOCK_ACCESS_FS_MAKE_SOCK
    | LANDLOCK_ACCESS_FS_MAKE_FIFO
    | LANDLOCK_ACCESS_FS_MAKE_BLOCK
    | LANDLOCK_ACCESS_FS_MAKE_SYM
)

# landlock_ruleset_attr for an FS-only ruleset: exactly one __u64. Newer
# kernels append fields (handled_access_net, scoped) but accept the short
# request — the trailing fields are treated as zero (ABI-compatible
# extension), so ABI 1 hosts work unchanged.
_READ = LANDLOCK_ACCESS_FS_READ_FILE | LANDLOCK_ACCESS_FS_READ_DIR
_READ_EXEC = _READ | LANDLOCK_ACCESS_FS_EXECUTE
# A write grant is the FULL 13-bit set: without the MAKE_*/REMOVE_* bits
# the payload could modify existing files but never create or delete
# anything (new-file creation is MAKE_REG on the parent; measured: a
# READ|EXEC|WRITE_FILE-only grant leaves mkdir/O_CREAT denied with EACCES).
_RW = _READ_EXEC
for _bit in (
    LANDLOCK_ACCESS_FS_WRITE_FILE,
    LANDLOCK_ACCESS_FS_REMOVE_DIR,
    LANDLOCK_ACCESS_FS_REMOVE_FILE,
    LANDLOCK_ACCESS_FS_MAKE_CHAR,
    LANDLOCK_ACCESS_FS_MAKE_DIR,
    LANDLOCK_ACCESS_FS_MAKE_REG,
    LANDLOCK_ACCESS_FS_MAKE_SOCK,
    LANDLOCK_ACCESS_FS_MAKE_FIFO,
    LANDLOCK_ACCESS_FS_MAKE_BLOCK,
    LANDLOCK_ACCESS_FS_MAKE_SYM,
):
    _RW |= _bit


class _RulesetAttr(ctypes.Structure):
    # __attribute__((packed)) per linux/landlock.h. _layout_="ms" is the
    # EXPLICIT declaration of the packed layout the _pack_=1 implies —
    # without it Python <3.19 emits a DeprecationWarning (and 3.19 makes
    # the implicit default an error).
    _layout_ = "ms"
    _pack_ = 1
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathBeneathAttr(ctypes.Structure):
    _layout_ = "ms"  # see _RulesetAttr: explicit packed layout
    _pack_ = 1  # __attribute__((packed)) per linux/landlock.h
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


class LandlockError(RuntimeError):
    """The tier could not be applied; message names the observed cause."""

    def __init__(self, message: str, *, cause: str = "") -> None:
        super().__init__(message)
        self.cause = cause or message


class LandlockUnsupportedError(LandlockError):
    """Landlock is not available on this host (ABI absent / unknown arch)."""


def _libc() -> ctypes.CDLL:
    libc_name = ctypes.util.find_library("c") or "libc.so.6"
    return ctypes.CDLL(libc_name, use_errno=True)


def _syscall(
    libc: ctypes.CDLL, nr: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0
) -> int:
    """Raw syscall(2) with a fixed 7-long argtypes (variadic-safe)."""
    fn = libc.syscall
    fn.argtypes = [ctypes.c_long] * 7
    fn.restype = ctypes.c_long
    return fn(nr, a, b, c, d, 0, 0)


def abi_version(libc: ctypes.CDLL | None = None) -> int:
    """The highest Landlock ABI this kernel supports; 0 when absent.

    ``landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)``
    returns the ABI version, -ENOSYS/-EOPNOTSUPP when the syscall or the
    LSM is missing. Also 0 on architectures outside the syscall table.
    """
    if libc is None:
        try:
            libc = _libc()
        except OSError:
            return 0
    numbers = _SYSCALL_NR.get(platform.machine())
    if numbers is None:
        return 0
    rv = _syscall(libc, numbers[0], 0, 0, LANDLOCK_CREATE_RULESET_VERSION)
    return rv if rv >= 1 else 0


def _require_arch() -> tuple[int, int, int]:
    numbers = _SYSCALL_NR.get(platform.machine())
    if numbers is None:
        raise LandlockUnsupportedError(
            f"no Landlock syscall numbers for this architecture ({platform.machine()})",
            cause=f"unsupported architecture {platform.machine()}",
        )
    return numbers


def _open_path_beneath(path: str) -> int:
    return os.open(path, os.O_PATH | os.O_CLOEXEC)


def _prctl_no_new_privs(libc: ctypes.CDLL) -> None:
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
    rv = prctl(38, 1, 0, 0, 0)  # PR_SET_NO_NEW_PRIVS
    if rv != 0:
        code = ctypes.get_errno()
        raise LandlockError(
            f"PR_SET_NO_NEW_PRIVS failed: {os.strerror(code)} (errno {code})",
            cause=f"PR_SET_NO_NEW_PRIVS: {os.strerror(code)}",
        )


def kernel_enforced(probe_path: str) -> bool:
    """True when reading ``probe_path`` is denied RIGHT NOW (EACCES).

    The property probe: an applied domain must deny the caller-owned
    mode-600 file. OSError-PermissionError → True; clean read → False;
    any other error (FileNotFound — the file vanished — etc.) is NOT
    evidence of enforcement → False.
    """
    try:
        with open(probe_path, "rb") as handle:
            handle.read(1)
    except PermissionError:
        return True
    except OSError:
        return False
    return False


def _restrict_and_verify(
    fd: int,
    layout: "TierLayout",
    libc: ctypes.CDLL,
    restrict_nr: int,
    *,
    dry_probe: bool = True,
) -> None:
    """Apply the finished ruleset to THIS process (no_new_privs, restrict).

    When ``dry_probe`` the enforcement property is verified BEFORE this
    process is restricted: the mode-600 probe read must return EACCES in
    a forked grandchild that applied ``fd`` — any other outcome raises
    LandlockError and THIS PROCESS STAYS UNRESTRICTED.
    """
    try:
        if dry_probe:
            _prove_enforcement_in_child(layout, libc, fd, restrict_nr)
        # This process applies the tier only AFTER the property proof.
        _prctl_no_new_privs(libc)
        ctypes.set_errno(0)
        rv = _syscall(libc, restrict_nr, fd, 0)
        if rv != 0:
            code = ctypes.get_errno()
            raise LandlockError(
                f"landlock_restrict_self failed: {os.strerror(code)} (errno {code})",
                cause=f"landlock_restrict_self: {os.strerror(code)}",
            )
    finally:
        os.close(fd)


def apply(
    layout: "TierLayout",
    *,
    libc: ctypes.CDLL | None = None,
    dry_probe: bool = True,
) -> int:
    """Build + apply the tier's ruleset to THIS process; return rule count.

    When ``dry_probe`` (default) the enforcement PROPERTY is verified
    BEFORE this process is restricted: a mode-600 probe file under a
    denied root (created here, while still unrestricted) must read back
    EACCES inside a forked child that applied the same ruleset. Any
    other outcome raises LandlockError and THIS PROCESS STAYS
    UNRESTRICTED — the TJ-DF-015 preflight lesson: prove the property,
    never the proxy, and never leave a half-applied state behind. The
    probe file is removed by this (unrestricted) process, so enforcement
    leaves no litter.

    On success this process is restricted (one-way) and every later
    exec inherits the domain — the caller is a loader about to exec the
    payload (standalone/landlock-loader.py) or a test.
    """
    if libc is None:
        libc = _libc()
    create_nr, add_nr, restrict_nr = _require_arch()

    fd, count = _build_rules_fd(layout, libc, create_nr, add_nr)
    _restrict_and_verify(fd, layout, libc, restrict_nr, dry_probe=dry_probe)
    return count


def _build_rules_fd(
    layout: "TierLayout", libc: ctypes.CDLL, create_nr: int, add_nr: int
) -> tuple[int, int]:
    """Create the ruleset and add every grant rule; returns (fd, count).

    Denied trees exist only as OMISSIONS (the allowlist model) — there
    is no deny-rule pass. Kernel constraint (landlock_add_rule EINVAL):
    a NON-directory target only accepts the file-relevant bits — a
    dir-only bit (READ_DIR, REMOVE_*, MAKE_*) on a file fd is rejected.
    """
    file_bits = (
        LANDLOCK_ACCESS_FS_EXECUTE
        | LANDLOCK_ACCESS_FS_WRITE_FILE
        | LANDLOCK_ACCESS_FS_READ_FILE
    )
    rules: list[tuple[int, str, int]] = []
    for path in layout.write_roots:
        allowed = _RW if _is_dir(path) else _RW & file_bits
        rules.append((allowed, path, _open_path_beneath(path)))
    for path in layout.read_roots:
        allowed = _READ_EXEC if _is_dir(path) else _READ_EXEC & file_bits
        rules.append((allowed, path, _open_path_beneath(path)))

    attr = _RulesetAttr(HANDLED_ACCESS_FS)
    ctypes.set_errno(0)
    fd = _syscall(libc, create_nr, ctypes.addressof(attr), ctypes.sizeof(attr), 0)
    if fd < 0:
        code = ctypes.get_errno()
        raise LandlockError(
            f"landlock_create_ruleset failed: {os.strerror(code)} (errno {code})",
            cause=f"landlock_create_ruleset: {os.strerror(code)}",
        )

    for idx, (allowed, path, parent_fd) in enumerate(rules):
        rule = _PathBeneathAttr()
        rule.allowed_access = allowed
        rule.parent_fd = parent_fd
        ctypes.set_errno(0)
        rv = _syscall(
            libc, add_nr, fd, LANDLOCK_RULE_PATH_BENEATH, ctypes.addressof(rule), 0
        )
        os.close(parent_fd)
        if rv != 0:
            code = ctypes.get_errno()
            os.close(fd)
            # Error-path fd hygiene: the not-yet-added rules' O_PATH fds
            # would otherwise leak (the failing rule's fd and the ruleset
            # fd are closed above).
            for _, _, leftover_fd in rules[idx + 1 :]:
                os.close(leftover_fd)
            raise LandlockError(
                f"landlock_add_rule({path}) failed: {os.strerror(code)} (errno {code})",
                cause=f"landlock_add_rule({path}): {os.strerror(code)}",
            )
    return fd, len(rules)


def _make_enforcement_probe(layout: "TierLayout") -> str:
    """A caller-owned mode-600 probe file at a DENIED-by-omission path.

    The proof target must be a path the CALLER can write right now
    (unrestricted) but the DOMAIN does not grant — so the denial can only
    come from Landlock, never from DAC. Candidates, each verified against
    the layout's grants: XDG_RUNTIME_DIR (a caller-owned tmpfs outside
    every grant on a normal desktop session), /run/<uid>, the HOME root
    (only named children are granted, never the root itself), and kernel
    tmpdirs (usable only in the drop_denied_tmp=False layout, where they
    are ungranted — each fallback dir is removed with its probe).
    Raises LandlockError when no such host exists — the property cannot
    be proven, which is exactly when the tier must refuse to claim.
    """
    granted = [os.path.realpath(p) for p in (*layout.write_roots, *layout.read_roots)]

    def _ungranted(candidate: str) -> bool:
        real = os.path.realpath(candidate)
        return not any(_is_inside(real, grant) for grant in granted)

    candidates: list[str] = []
    throwaway: list[str] = []
    runtime = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if runtime.startswith("/"):
        candidates.append(runtime)
    candidates.append(f"/run/user/{os.getuid()}")
    home = os.environ.get("HOME", "")
    if home:
        candidates.append(home)
    for temp in ("/tmp", "/var/tmp"):
        try:
            created = tempfile.mkdtemp(prefix="tj-ll-proof-", dir=temp)
        except OSError:
            continue
        candidates.append(created)
        throwaway.append(created)
    try:
        for root in candidates:
            if not os.path.isdir(root) or not _ungranted(root):
                continue
            probe = os.path.join(root, f".tj-landlock-eacces-probe-{os.getpid()}")
            try:
                with open(probe, "w", encoding="utf-8") as handle:
                    handle.write("terminal-jail landlock enforcement probe\n")
                os.chmod(probe, 0o600)
                return probe
            except OSError:
                continue
    finally:
        # The throwaway mkdtemp hosts are only used when chosen; whatever
        # was NOT used (and any empty leftover) is removed here. A chosen
        # host keeps its probe file until _prove_enforcement_in_child's
        # finally removes it — the dir itself is left (it was caller-
        # owned state or an empty kernel tempdir; removing a used
        # throwaway here is safe too, the probe is gone by then).
        for created in throwaway:
            try:
                os.rmdir(created)
            except OSError:
                pass
    raise LandlockError(
        "no caller-writable ungranted path to host the enforcement probe "
        "— cannot prove the tier (refusing to claim it unproven)",
        cause="no caller-writable ungranted path for the enforcement probe",
    )


def _prove_enforcement_in_child(
    layout: "TierLayout", libc: ctypes.CDLL, fd: int, restrict_nr: int
) -> None:
    """Prove the denied-read property inside a forked child.

    The child applies the ruleset (already fully assembled at ``fd``) to
    ITSELF and attempts the mode-600 read; the verdict comes back over a
    pipe. The parent stays unrestricted throughout: it created the probe
    file, reads the verdict, removes the file, and raises LandlockError
    on any outcome but a proven EACCES — this process is never left
    restricted by a FAILED proof.
    """
    probe = _make_enforcement_probe(layout)
    try:
        read_fd, write_fd = os.pipe()
        try:
            pid = os.fork()
        except OSError as exc:
            os.close(read_fd)
            os.close(write_fd)
            raise LandlockError(
                f"cannot fork the enforcement-probe child: {exc}",
                cause=f"fork: {exc}",
            ) from exc
        if pid == 0:  # child: restrict, probe, report, exit
            os.close(read_fd)
            verdict = b"0"
            try:
                _prctl_no_new_privs(libc)
                if _syscall(libc, restrict_nr, fd, 0) == 0 and kernel_enforced(probe):
                    verdict = b"1"
            except Exception:  # noqa: BLE001 — the verdict carries the failure
                verdict = b"0"
            try:
                os.write(write_fd, verdict)
            except OSError:
                pass
            finally:
                os.close(write_fd)
                os._exit(0)
        # parent
        os.close(write_fd)
        try:
            verdict = os.read(read_fd, 1)
        finally:
            os.close(read_fd)
            os.waitpid(pid, 0)
        if verdict != b"1":
            raise LandlockError(
                "Landlock enforcement NOT proven: the mode-600 probe read "
                f"under {probe} was not denied EACCES inside a child that "
                "applied the ruleset — not claiming the tier (TJ-DF-015 "
                "preflight: prove the property, not the proxy)",
                cause="enforcement probe read was not denied in the child",
            )
    finally:
        try:
            os.unlink(probe)
        except OSError:
            pass
        # When the proof host was one of this call's throwaway mkdtemp
        # dirs, remove it too (it is empty again after the unlink).
        parent = os.path.dirname(probe)
        if os.path.basename(parent).startswith("tj-ll-proof-"):
            try:
                os.rmdir(parent)
            except OSError:
                pass


# --- Layout ---------------------------------------------------------------


@dataclass
class TierLayout:
    """The tier's rule layout — Landlock is an ALLOWLIST model.

    ``write_roots``/``read_roots`` are the granted hierarchies; EVERYTHING
    else is denied by omission (the ruleset handles all FS rights and no
    rule covers the rest). ``ungranted_paths`` is the informational list
    of what the omission denies — credential surfaces, other users'
    homes — so probes/tests can assert the deny PROPERTY without the
    kernel's (non-existent) deny-rule concept. There are no zero-access
    rules: the kernel rejects an ``allowed_access == 0`` add_rule with
    ENOMSG, and a denied tree is expressed by not granting it.
    """

    workdir: str
    read_roots: list[str] = field(default_factory=list)
    write_roots: list[str] = field(default_factory=list)
    ungranted_paths: list[str] = field(default_factory=list)

    @property
    def rule_count(self) -> int:
        return len(self.read_roots) + len(self.write_roots)


def _exists_dir(path: str) -> bool:
    try:
        return stat.S_ISDIR(os.stat(path).st_mode)
    except OSError:
        return False


def _exists_file(path: str) -> bool:
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError:
        return False


def _is_dir(path: str) -> bool:
    try:
        return stat.S_ISDIR(os.stat(path).st_mode)
    except OSError:
        return False


def _home(home: str | None) -> str | None:
    if home is not None:
        return home or None
    return os.environ.get("HOME") or None


def _xdg_dir(env_name: str, default_tail: str, home: str | None) -> str | None:
    """XDG dir from env or the home-relative default; None when unset."""
    raw = os.environ.get(env_name, "").strip()
    if raw.startswith("/"):
        return os.path.normpath(raw)
    if home:
        return os.path.join(home, default_tail)
    return None


def _temp_dirs(extra: Iterable[str] = ()) -> list[str]:
    dirs = [os.environ.get(name, "").strip() for name in ("TMPDIR", "TMP", "TEMP")]
    dirs.extend(extra)
    dirs.extend(("/tmp", "/var/tmp"))
    seen: set[str] = set()
    ordered: list[str] = []
    for d in dirs:
        if d and d.startswith("/") and d not in seen:
            seen.add(d)
            ordered.append(d)
    return ordered


# Read-only home allowlist: what a payload plausibly needs to START (shell
# rc files, toolchain homes, user package trees). Everything else under
# HOME is ungranted → denied by the allowlist model.
_HOME_READ = (
    ".bashrc",
    ".profile",
    ".bash_profile",
    ".bash_aliases",
    ".zshrc",
    ".config/fish",
    ".cargo",
    ".rustup",
    ".nvm",
    "go/pkg/mod",
    ".local/bin",
    ".local/lib",
    ".local/share",
    ".local/pipx",
    ".config/git/config",
    ".gitconfig",
)

# Credential surfaces (NEVER granted: under the allowlist model they are
# denied by omission, and the workdir grant is split around any that sit
# inside it — see _split_workdir).
_CREDENTIAL_SURFACES = (
    ".ssh",
    ".gnupg",
    ".config/terminal-jail",
    ".config/terminal-jail/rules.d",
    ".hermes",
    ".git-credentials",
    ".config/git/credentials",
    ".netrc",
    ".aws",
    ".kube",
    ".docker",
    ".password-store",
)

# /etc is NOT granted wholesale (it holds sudoers, /etc/ssh host keys,
# shadow-adjacent state); only the named loader/NSS/release/DNS files.
_ETC_READ = (
    "/etc/ld.so.cache",
    "/etc/ld.so.preload",
    "/etc/nsswitch.conf",
    "/etc/hosts",
    "/etc/resolv.conf",
    "/etc/protocols",
    "/etc/services",
    "/etc/localtime",
    "/etc/passwd",
    "/etc/group",
    "/etc/os-release",
    "/etc/lsb-release",
    "/etc/debian_version",
    "/etc/alternatives",
    "/etc/ssl",
    "/etc/pki",
    "/etc/ca-certificates",
)

# DNS resolver state when systemd-resolved is in play (/etc/resolv.conf is
# typically a symlink INTO /run/systemd/resolve — the kernel opens the
# target, so the target needs the grant, not just the symlink).
_RUN_READ = (
    "/run/systemd/resolve",
    "/run/resolvconf",
)


def build_layout(
    workdir: str | None = None,
    *,
    home: str | None = None,
    drop_denied_tmp: bool = True,
) -> TierLayout | None:
    """Compute the tier's rule layout; None when a required input is gone.

    ``workdir`` defaults to the caller's cwd — the one tree the payload
    may write. ``drop_denied_tmp=False`` puts the temp directories in the
    ungranted set instead of the writable set (probe mode: prove a denied
    read on a temp fixture without touching real credential surfaces).
    """
    if not workdir:
        try:
            workdir = os.getcwd()
        except OSError:
            return None
    workdir = os.path.realpath(workdir)
    if not os.path.isdir(workdir):
        return None
    resolved_home = _home(home)
    if not resolved_home:
        return None

    layout = TierLayout(workdir=workdir)

    # ── write grants ──────────────────────────────────────────────────────
    write = [workdir]
    tmpdirs = _temp_dirs()
    if drop_denied_tmp:
        write.extend(tmpdirs)
    cache = _xdg_dir("XDG_CACHE_HOME", ".cache", resolved_home)
    if cache:
        write.append(cache)
    write.append("/dev")  # /dev/null, /dev/shm, /dev/stdout — device nodes
    layout.write_roots = _dedupe_existing(write, exclude=(workdir,))

    # ── read grants ───────────────────────────────────────────────────────
    # /proc: process self-inspection (ps, /proc/self/status readers) is a
    # legitimate payload need; on the bwrap backend this is the PRIVATE
    # procfs anyway, and on unshare the host-view exposure is the already
    # documented known limit (docs/backend-parity.md (a)) — the tier
    # neither improves nor worsens it, so it is granted read-only.
    read = [
        "/bin",
        "/sbin",
        "/usr",
        "/lib",
        "/lib64",
        "/opt",
        "/proc",
        "/sys",
        "/etc/alternatives",
        *_ETC_READ,
        *_RUN_READ,
    ]
    for tail in _HOME_READ:
        candidate = os.path.join(resolved_home, tail)
        if _exists_dir(candidate) or _exists_file(candidate):
            read.append(candidate)
    layout.read_roots = _dedupe_existing(read, exclude=(*layout.write_roots,))

    # ── the workdir grant is SUBDIVIDED around credential surfaces ───────
    # (an ungranted parent would deny the whole workdir — the deny must
    # carve the credential subtrees out of the granted one).
    ungranted = _credential_paths(resolved_home)
    if layout.workdir == resolved_home.rstrip("/"):
        return None  # refuse to grant HOME wholesale as the workdir
    split_grants, workdir_splits = _split_workdir(layout.workdir, resolved_home)
    non_workdir_writes = [p for p in layout.write_roots if p != layout.workdir]
    layout.write_roots = _dedupe_existing(
        [*non_workdir_writes, *split_grants], exclude=()
    )
    ungranted.extend(workdir_splits)

    # ── informational deny set (denied by OMISSION, not by a rule) ───────
    # Other users' home directories; /root; (when drop_denied_tmp=False)
    # the temp directories; everything else outside the grants.
    home_parent = os.path.dirname(resolved_home.rstrip("/"))
    if home_parent and home_parent != "/":
        ungranted.append(home_parent)
    ungranted.append("/root")
    if not drop_denied_tmp:
        ungranted.extend(tmpdirs)
    seen: set[str] = set()
    ordered: list[str] = []
    for path in ungranted:
        real = os.path.realpath(path) if os.path.exists(path) else path
        if real not in seen:
            seen.add(real)
            ordered.append(real)
    layout.ungranted_paths = ordered
    return layout


def _credential_paths(resolved_home: str) -> list[str]:
    """Credential surfaces that exist, most-specific first (rules.d first)."""
    found = [
        os.path.join(resolved_home, tail)
        for tail in reversed(_CREDENTIAL_SURFACES)
        if os.path.exists(os.path.join(resolved_home, tail))
    ]
    return found


def _split_workdir(workdir: str, resolved_home: str) -> tuple[list[str], list[str]]:
    """Subdivide the workdir write-grant around credential surfaces.

    Every ``<home>/<surface>`` that lives INSIDE the workdir replaces the
    flat workdir grant with grants that cover the workdir MINUS the
    surface: the walk recurses down the surface's ancestor chain and
    grants the surface's SIBLINGS at the deepest level (granting the
    parent path itself would re-include the surface — the bug this
    structure exists to avoid). Most-specific surface first, so a longer
    surface is already carved out when a shorter one is processed. Only
    path strings are computed here; callers open the resulting roots
    O_PATH.
    """
    inside = sorted(
        (
            os.path.join(resolved_home, tail)
            for tail in _CREDENTIAL_SURFACES
            if os.path.exists(os.path.join(resolved_home, tail))
            and _is_inside(os.path.join(resolved_home, tail), workdir)
            and os.path.realpath(os.path.join(resolved_home, tail))
            != os.path.realpath(workdir)
        ),
        key=len,
        reverse=True,  # most specific first (rules.d before terminal-jail)
    )
    if not inside:
        return [workdir], []

    grants = [workdir]
    splits: list[str] = []
    for surface in inside:
        splits.append(surface)
        carved: list[str] = []
        for grant in grants:
            if _is_inside(surface, grant):
                carved.extend(_split_grant_around(grant, surface))
            else:
                carved.append(grant)
        grants = carved
    return grants, splits


def _split_grant_around(grant: str, surface: str) -> list[str]:
    """Grants covering ``grant`` minus ``surface`` (surface strictly inside).

    The complete carve needs the surface's siblings at EVERY level of its
    ancestor chain: ``grant/a/surface`` → ``grant/a's siblings`` +
    ``grant/a/surface's siblings`` (granting only the deepest level would
    silently drop the rest of the grant).
    """
    real_grant = os.path.realpath(grant)
    real_surface = os.path.realpath(surface)
    rel = os.path.relpath(real_surface, real_grant)
    parts = rel.split(os.sep)
    carved: list[str] = []
    prefix = real_grant
    for part in parts[:-1]:
        try:
            names = os.listdir(prefix)
        except OSError:
            return carved
        for name in names:
            if name == part:
                continue
            carved.append(os.path.join(prefix, name))
        prefix = os.path.join(prefix, part)
    try:
        names = os.listdir(prefix)
    except OSError:
        return carved
    for name in names:
        candidate = os.path.join(prefix, name)
        if not _is_inside(candidate, real_surface):
            carved.append(candidate)
    return carved


def _is_inside(path: str, root: str) -> bool:
    """True when ``path`` is ``root`` or lives under it (realpaths)."""
    try:
        return os.path.commonpath((os.path.realpath(path), os.path.realpath(root))) == (
            os.path.realpath(root)
        )
    except ValueError:  # different drives etc.
        return False


def _dedupe_existing(paths: Iterable[str], exclude: Iterable[str]) -> list[str]:
    """Order-preserving dedupe of paths that exist, minus excluded ones."""
    excluded = {os.path.realpath(p) for p in exclude}
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        real = os.path.realpath(path)
        if real in excluded or real in seen:
            continue
        if os.path.exists(real):
            seen.add(real)
            out.append(real)
    return out


# --- Engine seam (single-sourced, consumed by decider.py) ------------------

_WARNING_PREFIX = "terminal-jail: WARNING: Landlock filesystem tier not applied"

_WARNED = False


def degradation_warning(cause: str) -> str:
    """One line naming the degradation, its cause and the way out."""
    return (
        f"{_WARNING_PREFIX} ({cause}); commands run unchanged without kernel "
        "filesystem enforcement — classify the host with "
        "scripts/landlock-capability-probe.py, or disable this warning "
        "deliberately with TERMINAL_JAIL_LANDLOCK=0"
    )


def _degrade(cause: str) -> str:
    """Print the loud warning ONCE per process; return the empty prefix.

    Silent ONLY on a deliberate disable (TERMINAL_JAIL_LANDLOCK explicitly
    falsy — the knob IS the acknowledgment). An UNSET variable is the
    default-on posture, so a degradation there still warns.
    """
    global _WARNED
    raw = os.environ.get(ENV_VAR)
    if raw is not None and raw.strip().lower() in _FALSY:
        return ""
    if not _WARNED:
        _WARNED = True
        print(degradation_warning(cause), file=sys.stderr)
    return ""


def sandbox_prefix() -> str:
    """The Landlock launch-tail prefix for auto-sandbox/modify rewrites.

    ``"python3 <loader> -- "`` when the host supports Landlock, the tier
    applies (proven by the fork-isolated EACCES preflight) AND the loader
    is reachable under the launch (world-traversable path — a mapping-
    less rewrite runs its payload as nobody, and a 0750/0700 home makes
    the loader unopenable); the empty string otherwise. The composed
    payload is ``python3 <loader> -- <command>``: inside the namespace
    the loader applies the ruleset and execs the command (TJ-GAP-082).
    Degradation is LOUD: one warning names the cause and the command
    runs unchanged (behavior identical to the pre-tier engine). Cached
    per process.
    """
    global _SANDBOX_PREFIX_CACHE
    if _SANDBOX_PREFIX_CACHE is not None:
        return _SANDBOX_PREFIX_CACHE
    _SANDBOX_PREFIX_CACHE = _compute_sandbox_prefix()
    return _SANDBOX_PREFIX_CACHE


_SANDBOX_PREFIX_CACHE: str | None = None

_PROBE_ENV = "TERMINAL_JAIL_LANDLOCK_PROBE"


def loader_path() -> str | None:
    """The standalone landlock-loader.py, or None when not shipped here.

    Walks up from this module (repo checkout: <root>/standalone/;
    installed layout: <lib>/landlock-loader.py next to the plugin tree).
    """
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        for base in (
            os.path.join(current, "standalone"),
            current,
        ):
            candidate = os.path.join(base, "landlock-loader.py")
            if os.path.isfile(candidate):
                return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _world_traversable(path: str) -> bool:
    """True when EVERY directory on ``path`` grants other-execute (o+x).

    A mapping-less rewrite runs its payload as nobody (65534); a loader
    under a 0700/0750 home is unopenable for it, and a payload that
    cannot exec the loader dies with Errno 13 instead of running. The
    tail is only emitted when the launch can actually reach the loader.
    """
    real = os.path.realpath(path)
    parent = os.path.dirname(real)
    while True:
        try:
            mode = os.stat(parent).st_mode
        except OSError:
            return False
        if not mode & stat.S_IXOTH:
            return False
        nxt = os.path.dirname(parent)
        if nxt == parent:
            return True
        parent = nxt


def _probe_child_verdict() -> str:
    """The child half of the fork-isolated capability probe.

    Re-imported by path in the child (decoupling from the parent's module
    cache): the tier is APPLIED here — proof or not — and the verdict is
    one line on the pipe. The child exits without touching the parent.
    """
    module_path = os.environ[_PROBE_ENV]
    spec = importlib.util.spec_from_file_location(
        "terminal_jail_landlock_probe", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # before exec_module (dataclass hint walk)
    spec.loader.exec_module(module)
    try:
        layout = module.build_layout()
        if layout is None:
            return "FAIL layout refused"
        module.apply(layout, dry_probe=True)
    except module.LandlockError as exc:
        return f"FAIL {exc.cause}"
    except OSError as exc:
        return f"FAIL layout inspection failed: {exc}"
    return "OK"


def _compute_sandbox_prefix() -> str:
    """Decide WITHOUT enforcing: the rewrite's loader applies the tier.

    The engine process must stay unrestricted (its own RuleLoader reads
    ~/.config/terminal-jail AFTER this module is imported), so the
    capability question is answered inside a forked child: the child
    applies the tier to ITSELF (EACCES-preflighted); "OK" proves the
    host CAN enforce. The tail is then emitted only when the loader is
    reachable under the launch. Any other outcome degrades loudly and
    keeps the wrap byte-identical to the pre-tier engine.
    """
    if not landlock_enabled_from_environment():
        return ""
    if _PROBE_ENV not in os.environ:
        module_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "landlock.py"
        )
        read_fd, write_fd = os.pipe()
        try:
            pid = os.fork()
        except OSError as exc:
            os.close(read_fd)
            os.close(write_fd)
            return _degrade(f"capability probe fork failed: {exc}")
        if pid == 0:  # child: decide, report, never touch parent state
            os.close(read_fd)
            os.environ[_PROBE_ENV] = module_path
            try:
                verdict = _probe_child_verdict()
            except Exception as exc:  # noqa: BLE001 — a probe must never crash
                verdict = f"FAIL probe crash: {exc}"
            try:
                os.write(write_fd, verdict.encode("utf-8", "replace")[:512])
            except OSError:
                pass
            finally:
                os.close(write_fd)
                os._exit(0)
        # parent
        os.close(write_fd)
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(read_fd, 256)
                if not chunk:
                    break
                chunks.append(chunk)
            verdict = b"".join(chunks).decode("utf-8", "replace")
        finally:
            os.close(read_fd)
            os.waitpid(pid, 0)
    else:
        # Inside the probe child itself (the env var re-entry): decide.
        verdict = _probe_child_verdict()
    if not verdict.startswith("OK"):
        return _degrade(verdict[5:].strip() or "capability probe failed")
    loader = loader_path()
    if loader is None:
        return _degrade("landlock-loader.py not found next to the plugin")
    if not _world_traversable(loader):
        return _degrade(
            "landlock-loader.py is not reachable by the launch's payload "
            f"uid (a parent of {loader} lacks o+x — e.g. a 0700/0750 home)"
        )
    return f"python3 {shlex.quote(loader)} -- "


def apply_tier() -> tuple[bool, str]:
    """Apply the tier to the calling process (loader entry point).

    Returns (True, "") after a PROVEN enforcement, or (False, cause)
    without touching the process when the tier cannot apply. Never
    raises past LandlockError — the loader execs the payload unchanged
    with the cause.
    """
    if not landlock_enabled_from_environment():
        return False, ""
    try:
        layout = build_layout()
    except OSError as exc:
        return False, f"layout inspection failed: {exc}"
    if layout is None:
        return False, "working directory or HOME unavailable"
    try:
        apply(layout, dry_probe=True)
    except LandlockError as exc:
        return False, exc.cause
    return True, ""


__all__ = [
    "ENV_VAR",
    "LandlockError",
    "LandlockUnsupportedError",
    "TierLayout",
    "abi_version",
    "apply",
    "apply_tier",
    "build_layout",
    "degradation_warning",
    "kernel_enforced",
    "landlock_enabled_from_environment",
    "sandbox_prefix",
]
