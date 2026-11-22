"""DF-TERMINAL-JAIL-11 — degraded-host auto-sandbox (``modify``) preflight.

Contract under test (``specs/cli.md`` §4 "Extended launch forms", README
"Graceful Degradation"): an ``action=modify`` rewrite already carries the
interruptor bridge's own ``unshare`` prefix. The wrapper's bare-mode namespace
preflight describes the wrapper's OWN launch — which a rewrite never uses — so
it must not gate the rewrite. Before this fix the ordering did exactly that: on
a DEGRADED host (bare ``unshare --mount-proc`` denied while ``unshare --user``
works) ``terminal-jail bash script.sh`` printed
``[terminal-jail] Modified: … → sandboxed`` and then exited 2 with
``namespace creation failed (unshare exit 1)``; the command never ran, so all 8
auto-sandbox classes were unusable end-to-end even though the prefix itself
works.

Fixed behaviour, all four arms pinned here:

1. DEGRADED host + bridge rewrite → the REWRITE'S OWN flags are probed, the
   rewrite runs, and the inner command's exit code propagates.
2. DEGRADED host + a rewrite whose own prefix cannot be created → exit 2 with
   the honest ``auto-sandbox modify unavailable`` verdict, never the generic
   namespace-creation message and never a silent execution claim.
3. DEGRADED host + no rewrite (``allow``) → bare mode stays fail-closed with
   the unchanged message (the fix skips the bare probe only where it is not
   representative).
4. FULL host + bridge rewrite → unchanged: probe green, rewrite runs.

Host-independence comes from two stubs, both already proven seams in
``plugin/test_backend_selection.py``: an argv-recording ``unshare`` stub on a
curated PATH that models the host shape (``TJ_DEGRADED=1`` ⇒ any invocation
WITHOUT ``--user`` fails) and pass-throughs the payload so inner exit codes are
real, plus a recorded ``interruptor_bridge.py`` stand-in that emits a canned
``action=modify`` response. No test depends on this host being degraded, and no
privileges are needed.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from refusal_test_support import skip_namespace_refusal
from terminal_jail.interruptor import landlock as ll

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
BRIDGE_SCRIPT = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor_bridge.py"

# The bridge's own prefix for a transparent auto-sandbox rewrite on a DEGRADED
# host (userns.py LEGACY_USER_FLAGS + _PREFIX_SUFFIX). Both host shapes produce
# `unshare <flags> bash -c `, which is the shape the wrapper parses.
USER_PREFIX = "unshare --user --pid --fork --kill-child=SIGKILL "
# A rewrite whose own prefix cannot be created on a degraded host: the
# bare-mode flags the wrapper used to probe for itself.
BARE_PREFIX = "unshare --pid --fork --kill-child=SIGKILL --mount-proc "
# A rewrite that is NOT unshare-prefixed (out-of-contract user rule).
NON_NS_PREFIX = "env TJ_NON_NS_MARK=1 "

# Recorder + host model + pass-through sandbox. Records every argv as
# NUL-terminated tokens followed by "EOR" (empty-arg vs record-boundary
# distinction, same convention as test_backend_selection.py). With TJ_DEGRADED
# set, any invocation without `--user` fails like a host whose kernel denies
# bare-mode PID namespaces; an invocation that carries `bash -c …` executes the
# payload for real so exit codes propagate.
_UNSHARE_STUB = """#!/usr/bin/env bash
log="${TJ_UNSHARE_STUB_LOG:-/dev/null}"
for a in "$@"; do printf '%s\\0' "$a" >> "$log"; done
printf 'EOR\\0' >> "$log"
args=("$@")
has_user=0
bash_idx=-1
i=0
for a in "$@"; do
    [ "$a" = "--user" ] && has_user=1
    [ "$a" = "bash" ] && bash_idx=$i
    i=$((i + 1))
done
if [ -n "${TJ_DEGRADED:-}" ] && [ "$has_user" -eq 0 ]; then
    echo "unshare: unshare failed: Operation not permitted" >&2
    exit 1
fi
if [ "$bash_idx" -ge 0 ]; then
    bash_command="${args[$((bash_idx + 2))]:-}"
    exec "${args[@]:$bash_idx}"
