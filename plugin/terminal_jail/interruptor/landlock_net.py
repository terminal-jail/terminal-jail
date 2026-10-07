"""Landlock TCP-connect (network egress) tier (TJ-GAP-083).

A kernel-enforced egress tier that composes with the filesystem tier
(TJ-GAP-082): where the regex egress rules (TJ-GAP-058 — /dev/tcp,
``nc -e``, ``socat EXEC:`` ...) can only match command STRINGS, this tier
denies ``connect(2)`` on TCP sockets at the KERNEL level. The 22-payload
review matrix showed the regex class misses raw sockets and tunnels — a
bare ``python3 -c "socket...connect(('host', port))"`` or a relay tool's
outbound leg never mentions a blocked token. Landlock ABI v4
(``LANDLOCK_ACCESS_NET_CONNECT_TCP`` on the ruleset's
``handled_access_net``) closes exactly that gap: ANY process in the
domain — the payload and every descendant, exec and fork included — gets
EPERM/EACCES from ``connect()`` unless the destination PORT is explicitly
allowlisted. The rule granularity is the port (Landlock v4 has no
host/address selector); a deny is therefore FAIL-CLOSED by construction —
everything not granted is denied — and allow entries are explicit.

Threat model fit: the tier is deny-path hardening, NOT a gate. It is
opt-in (``TERMINAL_JAIL_LANDLOCK_NET``; unset = off, unlike the fs tier —
a kernel-wide egress deny on an undocumented allowlist changes payload
behavior in ways an operator must choose deliberately).

Knobs:
- ``TERMINAL_JAIL_LANDLOCK_NET`` — ``1/true/yes/on`` enables the tier;
  unset/``0/off/false`` (and any unrecognised value) keeps it off
  (fail-closed knob semantics, mirrored from
  ``landlock_enabled_from_environment``).
- ``TERMINAL_JAIL_LANDLOCK_NET_ALLOW`` — the connect allowlist: comma/
  space-separated ports or service names (``443``, ``https``, ``ssh``,
  ``domain``, ``53/tcp``...). Unset → the documented default allowlist
  (``DEFAULT_EGRESS_ALLOW_PORTS``: SSH 22, DNS-over-TCP 53, HTTP 80,
  HTTPS 443 — git push/fetch, pip/pypi, apt and general TLS traffic).
  A parse failure REFUSES the tier (never a silent broader allow).

Distinguishing a kernel denial from a rule verdict (operator contract):
the interruptor's regex BLOCK prints a rule-engine verdict naming the
rule id; this tier's denial happens at connect() time INSIDE the payload
and surfaces as EPERM/EACCES from the payload's own socket call. The
loader prints ONE stderr line when the tier is applied
(``kernel_denial_notice``) — any EPERM/EACCES from ``connect()`` below
that line is the KERNEL, not a rule. ``apply_net_tier()`` returns the
programmatic verdict for tools.

Preflight lesson (TJ-DF-015, applied like the fs tier): ``apply()``
proves the PROPERTY before restricting this process — inside a forked
child that applied the finished ruleset, a real ``connect()`` to a
bound-but-unallowlisted loopback listener must fail EACCES/EPERM AND a
connect to a allowlisted one must SUCCEED (no-overblock half). Any other
outcome raises ``LandlockError`` and THIS PROCESS STAYS UNRESTRICTED.

Degrades honestly on hosts without Landlock ABI >= 4: the tier raises
``LandlockUnsupportedError`` naming the ABI (or reports the cause
through ``apply_net_tier()``/the loader's one-line warning) — never a
silent no-op while enabled.

Implementation: ctypes against the kernel syscalls via landlock.py's
shared helpers (``_syscall``, ``_prctl_no_new_privs``, ``_require_arch``,
``abi_version`` — no python-landlock dependency, stdlib only, same arch
allowlist 444-446). The ``landlock_net_port_attr.port`` field is in HOST
endianness per linux/landlock.h (measured: the htons spelling denies the
allowlisted port too). The standalone pre-exec entry point is
``standalone/landlock-net-loader.py``; ``sandbox_prefix()`` is the
engine seam decider.py composes after the fs tier's tail.
"""

