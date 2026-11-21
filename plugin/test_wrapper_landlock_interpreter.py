"""RELEASE-TJ-021 — the in-jail trampolines resolve the bridge interpreter.

TJ-DF-061 fixed the BRIDGE half: the wrapper evaluates the interruptor bridge
under ``$_TJ_BRIDGE_PY`` (``TERMINAL_JAIL_PYTHON`` when set/non-empty, else the
historical bare ``python3``). The in-jail trampolines the wrapper splices for
the seccomp and Landlock tiers still spliced a literal ``python3``, so on the
layouts this tool actually installs into — a wheel or ``install.sh`` tree whose
installing venv is not on PATH — the ALLOW path died with a bare 127 *after* a
perfectly good verdict: the firewall decision was fine, the launch could not
start its loader.

These pins drive the real wrapper (both copies: the bundled data file a wheel
ships and ``standalone/terminal-jail``) from a staged install layout with a
``python3`` that is broken on purpose first on PATH:

* source level — no in-jail trampoline splices the literal ``python3`` any
  more; every tier trampoline splices ``$_TJ_BRIDGE_PY``;
* the allow verdict still RUNS the command under a broken ``python3``
  (filesystem tier and ``--seccomp`` arms);
* a pinned interpreter outside PATH is honored (the broken shim is never
  selected);
* a pin that cannot be executed fails loudly in enforce mode — never a silent
  fallback to ``python3`` — and warns (fail-open) in warn mode.

TJ-DF-073 adds the other half of the same contract: the pin is ALSO exec'd
before the tier launch, to JSON-escape the command and to run the bridge. A
broken pin therefore failed at that first exec, bash printed its own raw noise
(``line 347: /path/nope/python3: No such file or directory``) and control fell
into the *bridge-unavailable* handler — which blamed ``./install.sh`` /
``TERMINAL_JAIL_BRIDGE`` for a fault that lives in the pin, while this module's
own refusal (``interpreter-unavailable``) was unreachable for the very fault it
names. The arms below pin all three static fault classes plus an executable-file
pin whose execution fails, on both shipped copies, and assert the refusal is the
interpreter box with no exec noise and no ``install.sh`` guidance.

No network, no wheel build: the staged layout is a file copy of
``plugin/terminal_jail`` (the loader's tier-module walk needs the package
sibling), the way ``test_packaging_wheel`` stages its synthetic install.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = PROJECT_ROOT / "plugin" / "terminal_jail"
STANDALONE_CLI = PROJECT_ROOT / "standalone" / "terminal-jail"

# The shim every invocation in this module puts first on PATH: a python3 that
# exists, is executable, and cannot work. Pre-fix, a spliced `python3` selects
# it and the launch exits 127 with this marker on stderr.
BROKEN_PYTHON_MARKER = "tj021-broken-python3"
_BROKEN_SHIM = f"""#!/bin/sh
echo "{BROKEN_PYTHON_MARKER}: this python3 is broken on purpose" >&2
exit 127
"""


def _bash() -> str:
    bash = shutil.which("bash")
    assert bash, "test host lacks bash"
    return bash


@pytest.fixture(scope="module")
def bundled_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Stage a wheel/install.sh-shaped layout and return its wrapper path.

    A file copy of the package (no pip, no network): the wrapper lives in
    ``terminal_jail/_bundled/`` exactly as a wheel ships it, next to its three
    loaders, with the tier module one directory up — which is what
    ``landlock-loader.py``'s ``_find_landlock_module`` walk expects.
    """
    root = tmp_path_factory.mktemp("tj021-install")
    package = root / "terminal_jail"
    shutil.copytree(PACKAGE_DIR, package)
    wrapper = package / "_bundled" / "terminal-jail"
    assert wrapper.is_file(), f"staged wrapper missing: {wrapper}"
    return wrapper


