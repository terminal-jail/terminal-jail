"""Offline tests for scripts/rules-drift-probe.py (TJ-GAP-069).

The probe is a per-host classifier for silent same-id rule-mirror drift:
install.sh copies the shipped default rules file into the USER rules dir the
engine loads, where a same-id entry REPLACES the builtin — so a mirror
installed before a fix (DF-TERMINAL-JAIL-20 moved four upload ids from
`action: sandbox` to `action: block`) keeps enforcing the OLD, weaker action
after the repo is upgraded (live evidence, tick #292 kara-lair: an upload
returned MODIFY instead of BLOCK and the payload left the host).

These tests exercise the verdict logic WITHOUT touching the host's real rules
dirs: every run points TERMINAL_JAIL_INTERRUPTOR_RULES_DIR and
TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR at tmp_path fixtures (deliberately
downgraded copies, clean dirs, absent dirs, corrupt YAML). Nothing outside
tmp is written or read. The classifier contract is pinned: a bare run ALWAYS
exits 0; only --fail-on-drift may exit non-zero.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROBE_SCRIPT = PROJECT_ROOT / "scripts" / "rules-drift-probe.py"
SHIPPED_MIRROR = (
    PROJECT_ROOT / "plugin" / "terminal_jail" / "rules" / "00-builtins.yaml"
)

ENV_SYSTEM = "TERMINAL_JAIL_INTERRUPTOR_RULES_DIR"
ENV_USER = "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR"

# Engine constant: builtin-kill-all is a priority-1000 block rule
# (plugin/terminal_jail/interruptor/blocklist.py).
DOWNGRADED_ID = "builtin-kill-all"
ENGINE_ACTION = "block"
DOWNGRADED_ACTION = "sandbox"


def load_probe_module():
    """Import scripts/rules-drift-probe.py by path (dashes in name)."""
    spec = importlib.util.spec_from_file_location("rules_drift_probe", PROBE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe_mod = load_probe_module()


def write_rules_dir(directory: Path, files: dict[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")
    return directory


def downgraded_yaml(action: str) -> str:
    return (
        "rules:\n"
        f'  - id: "{DOWNGRADED_ID}"\n'
        '    description: "test fixture copy"\n'
        "    priority: 1000\n"
        f"    action: {action}\n"
        "    match:\n"
        "      type: pattern\n"
        '      pattern: "kill\\\\s+-9\\\\s+-1"\n'
    )


def run_probe(
    *args: str,
    env_extra: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(PROBE_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=120,
    )


# ── drift detection: downgraded same-id copy (subprocess, hermetic) ────────


class TestDowngradedCopyDrift:
    def test_drift_row_printed_with_id_actions_and_both_paths(
        self, tmp_path: Path
    ) -> None:
        user_dir = write_rules_dir(
            tmp_path / "user", {"00-builtins.yaml": downgraded_yaml(DOWNGRADED_ACTION)}
        )
        result = run_probe(
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)}
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"DRIFT: {DOWNGRADED_ID}: engine action={ENGINE_ACTION} " in result.stdout
        assert f"installed action={DOWNGRADED_ACTION} (weaker)" in result.stdout
        # both file paths named: the shipped mirror (engine constant) and the
        # installed file that shadows it
        assert str(SHIPPED_MIRROR) in result.stdout
        assert str(user_dir / "00-builtins.yaml") in result.stdout
        assert "RESULT: drift=1" in result.stdout

    def test_bare_run_exits_zero_on_drift(self, tmp_path: Path) -> None:
        user_dir = write_rules_dir(
            tmp_path / "user", {"00-builtins.yaml": downgraded_yaml(DOWNGRADED_ACTION)}
        )
        result = run_probe(
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)}
        )
        assert "DRIFT" in result.stdout
        assert result.returncode == 0

    def test_fail_on_drift_exits_nonzero_on_drift(self, tmp_path: Path) -> None:
        user_dir = write_rules_dir(
            tmp_path / "user", {"00-builtins.yaml": downgraded_yaml(DOWNGRADED_ACTION)}
        )
        result = run_probe(
            "--fail-on-drift",
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)},
        )
        assert "DRIFT" in result.stdout
        assert result.returncode == 1

    def test_action_changed_but_equal_strength_is_still_drift(
        self, tmp_path: Path
    ) -> None:
        # sandbox -> block is a TIGHTENING, not a downgrade: the row direction
        # says "stronger", but a gate still fails — drift is drift.
        user_dir = write_rules_dir(
            tmp_path / "user",
            {
                "00-builtins.yaml": downgraded_yaml(DOWNGRADED_ACTION),
                "10-tighten.yaml": downgraded_yaml("block").replace(
                    DOWNGRADED_ID, "auto-pytest"
                ).replace("sandbox\n", "block\n", 1),
            },
        )
        result = run_probe(
            "--fail-on-drift",
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)},
        )
        assert "DRIFT: auto-pytest: engine action=sandbox installed action=block (stronger)" in result.stdout
        assert result.returncode == 1


# ── OK cases: clean/absent dirs (subprocess, hermetic) ──────────────────────


class TestOkCases:
    def test_absent_dirs_report_no_installed_override(self, tmp_path: Path) -> None:
        result = run_probe(
            env_extra={
                ENV_SYSTEM: str(tmp_path / "no-system"),
                ENV_USER: str(tmp_path / "no-user"),
            }
        )
        assert result.returncode == 0
        assert "DRIFT" not in result.stdout
        assert "OK: no installed override" in result.stdout
        assert "rules dirs absent" in result.stdout
        assert "RESULT: drift=0" in result.stdout

    def test_empty_dirs_report_no_installed_override(self, tmp_path: Path) -> None:
        system_dir = tmp_path / "system"
        user_dir = tmp_path / "user"
        system_dir.mkdir()
        user_dir.mkdir()
        result = run_probe(
            env_extra={ENV_SYSTEM: str(system_dir), ENV_USER: str(user_dir)}
        )
        assert result.returncode == 0
        assert "OK: no installed override" in result.stdout
        assert "RESULT: drift=0" in result.stdout

    def test_full_parity_mirror_reports_zero_drift(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "user"
        user_dir.mkdir()
        shutil.copy(SHIPPED_MIRROR, user_dir / "00-builtins.yaml")
        result = run_probe(
            "--fail-on-drift",
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)},
        )
        assert result.returncode == 0, result.stdout
        assert "DRIFT" not in result.stdout
        assert "RESULT: drift=0 overridden=54" in result.stdout

    def test_fail_on_drift_exits_zero_when_clean(self, tmp_path: Path) -> None:
        result = run_probe(
            "--fail-on-drift",
            env_extra={
                ENV_SYSTEM: str(tmp_path / "no-system"),
                ENV_USER: str(tmp_path / "no-user"),
            },
        )
        assert result.returncode == 0


# ── scope discipline: what must NOT count as drift ──────────────────────────


class TestNotDrift:
    def test_same_action_different_pattern_is_not_drift(self, tmp_path: Path) -> None:
        # The probe's contract is the ACTION only — a same-id copy with a
        # weaker PATTERN is yaml-mirror-parity-probe's concern (repo-internal);
        # the loader overrides patterns too, but this probe reports action
        # drift, the refused-vs-executed property.
        content = downgraded_yaml(ENGINE_ACTION)
        user_dir = write_rules_dir(tmp_path / "user", {"00-builtins.yaml": content})
        result = run_probe(
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)}
        )
        assert result.returncode == 0
        assert "DRIFT" not in result.stdout
        assert "RESULT: drift=0 overridden=1" in result.stdout

    def test_non_builtin_ids_are_info_never_drift(self, tmp_path: Path) -> None:
        user_dir = write_rules_dir(
            tmp_path / "user",
            {
                "99-custom.yaml": (
                    "rules:\n"
                    '  - id: "my-catch-all"\n'
                    '    description: "user rule"\n'
                    "    priority: 10\n"
                    "    action: block\n"
                    "    match:\n"
                    "      type: pattern\n"
                    '      pattern: "rm\\\\s+-rf"\n'
                )
            },
        )
        result = run_probe(
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)}
        )
        assert result.returncode == 0
        assert "DRIFT" not in result.stdout
        assert "my-catch-all" in result.stdout
        assert "never drift" in result.stdout

    def test_corrupt_yaml_is_warning_not_drift(self, tmp_path: Path) -> None:
        # The engine's loader fails open on an unparseable file (the builtin
        # stays live), so corruption is reported as WARNING, never as drift.
        user_dir = write_rules_dir(
            tmp_path / "user",
            {"00-builtins.yaml": "rules: [ { id: \"unterminated\", action: "},
        )
        result = run_probe(
            "--fail-on-drift",
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)},
        )
        assert result.returncode == 0, result.stdout
        assert "WARNING: unparseable rule file" in result.stdout
        assert "DRIFT" not in result.stdout

    def test_non_yaml_files_are_ignored(self, tmp_path: Path) -> None:
        user_dir = write_rules_dir(
            tmp_path / "user",
            {
                "00-builtins.yaml.bak": downgraded_yaml(DOWNGRADED_ACTION),
                "README.txt": "not rules",
            },
        )
        result = run_probe(
            env_extra={ENV_SYSTEM: str(tmp_path / "absent"), ENV_USER: str(user_dir)}
        )
        assert result.returncode == 0
        assert "DRIFT" not in result.stdout
        assert "RESULT: drift=0 overridden=0" in result.stdout

    def test_user_dir_wins_over_system_dir_same_id(self, tmp_path: Path) -> None:
        # Resolution order under test: user dir loads after system dir, same-id
        # user entry replaces the system one — the drift row must name the USER
        # file (the one the engine actually enforces).
        system_dir = write_rules_dir(
            tmp_path / "system",
            {"00-builtins.yaml": downgraded_yaml(ENGINE_ACTION)},
        )
        user_dir = write_rules_dir(
            tmp_path / "user",
            {"00-builtins.yaml": downgraded_yaml(DOWNGRADED_ACTION)},
        )
        result = run_probe(
            env_extra={ENV_SYSTEM: str(system_dir), ENV_USER: str(user_dir)}
        )
        assert result.returncode == 0
        assert f"DRIFT: {DOWNGRADED_ID}: engine action={ENGINE_ACTION}" in result.stdout
        assert str(user_dir / "00-builtins.yaml") in result.stdout
        assert str(system_dir / "00-builtins.yaml") not in result.stdout


# ── in-process unit tests: probe() structure + classifier never-crash ──────


class TestProbeInProcess:
    def test_probe_returns_lines_and_drift_count(self, tmp_path: Path) -> None:
        user_dir = write_rules_dir(
            tmp_path / "user", {"00-builtins.yaml": downgraded_yaml(DOWNGRADED_ACTION)}
        )
        lines, drift = probe_mod.probe(str(tmp_path / "absent"), str(user_dir))
        assert drift == 1
        joined = "\n".join(lines)
        assert f"DRIFT: {DOWNGRADED_ID}" in joined
        assert any(line.startswith("DRIFT: ") for line in lines)

    def test_probe_names_source_file_per_drift_row(self, tmp_path: Path) -> None:
        # Two downgraded ids in two different files: each DRIFT row must name
        # ITS OWN source file (a host may have several installed files).
        second = downgraded_yaml(DOWNGRADED_ACTION).replace(DOWNGRADED_ID, "builtin-sudo")
        write_rules_dir(
            tmp_path / "user",
            {"00-a.yaml": downgraded_yaml(DOWNGRADED_ACTION), "10-b.yaml": second},
        )
        lines, drift = probe_mod.probe(str(tmp_path / "absent"), str(tmp_path / "user"))
        assert drift == 2
        sources = [
            line for line in lines if line.startswith("    installed copy")
        ]
        assert len(sources) == 2
        assert "00-a.yaml" in sources[0] and "10-b.yaml" in sources[1]

    def test_main_returns_zero_on_internal_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Classifier contract: even a broken environment must not crash a host
        # run — UNKNOWN + exit 0.
        def boom() -> object:
            raise RuntimeError("injected failure")

        monkeypatch.setattr(probe_mod.Config, "from_environ", classmethod(lambda cls: boom()))
        monkeypatch.setattr(sys, "argv", ["rules-drift-probe.py"])
        rc = probe_mod.main()
        assert rc == 0
        assert capsys.readouterr().out.startswith("UNKNOWN: probe error: injected failure")

    def test_engine_covers_all_builtin_layers(self) -> None:
        # Guard the engine-constant aggregation: every blocklist/sandbox/
        # allowlist id must be present exactly once in the compared set.
        assert len(probe_mod.ENGINE_RULES) == 54
        assert DOWNGRADED_ID in probe_mod.ENGINE_RULES
        assert probe_mod.ENGINE_RULES[DOWNGRADED_ID].action == ENGINE_ACTION