from __future__ import annotations

import ctypes
import importlib.util
import logging
import os
import shlex
import socket
import sys
from dataclasses import dataclass, field

try:
    from .landlock import (
        LandlockError,
        LandlockUnsupportedError,
        _libc,
        _prctl_no_new_privs,
        _require_arch,
        _syscall,
        _world_traversable,
        abi_version,
    )
except ImportError:  # by-path import (standalone/landlock-net-loader.py)
    # There is no parent package under a file-location import, so the
    # sibling is resolved NEXT TO THIS FILE and registered in sys.modules
    # BEFORE exec_module (the documented dataclass-hint pattern). The
    # helpers/exceptions are rebound to THIS module's names so
    # ``except LandlockError`` and the _world_traversable calls stay
    # identity-correct in every entry point.
    _fs_spec = importlib.util.spec_from_file_location(
        "terminal_jail_landlock_fs_by_path",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "landlock.py"),
    )
    assert _fs_spec is not None and _fs_spec.loader is not None
    _fs = importlib.util.module_from_spec(_fs_spec)
    sys.modules[_fs_spec.name] = _fs
    _fs_spec.loader.exec_module(_fs)

    LandlockError = _fs.LandlockError
    LandlockUnsupportedError = _fs.LandlockUnsupportedError
    _libc = _fs._libc
    _prctl_no_new_privs = _fs._prctl_no_new_privs
    _require_arch = _fs._require_arch
    _syscall = _fs._syscall
    _world_traversable = _fs._world_traversable
    abi_version = _fs.abi_version

LOGGER: logging.Logger = logging.getLogger("terminal_jail")

# --- Environment ------------------------------------------------------------

ENV_VAR = "TERMINAL_JAIL_LANDLOCK_NET"
ENV_ALLOWLIST = "TERMINAL_JAIL_LANDLOCK_NET_ALLOW"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"", "0", "false", "no", "off"})


def net_enabled_from_environment() -> bool:
    """Parse ``TERMINAL_JAIL_LANDLOCK_NET`` (default DISABLED).

    Opt-in by design: unlike the fs tier (deny-path hardening whose
    denials are invisible to legitimate payloads), a kernel-wide egress
    deny changes behavior for every socket the payload opens, so the
    operator must turn it on deliberately. Truthy values enable;
    unset/empty/falsy/unrecognised values keep it off (unrecognised
    values warn — fail-closed knob semantics).
    """
    raw = os.environ.get(ENV_VAR)
    if raw is None:
        return False  # unset: the tier is OFF unless asked for
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value == "" or value in _FALSY:
        return False
    LOGGER.warning(
        "terminal-jail: unrecognised value %r for %s; keeping the "
        "Landlock network (egress) tier off",
        raw,
        ENV_VAR,
    )
    return False


# --- Kernel ABI (ctypes; linux/landlock.h network extensions, ABI v4) -------

# LANDLOCK_RULE_NET_PORT (linux/landlock.h enum landlock_rule_type).
LANDLOCK_RULE_NET_PORT = 2
LANDLOCK_ACCESS_NET_BIND_TCP = 1 << 0
LANDLOCK_ACCESS_NET_CONNECT_TCP = 1 << 1

# TCP connect rules landed in Landlock ABI v4 (kernel 6.7). The create
# syscall itself rejects ``handled_access_net`` on older ABIs (EINVAL);
# the explicit version gate below just produces a HONEST error first.
NET_ABI_MIN = 4


