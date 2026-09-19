"""TJ-GAP-060 — wrapper env-scrub regression tests (LD_PRELOAD / BASH_ENV class).

Boundary this pins: Layer-1 interruptor rules evaluate only the command
string, so an environment-set loader/interpreter hook (LD_PRELOAD, BASH_ENV,
PYTHONSTARTUP, …) executes attacker-controlled code with no command to
match. Env hygiene is wrapper-layer (standalone/terminal-jail, specs/
threat-model.md). These tests launch the wrapper with every audited
variable set to a marker value and assert the marker never reaches the
jailed payload's environment — on every backend this host can run, with
grep-able HOST-DEGRADED-* skips for the ones it cannot (same philosophy
as HOST-DEGRADED-PIDNS / HOST-DEGRADED-FSISO in test_standalone_cli.py
and test_userns.py: a test that cannot run must SKIP loudly, never pass
vacuously).

Audited-variable matrix (TJ-GAP-060; wrapper behavior is backend-independent
because the scrub runs before backend selection — see test_scrub_precedes_
backend_selection):
    LD_PRELOAD / LD_LIBRARY_PATH / LD_AUDIT / LD_DEBUG      scrubbed (all backends)
    BASH_ENV / ENV                                          scrubbed (all backends)
    PYTHONSTARTUP / PYTHONPATH                              scrubbed (all backends)
    PERL5OPT / PERL5LIB                                     scrubbed (all backends)
    RUBYOPT / RUBYLIB                                       scrubbed (all backends)
    NODE_OPTIONS                                            scrubbed (all backends)
    GIT_EXEC_PATH / GEM_PATH / GEM_HOME                     scrubbed (all backends)
    CPATH / C_INCLUDE_PATH / CPLUS_INCLUDE_PATH /
        OBJC_INCLUDE_PATH                                   scrubbed (all backends)
    imported bash functions (BASH_FUNC_*%%)                 swept (all backends)
    TERMINAL_JAIL_* control vars / PATH / benign vars /
        values containing newlines                          preserved (all backends)

Known, documented residual (specs/threat-model.md): the mandated
`#!/usr/bin/env bash` shebang (install.sh integrity check) means the
wrapper interpreter's OWN startup still honors an inherited BASH_ENV/ENV
before the first statement runs. Everything the wrapper LAUNCHES — the
payload, the bridge's python3, the preflight probes — runs in the scrubbed
environment built by the first statements, and that is the surface these
tests verify.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from terminal_jail.interruptor import userns

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"

# Every audited variable → marker value an attacker might set. The marker
# value is intentionally recognizable; the assertions below check for the
# NAME's absence from the payload env (values are belt-and-braces).
HOOK_VARS: dict[str, str] = {
    "LD_PRELOAD": "/tmp/tj060-evil-preload.so",
    "LD_LIBRARY_PATH": "/tmp/tj060-evil-lib",
    "LD_AUDIT": "/tmp/tj060-evil-audit.so",
    "LD_DEBUG": "all",
    "BASH_ENV": "/tmp/tj060-evil-bashrc",
    "ENV": "/tmp/tj060-evil-envfile",
    "PYTHONSTARTUP": "/tmp/tj060-evil-startup.py",
    "PYTHONPATH": "/tmp/tj060-evil-pp",
    "PERL5OPT": "-MTJ060Evil",
    "PERL5LIB": "/tmp/tj060-evil-perl",
    "RUBYOPT": "-rtj060evil",
    "RUBYLIB": "/tmp/tj060-evil-ruby",
    "NODE_OPTIONS": "--require=/tmp/tj060-evil.js",
    "GIT_EXEC_PATH": "/tmp/tj060-evil-gitexec",
    "GEM_PATH": "/tmp/tj060-evil-gems",
    "GEM_HOME": "/tmp/tj060-evil-gemhome",
    "CPATH": "/tmp/tj060-evil-include",
    "C_INCLUDE_PATH": "/tmp/tj060-evil-cinclude",
    "CPLUS_INCLUDE_PATH": "/tmp/tj060-evil-cppinclude",
    "OBJC_INCLUDE_PATH": "/tmp/tj060-evil-objcinclude",
}
FN_NAME = "tj060_evil"


def _base_env(backend_env: dict[str, str]) -> dict[str, str]:
    """Attacker environment: every hook var set + an imported evil function."""
    env = os.environ.copy()
    for name in HOOK_VARS:
        env.pop(name, None)
    env.update(HOOK_VARS)
    # The CVE-2014-6271-class export: bash imports this into its function
    # table as `tj060_evil` at startup.
    env["BASH_FUNC_%s%%%%" % FN_NAME] = "() { echo tj060-evil-ran; }"
    # Passthrough controls that must survive the scrub.
    env["TJ060_BENIGN"] = "keep-tj060"
    env["TJ060_WEIRD"] = "line1\nPATH=/tmp/tj060-forged"
    env["TERMINAL_JAIL_INTERRUPTOR_MODE"] = "disabled"
    env.update(backend_env)
    return env


def _run_cli(
    cli: Path,
    *args: str,
    env: dict[str, str],
    timeout: int = 90,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(cli), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _payload_env_names(result: subprocess.CompletedProcess[str]) -> set[str]:
    """Variable NAMES present in a payload that ran `env | cut -d= -f1`
    (bare lines) or a raw `env` dump (KEY=value lines)."""
    names = set()
    for line in result.stdout.splitlines():
        if "=" in line:
            names.add(line.split("=", 1)[0])
        elif line.strip():
            names.add(line.strip())
    return names


# ── Host capability probes (grep-able skip markers) ─────────────────────────


def _bare_unshare_works() -> bool:
    try:
        probe = subprocess.run(
            ["unshare", "--pid", "--fork", "--mount-proc", "true"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def _user_unshare_works() -> bool:
    # The mapping-less --user launch (LEGACY_USER_FLAGS) is the one this
    # class needs: env scrub is identical on mapped and degraded hosts.
    try:
        probe = subprocess.run(
            ["unshare", *userns.LEGACY_USER_FLAGS.split(), "true"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def _bwrap_usable() -> bool:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return False
    try:
        probe = subprocess.run(
            [
                bwrap,
                "--unshare-user",
                "--unshare-pid",
                "--die-with-parent",
                "--bind",
                "/",
                "/",
                "--dev-bind",
                "/dev",
                "/dev",
                "--proc",
                "/proc",
                "true",
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


# ── Structural + attack-mechanism tests (host-independent) ──────────────────


class TestScrubStructure:
    def test_wrapper_source_names_every_audited_var(self) -> None:
        """Every audited variable must be named in the wrapper's scrub —
        dropping one from the regex assembly fails here even on a host
        where the live backends cannot run. The wrapper assembles hook
        names from adjacent string literals (`"LD_""PRELOAD"`), so the
        check runs against the quote-flattened source."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        flat = text.replace('"', "")
        for name in HOOK_VARS:
            assert name in flat, f"{name} missing from wrapper scrub"
        # The two scrub phases must be present.
        assert "/proc/self/environ" in text
        assert "declare -F" in text

    def test_attack_mechanism_control_bash_env_sources(self, tmp_path: Path) -> None:
        """Control (no wrapper): a plain non-interactive bash SOURCES an
        inherited BASH_ENV before running a script — proving the attack
        class the scrub defends against is real on this bash. With the
        wrapper's scrub, the payload bash receives no BASH_ENV (the
        backend classes below pin that)."""
        marker = tmp_path / "bashenv-marker.sh"
        marker.write_text("echo BASH_ENV_SOURCED >&2\n", encoding="utf-8")
        payload = tmp_path / "payload.sh"
        payload.write_text("echo payload-ran\n", encoding="utf-8")
        env = os.environ.copy()
        env["BASH_ENV"] = str(marker)
        result = subprocess.run(
            ["bash", str(payload)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0
        assert "BASH_ENV_SOURCED" in result.stderr, (
            "expected plain bash to source inherited BASH_ENV — "
            "the mechanism this task defends against vanished?"
        )


# ── Backend classes: every hook var, per backend that can run ───────────────


class _BackendScrubBase:
    """Shared behavior: payload env must contain none of the audited vars,
    no imported function, and must keep the passthrough variables."""

    @staticmethod
    def _backend_args() -> list[str]:  # pragma: no cover - overridden
        return []

    @staticmethod
    def _backend_env() -> dict[str, str]:  # pragma: no cover - overridden
        return {}

    def _launch(self, payload: list[str]) -> subprocess.CompletedProcess[str]:
        return _run_cli(
            CLI_SCRIPT,
            *self._backend_args(),
            "--no-interruptor",
            *payload,
            env=_base_env(self._backend_env()),
        )

    def _assert_clean(self, result: subprocess.CompletedProcess[str]) -> None:
        # NOTE: payloads print variable NAMES only (env | cut -d= -f1) so a
        # failing assertion never captures unrelated session secrets that
        # ride in os.environ.
        assert result.returncode == 0, result.stderr
        names = _payload_env_names(result)
        leaked = sorted(set(HOOK_VARS) & names)
        assert not leaked, f"hook variables survived into the jail: {leaked}"
        # Imported function (or its raw BASH_FUNC_* entry) must not surface.
        assert "BASH_FUNC_" not in result.stdout
        # Passthrough must survive.
        assert "TJ060_BENIGN" in names
        delimiter_dump = _run_cli(
            CLI_SCRIPT,
            *self._backend_args(),
            "--no-interruptor",
            "bash",
            "-c",
            'printf "WEIRD<%s>END\\n" "$TJ060_WEIRD"',
            env=_base_env(self._backend_env()),
        )
        assert delimiter_dump.returncode == 0, delimiter_dump.stderr
        assert "WEIRD<line1\nPATH=/tmp/tj060-forged>END" in delimiter_dump.stdout, (
            delimiter_dump.stdout
        )

    def _payload_argv_env_dump(self) -> list[str]:
        # NAMES only: never dump the full inherited environment into test
        # output (os.environ may carry unrelated credentials).
        return ["bash", "-c", "env | cut -d= -f1"]

    def test_hook_vars_never_reach_the_jail(self) -> None:
        result = self._launch(self._payload_argv_env_dump())
        self._assert_clean(result)


@pytest.mark.integration
@pytest.mark.standalone_cli
class TestUserBackendScrub(_BackendScrubBase):
    """--user launch (mapped or degraded — the env path is identical)."""

    @staticmethod
    def _backend_args() -> list[str]:
        return ["--user"]

    @staticmethod
    def _backend_env() -> dict[str, str]:
        return {}

    def _skip_unless_userns(self) -> None:
        if not _user_unshare_works():
            pytest.skip(
                "HOST-DEGRADED-USERNS: no user namespace on this host — "
                "env scrub unverifiable through the --user launch here"
            )

    def test_hook_vars_never_reach_the_jail(self) -> None:
        self._skip_unless_userns()
        super().test_hook_vars_never_reach_the_jail()

    @pytest.mark.parametrize("var", sorted(HOOK_VARS))
    def test_var_scrubbed_individually(self, var: str) -> None:
        """One variable per launch: absence is proven per name, not just in
        aggregate (a regex typo in one alternative must fail its own test)."""
        self._skip_unless_userns()
        payload = [
            "bash",
            "-c",
            f'if [ -n "${{{var}+x}}" ]; then echo "{var}=$({var})"; fi; env',
        ]
        env = _base_env({})
        for name in HOOK_VARS:
            env.pop(name, None)
        env[var] = HOOK_VARS[var]
        env["TJ060_BENIGN"] = "keep-tj060"
        result = _run_cli(CLI_SCRIPT, "--user", "--no-interruptor", *payload, env=env)
        assert result.returncode == 0, result.stderr
        assert var not in _payload_env_names(result), f"{var} survived the scrub"
        assert "TJ060_BENIGN" in _payload_env_names(result)

    def test_imported_function_swept(self) -> None:
        self._skip_unless_userns()
        result = self._launch(
            [
                "bash",
                "-c",
                f"declare -F {FN_NAME} >/dev/null 2>&1 && echo FN-PRESENT "
                "|| echo FN-ABSENT; env",
            ]
        )
        assert result.returncode == 0, result.stderr
        assert "FN-ABSENT" in result.stdout, result.stdout
        assert "FN-PRESENT" not in result.stdout
        self._assert_clean(result)

    def test_scrub_active_with_firewall_enforced(self) -> None:
        """Default enforce mode: the bridge's python3 runs in the already
        scrubbed environment — a launch with every hook set must still
        succeed end-to-end."""
        self._skip_unless_userns()
        result = _run_cli(
            CLI_SCRIPT,
            "--user",
            "echo",
            "tj060-enforce-ok",
            env=_base_env({}),
        )
        assert result.returncode == 0, result.stderr
        assert "tj060-enforce-ok" in result.stdout


@pytest.mark.integration
@pytest.mark.standalone_cli
class TestBwrapBackendScrub(_BackendScrubBase):
    """bwrap launch (TERMINAL_JAIL_JAIL_BACKEND=bwrap)."""

    @staticmethod
    def _backend_args() -> list[str]:
        return []

    @staticmethod
    def _backend_env() -> dict[str, str]:
        return {"TERMINAL_JAIL_JAIL_BACKEND": "bwrap"}

    def _skip_unless_bwrap(self) -> None:
        if not _bwrap_usable():
            pytest.skip(
                "HOST-DEGRADED-BWRAP: bubblewrap is absent or cannot create "
                "namespaces on this host — bwrap-backend scrub not verified"
            )

    def test_hook_vars_never_reach_the_jail(self) -> None:
        self._skip_unless_bwrap()
        super().test_hook_vars_never_reach_the_jail()

    @pytest.mark.parametrize("var", sorted(HOOK_VARS))
    def test_var_scrubbed_individually(self, var: str) -> None:
        self._skip_unless_bwrap()
        payload = [
            "bash",
            "-c",
            f'if [ -n "${{{var}+x}}" ]; then echo "{var}=$({var})"; fi; env',
        ]
        env = _base_env(self._backend_env())
        for name in HOOK_VARS:
            env.pop(name, None)
        env[var] = HOOK_VARS[var]
        env["TJ060_BENIGN"] = "keep-tj060"
        result = _run_cli(CLI_SCRIPT, "--no-interruptor", *payload, env=env)
        assert result.returncode == 0, result.stderr
        assert var not in _payload_env_names(result), f"{var} survived the scrub"
        assert "TJ060_BENIGN" in _payload_env_names(result)

    def test_imported_function_swept(self) -> None:
        self._skip_unless_bwrap()
        result = self._launch(
            [
                "bash",
                "-c",
                f"declare -F {FN_NAME} >/dev/null 2>&1 && echo FN-PRESENT "
                "|| echo FN-ABSENT; env",
            ]
        )
        assert result.returncode == 0, result.stderr
        assert "FN-ABSENT" in result.stdout, result.stdout
        self._assert_clean(result)


@pytest.mark.integration
@pytest.mark.standalone_cli
class TestBareBackendScrub(_BackendScrubBase):
    """Bare launch (auto/unshare without --user)."""

    @staticmethod
    def _backend_args() -> list[str]:
        return []

    @staticmethod
    def _backend_env() -> dict[str, str]:
        return {"TERMINAL_JAIL_JAIL_BACKEND": "unshare"}

    def test_hook_vars_never_reach_the_jail(self) -> None:
        if not _bare_unshare_works():
            pytest.skip(
                "HOST-DEGRADED-PIDNS: host refused bare PID namespace "
                "creation — env scrub unverifiable through the bare launch "
                "here (the fail-closed contract is pinned by "
                "test_bare_mode_fails_closed_with_poisoned_env)"
            )
        super().test_hook_vars_never_reach_the_jail()

    def test_bare_mode_fails_closed_with_poisoned_env(self) -> None:
        """TJ-GAP-034 contract preserved: on a host that denies the bare
        launch, a poisoned environment must still exit 2 (fail-closed) —
        never fall back to an unjailed run."""
        if _bare_unshare_works():
            pytest.skip(
                "HOST-BARE-AVAILABLE: bare mode works here — the degraded "
                "exit-2 contract is not reachable on this host"
            )
        result = self._launch(["echo", "should-not-print"])
        assert result.returncode == 2, (result.returncode, result.stderr)
        assert "namespace creation failed" in result.stderr
        assert "should-not-print" not in result.stdout


@pytest.mark.integration
@pytest.mark.standalone_cli
class TestMappedBackendScrub:
    """Mapped --user launch: only reachable on hosts that permit uid
    mapping (this dev host denies it — AppArmor 'unprivileged_userns').
    The env scrub runs BEFORE backend/flag selection, so the mapped launch
    exercises the same scrub code; this class pins that equality on hosts
    where the mapping exists instead of duplicating the full matrix."""

    def test_one_hook_var_scrubbed_under_mapped_launch(self) -> None:
        if not userns.mapped_launch_ok():
            pytest.skip(
                "HOST-DEGRADED-FSISO: host denies uid mapping inside "
                "unprivileged user namespaces (see scripts/fs-isolation-probe.py)"
            )
        result = _run_cli(
            CLI_SCRIPT,
            "--user",
            "--no-interruptor",
            "env",
            env=_base_env({}),
        )
        assert result.returncode == 0, result.stderr
        assert "LD_PRELOAD" not in _payload_env_names(result)
        assert result.stdout.count("BASH_FUNC_") == 0
        assert "TJ060_BENIGN" in _payload_env_names(result)


class TestScrubPrecedesBackendSelection:
    """The scrub is not backend-specific: it runs in the wrapper's preamble,
    before TERMINAL_JAIL_JAIL_BACKEND is even read. Pinned structurally so
    a reordering that leaves, e.g., the bwrap path unscrubbed fails on any
    host."""

    def test_scrub_blocks_come_before_backend_request(self) -> None:
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        scrub_phase1 = text.index("environment scrub, phase 1")
        scrub_phase2 = text.index("environment scrub, phase 2")
        backend_request = text.index("jail backend request")
        interruptor_eval = text.index("interruptor evaluation")
        assert scrub_phase1 < scrub_phase2 < backend_request < interruptor_eval
        # ...and before the wrapper's first python3 invocations: the
        # interruptor bridge (interruptor evaluation section) and the
        # seccomp loader handoff (TERMINAL_JAIL_SECCOMP=1 export).
        seccomp_export = text.index("TERMINAL_JAIL_SECCOMP=1")
        assert scrub_phase2 < interruptor_eval < seccomp_export

    def test_wrapper_runs_when_called_with_no_env_scrub_self_checks(
        self, tmp_path: Path
    ) -> None:
        """The scrub must not break a stripped-environment launch (set -u)."""
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path)}
        result = _run_cli(
            CLI_SCRIPT,
            "--help",
            env=env,  # type: ignore[arg-type]
        )
        assert result.returncode == 0, result.stderr
        assert "Usage:" in result.stdout
