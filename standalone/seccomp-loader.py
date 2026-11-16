#!/usr/bin/env python3
"""
terminal-jail seccomp loader — T9.5.

Applies the seccomp BPF filter to the calling process, then exec's the
provided command.  Designed to be invoked from the standalone CLI when
``--seccomp`` is requested.

Usage:
  seccomp-loader.py [--] <command> [args...]

Environment:
  TERMINAL_JAIL_SECCOMP  — truthy (1/true/yes/on) enables the filter.
                            Default disabled.  The standalone CLI sets
                            this before invoking the loader.

Exit:
  If the filter is applied, the process exec's the command and inherits
  its exit code.
  If the filter cannot be applied, a warning is written to stderr and
  the command is exec'd without seccomp.
  A missing command is a usage error (exit 2).  A command that cannot be
  found exits 127; a command that cannot be executed exits 126.
"""

from __future__ import annotations

import os
import sys


def _setup_path() -> None:
    """Add the plugin directory to sys.path so we can import terminal_jail.

    The plugin package lives at ``plugin/terminal_jail/`` relative to the
    repo root in a checkout, and at ``<lib>/terminal-jail/plugin/terminal_jail/``
    in the installed layout (install.sh local mode ships the loader one level
    above the plugin tree).  Walk up from this loader's own directory until a
    directory containing ``plugin/terminal_jail`` (or a bare ``terminal_jail``
    package) is found, so both layouts resolve (TJ-DF-002).
    """
    loader_dir = os.path.dirname(os.path.abspath(__file__))
    current = loader_dir
    while True:
        plugin_dir = os.path.join(current, "plugin")
        if os.path.isdir(os.path.join(plugin_dir, "terminal_jail")):
            if plugin_dir not in sys.path:
                sys.path.insert(0, plugin_dir)
            return
        if os.path.isdir(os.path.join(current, "terminal_jail")):
            if current not in sys.path:
                sys.path.insert(0, current)
            return
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent


def _payload_args(argv: list[str]) -> list[str]:
    """Return the payload, consuming one leading ``--`` separator."""
    if argv and argv[0] == "--":
        argv = argv[1:]
    return argv


def _print_help() -> None:
    print("Usage: seccomp-loader.py [--] <command> [args...]")
    print("       seccomp-loader.py -h|--help")


def _exec_payload(args: list[str]) -> None:
    """Exec the payload, preserving the shell-compatible failure contract."""
    if not args:
        print("Usage: seccomp-loader.py [--] <command> [args...]", file=sys.stderr)
        raise SystemExit(2)

    try:
        os.execvp(args[0], args)
    except FileNotFoundError:
        print(f"terminal-jail: {args[0]}: command not found", file=sys.stderr)
        raise SystemExit(127) from None
    except PermissionError:
        print(f"terminal-jail: {args[0]}: Permission denied", file=sys.stderr)
        raise SystemExit(126) from None


def _main() -> None:
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] in ("-h", "--help"):
        _print_help()
        return

    _setup_path()

    from terminal_jail.seccomp import seccomp_enabled_from_environment, try_apply

    if seccomp_enabled_from_environment():
        result = try_apply()
        if not result.applied:
            print(
                f"terminal-jail: seccomp not applied ({result.reason}); "
                f"running without seccomp",
                file=sys.stderr,
            )

    _exec_payload(_payload_args(sys.argv[1:]))


if __name__ == "__main__":
    _main()