class _NetRulesetAttr(ctypes.Structure):
    """landlock_ruleset_attr with BOTH fields (ABI v4 layout, 16 bytes).

    ``handled_access_fs`` is 0 — this tier handles ONLY network rights,
    so it adds no filesystem restriction of its own and stacks cleanly
    on top of the fs tier's domain (restrictions accumulate across
    restrict_self calls; the net tier can never widen the fs domain).
    Older kernels reject a size-16 attr (E2BIG) — the same hosts that
    lack ABI v4, so the explicit ABI gate fires first with the cause.
    """

    _layout_ = "ms"  # explicit packed layout (see landlock._RulesetAttr)
    _pack_ = 1
    _fields_ = [
        ("handled_access_fs", ctypes.c_uint64),
        ("handled_access_net", ctypes.c_uint64),
    ]


class _NetPortAttr(ctypes.Structure):
    """landlock_net_port_attr: (allowed_access, port).

    ``port`` is in HOST endianness per linux/landlock.h — the kernel
    compares the numeric value; feeding htons(port) makes the rule apply
    to the WRONG port (measured on ABI 8: the allowlisted listener then
    gets denied too). Ports >65535 are refused at layout build time.
    """

    _layout_ = "ms"
    _pack_ = 1
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("port", ctypes.c_uint64),
    ]


# --- The documented allowlist ------------------------------------------------

# The default connect allowlist: what a legitimate payload plausibly
# needs (git push/fetch over ssh/https, TLS to package registries —
# pypi/pypi.org are 443 —, plain HTTP mirrors, DNS answers arriving on
# TCP after truncation). Everything else is DENIED BY OMISSION: Landlock
# is allowlist-shaped and there is no deny-rule pass.
DEFAULT_EGRESS_ALLOW_PORTS: tuple[int, ...] = (22, 53, 80, 443)

# Service-name spellings accepted in the allowlist (socket.getservbyname
# would accept thousands; the tier accepts only the ones its threat
# model names, so a typo'd service name fails loudly instead of
# resolving to something unexpected).
_SERVICE_PORTS: dict[str, int] = {
    "ssh": 22,
    "domain": 53,
    "dns": 53,
    "http": 80,
    "https": 443,
}


def parse_allowlist(raw: str) -> list[int]:
    """Parse the allowlist string into sorted unique ports; fail closed.

    Accepts comma/space/semicolon-separated tokens: plain ints (``443``),
    known service names (``https``), and ``svc/port`` / ``port/svc``
    spellings (``443/https``, ``53/tcp``). An empty string is an empty
    allowlist (deny ALL TCP connect — the operator asked for it). An
    invalid token raises ``LandlockError`` — a typo'd allowlist must
    never silently become a different policy.
    """
    ports: set[int] = set()
    for token in raw.replace(";", ",").replace(" ", ",").split(","):
        token = token.strip().lower()
        if not token:
            continue
        value: int | None = None
        if token.isdigit():
            value = int(token)
        else:
            head, _, tail = token.partition("/")
            for candidate in (token, head, tail):
                if candidate in _SERVICE_PORTS:
                    value = _SERVICE_PORTS[candidate]
                    break
                if candidate.isdigit():
                    value = int(candidate)
                    break
        if value is None or not 1 <= value <= 65535:
            raise LandlockError(
                f"invalid {ENV_ALLOWLIST} token {token!r} — expected a port "
                f"(1-65535) or one of {sorted(_SERVICE_PORTS)}; refusing to "
                "apply a misparsed allowlist",
                cause=f"invalid allowlist token {token!r}",
            )
        ports.add(value)
    return sorted(ports)


# --- Layout -------------------------------------------------------------------


@dataclass
class EgressLayout:
    """The tier's rule layout — a TCP-connect PORT allowlist.

    Landlock v4 network rules are port-granular: ``allow_ports`` are the
    only TCP destinations a connect(2) may target; EVERY other port is
    denied by omission (there is no deny-rule concept). ``denied`` is
    the informational summary of that omission, the way the fs tier's
    ``ungranted_paths`` names its denials.
    """

    allow_ports: list[int] = field(default_factory=list)
    denied: str = "all TCP connect() to non-allowlisted ports (by omission)"

    @property
    def rule_count(self) -> int:
        return len(self.allow_ports)


