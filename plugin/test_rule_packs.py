"""Tests for the opt-in rule-pack system (TJ-GAP-061).

Two surfaces:

* the shipped ``db`` pack, driven end to end through the engine's ``intercept()``
  with a SCRATCH ``TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR`` (never the host's
  live rules dir, which may hold a stale ``00-builtins.yaml``);
* ``scripts/rule-pack-tool.py`` — the validator the installer runs BEFORE it
  writes anything. Its refusals are the install-time contract: bad schema,
  malformed YAML, an id outside the pack's namespace, or an id collision with
  an engine builtin / an already-installed rule file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from terminal_jail.interruptor import Action, intercept
from terminal_jail.interruptor.allowlist import BUILTIN_ALLOWLIST
from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST
from terminal_jail.interruptor.rules import RuleLoader
from terminal_jail.interruptor.sandbox import BUILTIN_SANDBOX

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules" / "packs"
DB_PACK = PACKS_DIR / "db.yaml"
PACK_TOOL = PROJECT_ROOT / "scripts" / "rule-pack-tool.py"

ENGINE_BUILTIN_COUNT = len(BUILTIN_BLOCKLIST) + len(BUILTIN_SANDBOX) + len(BUILTIN_ALLOWLIST)

# The pack's positive vectors: one per rule id, with the verdict the engine
# must produce when the pack is installed.
DB_PACK_POSITIVES = (
    (
        'psql -h db.internal -c "DROP DATABASE prod_app"',
        Action.BLOCK,
        "pack-db-drop-database",
    ),
    ('mysql -e "DROP TABLE customers"', Action.BLOCK, "pack-db-drop-table"),
    ("pg_dump mydb > /tmp/dump.sql", Action.MODIFY, "pack-db-dump-restore"),
)

# Benign controls: ordinary reads the pack must not touch (default-allow —
# no rule matched at all, which is NOT the same as an approved allow).
DB_PACK_BENIGN_CONTROLS = ('psql -c "SELECT 1"', 'mysql -e "SELECT 1"')


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the installer's validator exactly as install.sh does."""
    return subprocess.run(
        [sys.executable, str(PACK_TOOL), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT),
        timeout=60,
    )


