"""Offline tests for scripts/systemd-directive-probe.py (TJ-GAP-052).

The probe is a per-host classifier for staged systemd directives; these tests
exercise its verdict logic WITHOUT real systemd: a fake `systemd-run` shell
script (written to tmp_path, passed via --systemd-run) models the three
behaviours the classifier must distinguish — reject a directive at load,
accept and produce enforcing evidence, accept and produce no evidence.

The real-system path is covered by ONE host-conditional test that skips with
HOST-NO-SYSTEMD-RUN when no working user-scope systemd-run exists (CI runners).
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROBE_SCRIPT = PROJECT_ROOT / "scripts" / "systemd-directive-probe.py"

EXPECTED_DIRECTIVES = (
    "ProtectProc",
    "NoNewPrivileges",
    "ProtectControlGroups",
    "TasksMax",
    "PrivateUsers",
    "RestrictNamespaces",
    "CapabilityBoundingSet",
    "RestrictAddressFamilies",
    "ProtectSystem",
    "ProtectHome",
    "MemoryMax",
    "ReadWritePaths",
    "CloseOnExec",
)

VERDICTS = {"ENFORCED", "NOT_ENFORCED", "UNSUPPORTED", "UNKNOWN"}

# Safety invariants: what the probe must NEVER put in a systemd-run argv, and
# what must never appear in its source as a write path or control verb.
FORBIDDEN_ARGV_TOKENS = ("hermes-gateway", "/etc/", "daemon-reload")
FORBIDDEN_VERBS = ("restart", "stop")


# ── helpers ────────────────────────────────────────────────────────


def load_probe_module():
    """Import scripts/systemd-directive-probe.py by path (dashes in name)."""
    spec = importlib.util.spec_from_file_location(
        "systemd_directive_probe", PROBE_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_fake_systemd_run(tmp_path: Path) -> Path:
    """A tiny fake systemd-run modelling load-rejection / evidence / silence.

    TJ_FAKE_MODE selects the behaviour:
      reject      -> stderr "Unknown assignment: <Directive>=..." exit 1
      evidence    -> canned enforcing evidence on stdout, exit 0
      silent      -> accept, produce nothing, exit 0
      passthrough -> run the payload for real (local, no systemd)
    """
    fake = tmp_path / "systemd-run"
    fake.write_text(
        "#!/bin/sh\n"
        '# Fake systemd-run for offline TJ-GAP-052 tests (NOT a real unit).\n'
        'MODE="${TJ_FAKE_MODE:-passthrough}"\n'
        'ASSIGN=""\n'
        'prev=""\n'
        'for a in "$@"; do\n'
        '  if [ "$prev" = "-p" ]; then ASSIGN="$a"; fi\n'
        '  prev="$a"\n'
        "done\n"
        'PAYLOAD=""\n'
        'for a in "$@"; do PAYLOAD="$a"; done\n'
        'if [ "$MODE" = "reject" ] && [ -n "$ASSIGN" ]; then\n'
        '  echo "Unknown assignment: $ASSIGN" >&2\n'
        "  exit 1\n"
        "fi\n"
        'if [ "$MODE" = "evidence" ]; then\n'
        '  echo "NoNewPrivs_1"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "$MODE" = "silent" ]; then\n'
        "  exit 0\n"
        "fi\n"
        '# passthrough: execute the payload exactly as a unit would\n'
        '/bin/sh -c "$PAYLOAD"\n',
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return fake


def run_probe(
    *args: str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(PROBE_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=120,
    )


# ── offline: fake systemd-run, one directive per behaviour ─────────


def test_rejected_directive_is_unsupported(tmp_path):
    """(i) load rejection ('Unknown assignment') classifies UNSUPPORTED."""
    fake = write_fake_systemd_run(tmp_path)
    result = run_probe(
        "--systemd-run", str(fake),
        "--scope", "user",
        "--json",
        "--directive", "NoNewPrivileges",
        env_extra={"TJ_FAKE_MODE": "reject"},
    )
    assert result.returncode == 0, result.stderr  # classifier, never a gate
    report = json.loads(result.stdout)
    (record,) = report["records"]
    assert record["verdict"] == "UNSUPPORTED"
    assert "Unknown assignment: NoNewPrivileges=true" in record["evidence"]


def test_accepted_with_evidence_is_enforced(tmp_path):
    """(ii) accepted + enforcing evidence classifies ENFORCED."""
    fake = write_fake_systemd_run(tmp_path)
    result = run_probe(
        "--systemd-run", str(fake),
        "--scope", "user",
        "--json",
        "--directive", "NoNewPrivileges",
        env_extra={"TJ_FAKE_MODE": "evidence"},
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    (record,) = report["records"]
    assert record["verdict"] == "ENFORCED"
    assert record["evidence"] == "NoNewPrivs: 1"


def test_accepted_without_enforcing_evidence_is_not_enforced(tmp_path):
    """(iii) accepted but effect NOT observed classifies NOT_ENFORCED."""
    fake = write_fake_systemd_run(tmp_path)
    result = run_probe(
        "--systemd-run", str(fake),
        "--scope", "user",
        "--json",
        "--directive", "NoNewPrivileges",
        env_extra={"TJ_FAKE_MODE": "passthrough"},
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    (record,) = report["records"]
    assert record["verdict"] == "NOT_ENFORCED"
    assert "NoNewPrivs: 0" in record["evidence"]


def test_accepted_with_no_output_at_all_is_unknown(tmp_path):
    """A silent accept carries NO interpretable evidence: honest UNKNOWN."""
    fake = write_fake_systemd_run(tmp_path)
    result = run_probe(
        "--systemd-run", str(fake),
        "--scope", "user",
        "--json",
        "--directive", "NoNewPrivileges",
        env_extra={"TJ_FAKE_MODE": "silent"},
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    (record,) = report["records"]
    assert record["verdict"] == "UNKNOWN"
    assert "no NoNewPrivs evidence" in record["evidence"]


def test_full_table_rejected_by_manager_is_all_unsupported(tmp_path):
    """A manager rejecting every directive yields 13 UNSUPPORTED records."""
    fake = write_fake_systemd_run(tmp_path)
    result = run_probe(
        "--systemd-run", str(fake),
        "--scope", "user",
        "--json",
        env_extra={"TJ_FAKE_MODE": "reject"},
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert len(report["records"]) == len(EXPECTED_DIRECTIVES)
    assert {r["directive"] for r in report["records"]} == set(EXPECTED_DIRECTIVES)
    assert all(r["verdict"] == "UNSUPPORTED" for r in report["records"])
    # The negative control is among them and is never ENFORCED.
    coe = next(r for r in report["records"] if r["directive"] == "CloseOnExec")
    assert coe["verdict"] != "ENFORCED"


def test_json_output_covers_every_directive_and_parses(tmp_path):
    """--json parses and carries one record per table directive."""
    fake = write_fake_systemd_run(tmp_path)
    result = run_probe(
        "--systemd-run", str(fake),
        "--scope", "user",
        "--json",
        env_extra={"TJ_FAKE_MODE": "passthrough"},
    )
    assert result.returncode == 0, result.stderr
    # Nothing but the JSON document on stdout.
    report = json.loads(result.stdout)
    assert len(report["records"]) == len(EXPECTED_DIRECTIVES)
    assert {r["directive"] for r in report["records"]} == set(EXPECTED_DIRECTIVES)
    for record in report["records"]:
        assert record["verdict"] in VERDICTS
        assert set(record) == {"directive", "value", "scope", "verdict", "evidence"}
        assert isinstance(record["evidence"], str) and record["evidence"]
    # CloseOnExec explicitly present (negative control always reported).
    assert any(r["directive"] == "CloseOnExec" for r in report["records"])


def test_plain_text_mode_prints_verdict_and_summary(tmp_path):
    """Plain mode: one line per directive plus a final summary line."""
    fake = write_fake_systemd_run(tmp_path)
    result = run_probe(
        "--systemd-run", str(fake),
        "--scope", "user",
        "--directive", "NoNewPrivileges",
        env_extra={"TJ_FAKE_MODE": "evidence"},
    )
    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert lines[0].startswith("ENFORCED")
    assert "NoNewPrivileges" in lines[0]
    assert lines[1].startswith("SUMMARY:")


# ── offline: missing systemd-run ────────────────────────────────────


def test_missing_systemd_run_is_all_unknown_exit_zero(tmp_path):
    """systemd-run not found -> all UNKNOWN, note, exit 0."""
    missing = tmp_path / "does-not-exist"
    result = run_probe(
        "--systemd-run", str(missing),
        "--scope", "user",
        "--json",
        "--directive", "NoNewPrivileges",
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    (record,) = report["records"]
    assert record["verdict"] == "UNKNOWN"
    assert "not found" in record["evidence"]


# ── safety invariants ───────────────────────────────────────────────


def test_built_argv_never_touches_gateway_or_etc_or_control_verbs(tmp_path):
    """Every systemd-run argv the probe builds is throwaway-unit only."""
    probe = load_probe_module()
    captured: list[list[str]] = []
    real_run = subprocess.run

    def spy_run(argv, *a, **kw):
        captured.append(list(argv))
        return real_run(argv, *a, **kw)

    fake = write_fake_systemd_run(tmp_path)
    original_run = probe.subprocess.run
    probe.subprocess.run = spy_run
    try:
        records, _note = probe.probe_directives(
            list(EXPECTED_DIRECTIVES), str(fake), "user", 20
        )
    finally:
        probe.subprocess.run = original_run

    assert records  # the probe actually ran its engines
    assert captured  # and every launch was captured
    for argv in captured:
        joined = "\x00".join(argv)
        for token in FORBIDDEN_ARGV_TOKENS:
            assert token not in joined, f"forbidden {token!r} in argv {argv}"
        for verb in FORBIDDEN_VERBS:
            assert verb not in argv, f"forbidden systemctl verb {verb!r} in {argv}"
        # Transient-only: every unit launch carries the throwaway switches.
        if any("systemd-run" in part for part in argv):
            assert "--wait" in argv and "--collect" in argv
            assert any(part.startswith("--unit=tj-probe-") for part in argv)


def test_source_has_no_etc_write_path_no_gateway_unit_no_daemon_reload():
    """Static invariant: no /etc write path, no hermes-gateway.service, no
    daemon-reload anywhere in the probe source (grep-verifiable safety)."""
    source = PROBE_SCRIPT.read_text(encoding="utf-8")
    assert "hermes-gateway.service" not in source
    assert "/etc/" not in source
    assert "daemon-reload" not in source
    assert "shell=True" not in source


# ── host-conditional live test ──────────────────────────────────────


def test_live_host_close_on_exec_control_and_enforcement():
    """On a host with a working user-scope systemd-run, the real probe must
    classify CloseOnExec=true UNSUPPORTED and enforce at least one directive.
    Skips (HOST-NO-SYSTEMD-RUN) on hosts/CI runners without one."""
    systemd_run = "/usr/bin/systemd-run"
    if not os.path.isfile(systemd_run) or not os.access(systemd_run, os.X_OK):
        pytest.skip(
            "HOST-NO-SYSTEMD-RUN: no systemd-run binary on this host"
        )
    try:
        canary = subprocess.run(
            [systemd_run, "--user", "--pipe", "--wait", "--collect",
             f"--unit=tj-probe-test-canary-{os.getpid()}", "/bin/true"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        canary = None
    if canary is None or canary.returncode != 0:
        pytest.skip(
            "HOST-NO-SYSTEMD-RUN: user-scope systemd-run did not start a unit "
            f"(rc={getattr(canary, 'returncode', 'n/a')})"
        )

    result = run_probe(
        "--systemd-run", systemd_run,
        "--scope", "user",
        "--json",
        "--directive", "CloseOnExec",
        "--directive", "NoNewPrivileges",
        "--directive", "TasksMax",
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    by_name = {r["directive"]: r for r in report["records"]}
    assert by_name["CloseOnExec"]["verdict"] == "UNSUPPORTED"
    enforced = [r for r in report["records"] if r["verdict"] == "ENFORCED"]
    assert enforced, "expected at least one ENFORCED directive on a live host"