def build_layout(*, allow_raw: str | None = None) -> EgressLayout:
    """Compute the tier's layout from the env allowlist (or the default).

    Unlike the fs tier's ``build_layout`` this cannot return None: the
    inputs are a parsed integer list, and a bad one raises instead of
    degrading (fail-closed allowlist).
    """
    raw = os.environ.get(ENV_ALLOWLIST) if allow_raw is None else allow_raw
    if raw is None:
        ports = list(DEFAULT_EGRESS_ALLOW_PORTS)
    else:
        # UNSET → documented default; SET (even empty) → parsed verbatim,
        # so an explicitly empty allowlist is a deliberate deny-ALL, and
        # parse failures raise instead of degrading to a broader policy.
        ports = parse_allowlist(raw)
    return EgressLayout(allow_ports=ports)


# --- Connect probe (the tier's enforcement property) --------------------------


def _reserve_loopback_listener() -> socket.socket | None:
    """A listening TCP socket on 127.0.0.1 with a kernel-chosen port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
    except OSError:
        sock.close()
        return None
    return sock


class _ConnectProbe:
    """Two loopback listeners hosting the enforcement proof.

    ``denied_port`` is intentionally absent from the ruleset (the connect
    against it must be EACCES/EPERM); ``allowed_port`` is a kernel-chosen
    port the caller ADDS to the ruleset (the connect against it must
    succeed — the no-overblock half of the proof). Binding never targets
    allowlisted service ports themselves: <1024 may need privileges and
    real services may already hold them.
    """

    def __init__(self, layout_ports: list[int]) -> None:
        self._denied_sock = _reserve_loopback_listener()
        self._allowed_sock = _reserve_loopback_listener()
        self.denied_port = (
            self._denied_sock.getsockname()[1] if self._denied_sock else 0
        )
        self.allowed_port = (
            self._allowed_sock.getsockname()[1] if self._allowed_sock else 0
        )
        self.extra_ports = [self.allowed_port] if self._allowed_sock else []
        self.layout_ports = layout_ports

    @property
    def ready(self) -> bool:
        return self._denied_sock is not None and self._allowed_sock is not None

    def close(self) -> None:
        for sock in (self._denied_sock, self._allowed_sock):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


def kernel_denies_connect(host: str, port: int, *, timeout: float = 2.0) -> bool | None:
    """True when connect() is DENIED (EACCES/EPERM); False when it works.

    None = INCONCLUSIVE: connection refused (nothing listening — no
    evidence either way), timeout, or any other network error. Only a
    permission denial counts as evidence of enforcement; this mirrors
    the fs tier's ``kernel_enforced`` (clean read → False) and keeps a
    dead probe target from masquerading as a denial.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
    except (PermissionError, OSError) as exc:
        errno_value = getattr(exc, "errno", None)
        if errno_value in (errno_eacces, errno_eperm):
            return True
        return None  # refused/timeout/unreachable: no evidence
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return False


# errno spellings without importing the errno module wholesale (the fs
# module keeps to a flat stdlib surface; these are stable POSIX values).
errno_eacces = 13
errno_eperm = 1


# --- Ruleset build + apply ------------------------------------------------------


def _require_net_abi(libc: ctypes.CDLL) -> int:
    """Refuse hosts whose Landlock ABI predates network rules (v4)."""
    abi = abi_version(libc)
    if abi < NET_ABI_MIN:
        raise LandlockUnsupportedError(
            f"Landlock TCP connect rules need ABI >= {NET_ABI_MIN}; this "
            f"kernel reports ABI {abi} — the network (egress) tier cannot "
            "enforce here (classify with scripts/landlock-capability-probe.py)",
            cause=f"Landlock ABI {abi} < {NET_ABI_MIN}",
        )
    return abi


