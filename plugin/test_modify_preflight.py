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

import shutil
import stat
import subprocess
from pathlib import Path

import pytest

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
    # Exactly two invocations: the rewrite's own prefix probe, then the rewrite.
    assert len(records) == 2, records
    assert _bare_mode_probes(records) == [], (
        "the wrapper ran its bare-mode preflight for an already-prefixed rewrite"
    )
    assert records[0] == ["--user", "--pid", "--fork", "--kill-child=SIGKILL", "true"]
    assert records[1][:4] == ["--user", "--pid", "--fork", "--kill-child=SIGKILL"]
    assert records[1][4:6] == ["bash", "-c"]
    assert str(inner) in records[1][6]

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


# ── 3. DEGRADED host + no rewrite: bare mode stays fail-closed ─────────────


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


# ── 4. FULL host + bridge rewrite: unchanged (probe green, rewrite runs) ────


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
