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


def _main() -> None:
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

    args = sys.argv[1:]
    if not args:
        print("Usage: seccomp-loader.py [--] <command> [args...]", file=sys.stderr)
        sys.exit(2)

    os.execvp(args[0], args)


if __name__ == "__main__":
    _main()
