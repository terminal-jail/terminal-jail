"""pytest configuration for terminal-jail tests."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _simulate_namespace_refusal(request, monkeypatch, tmp_path_factory):
    """Inject a failing unshare only into real wrapper launches in QA modules."""
    if os.environ.get("TERMINAL_JAIL_TEST_REFUSAL_SIM") != "1":
        return
    if request.module.__name__.split(".")[-1] not in {
        "test_install",
        "test_interruptor",
        "test_modify_preflight",
        "test_wrapper_landlock_interpreter",
    }:
        return
    shim_dir = tmp_path_factory.mktemp("refusal-bin")
    shim = shim_dir / "unshare"
    shim.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    shim.chmod(0o755)
    real_run = subprocess.run

    def run(*args, **kwargs):
        command = args[0] if args else kwargs.get("args", ())
        if isinstance(command, (list, tuple)) and any(
            str(arg).endswith("/terminal-jail") for arg in command[:2]
        ):
            env = dict(kwargs.get("env") or os.environ)
            # Preserve purpose-built unshare stubs used by deterministic tests.
            path = env.get("PATH", os.defpath)
            if request.module.__name__.split(".")[
                -1
            ] != "test_modify_preflight" or not (
                len(path.split(os.pathsep)) == 1 and (Path(path) / "unshare").exists()
            ):
                env["PATH"] = str(shim_dir) + os.pathsep + path
                env["TERMINAL_JAIL_COMPOSED"] = "off"
                env["TERMINAL_JAIL_JAIL_BACKEND"] = "unshare"
                kwargs["env"] = env
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)


# Add plugin directory to sys.path so tests can import terminal_jail
sys.path.insert(0, str(Path(__file__).parent))