def _write_pack(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _scratch_rule_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the engine at a scratch rules dir + an empty system rules dir."""
    rules_dir = tmp_path / "rules.d"
    rules_dir.mkdir()
    empty_system = tmp_path / "empty-system-rules.d"
    empty_system.mkdir()
    monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR", str(rules_dir))
    monkeypatch.setenv("TERMINAL_JAIL_INTERRUPTOR_RULES_DIR", str(empty_system))
    return rules_dir


@pytest.fixture()
def installed_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The shipped ``db`` pack installed under the installer's own file name."""
    rules_dir = _scratch_rule_dirs(tmp_path, monkeypatch)
    (rules_dir / "terminal-jail-pack-db.yaml").write_bytes(DB_PACK.read_bytes())
    return rules_dir


@pytest.fixture()
def empty_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The same scratch config, but with NO pack installed."""
    return _scratch_rule_dirs(tmp_path, monkeypatch)


# ---------------------------------------------------------------------------
# the shipped pack, through the live engine
# ---------------------------------------------------------------------------


class TestShippedDbPack:
    """The pack is real policy: its ids fire through intercept()."""

    @pytest.mark.parametrize(("command", "action", "rule_id"), DB_PACK_POSITIVES)
    def test_each_pack_rule_fires_on_its_positive_vector(
        self,
        installed_pack: Path,
        command: str,
        action: Action,
        rule_id: str,
    ) -> None:
        result = intercept(command)

        assert result.rule_id == rule_id, result
        assert result.action == action, result
        if action == Action.MODIFY:
            # A sandbox verdict is a rewrite, not a refusal: the command still
            # runs, wrapped in the namespace prefix.
            assert result.modified, result
            assert "unshare" in result.modified

    @pytest.mark.parametrize("command", DB_PACK_BENIGN_CONTROLS)
    def test_benign_controls_are_not_attributed_to_the_pack(
        self, installed_pack: Path, command: str
    ) -> None:
        result = intercept(command)

        assert result.action == Action.ALLOW, result
        assert result.rule_id is None, (result, "pack must not match an ordinary read")

    def test_positive_vectors_are_unattributed_without_the_pack(
        self, empty_rules: Path
    ) -> None:
        """Control: with no pack installed the same commands are default-allow."""
        for command, _action, rule_id in DB_PACK_POSITIVES:
            result = intercept(command)
            assert result.action != Action.BLOCK, (command, result)
            assert result.rule_id != rule_id, (command, result)
            assert not str(result.rule_id or "").startswith("pack-"), (command, result)

    def test_pack_file_loads_through_the_engine_loader(self, installed_pack: Path) -> None:
        """The pack is an ordinary rules.d file: the engine's own loader reads
        all three rules under the installer's file name."""
        loaded = RuleLoader(
            system_dir=str(installed_pack.parent / "empty-system-rules.d"),
            user_dir=str(installed_pack),
        ).load_all()

        ids = {rule.id for rule in loaded.rules}
        assert ids == {
            "pack-db-drop-database",
            "pack-db-drop-table",
            "pack-db-dump-restore",
        }, ids


# ---------------------------------------------------------------------------
# the installer's validator
# ---------------------------------------------------------------------------


class TestValidatorAccepts:
    def test_shipped_pack_is_valid(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules.d"
        result = _run_tool(
            "validate", str(DB_PACK), "--pack-name", "db", "--rules-dir", str(rules_dir)
        )

        assert result.returncode == 0, result.stderr
        assert "pack 'db' valid" in result.stdout
        assert "3 rule(s)" in result.stdout
        assert f"{ENGINE_BUILTIN_COUNT} engine builtin ids" in result.stdout, result.stdout

    def test_engine_match_types_are_derived_from_the_engine(self, tmp_path: Path) -> None:
        """A non-pattern dispatch type is accepted, an invented one refused:
        the valid set comes from matcher.py, not from a hardcoded list."""
        src = tmp_path / "packs-src"
        src.mkdir()
        rules_dir = tmp_path / "rules.d"  # absent: nothing installed to collide with
        pack = _write_pack(
            src / "db.yaml",
            "rules:\n"
            '  - id: "pack-db-syscall"\n'
            "    priority: 650\n"
            "    action: sandbox\n"
            "    match:\n"
            "      type: syscall\n",
        )
        accepted = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(rules_dir)
        )
        assert accepted.returncode == 0, accepted.stderr

        invented = _write_pack(
            src / "invented.yaml",
            "rules:\n"
            '  - id: "pack-db-telepathy"\n'
            "    priority: 650\n"
            "    action: sandbox\n"
            "    match:\n"
            "      type: telepathy\n",
        )
        refused = _run_tool(
            "validate", str(invented), "--pack-name", "db", "--rules-dir", str(rules_dir)
        )
        assert refused.returncode == 2, refused.stdout
        assert "telepathy" in refused.stderr
        assert "pattern" in refused.stderr, refused.stderr

    def test_reinstall_over_its_own_file_is_not_a_self_collision(
        self, tmp_path: Path
    ) -> None:
        rules_dir = tmp_path / "rules.d"
        rules_dir.mkdir()
        (rules_dir / "terminal-jail-pack-db.yaml").write_bytes(DB_PACK.read_bytes())

        result = _run_tool(
            "validate", str(DB_PACK), "--pack-name", "db", "--rules-dir", str(rules_dir)
        )

        assert result.returncode == 0, result.stderr


class TestValidatorRefusals:
    """Every refusal: exit 2, nothing written, ONE reason line on stderr."""

    def _assert_refused(
        self, result: subprocess.CompletedProcess[str], needle: str
    ) -> None:
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert needle in result.stderr, result.stderr
        stderr_lines = [line for line in result.stderr.splitlines() if line.strip()]
        assert len(stderr_lines) == 1, stderr_lines

    def test_builtin_id_collision_is_refused(self, tmp_path: Path) -> None:
        pack = _write_pack(
            tmp_path / "shadow.yaml",
            "rules:\n"
            '  - id: "builtin-rm-rf-root"\n'
            "    priority: 950\n"
            "    action: block\n"
            "    match:\n"
            "      type: pattern\n"
            '      pattern: "zzz"\n',
        )

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "collide with engine builtin ids")

    def test_id_outside_the_pack_namespace_is_refused(self, tmp_path: Path) -> None:
        pack = _write_pack(
            tmp_path / "namespace.yaml",
            "rules:\n"
            '  - id: "my-own-rule"\n'
            "    priority: 950\n"
            "    action: block\n"
            "    match:\n"
            "      type: pattern\n"
            '      pattern: "zzz"\n',
        )

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "outside the pack namespace 'pack-db-*'")

    def test_schema_invalid_rule_is_refused(self, tmp_path: Path) -> None:
        pack = _write_pack(
            tmp_path / "schema.yaml",
            "rules:\n"
            '  - id: "pack-db-no-match"\n'
            "    priority: 950\n"
            "    action: block\n",
        )

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "has no 'match' mapping")

    def test_invalid_action_is_refused(self, tmp_path: Path) -> None:
        pack = _write_pack(
            tmp_path / "action.yaml",
            "rules:\n"
            '  - id: "pack-db-bad-action"\n'
            "    priority: 950\n"
            "    action: nuke\n"
            "    match:\n"
            "      type: pattern\n"
            '      pattern: "zzz"\n',
        )

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "action 'nuke' is not one of")

    def test_pattern_rule_without_a_pattern_is_refused(self, tmp_path: Path) -> None:
        pack = _write_pack(
            tmp_path / "nopattern.yaml",
            "rules:\n"
            '  - id: "pack-db-empty-pattern"\n'
            "    priority: 950\n"
            "    action: block\n"
            "    match:\n"
            "      type: pattern\n"
            '      pattern: ""\n',
        )

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "without a non-empty 'pattern'")

    def test_malformed_yaml_is_refused_on_one_line(self, tmp_path: Path) -> None:
        pack = _write_pack(tmp_path / "malformed.yaml", "rules: [ this : is : not : valid\n")

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        # The PyYAML ParserError is multi-line; the refusal contract is ONE line.
        self._assert_refused(result, "cannot parse")

    def test_missing_rules_key_is_refused(self, tmp_path: Path) -> None:
        pack = _write_pack(tmp_path / "norules.yaml", "not_rules: []\n")

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "no top-level 'rules' key")

    def test_empty_rules_list_is_refused(self, tmp_path: Path) -> None:
        pack = _write_pack(tmp_path / "empty.yaml", "rules: []\n")

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "top-level 'rules' list is empty")

    def test_duplicate_ids_inside_the_pack_are_refused(self, tmp_path: Path) -> None:
        rule = (
            "  - id: \"pack-db-dup\"\n"
            "    priority: 950\n"
            "    action: block\n"
            "    match:\n"
            "      type: pattern\n"
            '      pattern: "zzz"\n'
        )
        pack = _write_pack(tmp_path / "dup.yaml", "rules:\n" + rule + rule)

        result = _run_tool(
            "validate", str(pack), "--pack-name", "db", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "duplicate rule id(s) inside the pack")

    def test_id_already_installed_in_the_rules_dir_is_refused(self, tmp_path: Path) -> None:
        """The other-packs oracle: an id an installed file already carries is
        refused (a pack must not shadow it)."""
        rules_dir = tmp_path / "rules.d"
        rules_dir.mkdir()
        (rules_dir / "zz-handwritten.yaml").write_text(
            "rules:\n"
            '  - id: "pack-db-drop-database"\n'
            "    priority: 900\n"
            "    action: warn\n"
            "    match:\n"
            "      type: pattern\n"
            '      pattern: "drop database"\n',
            encoding="utf-8",
        )

        result = _run_tool(
            "validate", str(DB_PACK), "--pack-name", "db", "--rules-dir", str(rules_dir)
        )

        self._assert_refused(result, "are already installed in")
        assert "zz-handwritten.yaml" in result.stderr, result.stderr

    def test_unknown_pack_name_pattern_is_refused(self, tmp_path: Path) -> None:
        result = _run_tool(
            "validate", str(DB_PACK), "--pack-name", "db/../evil", "--rules-dir", str(tmp_path)
        )

        self._assert_refused(result, "invalid pack name")

    def test_missing_pack_file_is_refused(self, tmp_path: Path) -> None:
        result = _run_tool(
            "validate",
            str(tmp_path / "absent.yaml"),
            "--pack-name",
            "db",
            "--rules-dir",
            str(tmp_path),
        )

        self._assert_refused(result, "pack file not found")

    def test_unknown_option_is_refused(self, tmp_path: Path) -> None:
        result = _run_tool(
            "validate", str(DB_PACK), "--pack-name", "db", "--bogus", "x"
        )

        self._assert_refused(result, "unknown option '--bogus'")

    def test_installed_files_the_engine_cannot_parse_fail_closed(
        self, tmp_path: Path
    ) -> None:
        """The engine fails OPEN on an unparseable rules file; the collision
        oracle must not — a skipped file would make its ids invisible."""
        rules_dir = tmp_path / "rules.d"
        rules_dir.mkdir()
        (rules_dir / "broken.yaml").write_text(
            "rules: [ this : is : not : valid\n", encoding="utf-8"
        )

        result = _run_tool(
            "validate", str(DB_PACK), "--pack-name", "db", "--rules-dir", str(rules_dir)
        )

        self._assert_refused(result, "installed rule file")
        assert "cannot be read" in result.stderr, result.stderr