fi
exit "${TJ_PROBE_EXIT:-0}"
"""

# Bridge stand-in: records the reconstructed command the wrapper sent, then
# answers with a canned verdict. `modify` mirrors the engine's rewrite shape
# (`<prefix>bash -c <command>`) around the command it received.
_BRIDGE_STUB = """#!/usr/bin/env python3
import json
import os
import shlex
import sys

raw = sys.stdin.readline()
command = ""
try:
    command = json.loads(raw).get("command", "")
except Exception:  # noqa: BLE001 - the stand-in still answers
    pass
with open(os.environ["TJ_BRIDGE_LOG"], "a", encoding="utf-8") as handle:
    handle.write(command + "\\n")
mode = os.environ.get("TJ_BRIDGE_MODE", "modify")
if mode == "modify":
    prefix = os.environ["TJ_BRIDGE_PREFIX"]
    response = {
        "action": "modify",
        "command": command,
        "modified": prefix + "bash -c " + shlex.quote(command),
        "rule_id": "stub-auto",
        "reason": "stub auto-sandbox",
    }
else:
    response = {
        "action": "allow",
        "command": command,
        "modified": None,
        "rule_id": None,
        "reason": "",
    }
json.dump(response, sys.stdout)
sys.stdout.write("\\n")
"""


def _make_stub_path(tmp_path: Path) -> str:
    """Curated PATH: real bash/uname/python3 plus the argv-recording stub.

    A real ``/usr/bin/unshare`` and a real ``/usr/bin/bwrap`` are deliberately
    absent, so the resolved backend and every probe are deterministic on hosts
    that have either binary installed.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name in ("bash", "uname", "python3", "env"):
        real = shutil.which(name)
        if real:
            (bindir / name).symlink_to(real)
    stub = bindir / "unshare"
    stub.write_text(_UNSHARE_STUB, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(bindir)


def _write_inner_script(tmp_path: Path, *, rc: int) -> Path:
    script = tmp_path / "inner.sh"
    script.write_text(
        "#!/usr/bin/env bash\necho INNER_RAN\nexit %d\n" % rc,
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _env(
    tmp_path: Path,
    path: str,
    *,
    degraded: bool,
    prefix: str = USER_PREFIX,
    mode: str = "modify",
    probe_exit: str = "0",
    bridge: Path | None = None,
) -> dict[str, str]:
    bridge_stub = tmp_path / "bridge-stub.py"
    bridge_stub.write_text(_BRIDGE_STUB, encoding="utf-8")
    env = {
        "PATH": path,
        "HOME": str(tmp_path / "home"),
        "TERMINAL_JAIL_INTERRUPTOR_MODE": "enforce",
        "TERMINAL_JAIL_BRIDGE": str(bridge if bridge is not None else bridge_stub),
        "TJ_UNSHARE_STUB_LOG": str(tmp_path / "unshare.log"),
        "TJ_BRIDGE_LOG": str(tmp_path / "bridge.log"),
        "TJ_BRIDGE_PREFIX": prefix,
        "TJ_BRIDGE_MODE": mode,
        "TJ_PROBE_EXIT": probe_exit,
        # TJ-GAP-082: these tests pin the wrapper's modify-preflight call
        # count for the rewrite itself; the Landlock tier's loader probe
        # is an additional call the tier tests own.
        "TERMINAL_JAIL_LANDLOCK": "0",
    }
    if degraded:
        env["TJ_DEGRADED"] = "1"
    Path(env["HOME"]).mkdir(exist_ok=True)
    return env


def _run_cli(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI_SCRIPT), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _records(log_path: str) -> list[list[str]]:
    """Parse the stub log: NUL-terminated args, "EOR" ends a record."""
    log = Path(log_path)
    if not log.exists():
        return []
    records: list[list[str]] = []
    current: list[bytes] = []
    for token in log.read_bytes().split(b"\0"):
        if token == b"EOR":
            records.append([t.decode("utf-8", "replace") for t in current])
            current = []
        else:
            current.append(token)
    return records


def _bare_mode_probes(records: list[list[str]]) -> list[list[str]]:
    """Probe/launch argv that could only be the wrapper's own bare launch."""
    return [r for r in records if "--mount-proc" in r]


# ── 1. DEGRADED host + bridge rewrite: probe the rewrite, run it, rc ────────


@pytest.mark.standalone_cli
def test_degraded_host_modify_executes_and_propagates_inner_rc(tmp_path: Path) -> None:
    inner = _write_inner_script(tmp_path, rc=7)
    env = _env(tmp_path, _make_stub_path(tmp_path), degraded=True)

    result = _run_cli("bash", str(inner), env=env)

    assert result.returncode == 7, result.stderr
    assert "INNER_RAN" in result.stdout
    # The generic bare-mode verdict must not appear once a prefix is supplied.
    assert "namespace creation failed" not in result.stderr
    assert "auto-sandbox modify unavailable" not in result.stderr

    records = _records(env["TJ_UNSHARE_STUB_LOG"])
    # Three invocations: the rewrite's namespace probe, its interpreter
    # preflight, then the rewrite itself.
    assert len(records) == 3, records
    assert _bare_mode_probes(records) == [], (
        "the wrapper ran its bare-mode preflight for an already-prefixed rewrite"
    )
    assert records[0] == ["--user", "--pid", "--fork", "--kill-child=SIGKILL", "true"]
    assert records[1][4:6] == ["bash", "-c"]
    assert "command -v" in records[1][6]
    assert records[2][:4] == ["--user", "--pid", "--fork", "--kill-child=SIGKILL"]
    assert records[2][4:6] == ["bash", "-c"]
    assert str(inner) in records[2][6]

    # Bridge command reconstruction is unchanged: the reconstructed CMD_STR is
    # what the bridge evaluated (quote-preserving, one arg per token).
    bridge_log = Path(env["TJ_BRIDGE_LOG"]).read_text(encoding="utf-8").strip()
    assert bridge_log == f"'bash' '{inner}'", bridge_log


# ── 2. DEGRADED host + uncreatable rewrite prefix: honest verdict ───────────


@pytest.mark.standalone_cli
def test_degraded_host_uncreatable_rewrite_prefix_is_honest(tmp_path: Path) -> None:
    inner = _write_inner_script(tmp_path, rc=0)
    env = _env(
        tmp_path,
        _make_stub_path(tmp_path),
        degraded=True,
        prefix=BARE_PREFIX,
    )

    result = _run_cli("bash", str(inner), env=env)

    assert result.returncode == 2
    assert "INNER_RAN" not in result.stdout
    assert "auto-sandbox modify unavailable" in result.stderr
    # Never the generic wrapper verdict after a prefix was already supplied.
    assert "namespace creation failed" not in result.stderr
    # The message names the flags it actually probed.
    assert "unshare --pid --fork --kill-child=SIGKILL --mount-proc" in result.stderr
    # The rewrite was never launched (probe only).
    records = _records(env["TJ_UNSHARE_STUB_LOG"])
    assert len(records) == 1 and records[0][-1] == "true", records


# ── 3. REWRITE prefix can create a namespace but cannot exec python3 ────────


@pytest.mark.standalone_cli
def test_modify_rewrite_interpreter_denial_is_named(tmp_path: Path) -> None:
    """A rewrite must preflight its interpreter, not leak rc=126 from bash."""
    path = _make_stub_path(tmp_path)
    denied_interpreter = tmp_path / "denied-python3"
    denied_interpreter.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    denied_interpreter.chmod(0o644)
    pytest_executable = Path(path) / "pytest"
    pytest_executable.write_text(f"#!{denied_interpreter}\n", encoding="utf-8")
    pytest_executable.chmod(0o755)

    env = _env(
        tmp_path,
        path,
        degraded=False,
    )
    result = _run_cli("pytest", "--version", env=env)

    assert result.returncode == 2, result.stderr
    assert "auto-sandbox modify unavailable" in result.stderr
    assert "Permission denied" not in result.stderr
    records = _records(env["TJ_UNSHARE_STUB_LOG"])
    assert len(records) == 2, records
    assert records[0][-1] == "true"
    assert records[1][4:6] == ["bash", "-c"], records
    assert "command -v" in records[1][6], records


# ── 4. DEGRADED host + no rewrite: bare mode stays fail-closed ─────────────


@pytest.mark.standalone_cli
def test_degraded_host_allow_path_keeps_bare_mode_fail_closed(tmp_path: Path) -> None:
    env = _env(tmp_path, _make_stub_path(tmp_path), degraded=True, mode="allow")

    result = _run_cli("echo", "plain", env=env)

    assert result.returncode == 2
    assert "namespace creation failed (unshare exit 1)" in result.stderr
    assert "try --user" in result.stderr
    assert "plain" not in result.stdout
    records = _records(env["TJ_UNSHARE_STUB_LOG"])
    assert _bare_mode_probes(records) == records, records


# ── 5. FULL host + allow: unchanged plain launch ----------------------------


@pytest.mark.standalone_cli
def test_full_host_allow_path_still_runs(tmp_path: Path) -> None:
    env = _env(tmp_path, _make_stub_path(tmp_path), degraded=False, mode="allow")

    result = _run_cli("bash", "-c", "printf 'plain\\n'", env=env)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "plain\n"
    assert "auto-sandbox modify unavailable" not in result.stderr
    records = _records(env["TJ_UNSHARE_STUB_LOG"])
    assert len(records) == 2, records
    assert records[0][-1] == "true"
    assert records[1][4:9] == ["bash", "-c", 'exec "$@"', "terminal-jail", "bash"], (
        records
    )


# ── 6. FULL host + bridge rewrite: unchanged (probe green, rewrite runs) ────


@pytest.mark.standalone_cli
def test_full_host_modify_still_probes_the_rewrite_and_runs(tmp_path: Path) -> None:
    inner = _write_inner_script(tmp_path, rc=0)
    env = _env(tmp_path, _make_stub_path(tmp_path), degraded=False)

    result = _run_cli("bash", str(inner), env=env)

    assert result.returncode == 0, result.stderr
    assert "INNER_RAN" in result.stdout
    assert "namespace creation failed" not in result.stderr
    records = _records(env["TJ_UNSHARE_STUB_LOG"])
    assert _bare_mode_probes(records) == [], records
    assert records[0][-1] == "true"


# ── 5. NON-unshare rewrite: executed as-is, no namespace probe ─────────────


@pytest.mark.standalone_cli
def test_degraded_host_non_namespace_rewrite_is_not_bare_mode_gated(
    tmp_path: Path,
) -> None:
    """A rewrite that adds no unshare prefix has no prefix to preflight.

    The wrapper adds no namespace of its own to a ``modify`` rewrite, so the
    bare-mode probe is not applicable; the rewrite is executed as-is
    (``specs/cli.md`` §4: "executed as-is via ``bash -c``").
    """
    inner = _write_inner_script(tmp_path, rc=7)
    env = _env(
        tmp_path,
        _make_stub_path(tmp_path),
        degraded=True,
        prefix=NON_NS_PREFIX,
    )

    result = _run_cli("bash", str(inner), env=env)

    assert result.returncode == 7, result.stderr
    assert "INNER_RAN" in result.stdout
    assert "namespace creation failed" not in result.stderr
    assert _records(env["TJ_UNSHARE_STUB_LOG"]) == []


# ── 6. Real bridge + DEGRADED host: the integration the ticket measured ─────


@pytest.mark.standalone_cli
def test_real_bridge_modify_on_degraded_host(tmp_path: Path) -> None:
    """End-to-end through the shipped bridge (not the stand-in).

    The bridge's own rewrite shape and quote-escaping are the real ones, so
    this pins the wrapper's parse of ``unshare <flags> bash -c <payload>``
    against the artifact the engine actually emits. Both possible prefixes
    (mapped and legacy) carry ``--user``; the assertion below is invariant to
    which one the host/stub shape selects.
    """
    inner = _write_inner_script(tmp_path, rc=7)
    env = _env(
        tmp_path,
        _make_stub_path(tmp_path),
        degraded=True,
        bridge=BRIDGE_SCRIPT,
    )

    result = _run_cli("bash", str(inner), env=env)

    assert result.returncode == 7, result.stderr
    assert "INNER_RAN" in result.stdout
    assert "namespace creation failed" not in result.stderr
    records = _records(env["TJ_UNSHARE_STUB_LOG"])
    assert _bare_mode_probes(records) == [], records
    # The rewrite itself was launched through a --user prefix.
    launch = records[-1]
    assert "--user" in launch and launch[-2] == "-c", records
    assert str(inner) in launch[-1]
    # No unsatisfiable-prefix verdict, and the bridge really evaluated it.
    assert "auto-sandbox modify unavailable" not in result.stderr
    assert Path(env["TJ_BRIDGE_LOG"]).exists() is False  # stand-in log unused


# ── 7. TJ-REVIEW-074: the tier's head interpreter, real loader + real denial ─

LANDLOCK_PROBE = PROJECT_ROOT / "scripts" / "landlock-capability-probe.py"
HOST_DEGRADED = "HOST-DEGRADED-LANDLOCK"
MAKEFILE_OK = "ok:\n\t@echo PAYLOAD-RAN\n"


def _host_permits_landlock() -> bool:
    """True when this host can attach the filesystem tier (else skip marker)."""
    try:
        probe = subprocess.run(
            [sys.executable, str(LANDLOCK_PROBE), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if probe.returncode != 0:
        return False
    try:
        return json.loads(probe.stdout).get("verdict") == "FULL"
    except json.JSONDecodeError:
        return False


def _outside_every_grant(path: Path) -> bool:
    """True when no grant of the checkout layout covers ``path``.

    The tier's ruleset is an ALLOWLIST: "the payload cannot read it" means "no
    grant names it". Mode bits alone never reproduce this — a payload running
    as the caller still reads a 0700 directory it owns.

    Landlock judges the file the kernel actually OPENS, so a symlinked
    interpreter (a runner venv's ``bin/python3`` is a symlink chain into its
    base install) must be judged at its fully RESOLVED target — the whole
    chain is collapsed into that one file before the grant comparison, because
    the engine's denial happens there, not on the as-given name. And a grant
    that covers only directory TRAVERSAL (``read_dir_roots``: HOME is
    listable while its files are granted individually) never makes a FILE
    readable or executable, so only the file-level roots (write + read) can
    cover it — the tier itself proves that shape by exec'ing the interpreter
    in-domain.
    """
    layout = ll.build_layout(str(PROJECT_ROOT), payload_argv=None)
    assert layout is not None, "the tier cannot compute a layout for the checkout"
    resolved = os.path.realpath(str(path))
    file_level = (*layout.write_roots, *layout.read_roots)
    return not any(ll._is_inside(resolved, grant) for grant in file_level)


def _denied_fixture_root() -> Path | None:
    """A caller-writable directory the tier never grants.

    Not a temp dir: TMPDIR/TMP/TEMP and /tmp, /var/tmp are WRITE grants, so a
    fixture there is readable inside the domain and the arm could not fail.
    What is left are the two host shapes the tier's own enforcement probe uses
    for the same reason — XDG_RUNTIME_DIR (a caller-owned tmpfs outside every
    grant on a normal session) and the HOME root (only named children are
    granted, never the root).
    """
    for candidate in (
        os.environ.get("XDG_RUNTIME_DIR", "").strip(),
        os.environ.get("HOME", "").strip(),
    ):
        if not candidate.startswith("/") or not os.path.isdir(candidate):
            continue
        try:
            root = Path(tempfile.mkdtemp(prefix="tj074-r2-", dir=candidate))
        except OSError:
            continue
        if _outside_every_grant(root):
            return root
        os.rmdir(root)
    return None


def _denied_interpreter(root: Path) -> Path:
    """A REAL interpreter under a 0700 ancestor that the tier denies.

    Not a stub: it executes for real before the ruleset exists — the interruptor
    bridge runs through it — which is the ticket's shape (PATH's ``python3``
    resolving into a tree the allowlist never grants). The 0700 ancestor is the
    ticket's stated fixture and is kept; the denial itself is the allowlist, so
    a mode-only fixture would not reproduce it.
    """
    hidden = root / "hidden"
    hidden.mkdir(mode=0o700)
    interpreter = hidden / "python3"
    interpreter.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n', encoding="utf-8"
    )
    interpreter.chmod(0o755)
    return interpreter


def _tier_env(tmp_path: Path, interpreter: Path) -> dict[str, str]:
    """Real-bridge env with the filesystem tier left at its DEFAULT (on).

    ``_env`` pins ``TERMINAL_JAIL_LANDLOCK=0`` so the call-count arms above
    measure the preflight alone; this arm needs the tier ATTACHED. HOME stays
    the real one so the fixture's grant story matches the parent-side premise
    check — a fake home under tmp_path would itself be a granted temp dir.
    """
    env = _env(
        tmp_path,
        os.pathsep.join([str(interpreter.parent), "/usr/bin", "/bin"]),
        degraded=False,
        bridge=BRIDGE_SCRIPT,
    )
    env.pop("TERMINAL_JAIL_LANDLOCK", None)
    # The child gets no inherited TMPDIR from ``_env``, and the tier grants the
    # temp dirs it can SEE: without this the fixture Makefile under tmp_path
    # would be outside every grant and the payload could not read it.
    env["TMPDIR"] = str(tmp_path)
    real_home = os.environ.get("HOME", "").strip()
    if real_home.startswith("/"):
        env["HOME"] = real_home
    return env


@pytest.mark.standalone_cli
def test_tier_on_unreachable_payload_interpreter_is_named(tmp_path: Path) -> None:
    """TJ-REVIEW-074: the tier-ON modify arm must NAME the interpreter.

    The engine splices its filesystem-tier tail into the rewrite's payload as a
    literal ``python3`` (``bash -c 'python3 <landlock-loader.py> -- <cmd>'``),
    and bash resolves that head only AFTER the ruleset is installed. With
    PATH's ``python3`` under a tree the allowlist never grants, the exec died
    EACCES: bash leaked ``Permission denied`` and rc=126 after a clean
    ``Command modified by auto-sandbox`` verdict — no surface said the command
    never ran, and none named the interpreter. The wrapper must refuse through
    the named ``auto-sandbox modify unavailable`` verdict instead.
    """
    if not _host_permits_landlock():
        pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
    root = _denied_fixture_root()
    if root is None:
        pytest.skip(
            f"{HOST_DEGRADED}: no caller-writable directory outside every grant"
        )
    try:
        interpreter = _denied_interpreter(root)
        mkfile = tmp_path / "Makefile.ok"
        mkfile.write_text(MAKEFILE_OK, encoding="utf-8")
        assert not _outside_every_grant(mkfile), (
            "test bug: the fixture Makefile sits outside every tier grant — "
            "the payload could not read it even after the fix"
        )
        env = _tier_env(tmp_path, interpreter)

        result = _run_cli("make", "-f", str(mkfile), "ok", env=env)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    skip_namespace_refusal(result)
    assert result.returncode == 2, result.stderr
    assert "PAYLOAD-RAN" not in result.stdout, result.stdout
    verdicts = [
        line
        for line in result.stderr.splitlines()
        if "auto-sandbox modify unavailable" in line
    ]
    assert len(verdicts) == 1, result.stderr  # exactly ONE named line
    assert str(interpreter) in verdicts[0], verdicts[0]  # names the interpreter
    assert "command not run" in verdicts[0], verdicts[0]
    # Never the bare bash leak the ticket was filed on.
    assert "Permission denied" not in result.stderr, result.stderr


@pytest.mark.standalone_cli
def test_tier_on_pinned_interpreter_runs_the_payload(tmp_path: Path) -> None:
    """TERMINAL_JAIL_PYTHON must reach the tier's head interpreter too.

    The wrapper's own trampolines resolve their interpreter through
    ``$_TJ_BRIDGE_PY`` (TJ-DF-061 / RELEASE-TJ-021); the engine's spliced head
    is the one that ignored the pin, so setting it could not rescue a command
    whose PATH ``python3`` the tier denies. Splicing the pin over that head
    must make the same command run the payload.
    """
    if not _host_permits_landlock():
        pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
    root = _denied_fixture_root()
    if root is None:
        pytest.skip(
            f"{HOST_DEGRADED}: no caller-writable directory outside every grant"
        )
    if _outside_every_grant(Path(sys.executable)):
        pytest.skip(
            f"{HOST_DEGRADED}: the test interpreter {sys.executable} is itself "
            "outside every tier grant, so no readable pin exists on this host"
        )
    try:
        interpreter = _denied_interpreter(root)
        mkfile = tmp_path / "Makefile.ok"
        mkfile.write_text(MAKEFILE_OK, encoding="utf-8")
        env = _tier_env(tmp_path, interpreter)
        env["TERMINAL_JAIL_PYTHON"] = sys.executable

        result = _run_cli("make", "-f", str(mkfile), "ok", env=env)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    skip_namespace_refusal(result)
    assert result.returncode == 0, result.stderr
    assert "PAYLOAD-RAN" in result.stdout, result.stdout
    assert "auto-sandbox modify unavailable" not in result.stderr, result.stderr
