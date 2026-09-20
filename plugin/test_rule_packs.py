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

# DF-TERMINAL-JAIL-28: documented stderr banners the validator's process may
# emit BESIDES its one refusal line. The tool imports the engine builtins, and
# importing any terminal_jail.interruptor submodule first runs the package
# __init__, whose decider import evaluates ``userns.unshare_prefix()`` at
# import time; on a subuid host whose mapped uid launch is creatable but not
# file-access preserving that prints the DF-TERMINAL-JAIL-15 degradation
# warning to stderr BEFORE the refusal:
#     terminal-jail: WARNING: no filesystem isolation — the transparent
#     auto-sandbox fell back to the mapping-less PID namespace (...)
# That behavior is correct per DF-TERMINAL-JAIL-15, so the test contract
# asserts refusal PRESENCE (not an exact stderr line count) and tolerates
# exactly these banners, each at most once. Registered by STABLE PREFIX —
# future documented banners register here in one place. Any other stderr
# line is a hard failure: arbitrary output is never swallowed.
DOCUMENTED_SANDBOX_BANNERS = (
    "terminal-jail: WARNING: no filesystem isolation",
)

# Every validator refusal is emitted by ``rule-pack-tool.py::_refuse`` as this
# single line prefix; the helper asserts refusal PRESENCE by anchoring on it.
REFUSAL_PREFIX = "rule-pack-tool: refused:"

ENGINE_BUILTIN_COUNT = len(BUILTIN_BLOCKLIST) + len(BUILTIN_SANDBOX) + len(BUILTIN_ALLOWLIST)

