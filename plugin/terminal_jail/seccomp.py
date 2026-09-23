"""
terminal-jail seccomp BPF filter — T9.5.

Implements an *optional*, default-allow seccomp BPF filter that denies a
focused list of dangerous syscalls inside the PID namespace jail:

    mount, pivot_root, kexec_load, kexec_file_load, init_module, finit_module,
    delete_module, create_module, swapon, swapoff, settimeofday, adjtimex,
    clock_settime, acct, add_key, request_key, keyctl

glibc routing note (TJ-DF-020): glibc does not always issue the *classic*
syscall number for a libc wrapper. On x86_64, ``adjtimex()`` and
``clock_adjtime()`` route to ``clock_adjtime`` (NR 305), not ``adjtimex``
(NR 159) — so the deny list must pin BOTH the classic NR and the
glibc-routed variant NR, or the libc wrapper silently bypasses the filter.
``settimeofday()`` routes to ``clock_settime`` (227, already denied);
``init_module()``/``finit_module()`` (175/313) and
``kexec_load()``/``kexec_file_load()`` (246/320) variants are already
covered. See the ``glibc variant routing`` note at ``_DENY_EXTRA``.

The filter is documented in the project threat model (docs/threat-model.md,
section 9.2, recommendation #5) and is exercised manually by pentest tests
PT-004a, PT-004b, and PT-004c (docs/pentest-plan.md, section 3.4).

Design constraints:

* Stdlib only — no `seccomp` / `libseccomp` PyPI package. We build the BPF
  program by hand and apply it via ``prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER,
  ...)`` using ``ctypes``. ``seccomp`` *is* listed as an optional acceleration
  but is not required for correctness.
* Default-allow with explicit denials. This is the safest posture for a
  jail that must continue to run the full Python/Node/Rust toolchain — the
  threat model calls out the dangerous set, not a positive allow-list.
* Single-architecture (x86_64 / aarch64) detection at import time. The
  kernel will reject filters with an unknown ``AUDIT_ARCH`` value, so the
  module raises ``SeccompUnsupportedError`` on unknown arches rather than
  silently installing a no-op filter.
* Environment variable parsing reuses the truthy/falsy sets from
  :mod:`plugin.terminal_jail.plugin` so the UX is identical to other
  terminal-jail toggles.
* Graceful degradation: callers (the standalone loader, the standalone CLI)
  can catch :class:`SeccompError` and continue without the filter.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import errno
import logging
import os
import platform
import struct
from dataclasses import dataclass
from typing import Final

LOGGER: Final[logging.Logger] = logging.getLogger("terminal_jail")

# --- Environment -------------------------------------------------------------

_ENV_VAR: Final[str] = "TERMINAL_JAIL_SECCOMP"

_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"", "0", "false", "no", "off"})


def seccomp_enabled_from_environment() -> bool:
    """Parse ``TERMINAL_JAIL_SECCOMP`` using the truthy/falsy pattern.

    Returns ``True`` if the value is one of ``1``/``true``/``yes``/``on``,
    ``False`` for everything else (including empty/unset). Unrecognised
    values fall back to *disabled* — matching the fail-closed posture used
    by ``HERMES_TERMINAL_JAIL_ENABLED``.
    """
    raw = os.environ.get(_ENV_VAR, "")
    value = raw.strip().lower()
    if value in _FALSY:
        return False
    if value in _TRUTHY:
        return True
    LOGGER.warning(
        "terminal-jail: unrecognised value %r for %s; disabling seccomp",
        raw,
        _ENV_VAR,
    )
    return False


# --- BPF program --------------------------------------------------------------
#
# A ``struct sock_filter`` is a classic BPF instruction: 8 bytes total —
# ``code`` (u16), ``jt`` (u8), ``jf`` (u8), ``k`` (u32). The seccomp
# interpreter reads the ``seccomp_data`` argument as the BPF "packet":
#
#     offset 0: nr   (u32)
#     offset 4: arch (u32)
#     offset 8: instruction_pointer (u64)
#    offset 16: args[0] (u64) ...
#
# Our filter walks:
#
#   1. Load arch (offset 4) into A; compare to AUDIT_ARCH; if not equal,
#      KILL_PROCESS. This prevents a 32-bit-compat binary from issuing
#      x86_64 syscall numbers (or vice versa).
#   2. Load syscall number (offset 0) into A.
#   3. Jump into a binary search over the deny-list. Misses fall through
#      to ALLOW.
#   4. Hits return SECCOMP_RET_ERRNO | EPERM.

# BPF opcodes (subset of linux/filter.h)
_BPF_LD: Final[int] = 0x00
_BPF_JMP: Final[int] = 0x05
_BPF_RET: Final[int] = 0x06
_BPF_W: Final[int] = 0x00
_BPF_ABS: Final[int] = 0x20
_BPF_JEQ: Final[int] = 0x10
_BPF_JGT: Final[int] = 0x20
_BPF_JGE: Final[int] = 0x30
_BPF_K: Final[int] = 0x00

# seccomp_data offsets
_SECCOMP_DATA_NR: Final[int] = 0x00000000
_SECCOMP_DATA_ARCH: Final[int] = 0x00000004

# Returns
_SECCOMP_RET_ALLOW: Final[int] = 0x7FFF0000
_SECCOMP_RET_ERRNO: Final[int] = 0x00050000
_EPERM: Final[int] = 1

# prctl constants (linux/prctl.h + linux/seccomp.h)
_PR_SET_SECCOMP: Final[int] = 22
_PR_SET_NO_NEW_PRIVS: Final[int] = 38
_SECCOMP_MODE_FILTER: Final[int] = 2

# AUDIT_ARCH_* values from linux/audit.h (also see _ARCH_TABLE below).
_AUDIT_ARCH_LE: Final[int] = 0x40000000
_AUDIT_ARCH_64BIT: Final[int] = 0x80000000


@dataclass(frozen=True, slots=True)
class _Arch:
    """A target architecture the BPF filter must match."""

    name: str
    audit_arch: int


_ARCH_TABLE: Final[tuple[_Arch, ...]] = (
    _Arch("x86_64", 62 | _AUDIT_ARCH_64BIT | _AUDIT_ARCH_LE),  # EM_X86_64
    _Arch("aarch64", 183 | _AUDIT_ARCH_64BIT | _AUDIT_ARCH_LE),  # EM_AARCH64
)


# Syscalls to deny — per threat-model §9.2 (#5) and pentest plan §3.4.
# See :data:`_DENY_EXTRA` for per-architecture number assignments.
#
# Threat-model-deny list (semantics, names):
#   mount, pivot_root, kexec_load, kexec_file_load,
#   init_module, finit_module, delete_module, create_module,
#   swapon, swapoff, settimeofday, adjtimex, clock_settime,
#   acct, add_key, request_key, keyctl
#
# Architecture note
# -----------------
# Several of these syscalls are only present on x86_64 (e.g. ``create_module``,
# ``init_module``, ``acct``, ``adjtimex``, ``kexec_load``, ``kexec_file_load``,
# ``add_key``, ``request_key``, ``keyctl``, ``pivot_root``). On aarch64 the
# equivalents are absent or live at different NRs. We therefore keep a
# per-arch lookup table (``_DENY_EXTRA``) that pins *only* the numbers
# known to exist on the target arch. Any unrecognised NR we include
# would never be issued by userspace, so it is harmless to filter.
#
# Concretely: the threat-model deny list is the *x86_64* deny list. On
# aarch64 we install a smaller, verified subset (mount, settimeofday,
# swapon, swapoff, clock_settime) and skip the rest. Future work can
# expand the aarch64 table as kernel coverage is confirmed.
#
# glibc variant routing (TJ-DF-020)
# ---------------------------------
# glibc may implement a libc wrapper via a DIFFERENT syscall than the
# classic one with the same name. The bypass proven live on x86_64
# (2026-09-23, control host): libc ``adjtimex()`` returns 0 under this
# filter because glibc routes it to ``clock_adjtime`` (NR 305), while the
# raw ``adjtimex`` NR (159) is denied. Therefore each classic NR that
# glibc may re-route must ALSO pin its glibc-routed variant NR:
#
#   x86_64: adjtimex(159) -> clock_adjtime(305)   [added]
#           settimeofday(164) -> clock_settime(227)  [227 already denied]
#           init_module(175) -> finit_module(313)    [313 already denied]
#           kexec_load(246) -> kexec_file_load(320)  [320 already denied]
#
# TODO(aarch64): the kernel-generic aarch64 table places the equivalents
# at different NRs (adjtimex 171, clock_adjtime 266, kexec_file_load
# absent, finit_module 273); the current aarch64 deny set below does not
# include adjtimex-family numbers at all, so mirroring the variant NRs
# there is deferred until the aarch64 table itself is audited/verified on
# an aarch64 host.


# Subset of deny syscalls that exist on *both* x86_64 and aarch64 with the
# same semantics. This is the conservative cross-arch deny set. It is
# computed by intersecting the per-arch extension tables; we hard-code it
# here so that an audit can verify the values without running the code.
_DENY_COMMON_BOTH: Final[frozenset[int]] = frozenset(
    {
        167,  # swapon  (both arches)
        168,  # swapoff (both arches)
    }
)

# Per-arch extension: numbers that exist with the *same semantics* on the
# given arch. Keys are architecture names from :data:`_ARCH_TABLE`.
_DENY_EXTRA: Final[dict[str, frozenset[int]]] = {
    "x86_64": frozenset(
        {
            155,  # pivot_root
            159,  # adjtimex
            163,  # acct
            164,  # settimeofday
            165,  # mount
            167,  # swapon
            168,  # swapoff
            174,  # create_module
            175,  # init_module
            176,  # delete_module
            227,  # clock_settime
            246,  # kexec_load
            248,  # add_key
            249,  # request_key
            250,  # keyctl
            305,  # clock_adjtime — glibc routes adjtimex() here (TJ-DF-020)
            313,  # finit_module
            320,  # kexec_file_load
        }
    ),
    "aarch64": frozenset(
        {
            40,  # mount
            163,  # settimeofday
            167,  # swapon
            168,  # swapoff
            222,  # clock_settime
            # NOTE: pivot_root, init_module, finit_module, create_module,
            # delete_module, kexec_load, kexec_file_load, acct, adjtimex,
            # add_key, request_key, keyctl are not implemented as syscalls on
            # standard aarch64 kernels. Including their NRs would be harmless
            # (the kernel never sees them) but adds noise to the filter.
        }
    ),
}


# --- Errors -------------------------------------------------------------------


class SeccompError(Exception):
    """Base class for seccomp-related failures."""


class SeccompUnsupportedError(SeccompError):
    """The current platform/architecture does not support seccomp."""


class SeccompPermissionError(SeccompError):
    """The kernel refused the filter (typically missing CAP_SYS_ADMIN)."""


# --- BPF encoding -------------------------------------------------------------


def _bpf_stmt(code: int, k: int) -> bytes:
    """Encode a single BPF ``sock_filter`` instruction.

    Format matches ``struct sock_filter`` in ``<linux/filter.h>``:
        u16 code, u8 jt, u8 jf, u32 k
    """
    return struct.pack("<HBBI", code, 0, 0, k)


def _bpf_jump(code: int, k: int, jt: int, jf: int) -> bytes:
    """Encode a BPF branch instruction."""
    return struct.pack("<HBBI", code, jt, jf, k)


def _build_filter(arch_value: int, deny_numbers: frozenset[int]) -> tuple[bytes, int]:
    """Return ``(encoded_filter, instruction_count)``.

    The filter is laid out so that misses fall through to ``ALLOW``:

        0:      LD   [4]                # A = arch
        1:      JEQ  arch_value, 1, 0   # if equal, skip KILL; else fall into it
        2:      RET  KILL_PROCESS
        3:      LD   [0]                # A = nr
        4..N:   linear scan: JEQ nr, jt=deny, jf=1   (N-4 instructions)
        N:      RET  ALLOW
        N+1:    RET  ERRNO|EPERM   (the deny block — hit on match)

    BPF jump semantics: ``jt`` is taken when the condition is TRUE,
    ``jf`` when FALSE — both relative to the *next* instruction. So
    instruction 1 uses ``jt=1, jf=0``: a matching arch skips the KILL
    (pc+1 lands on LD nr); a mismatched arch falls through to KILL.
    """
    if not deny_numbers:
        # Nothing to deny — install a no-op filter that just checks arch.
        # This still validates arch and serves as a placeholder.
        body = b"".join(
            (
                _bpf_stmt(_BPF_LD | _BPF_W | _BPF_ABS, _SECCOMP_DATA_ARCH),
                _bpf_jump(_BPF_JMP | _BPF_JEQ | _BPF_K, arch_value, 1, 0),
                _bpf_stmt(_BPF_RET, 0x80000000),  # SECCOMP_RET_KILL_PROCESS
                _bpf_stmt(_BPF_RET, _SECCOMP_RET_ALLOW),
            )
        )
        return body, 4

    # Linear scan over a sorted deny list. With N entries, the layout is:
    #   3 (arch prologue) + 1 (LD nr) + N (JEQ nr) + 1 (RET ALLOW) + 1 (RET deny)
    # So the deny block sits at index 3 + 1 + N + 1 = N + 5.
    sorted_denies = sorted(deny_numbers)
    deny_block_index = 3 + 1 + len(sorted_denies) + 1

    instructions: list[bytes] = []
    # 0: LD [4]   — load arch
    instructions.append(_bpf_stmt(_BPF_LD | _BPF_W | _BPF_ABS, _SECCOMP_DATA_ARCH))
    # 1: JEQ arch_value, jt=1, jf=0 — matching arch skips the KILL and falls
    #    through to LD nr; mismatched arch falls into RET KILL_PROCESS.
    instructions.append(_bpf_jump(_BPF_JMP | _BPF_JEQ | _BPF_K, arch_value, 1, 0))
    # 2: RET KILL_PROCESS — wrong arch: kill the process
    instructions.append(_bpf_stmt(_BPF_RET, 0x80000000))
    # 3: LD [0]   — load syscall number
    instructions.append(_bpf_stmt(_BPF_LD | _BPF_W | _BPF_ABS, _SECCOMP_DATA_NR))
    # 4..3+N: linear JEQ chain
    for idx, nr in enumerate(sorted_denies):
        # jt: on match, jump forward to the deny block (instruction deny_block_index)
        # jf: on no match, fall through to the NEXT instruction (the next JEQ
        #     in the chain, or RET ALLOW after the last one).
        #
        # BPF jump offsets are relative to the *next* instruction, so
        # fall-through is jf=0. A jf=1 here would skip the next JEQ
        # entirely — every other deny NR silently bypassed the filter
        # (root cause of the TJ-DF-020 clock_adjtime/305 miss: 305 sits
        # at an odd chain position and was never consulted).
        jt = deny_block_index - (len(instructions) + 1)
        instructions.append(_bpf_jump(_BPF_JMP | _BPF_JEQ | _BPF_K, nr, jt, 0))
    # 3+N+1: RET ALLOW — no match in the JEQ chain
    instructions.append(_bpf_stmt(_BPF_RET, _SECCOMP_RET_ALLOW))
    # 3+N+2 = deny_block_index: RET ERRNO|EPERM — the deny block
    instructions.append(_bpf_stmt(_BPF_RET, _SECCOMP_RET_ERRNO | _EPERM))

    body = b"".join(instructions)
    return body, len(instructions)


def build_bpf_program(
    *, arch: str | None = None, extra_denies: frozenset[int] = frozenset()
) -> tuple[bytes, int, int]:
    """Return ``(encoded_sock_filter_bytes, instruction_count, audit_arch)``.

    Parameters
    ----------
    arch:
        Target architecture name (e.g. ``"x86_64"``). Defaults to the host
        architecture from :func:`platform.machine`.
    extra_denies:
        Additional syscall numbers to deny, merged into the default set.

    Raises
    ------
    SeccompUnsupportedError
        If the requested (or detected) architecture is not in :data:`_ARCH_TABLE`.
    """
    if arch is None:
        arch = platform.machine()
    target: _Arch | None = next((a for a in _ARCH_TABLE if a.name == arch), None)
    if target is None:
        raise SeccompUnsupportedError(
            f"seccomp filter does not support architecture {arch!r}"
        )
    deny_set = _DENY_EXTRA.get(target.name, frozenset()) | set(extra_denies)
    body, count = _build_filter(target.audit_arch, frozenset(deny_set))
    return body, count, target.audit_arch


def filter_for_host() -> tuple[bytes, int, int]:
    """Like :func:`build_bpf_program` but pinned to the current host arch."""
    return build_bpf_program()


def deny_set_for_arch(arch: str) -> frozenset[int]:
    """Return the syscall numbers that will be denied for ``arch``.

    Exposed for testing and for documentation tooling.
    """
    if arch not in _DENY_EXTRA:
        raise SeccompUnsupportedError(f"unknown architecture {arch!r}")
    return _DENY_EXTRA[arch]


def supported_architectures() -> tuple[str, ...]:
    """Return the names of architectures for which a filter can be built."""
    return tuple(a.name for a in _ARCH_TABLE)


# --- Apply filter via prctl --------------------------------------------------


def _libc() -> ctypes.CDLL:
    libc_name = ctypes.util.find_library("c") or "libc.so.6"
    return ctypes.CDLL(libc_name, use_errno=True)


def apply_filter(
    *,
    arch: str | None = None,
    extra_denies: frozenset[int] = frozenset(),
    libc: ctypes.CDLL | None = None,
) -> int:
    """Install the BPF filter on the calling thread.

    Returns the kernel return value from ``prctl`` (``0`` on success).

    Raises
    ------
    SeccompError
        If the filter cannot be applied. The error message is suitable for
        end users — callers can print it and continue without seccomp.
    """
    body, count, _audit = build_bpf_program(arch=arch, extra_denies=extra_denies)
    if libc is None:
        libc = _libc()

    # struct sock_fprog { unsigned short len; struct sock_filter *filter; }
    class _SockFilter(ctypes.Structure):
        _fields_ = [
            ("code", ctypes.c_uint16),
            ("jt", ctypes.c_uint8),
            ("jf", ctypes.c_uint8),
            ("k", ctypes.c_uint32),
        ]

    class _SockFprog(ctypes.Structure):
        _fields_ = [
            ("len", ctypes.c_uint16),
            ("filter", ctypes.POINTER(_SockFilter)),
        ]

    # Cast the encoded filter bytes to a _SockFilter pointer the kernel
    # can read. The pointer must remain valid across the prctl call.
    flt = ctypes.cast(ctypes.c_char_p(body), ctypes.POINTER(_SockFilter))
    fprog = _SockFprog(len=count, filter=flt)
    fprog_ref = ctypes.byref(fprog)

    # Build the ifunc for prctl: long prctl(int option, unsigned long arg2, ...)
    # Full variadic arity so ctypes accepts the 5-argument calls below.
    prctl = libc.prctl
    prctl.restype = ctypes.c_long
    prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]

    # PR_SET_NO_NEW_PRIVS must be set before PR_SET_SECCOMP: an unprivileged
    # process cannot install a filter otherwise (EPERM). It is a one-way
    # latch — once set it can never be cleared, and the payload inherits it
    # across exec, which is intended.
    rv = prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
    if rv != 0:
        err = ctypes.get_errno()
        message = os.strerror(err) if err else "unknown error"
        raise SeccompPermissionError(
            f"prctl(PR_SET_NO_NEW_PRIVS) failed: {message} (errno={err}) — "
            "cannot install seccomp filter without no_new_privs"
        )

    rv = prctl(
        _PR_SET_SECCOMP,
        _SECCOMP_MODE_FILTER,
        ctypes.cast(fprog_ref, ctypes.c_void_p),
        0,
        0,
    )
    if rv != 0:
        err = ctypes.get_errno()
        message = os.strerror(err) if err else "unknown error"
        if err in (errno.EPERM, errno.EACCES):
            raise SeccompPermissionError(
                f"prctl(PR_SET_SECCOMP) refused the filter: {message} "
                f"(missing CAP_SYS_ADMIN or no_new_privs set?)"
            )
        raise SeccompError(f"prctl(PR_SET_SECCOMP) failed: {message} (errno={err})")
    return rv


# --- High-level loader entry point -------------------------------------------


@dataclass(frozen=True, slots=True)
class SeccompApplyResult:
    """Outcome of :func:`try_apply` — useful for tests and metrics."""

    applied: bool
    reason: str = ""
    instructions: int = 0


def try_apply(*, extra_denies: frozenset[int] = frozenset()) -> SeccompApplyResult:
    """Best-effort: try to apply the seccomp filter, log on failure.

    Returns a :class:`SeccompApplyResult` describing the outcome. On
    success the filter is installed on the calling thread (and inherited
    by any subprocesses via fork or exec).

    This function never raises — it is the entry point the standalone
    loader uses so a missing capability or kernel rejection falls back to
    running the payload without seccomp.
    """
    try:
        _body, count, _ = build_bpf_program(extra_denies=extra_denies)
    except SeccompUnsupportedError as exc:
        LOGGER.warning("terminal-jail: %s; running without seccomp", exc)
        return SeccompApplyResult(applied=False, reason=str(exc))
    try:
        apply_filter(extra_denies=extra_denies)
    except SeccompError as exc:
        LOGGER.warning(
            "terminal-jail: seccomp filter not installed (%s); running without seccomp",
            exc,
        )
        return SeccompApplyResult(applied=False, reason=str(exc))
    return SeccompApplyResult(applied=True, instructions=count)


__all__ = [
    "SeccompApplyResult",
    "SeccompError",
    "SeccompPermissionError",
    "SeccompUnsupportedError",
    "apply_filter",
    "build_bpf_program",
    "deny_set_for_arch",
    "filter_for_host",
    "seccomp_enabled_from_environment",
    "supported_architectures",
    "try_apply",
]