def _build_rules_fd(
    ports: list[int], libc: ctypes.CDLL, create_nr: int, add_nr: int
) -> int:
    """Create the net-only ruleset and add one allow rule per port.

    The ruleset declares ONLY ``LANDLOCK_ACCESS_NET_CONNECT_TCP``
    (handled_access_fs == 0): bind is deliberately NOT handled — the
    tier denies OUTBOUND egress, not local listeners (a payload's own
    test server keeps working; only its outbound connect() is gated).
    """
    attr = _NetRulesetAttr(0, LANDLOCK_ACCESS_NET_CONNECT_TCP)
    ctypes.set_errno(0)
    fd = _syscall(libc, create_nr, ctypes.addressof(attr), ctypes.sizeof(attr), 0)
    if fd < 0:
        code = ctypes.get_errno()
        raise LandlockError(
            f"landlock_create_ruleset(net) failed: {os.strerror(code)} (errno {code})",
            cause=f"landlock_create_ruleset(net): {os.strerror(code)}",
        )
    for port in ports:
        rule = _NetPortAttr(LANDLOCK_ACCESS_NET_CONNECT_TCP, port)  # HOST endian
        ctypes.set_errno(0)
        rv = _syscall(
            libc, add_nr, fd, LANDLOCK_RULE_NET_PORT, ctypes.addressof(rule), 0
        )
        if rv != 0:
            code = ctypes.get_errno()
            os.close(fd)
            raise LandlockError(
                f"landlock_add_rule(net port {port}) failed: "
                f"{os.strerror(code)} (errno {code})",
                cause=f"landlock_add_rule(net {port}): {os.strerror(code)}",
            )
    return fd


def apply(
    layout: EgressLayout, *, libc: ctypes.CDLL | None = None, dry_probe: bool = True
) -> int:
    """Build + apply the egress ruleset to THIS process; return rule count.

    When ``dry_probe`` (default) the enforcement PROPERTY is proven
    BEFORE this process is restricted: inside a forked child that
    applied the same ruleset, connect() to an unallowlisted (bound)
    loopback listener must be denied EACCES/EPERM AND connect() to the
    allowlisted one must succeed. Any other outcome raises
    ``LandlockError`` and THIS PROCESS STAYS UNRESTRICTED — never a
    half-applied state. On success the domain survives exec: the caller
    is a loader about to exec the payload or a test.
    """
    if libc is None:
        libc = _libc()
    create_nr, add_nr, restrict_nr = _require_arch()
    _require_net_abi(libc)

    probe: _ConnectProbe | None = (
        _ConnectProbe(layout.allow_ports) if dry_probe else None
    )
    try:
        if probe is not None and not probe.ready:
            raise LandlockError(
                "no bindable loopback port to host the connect probe — "
                "cannot prove the tier (refusing to claim it unproven)",
                cause="no bindable loopback listener for the connect probe",
            )
        ports = list(layout.allow_ports) + (probe.extra_ports if probe else [])
        fd = _build_rules_fd(ports, libc, create_nr, add_nr)
        try:
            if probe is not None:
                _prove_enforcement_in_child(probe, libc, fd, restrict_nr)
            _prctl_no_new_privs(libc)
            ctypes.set_errno(0)
            rv = _syscall(libc, restrict_nr, fd, 0)
            if rv != 0:
                code = ctypes.get_errno()
                raise LandlockError(
                    f"landlock_restrict_self failed: {os.strerror(code)} "
                    f"(errno {code})",
                    cause=f"landlock_restrict_self: {os.strerror(code)}",
                )
        finally:
            os.close(fd)
    finally:
        if probe is not None:
            probe.close()
    return len(ports)