class TestValidatorList:
    def test_list_names_the_shipped_db_pack(self) -> None:
        result = _run_tool("list")

        assert result.returncode == 0, result.stderr
        rows = [line.split("\t") for line in result.stdout.splitlines() if line.strip()]
        by_name = {row[0]: row for row in rows}
        assert "db" in by_name, result.stdout
        name, path, count = by_name["db"]
        assert name == "db"
        assert Path(path) == DB_PACK
        assert count == "3"

    def test_list_rejects_arguments(self) -> None:
        result = _run_tool("list", "extra")

        assert result.returncode == 2
        assert "takes no arguments" in result.stderr


class TestValidatorEngineDefaults:
    def test_rules_dir_defaults_to_the_engine_user_rules_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without --rules-dir the validator reads the dir the ENGINE reads
        (TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR), so a manual run cannot
        silently validate against a different rules dir than the engine loads."""
        rules_dir = tmp_path / "engine-rules.d"
        rules_dir.mkdir()
        (rules_dir / "zz-handwritten.yaml").write_text(
            "rules:\n"
            '  - id: "pack-db-drop-table"\n'
            "    priority: 900\n"
            "    action: warn\n"
            "    match:\n"
            "      type: pattern\n"
            '      pattern: "drop table"\n',
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR"] = str(rules_dir)

        result = subprocess.run(
            [
                sys.executable,
                str(PACK_TOOL),
                "validate",
                str(DB_PACK),
                "--pack-name",
                "db",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(PROJECT_ROOT),
            timeout=60,
            env=env,
        )

        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "are already installed in" in result.stderr, result.stderr