@pytest.fixture(params=["bundled", "standalone"])
def wrapper(request: pytest.FixtureRequest, bundled_cli: Path) -> Path:
    """Both shipped copies, so the fix cannot drift between them."""
    return bundled_cli if request.param == "bundled" else STANDALONE_CLI


def _broken_python_bin(base: Path) -> str:
    """PATH with the broken ``python3`` first, real tool dirs after it.

    The trailing real directories keep the launch's own tools (bwrap, unshare,
    mktemp) resolvable, so the arm measures interpreter resolution and not a
    stripped PATH.
    """
    shim_dir = base / "brokenbin"
    shim_dir.mkdir(exist_ok=True)
    shim = shim_dir / "python3"
    shim.write_text(_BROKEN_SHIM)
    shim.chmod(0o755)
    return os.pathsep.join([str(shim_dir), "/usr/bin", "/bin"])


def _env(base: Path, path: str, **extra: str) -> dict[str, str]:
    """A minimal, explicit environment — no inherited TERMINAL_JAIL_* vars."""
    tmpdir = base / "tmp"
    tmpdir.mkdir(exist_ok=True)
    env = {
        "PATH": path,
        "HOME": os.environ.get("HOME", str(base)),
        "TMPDIR": str(tmpdir),
        "LANG": "C.UTF-8",
        "TERMINAL_JAIL_VERSION": "0.0.0-test",
        # The bridge the install layout ships; explicit so the arm never
        # depends on whether terminal_jail is importable by the host python.
        "TERMINAL_JAIL_BRIDGE": str(PACKAGE_DIR / "interruptor_bridge.py"),
    }
    env.update(extra)
    return env


