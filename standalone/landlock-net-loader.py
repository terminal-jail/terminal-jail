#!/usr/bin/env python3
"""
terminal-jail Landlock NETWORK (egress) loader — TJ-GAP-083.

Applies the kernel-enforced Landlock TCP-connect tier to the calling
process, then exec's the provided command. Composes with (never replaces)
the filesystem tier's loader (landlock-loader.py, TJ-GAP-082): run it
AFTER the fs loader so the egress domain stacks INSIDE the filesystem
domain — Landlock restrictions accumulate across landlock_restrict_self
and can only shrink what the payload may do.

Usage:
  landlock-net-loader.py [--] <command> [args...]

Environment:
  TERMINAL_JAIL_LANDLOCK_NET — "1"/"true"/"yes"/"on" enables the tier;
      unset/"0"/"off"/"false" keeps it off (the loader execs the command
      unchanged, silently: the knob is the operator's deliberate opt-in).
  TERMINAL_JAIL_LANDLOCK_NET_ALLOW — connect allowlist: ports and/or
      service names (default "22,53,80,443": ssh, DNS-over-TCP, http,
      https). An invalid token REFUSES the tier (fail-closed), printing
      the cause.

Exit:
  Tier applied (proven by the connect-probe property preflight) → the
  process exec's the command and inherits its exit code. The Landlock
  domain survives exec, so the command and every descendant get
  EPERM/EACCES from connect() to any non-allowlisted TCP port. ONE
  stderr notice precedes the payload: every such denial below it is the
  KERNEL enforcing the tier (TJ-GAP-083), distinct from an interruptor
  rule verdict (which names its rule id and fires before execution).
  Tier not applied (Landlock ABI < 4, enforcement unproven, allowlist
  refused) → ONE warning naming the cause on stderr, then the command
  is exec'd unchanged — behavior identical to the pre-tier launch, never
  a failure (the tier is deny-path hardening, not a gate).

The tier module is imported BY PATH, deliberately (same pattern as
landlock-loader.py): importing it through the ``terminal_jail``
package would run package machinery; landlock_net.py is stdlib-only
besides its landlock.py sibling import, which the by-path import
resolves relative to its own file location.
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _find_landlock_net_module():
    """Locate and exec landlock_net.py by path (repo checkout + installed)."""
    loader_dir = os.path.dirname(os.path.abspath(__file__))
    current = loader_dir
    while True:
        for base in (
            os.path.join(current, "plugin", "terminal_jail", "interruptor"),
            current,
        ):
            candidate = os.path.join(base, "landlock_net.py")
            if os.path.isfile(candidate):
                spec = importlib.util.spec_from_file_location(
                    "terminal_jail_landlock_net_standalone", candidate
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
        print("usage: landlock-net-loader.py [--] <command> [args...]", file=sys.stderr)
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
    module = _find_landlock_net_module()
    if module is None:
        print(
            "terminal-jail: WARNING: Landlock network (egress) tier not applied "
            "(tier module not found next to the loader); running the command "
            "unchanged",
            file=sys.stderr,
        )
        _exec_payload()

    # cwd is irrelevant to THIS tier (port rules have no filesystem
    # component); the allowlist resolves from the environment alone.
    applied, cause = module.apply_net_tier()
    if not applied and cause:
        print(
            f"terminal-jail: WARNING: Landlock network (egress) tier not applied "
            f"({cause}); commands run with network egress unchanged — classify "
            f"the host with scripts/landlock-capability-probe.py (network rules "
            f"need Landlock ABI >= {module.NET_ABI_MIN}), or disable this "
            f"warning deliberately with {module.ENV_VAR}=0",
            file=sys.stderr,
        )
    elif applied:
        print(
            module.kernel_denial_notice(module.build_layout().allow_ports),
            file=sys.stderr,
        )
    _exec_payload()


if __name__ == "__main__":
    _main()