# The pack's positive vectors: one per rule id, with the verdict the engine
# must produce when the pack is installed. TJ-GAP-062 landed the FULL catalogue
# and moved a single-table DROP to the GRAY zone, so `pack-db-drop-table` is
# asserted as MODIFY here (see plugin/test_rule_pack_db.py for the exhaustive
# per-rule matrix, which is the authoritative surface for this pack).
DB_PACK_POSITIVES = (
    (
        'psql -h db.internal -c "DROP DATABASE prod_app"',
        Action.BLOCK,
        "pack-db-drop-database",
    ),
    ('psql -c "DROP TABLE customers"', Action.MODIFY, "pack-db-drop-table"),
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
# DF-TERMINAL-JAIL-23: the two block rules match EXECUTION CONTEXT only
# ---------------------------------------------------------------------------

# The 9-shape regression matrix from the task, through the live engine with
# the pack installed. BLOCK side: the destructive SQL sits in a real SQL
# execution position (immediately after the client's -c/-e flag — arm A).
# The first entry is the task's mandated block; the rest pin the additional
# arms the pack header documents (after a semicolon inside the -c string —
# arm B1; positional after sqlite3 — arm C). TJ-GAP-062: a DROP TABLE is a GRAY
# shape now (single-table, scoped), so it is asserted as MODIFY — the doctrine
# lives in the pack header and the matrix in plugin/test_rule_pack_db.py.
DB_PACK_EXECUTION_CONTEXT_BLOCKS = (
    ('psql -c "DROP DATABASE prod"', Action.BLOCK, "pack-db-drop-database"),
    ('psql -c "DROP SCHEMA public CASCADE"', Action.BLOCK, "pack-db-drop-database"),
    ('mysql -e "drop database prod;"', Action.BLOCK, "pack-db-drop-database"),
    ('psql -c "SELECT 1; DROP DATABASE x"', Action.BLOCK, "pack-db-drop-database"),
    ('sqlite3 app.db "DROP DATABASE x"', Action.BLOCK, "pack-db-drop-database"),
)

# GRAY shapes: the statement sits in a real execution position (so the pack DO
# match it), but a single-table DROP/TRUNCATE is destructive-but-scoped, so the
# verdict is MODIFY (auto-sandbox), NOT block.
DB_PACK_EXECUTION_CONTEXT_GRAY = (
    ('psql -c "DROP TABLE users"', "pack-db-drop-table"),
    ('mysql -e "DROP TABLE users;"', "pack-db-drop-table"),
    ('sqlite3 app.db "DROP TABLE legacy"', "pack-db-drop-table"),
    ('psql -c "TRUNCATE users"', "pack-db-truncate"),
)

# ALLOW side: the statement TEXT is present but NOT in an execution position,
# so no pack rule may block (and none may attribute): sed/git are the
# remediation deadlock the reshaping closes, the psql SELECT literal is the
# read-only string whose words sit INSIDE a closed literal, echo/grep merely
# carry the text, and `psql -f` is the file-body gap that belongs to
# DF-TERMINAL-JAIL-10 (kept allowing here on purpose).
DB_PACK_EXECUTION_CONTEXT_ALLOWS = (
    'sed -i "s/DROP DATABASE/-- DROP DATABASE/" migrations/003_shard.sql',
    'git commit -am "park the DROP DATABASE migration"',
    'psql -c "SELECT msg FROM t WHERE msg = \'drop database retry\'"',
    'echo "DROP TABLE users" > build/rollback.sql',
    'psql -f migrations/002_legacy.sql',
    'grep -rn "DROP TABLE" migrations/',
)


class TestDbPackBlockRulesMatchExecutionContext:
    """DF-TERMINAL-JAIL-23: the pack's SQL rules require a SQL client AND the
    statement in an execution position — a destructive statement carried as
    plain text (sed replacement, commit message, quoted data literal, grep
    argument) is not matched. TJ-GAP-062 kept that contract and moved a
    single-table DROP/TRUNCATE to the GRAY (auto-sandbox) zone."""

    @pytest.mark.parametrize(
        ("command", "action", "rule_id"), DB_PACK_EXECUTION_CONTEXT_BLOCKS
    )
    def test_destructive_sql_in_execution_context_blocks(
        self, installed_pack: Path, command: str, action: Action, rule_id: str
    ) -> None:
        result = intercept(command)

        assert result.action == action, result
        assert result.rule_id == rule_id, (command, result)

    @pytest.mark.parametrize(
        ("command", "rule_id"), DB_PACK_EXECUTION_CONTEXT_GRAY
    )
    def test_single_table_destruction_is_sandboxed_not_blocked(
        self, installed_pack: Path, command: str, rule_id: str
    ) -> None:
        """Gray-zone doctrine: scoped destruction is wrapped, not refused."""
        result = intercept(command)

        assert result.action == Action.MODIFY, (command, result)
        assert result.rule_id == rule_id, (command, result)

    @pytest.mark.parametrize("command", DB_PACK_EXECUTION_CONTEXT_ALLOWS)
    def test_statement_text_outside_execution_context_is_not_attributed(
        self, installed_pack: Path, command: str
    ) -> None:
        result = intercept(command)

        assert result.action != Action.BLOCK, (command, result)
        assert not str(result.rule_id or "").startswith("pack-"), (command, result)

    def test_block_vectors_are_unattributed_without_the_pack(
        self, empty_rules: Path
    ) -> None:
        """Control: with no pack installed none of the vectors is a pack
        attribution (they ride on the engine's own defaults)."""
        for command, _action, rule_id in DB_PACK_EXECUTION_CONTEXT_BLOCKS:
            result = intercept(command)
            assert result.rule_id != rule_id, (command, result)
            assert not str(result.rule_id or "").startswith("pack-"), (command, result)
        for command, rule_id in DB_PACK_EXECUTION_CONTEXT_GRAY:
            result = intercept(command)
            assert result.rule_id != rule_id, (command, result)
            assert not str(result.rule_id or "").startswith("pack-"), (command, result)


# ---------------------------------------------------------------------------
# the installer's validator
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
        every catalogued rule under the installer's file name.

        The id set is the TJ-GAP-062 FULL catalogue (14 rules); the exhaustive
        per-rule behaviour matrix is plugin/test_rule_pack_db.py.
        """
        loaded = RuleLoader(
            system_dir=str(installed_pack.parent / "empty-system-rules.d"),
            user_dir=str(installed_pack),
        ).load_all()

        ids = {rule.id for rule in loaded.rules}
        assert ids == {
            "pack-db-psql-meta-shell",
            "pack-db-drop-database",
            "pack-db-truncate-cascade",
            "pack-db-admin-shutdown",
            "pack-db-redis-config",
            "pack-db-redis-module",
            "pack-db-redis-flush",
            "pack-db-mongosh-drop",
            "pack-db-mongosh-shutdown",
            "pack-db-data-dir-delete",
            "pack-db-dump-exfil",
            "pack-db-drop-table",
            "pack-db-truncate",
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
        assert "14 rule(s)" in result.stdout
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
    """Every refusal: exit 2 and its ONE reason line present on stderr.

    DF-TERMINAL-JAIL-28: the refusal is asserted by PRESENCE, not by an exact
    stderr line count — on subuid hosts whose mapped uid launch is creatable
    but not file-access preserving, the engine import emits the documented
    DF-TERMINAL-JAIL-15 degradation warning BEFORE the refusal (that behavior
    is correct). Any stderr line that is neither the refusal nor a documented
    banner (``DOCUMENTED_SANDBOX_BANNERS``) is still a hard failure.
    """

    def _assert_refused(
        self, result: subprocess.CompletedProcess[str], needle: str
    ) -> None:
        """Refusal contract: exit 2 and the ONE-LINE refusal reason present.

        The refusal must be the validator's own ``rule-pack-tool: refused:``
        line; the only other stderr lines tolerated are the
        DOCUMENTED_SANDBOX_BANNERS (the DF-TERMINAL-JAIL-15 degradation
        warning, at most once per prefix — it precedes the refusal on subuid
        hosts whose mapped uid launch is creatable but not file-access
        preserving). Anything else is a hard failure, so arbitrary output can
        never hide under this assertion.
        """
        assert result.returncode == 2, (result.stdout, result.stderr)
        lines = [line for line in result.stderr.splitlines() if line.strip()]
        refusal_lines = [line for line in lines if line.startswith(REFUSAL_PREFIX)]
        assert len(refusal_lines) == 1, lines
        assert needle in refusal_lines[0], result.stderr
        seen_banners: set[str] = set()
        for line in lines:
            if line.startswith(REFUSAL_PREFIX):
                continue
            for banner in DOCUMENTED_SANDBOX_BANNERS:
                if line.startswith(banner):
                    assert banner not in seen_banners, (banner, lines)
                    seen_banners.add(banner)
                    break
            else:
                raise AssertionError(
                    "stderr line matches neither the refusal nor a documented "
                    f"sandbox banner (expected at most {DOCUMENTED_SANDBOX_BANNERS}): "
                    f"{line!r} in {lines}"
                )

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


class TestAssertRefusedContract:
    """Self-tests for the refusal helper itself (DF-TERMINAL-JAIL-28).

    These drive ``_assert_refused`` with CONSTRUCTED stderr shapes, so the
    contract is proven on every host — including hosts where the degraded-FS
    warning never fires naturally (the dev host is one).
    """

    APPROVED = "collide with engine builtin ids"

    @staticmethod
    def _result(stderr: str, returncode: int = 2) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)

    def _assert(self, stderr: str, returncode: int = 2) -> None:
        TestValidatorRefusals()._assert_refused(
            self._result(stderr, returncode), self.APPROVED
        )

    def test_bare_refusal_passes(self) -> None:
        self._assert(f"{REFUSAL_PREFIX} ids collide with engine builtin ids\n")

    def test_refusal_plus_df15_warning_passes(self) -> None:
        """The degraded-host shape: the DF-15 banner precedes the refusal."""
        banner = (
            "terminal-jail: WARNING: no filesystem isolation — the transparent "
            "auto-sandbox fell back to the mapping-less PID namespace "
            "(--user --map-root-user): this host CAN create the uid-mapped "
            "launch (...) (DF-TERMINAL-JAIL-15). Set TERMINAL_JAIL_UID_MAP=0 ..."
        )
        self._assert(f"{banner}\n{REFUSAL_PREFIX} ids {self.APPROVED}\n")

    def test_unexpected_line_beside_the_refusal_fails(self) -> None:
        with pytest.raises(AssertionError, match="neither the refusal nor"):
            self._assert(
                f"{REFUSAL_PREFIX} ids {self.APPROVED}\nTraceback (most recent call last):\n"
            )

    def test_wrong_exit_code_fails(self) -> None:
        with pytest.raises(AssertionError):
            self._assert(f"{REFUSAL_PREFIX} ids {self.APPROVED}\n", returncode=0)

    def test_missing_refusal_line_fails(self) -> None:
        with pytest.raises(AssertionError):
            self._assert("terminal-jail: WARNING: no filesystem isolation x\n")

    def test_refusal_without_the_expected_reason_fails(self) -> None:
        with pytest.raises(AssertionError):
            self._assert(f"{REFUSAL_PREFIX} pack file not found\n")

    def test_repeated_banner_fails(self) -> None:
        warning = "terminal-jail: WARNING: no filesystem isolation once"
        with pytest.raises(AssertionError):
            self._assert(
                f"{warning}\n{warning}\n{REFUSAL_PREFIX} ids {self.APPROVED}\n"
            )

    def test_near_miss_line_that_merely_contains_a_banner_fails(self) -> None:
        """A line carrying arbitrary content before the banner prefix must
        not pass just because the banner text occurs inside it."""
        with pytest.raises(AssertionError, match="neither the refusal nor"):
            self._assert(
                f"prefix noise | terminal-jail: WARNING: no filesystem isolation\n"
                f"{REFUSAL_PREFIX} ids {self.APPROVED}\n"
            )


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
        assert count == "14"

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