def _run(wrapper: Path, args: list[str], env: dict[str, str], base: Path):
    return subprocess.run(
        [_bash(), str(wrapper), *args],
        cwd=str(base),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _verdicts(stderr: str) -> list[dict]:
    """The structured verdict log lines the wrapper/bridge emit on stderr."""
    entries = []
    for line in stderr.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event") == "verdict":
            entries.append(payload)
    return entries


def _tier_degraded(stderr: str) -> bool:
    """True when this host could not attach the filesystem tier at all."""
    return "Landlock filesystem tier not applied" in stderr


# --- acceptance B: source level ------------------------------------------------


@pytest.mark.parametrize("copy", ["bundled", "standalone"])
def test_no_in_jail_trampoline_splices_literal_python3(copy: str) -> None:
    """Every tier trampoline splices the one resolver, never bare python3."""
    path = (
        PACKAGE_DIR / "_bundled" / "terminal-jail"
        if copy == "bundled"
        else STANDALONE_CLI
    )
    text = path.read_text()
    lines = text.splitlines()

    # The single resolution scheme (TJ-DF-061) the trampolines must reuse.
    assert '_TJ_BRIDGE_PY="${TERMINAL_JAIL_PYTHON:-python3}"' in text

    trampolines = [line for line in lines if "bash -c 'exec" in line]
    tier_trampolines = [
        line for line in trampolines if "LANDLOCK" in line or "SECCOMP" in line
    ]
    # 7 unshare/bwrap tier sites + the composed-mode egress site; the exact
    # number may grow with a new launch shape, the invariant may not.
    assert len(tier_trampolines) >= 11, tier_trampolines

    for line in tier_trampolines:
        assert "python3" not in line, f"literal python3 splice: {line}"
        assert '"$_TJ_BRIDGE_PY"' in line, f"trampoline without the resolver: {line}"

    leftovers = [line for line in trampolines if "python3" in line]
    assert not leftovers, leftovers


def test_interpreter_fault_helper_covers_every_unusable_shape() -> None:
    """The fail-loud preflight distinguishes missing / not-executable / off-PATH.

    TJ-DF-073 extends the classes with a pin that resolves and is executable but
    whose execution fails — asked from the failure path only, so a healthy
    invocation never pays for the probe.
    """
    text = STANDALONE_CLI.read_text()
    assert "_tj_interpreter_fault()" in text
    assert "_tj_require_interpreter()" in text
    assert "_tj_pin_preflight()" in text
    assert "_tj_interpreter_fault_deep()" in text
    assert "(no such file)" in text
    assert "(not executable)" in text
    assert "(not on PATH)" in text
    assert "(cannot execute)" in text


@pytest.mark.parametrize("copy", ["bundled", "standalone"])
def test_pin_preflight_runs_before_the_first_bridge_exec(copy: str) -> None:
    """The preflight precedes the bridge exec, and evaluate never execs a bad pin.

    Order is the contract: if the refusal ran after the bridge exec, bash would
    already have printed its raw ``line NNN:`` noise (TJ-DF-073).
    """
    path = (
        PACKAGE_DIR / "_bundled" / "terminal-jail"
        if copy == "bundled"
        else STANDALONE_CLI
    )
    text = path.read_text()

    preflight_call = text.index("_tj_pin_preflight\n")  # a bare call line
    bridge_call = text.index('bridge_result=$(_interruptor_evaluate "$CMD_STR")')
    assert preflight_call < bridge_call

    evaluate = text.index("_interruptor_evaluate() {")
    guard = text.index('if [ -n "$(_tj_interpreter_fault)" ]; then', evaluate)
    find_bridge = text.index("bridge=$(_find_bridge) || return 1", evaluate)
    assert guard < find_bridge


# --- acceptance A / D: the allow path runs under a broken python3 --------------


def test_allow_verdict_runs_with_broken_python3_first_on_path(
    wrapper: Path, tmp_path: Path
) -> None:
    """A wheel-shaped install, broken python3 first on PATH: the command runs.

    Pre-fix this exited 127 with the shim's marker: the allow verdict was
    already emitted, then the filesystem-tier trampoline spliced `python3`.
    """
    marker = "tj021-fs-tier-ran"
    result = _run(
        wrapper,
        ["--interruptor", "/bin/echo", marker],
        _env(
            tmp_path, _broken_python_bin(tmp_path), TERMINAL_JAIL_PYTHON=sys.executable
        ),
        tmp_path,
    )
    if _tier_degraded(result.stderr):
        pytest.skip(f"host cannot attach the filesystem tier: {result.stderr}")
    assert result.returncode == 0, result.stderr
    assert marker in result.stdout, result.stdout
    assert BROKEN_PYTHON_MARKER not in result.stderr, result.stderr
    actions = [entry.get("action") for entry in _verdicts(result.stderr)]
    assert actions == ["allow"], result.stderr


def test_seccomp_trampoline_runs_with_broken_python3_first_on_path(
    wrapper: Path, tmp_path: Path
) -> None:
    """Same arm on the seccomp trampoline — the splice that needs no Landlock.

    Kept separate from the filesystem arm because it is deterministic on any
    host with a namespace backend (no kernel tier-ABI dependency), which makes
    it the arm that pins the regression everywhere.
    """
    marker = "tj021-seccomp-ran"
    result = _run(
        wrapper,
        ["--seccomp", "--interruptor", "/bin/echo", marker],
        _env(
            tmp_path, _broken_python_bin(tmp_path), TERMINAL_JAIL_PYTHON=sys.executable
        ),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert marker in result.stdout, result.stdout
    assert BROKEN_PYTHON_MARKER not in result.stderr, result.stderr
    assert [entry.get("action") for entry in _verdicts(result.stderr)] == ["allow"]


def test_pinned_interpreter_outside_path_is_the_one_that_runs(
    tmp_path: Path, bundled_cli: Path
) -> None:
    """TERMINAL_JAIL_PYTHON wins over PATH: the broken shim is never selected."""
    marker = "tj021-pinned-ran"
    env = _env(
        tmp_path,
        _broken_python_bin(tmp_path),
        TERMINAL_JAIL_PYTHON=sys.executable,
    )
    # The pin is a real interpreter that is NOT on the child's PATH.
    assert str(Path(sys.executable).parent) not in env["PATH"].split(os.pathsep)
    result = _run(
        bundled_cli, ["--seccomp", "--interruptor", "/bin/echo", marker], env, tmp_path
    )
    assert result.returncode == 0, result.stderr
    assert marker in result.stdout, result.stdout
    assert BROKEN_PYTHON_MARKER not in result.stderr, result.stderr


# --- acceptance C: an unusable pin fails loudly --------------------------------


# --- acceptance A/B/C (TJ-DF-073): a broken pin refuses with ITS box -----------


def _exec_noise(stderr: str) -> list[str]:
    """Raw bash exec-noise lines ("<script>: line 347: /path: No such file")."""
    return [line for line in stderr.splitlines() if re.search(r"\bline \d+:", line)]


def _pin_fault_cases(base: Path) -> dict[str, tuple[str, str]]:
    """The pin fault classes → (pinned value, the reason the box must name).

    The first three are the static classes TJ-DF-073 was filed for; the fourth
    resolves and is executable yet cannot run, which only the failure-path probe
    can see.
    """
    noexec = base / "pin" / "noexec-python"
    noexec.parent.mkdir(exist_ok=True)
    noexec.write_text("#!/bin/sh\nexit 0\n")
    noexec.chmod(0o644)

    fails = base / "pin" / "not-a-python"
    fails.write_text("#!/bin/sh\nexit 3\n")
    fails.chmod(0o755)

    return {
        "missing": (str(base / "nope" / "python3"), "(no such file)"),
        "not-executable": (str(noexec), "(not executable)"),
        "not-on-path": ("tj073-no-such-python", "(not on PATH)"),
        "exec-fails": (str(fails), "(cannot execute)"),
    }


@pytest.mark.parametrize(
    "case", ["missing", "not-executable", "not-on-path", "exec-fails"]
)
def test_broken_pin_refuses_with_the_interpreter_box(
    wrapper: Path, tmp_path: Path, case: str
) -> None:
    """Firewall-on, enforce mode: the INTERPRETER box, no install.sh, no noise.

    Pre-fix every one of these printed bash's own ``line 347/348`` exec noise and
    then the *bridge-unavailable* box, sending the operator to ``./install.sh``
    for a fault that lives in the pin.
    """
    pin, reason = _pin_fault_cases(tmp_path)[case]
    marker = f"tj073-must-not-run-{case}"
    result = _run(
        wrapper,
        ["--interruptor", "/bin/echo", marker],
        _env(tmp_path, _broken_python_bin(tmp_path), TERMINAL_JAIL_PYTHON=pin),
        tmp_path,
    )
    assert result.returncode == 126, result.stderr
    assert result.stdout == "", result.stdout
    assert marker not in result.stderr, result.stderr

    assert "COMMAND BLOCKED — interpreter-unavailable" in result.stderr, result.stderr
    assert f"TERMINAL_JAIL_PYTHON={pin} {reason}" in result.stderr, result.stderr
    # The wrong refusal: the pin is not a missing bridge.
    assert "interruptor-bridge-unavailable" not in result.stderr, result.stderr
    assert "install.sh" not in result.stderr, result.stderr
    assert "TERMINAL_JAIL_BRIDGE" not in result.stderr, result.stderr
    # The noise this row was filed for.
    assert not _exec_noise(result.stderr), _exec_noise(result.stderr)


def test_broken_pin_in_warn_mode_states_it_and_runs_without_noise(
    wrapper: Path, tmp_path: Path
) -> None:
    """Warn mode keeps its documented fail-open — one loud note, and the command runs.

    The pin fault is still NAMED (never a silent fallback) and bash's raw exec
    noise stays suppressed, but the run does not fail closed.
    """
    pin, reason = _pin_fault_cases(tmp_path)["not-executable"]
    marker = "tj073-warn-ran"
    result = _run(
        wrapper,
        ["--interruptor", "/bin/echo", marker],
        _env(
            tmp_path,
            os.pathsep.join(["/usr/bin", "/bin"]),
            TERMINAL_JAIL_PYTHON=pin,
            TERMINAL_JAIL_INTERRUPTOR_MODE="warn",
        ),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert marker in result.stdout, result.stdout
    assert f"TERMINAL_JAIL_PYTHON={pin} {reason}" in result.stderr, result.stderr
    assert "warn mode" in result.stderr, result.stderr
    assert "interpreter-unavailable" not in result.stderr, result.stderr
    assert not _exec_noise(result.stderr), _exec_noise(result.stderr)


def test_nonexistent_pin_fails_loudly_before_the_tier_launch(
    wrapper: Path, tmp_path: Path
) -> None:
    """Enforce mode, tier arm: the launch preflight blocks instead of exec'ing.

    Without it the trampoline would exec a missing path and surface a bare 127
    (the unexplained failure this row is about); a fallback to PATH's python3
    would silently ignore the operator's pin.
    """
    pin = str(tmp_path / "nonexistent" / "python9")
    result = _run(
        wrapper,
        ["--seccomp", "--no-interruptor", "/bin/echo", "tj021-must-not-run"],
        _env(tmp_path, _broken_python_bin(tmp_path), TERMINAL_JAIL_PYTHON=pin),
        tmp_path,
    )
    assert result.returncode == 126, result.stderr
    assert "interpreter-unavailable" in result.stderr
    assert pin in result.stderr, result.stderr
    assert BROKEN_PYTHON_MARKER not in result.stderr, result.stderr
    assert "tj021-must-not-run" not in result.stdout


def test_pin_that_is_not_executable_is_named_as_such(
    wrapper: Path, tmp_path: Path
) -> None:
    """A file that exists but cannot execute is a distinct, named cause."""
    pin = tmp_path / "python-noexec"
    pin.write_text("#!/bin/sh\nexit 0\n")
    pin.chmod(0o644)
    result = _run(
        wrapper,
        ["--seccomp", "--no-interruptor", "/bin/echo", "tj021-must-not-run"],
        _env(tmp_path, _broken_python_bin(tmp_path), TERMINAL_JAIL_PYTHON=str(pin)),
        tmp_path,
    )
    assert result.returncode == 126, result.stderr
    assert f"{pin} (not executable)" in result.stderr, result.stderr


def test_pin_that_is_absent_from_path_is_named_as_such(
    wrapper: Path, tmp_path: Path
) -> None:
    """A bare name the interpreter cannot resolve is named as such."""
    result = _run(
        wrapper,
        ["--seccomp", "--no-interruptor", "/bin/echo", "tj021-must-not-run"],
        _env(
            tmp_path,
            _broken_python_bin(tmp_path),
            TERMINAL_JAIL_PYTHON="tj021-absent-interpreter",
        ),
        tmp_path,
    )
    assert result.returncode == 126, result.stderr
    assert "tj021-absent-interpreter (not on PATH)" in result.stderr, result.stderr


def test_warn_mode_states_the_degradation_instead_of_blocking(
    wrapper: Path, tmp_path: Path
) -> None:
    """Warn mode keeps its documented fail-open, but it is stated, not silent.

    The pin is unusable and the PATH supplies a working ``python3``: warn mode
    warns, then runs under the historical resolution instead of failing
    closed. Without the statement this would be the silent fallback the
    enforce-mode arms forbid.
    """
    pin = str(tmp_path / "nonexistent" / "python9")
    result = _run(
        wrapper,
        ["--no-interruptor", "/bin/echo", "tj021-warn-ran"],
        _env(
            tmp_path,
            os.pathsep.join(["/usr/bin", "/bin"]),
            TERMINAL_JAIL_PYTHON=pin,
            TERMINAL_JAIL_INTERRUPTOR_MODE="warn",
        ),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "tj021-warn-ran" in result.stdout, result.stdout
    assert f"TERMINAL_JAIL_PYTHON={pin}" in result.stderr, result.stderr
    assert "warn mode" in result.stderr, result.stderr
