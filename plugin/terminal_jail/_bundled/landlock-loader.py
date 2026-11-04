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

Exit:
  Tier applied (proven by the EACCES property preflight) → the process
  exec's the command and inherits its exit code. The Landlock domain
  survives exec, so the command and every descendant run restricted.
  Tier not applied (Landlock absent, enforcement unproven, layout
  refused) → ONE warning naming the cause on stderr, then the command
  is exec'd unchanged — behavior identical to the pre-tier launch, never
  a failure (the tier is deny-path hardening, not a gate).

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
    """Locate and exec landlock.py by path (repo checkout + installed lib)."""
    loader_dir = os.path.dirname(os.path.abspath(__file__))
    current = loader_dir
    while True:
        for base in (
            os.path.join(current, "plugin", "terminal_jail", "interruptor"),
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
        print(
            "terminal-jail: WARNING: Landlock filesystem tier not applied "
            "(tier module not found next to the loader); running the command "
            "unchanged",
            file=sys.stderr,
        )
        _exec_payload()

    # cwd IS the workdir the tier grants: apply_tier()/build_layout()
    # resolve it from the inherited working directory of the launch.
    applied, cause = module.apply_tier()
    if not applied and cause:
        print(
            f"terminal-jail: WARNING: Landlock filesystem tier not applied "
            f"({cause}); commands run unchanged without kernel filesystem "
            "enforcement — classify the host with "
            "scripts/landlock-capability-probe.py, or disable this warning "
            "deliberately with TERMINAL_JAIL_LANDLOCK=0",
            file=sys.stderr,
        )
    _exec_payload()


if __name__ == "__main__":
    _main()
