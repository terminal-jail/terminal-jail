#!/usr/bin/env python3
"""
terminal-jail Landlock loader — TJ-GAP-082.

Applies the kernel-enforced Landlock filesystem tier to the calling
process, then exec's the provided command. Designed to be invoked from
the standalone CLI as the LAUNCH TAIL of an unshare namespace prefix
(the tier composes with — not replaces — the unshare/bwrap path; it must
be applied INSIDE the final namespace, immediately before the payload).

Usage:
  landlock-loader.py [--] <command> [args...]

Environment:
  TERMINAL_JAIL_LANDLOCK — "0"/"off"/"false" disables the tier (the
      loader execs the command unchanged, silently: the disable is
      deliberate). Unset/truthy attempts the tier.
  TERMINAL_JAIL_LANDLOCK_INHERITED — INTERNAL, set by this loader and only
      AFTER it proved an apply; never an operator knob. A launch can carry
      more than one attach (the wrapper's trampoline applies the tier in the
      un-namespaced caller context, then the payload re-attaches inside the
      namespace). Landlock restriction INHERITS across the namespace
      boundary, so the outer domain enforces for the payload — and that same
      inherited domain is what makes the inner attach's enforcement probe
      unprovable (the probe host is not writable beneath it). With the
      marker AND the kernel's NoNewPrivs flag set, an unprovable attach
      reports the INHERITED tier instead of claiming there is none
      (TJ-DF-072). Without the marker an unprovable attach still degrades
      loudly — a launch with no ancestor domain never silently downgrades.

Exit:
  Tier applied (proven by the EACCES property preflight) → the process
  exec's the command and inherits its exit code. The Landlock domain
  survives exec, so the command and every descendant run restricted.
  Tier not applied (Landlock absent, enforcement unproven, layout
  refused) → ONE warning naming the cause on stderr, then the command
  is exec'd unchanged — behavior identical to the pre-tier launch, never
  a failure (the tier is deny-path hardening, not a gate). The single
  exception is the inherited-domain shape above, which reports the tier.

The tier module is imported BY PATH, deliberately: importing it through
the ``terminal_jail.interruptor`` package would run that package's
__init__ (the decider), whose import already applies the tier in every
engine process — a loader process must apply the tier exactly once, on
its own schedule (module landlock.py is stdlib-only, so a file-location
import needs no package machinery).
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _find_landlock_module():
    """Locate and exec landlock.py by path (repo checkout + installed wheel).

    Repo checkout: ``<root>/plugin/terminal_jail/interruptor/landlock.py``
    found by walking up from the loader. Installed wheel (TJ-DF-060): the
    loader ships under ``terminal_jail/_bundled/`` and the tier module is
    its SIBLING directory ``terminal_jail/interruptor/landlock.py`` —
    the ``<current>/interruptor`` base covers it at the package root.
    """
    loader_dir = os.path.dirname(os.path.abspath(__file__))
    current = loader_dir
    while True:
        for base in (
            os.path.join(current, "plugin", "terminal_jail", "interruptor"),
            os.path.join(current, "interruptor"),
            current,
        ):
            candidate = os.path.join(base, "landlock.py")
            if os.path.isfile(candidate):
                spec = importlib.util.spec_from_file_location(
                    "terminal_jail_landlock_standalone", candidate
                )
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    # The dataclass decorator resolves type hints through
                    # sys.modules[cls.__module__]; the module must be
                    # registered BEFORE exec_module (documented pattern).
                    sys.modules[spec.name] = module
                    spec.loader.exec_module(module)
                    return module
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


_INHERITED_ENV = "TERMINAL_JAIL_LANDLOCK_INHERITED"


def _applied_notice() -> str:
    """The fs-tier twin of the net loader's 'kernel egress tier APPLIED' line.

    Printed when THIS attach cannot re-prove the property but the launch
    already has a domain that does the enforcing (TJ-DF-072). Twins
    ``landlock_net.kernel_denial_notice`` so an operator reads the same
    contract on both tiers: EACCES/EPERM below this line is the kernel.
    """
    return (
        "terminal-jail: landlock: kernel filesystem tier APPLIED — inherited "
        "from the launch's outer attach, which proved enforcement before the "
        "namespace boundary; EACCES/EPERM from open() below this line is the "
        "KERNEL denying (Landlock, TJ-GAP-082), not an interruptor rule "
        "verdict"
    )


def _no_new_privs_set() -> bool:
    """Read the kernel's NoNewPrivs flag — the second half of the evidence.

    Landlock requires no_new_privs before ``restrict_self``; the flag
    inherits across exec AND the namespace boundary and cannot be cleared
    from userspace, so it is kernel-observable proof that the process is
    inside someone's hardened lineage rather than a fresh shell that merely
    inherited a stray environment variable. Unreadable ⇒ False: an
    unconfirmable marker must never silence a genuine warning.
    """
    try:
        with open("/proc/self/status", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("NoNewPrivs:"):
                    return line.split(":", 1)[1].strip() == "1"
    except OSError:
        return False
    return False


def _inherited_tier_active() -> bool:
    """True when an ANCESTOR attach in this launch proved the tier.

    The marker is written by this loader only after a proven apply, so it
    encodes evidence, never intent: a launch that WANTS the tier but has no
    ancestor attach cannot manufacture it, and a stale/forged marker still
    fails the NoNewPrivs conjunct. Both halves are cheap (one env read, one
    /proc/self/status read) and neither touches containment.
    """
    return os.environ.get(_INHERITED_ENV) == "1" and _no_new_privs_set()


def _report_not_applied(message: str) -> None:
    """ONE stderr line for every not-applied outcome (TJ-DF-072).

    With an inherited, proven domain the tier IS delivering containment, so
    the "commands run unchanged without kernel filesystem enforcement"
    family is false — report the inherited APPLIED tier instead. Without
    one, print the genuine warning unchanged: a real degraded shape is
    never silently downgraded.
    """
    print(_applied_notice() if _inherited_tier_active() else message, file=sys.stderr)


def _exec_payload() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        print("usage: landlock-loader.py [--] <command> [args...]", file=sys.stderr)
        raise SystemExit(2)
    # Preserve the shell's exec-failure contract: a missing command is
    # 127 (not found), a non-executable one 126 — a Python traceback with
    # exit 1 would change every caller's error handling.
    try:
        os.execvp(args[0], args)
    except FileNotFoundError:
        print(f"terminal-jail: {args[0]}: command not found", file=sys.stderr)
        raise SystemExit(127) from None
    except PermissionError:
        print(f"terminal-jail: {args[0]}: Permission denied", file=sys.stderr)
        raise SystemExit(126) from None


def _main() -> None:
    module = _find_landlock_module()
    if module is None:
        _report_not_applied(
            "terminal-jail: WARNING: Landlock filesystem tier not applied "
            "(tier module not found next to the loader); running the command "
            "unchanged"
        )
        _exec_payload()

    # cwd IS the workdir the tier grants: apply_tier()/build_layout()
    # resolve it from the inherited working directory of the launch.
    applied, cause = module.apply_tier()
    if applied:
        # TJ-DF-072: a PROVEN apply is the evidence every later attach in
        # this launch relies on. The marker is set only here, after the
        # proof, so it can never stand in for a launch that merely wants
        # the tier; it rides the environment into the payload and across
        # the namespace boundary (Landlock restriction inherits there).
        os.environ[_INHERITED_ENV] = "1"
    elif cause:
        _report_not_applied(
            f"terminal-jail: WARNING: Landlock filesystem tier not applied "
            f"({cause}); commands run unchanged without kernel filesystem "
            "enforcement — classify the host with "
            "scripts/landlock-capability-probe.py and verify the loader path "
            "and launch context; do not disable filesystem protection to "
            "suppress this warning"
        )
    _exec_payload()


if __name__ == "__main__":
    _main()