def _prove_enforcement_in_child(
    probe: _ConnectProbe, libc: ctypes.CDLL, fd: int, restrict_nr: int
) -> None:
    """Prove BOTH halves of the property inside a forked child.

    The child applies the finished ruleset to ITSELF, then must see
    connect() to ``probe.denied_port`` FAIL with EACCES/EPERM and
    connect() to ``probe.allowed_port`` SUCCEED. The verdict comes back
    over a pipe; the parent stays unrestricted throughout and raises
    ``LandlockError`` on any outcome but the proven pair.
    """
    read_fd, write_fd = os.pipe()
    try:
        pid = os.fork()
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        raise LandlockError(
            f"cannot fork the connect-probe child: {exc}",
            cause=f"fork: {exc}",
        ) from exc
    if pid == 0:  # child: restrict, probe both arms, report, exit
        os.close(read_fd)
        verdict = b"0"
        try:
            _prctl_no_new_privs(libc)
            denied = None
            allowed = None
            if _syscall(libc, restrict_nr, fd, 0) == 0:
                denied = kernel_denies_connect("127.0.0.1", probe.denied_port)
                allowed = kernel_denies_connect("127.0.0.1", probe.allowed_port)
            if denied is True and allowed is False:
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
            "Landlock network enforcement NOT proven: inside a child that "
            "applied the ruleset, the unallowlisted connect was not denied "
            "EACCES/EPERM or the allowlisted connect failed — not claiming "
            "the tier (TJ-DF-015 preflight: prove the property, not the proxy)",
            cause="connect probe did not show the deny+allow pair in the child",
        )


# --- Loader entry point --------------------------------------------------------


def apply_net_tier() -> tuple[bool, str]:
    """Apply the tier to the calling process (loader entry point).

    Returns (True, "") after a PROVEN enforcement, or (False, cause)
    without touching the process when the tier is disabled (empty cause)
    or cannot apply (the cause names it: ABI < 4, syscall refusal,
    allowlist parse failure, unproven probe). Never raises past
    LandlockError — the loader execs the payload unchanged with the
    cause.
    """
    if not net_enabled_from_environment():
        return False, ""
    try:
        layout = build_layout()
        apply(layout, dry_probe=True)
    except LandlockError as exc:
        return False, exc.cause
    return True, ""


def kernel_denial_notice(ports: list[int]) -> str:
    """The one stderr line that makes kernel denials attributable.

    Printed by the loader AFTER a proven apply: every EPERM/EACCES a
    payload sees from connect() below this line is the KERNEL enforcing
    the egress allowlist — distinct from an interruptor rule verdict,
    which names its rule id and fires BEFORE execution (TJ-GAP-083
    operator contract).
    """
    return (
        "terminal-jail: landlock-net: kernel egress tier APPLIED — TCP "
        f"connect() restricted to ports {sorted(set(ports))}; EPERM/EACCES "
        "from connect() below this line is the KERNEL denying (Landlock, "
        "TJ-GAP-083), not an interruptor rule verdict"
    )


# --- Engine seam (single-sourced, consumed by decider.py) -----------------------

_WARNING_PREFIX = "terminal-jail: WARNING: Landlock network (egress) tier not applied"

_WARNED = False


def degradation_warning(cause: str) -> str:
    """One line naming the degradation, its cause and the way out."""
    return (
        f"{_WARNING_PREFIX} ({cause}); commands run with network egress "
        "unchanged — classify the host with scripts/landlock-capability-probe.py "
        f"(network rules need Landlock ABI >= {NET_ABI_MIN}), or disable this "
        f"warning deliberately with {ENV_VAR}=0"
    )


def _degrade(cause: str) -> str:
    """Print the loud warning ONCE per process; return the empty prefix."""
    global _WARNED
    raw = os.environ.get(ENV_VAR)
    if raw is not None and raw.strip().lower() in _FALSY:
        return ""
    if not _WARNED:
        _WARNED = True
        print(degradation_warning(cause), file=sys.stderr)
    return ""


_PROBE_ENV = "TERMINAL_JAIL_LANDLOCK_NET_PROBE"


def loader_path() -> str | None:
    """The standalone landlock-net-loader.py, or None when not shipped.

    Same walk as landlock.loader_path(): repo checkout (<root>/standalone/)
    and installed layout (<lib>/landlock-net-loader.py next to the plugin).
    """
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        for base in (
            os.path.join(current, "standalone"),
            current,
        ):
            candidate = os.path.join(base, "landlock-net-loader.py")
            if os.path.isfile(candidate):
                return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


