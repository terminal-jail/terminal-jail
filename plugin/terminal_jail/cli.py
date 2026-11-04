"""Console-script entry point for a pip-installed terminal-jail wheel.

The real CLI is the standalone bash script (``standalone/terminal-jail`` in
the repository checkout). A wheel ships it byte-identically as package data
under ``terminal_jail/_bundled/`` together with the three tier loaders, and
this module execs bash on it after pointing the wrapper's environment at the
shipped copies (RELPKG-001):

- ``TERMINAL_JAIL_VERSION`` — from importlib.metadata. A wheel has no
  sibling pyproject.toml, so the script's checkout fallback cannot resolve
  and ``--version`` would print an empty version.
- ``TERMINAL_JAIL_SECCOMP_LOADER`` / ``TERMINAL_JAIL_LANDLOCK_LOADER`` /
  ``TERMINAL_JAIL_LANDLOCK_NET_LOADER`` — the shipped loader copies, so the
  seccomp and Landlock tiers work instead of degrading with a
  "loader not found next to the plugin" warning.
- ``TERMINAL_JAIL_BRIDGE`` — the shipped ``interruptor_bridge.py``, so
  interruptor mode does not depend on ``python3`` resolving the venv.

Every variable is set only when unset/empty and only when the target file
exists, so operator overrides keep priority and the wrapper's hard-failure
contract for an explicit-but-missing bridge is preserved. The process image
is replaced with ``os.execvp``: exit status, stdin/stdout/stderr and signal
dispositions are the bash script's own.
"""

from __future__ import annotations

import importlib.metadata
import os
import sys
from pathlib import Path

_BUNDLED_DIR = Path(__file__).resolve().parent / "_bundled"
_CLI_SCRIPT = _BUNDLED_DIR / "terminal-jail"

# Loader overrides the wrapper honours (standalone/terminal-jail loader
# resolution block), mapped to the bundled copy names. The wrapper treats
# each independently; an unset/empty variable is the "not overridden" state.
_LOADER_ENV = {
    "TERMINAL_JAIL_SECCOMP_LOADER": "seccomp-loader.py",
    "TERMINAL_JAIL_LANDLOCK_LOADER": "landlock-loader.py",
    "TERMINAL_JAIL_LANDLOCK_NET_LOADER": "landlock-net-loader.py",
}


def _apply_bundled_environment() -> None:
    """Point the wrapper's environment at the shipped copies (no overrides)."""
    env = os.environ
    if not env.get("TERMINAL_JAIL_VERSION"):
        try:
            env["TERMINAL_JAIL_VERSION"] = importlib.metadata.version("terminal-jail")
        except importlib.metadata.PackageNotFoundError:
            pass
    for var, name in _LOADER_ENV.items():
        if not env.get(var):
            candidate = _BUNDLED_DIR / name
            if candidate.is_file():
                env[var] = str(candidate)
    if not env.get("TERMINAL_JAIL_BRIDGE"):
        bridge = _BUNDLED_DIR.parent / "interruptor_bridge.py"
        if bridge.is_file():
            env["TERMINAL_JAIL_BRIDGE"] = str(bridge)


def main(argv: list[str] | None = None) -> int:
    """Exec the bundled bash CLI with ``argv``; never returns on success."""
    if argv is None:
        argv = sys.argv[1:]
    if not _CLI_SCRIPT.is_file():
        print(
            f"terminal-jail: bundled CLI missing at {_CLI_SCRIPT} (broken install?)",
            file=sys.stderr,
        )
        return 127
    _apply_bundled_environment()
    try:
        os.execvp("bash", ["bash", str(_CLI_SCRIPT), *argv])
    except OSError as exc:  # exec failed — the bash script never ran
        print(f"terminal-jail: cannot exec bash: {exc}", file=sys.stderr)
        return 127