# _world_traversable arrives bound from the fs module (package import or
# the by-path fallback above) — a launch that cannot reach the fs loader
# cannot reach this one either (same walk, same rationale).


def _probe_child_verdict() -> str:
    """The child half of the fork-isolated capability probe.

    Re-imported by path in the child (decoupling from the parent's module
    cache): the tier is APPLIED here — proof or not — and the verdict is
    one line on the pipe. The child exits without touching the parent.
    """
    module_path = os.environ[_PROBE_ENV]
    spec = importlib.util.spec_from_file_location(
        "terminal_jail_landlock_net_probe", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # before exec_module (dataclass hint walk)
    spec.loader.exec_module(module)
    try:
        module.build_layout()
        module.apply(module.build_layout(), dry_probe=True)
    except LandlockError as exc:
        return f"FAIL {exc.cause}"
    except OSError as exc:
        return f"FAIL layout build failed: {exc}"
    return "OK"


def _compute_sandbox_prefix() -> str:
    """Decide WITHOUT enforcing: the rewrite's loader applies the tier.

    The engine process must stay unrestricted, so the capability question
    is answered inside a forked child: the child applies the tier to
    ITSELF (connect-probe preflighted); "OK" proves the host CAN enforce.
    The tail is then emitted only when the loader is reachable under the
    launch. Any other outcome degrades loudly and keeps the wrap
    byte-identical to the engine without the net tier.
    """
    if not net_enabled_from_environment():
        return ""
    if _PROBE_ENV not in os.environ:
        module_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "landlock_net.py"
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
        return _degrade("landlock-net-loader.py not found next to the plugin")
    if not _world_traversable(loader):
        return _degrade(
            "landlock-net-loader.py is not reachable by the launch's payload "
            f"uid (a parent of {loader} lacks o+x — e.g. a 0700/0750 home)"
        )
    return f"python3 {shlex.quote(loader)} -- "


_SANDBOX_PREFIX_CACHE: str | None = None


def sandbox_prefix() -> str:
    """The net tier's launch-tail prefix for auto-sandbox/modify rewrites.

    ``"python3 <net-loader> -- "`` only when the tier is ENABLED
    (``TERMINAL_JAIL_LANDLOCK_NET`` truthy), the host supports Landlock
    ABI >= 4 AND the tier applies (proven by the fork-isolated
    connect-probe preflight) AND the loader is reachable; the empty
    string otherwise — in particular always empty while the knob is
    unset, so the engine's wraps stay byte-identical to the pre-tier
    behavior unless the operator opts in. Degradation is LOUD: one
    warning names the cause. Cached per process. decider.py composes
    this AFTER the fs tier's tail so the net loader runs INSIDE the fs
    domain (restrictions accumulate; the net tier cannot widen it).
    """
    global _SANDBOX_PREFIX_CACHE
    if _SANDBOX_PREFIX_CACHE is not None:
        return _SANDBOX_PREFIX_CACHE
    _SANDBOX_PREFIX_CACHE = _compute_sandbox_prefix()
    return _SANDBOX_PREFIX_CACHE


__all__ = [
    "DEFAULT_EGRESS_ALLOW_PORTS",
    "ENV_ALLOWLIST",
    "ENV_VAR",
    "EgressLayout",
    "LANDLOCK_ACCESS_NET_BIND_TCP",
    "LANDLOCK_ACCESS_NET_CONNECT_TCP",
    "LANDLOCK_RULE_NET_PORT",
    "NET_ABI_MIN",
    "LandlockError",
    "LandlockUnsupportedError",
    "apply",
    "apply_net_tier",
    "build_layout",
    "degradation_warning",
    "kernel_denial_notice",
    "kernel_denies_connect",
    "loader_path",
    "net_enabled_from_environment",
    "parse_allowlist",
    "sandbox_prefix",
]
