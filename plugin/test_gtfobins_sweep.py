"""Tests for scripts/gtfobins-sweep.py (TJ-GAP-059).

The sweep harness is the measuring stick for the GTFOBins surface: it reports
what the shipped engine does with each GTFOBins invocation shape and guards the
postures the fleet consciously accepted. These tests pin its contract:

  * verdict computation runs against the LIVE engine in-process (no network, no
    payload execution — the engine matches command STRINGS),
  * posture classification is total and correct for both drift directions,
  * coverage math is exact for perfect / zero / partial sets,
  * the seed catalog is structurally valid and self-consistent,
  * malformed catalogs fail closed naming the catalog path,
  * the rendered report always carries the coverage line the CI gate greps.

Module import path: scripts/ is not a package, so the module is loaded from its
file path (the same pattern as plugin/test_board_id_guard.py). The sweep module
bootstraps plugin/ onto sys.path itself when it needs the engine.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SWEEP_SCRIPT = PROJECT_ROOT / "scripts" / "gtfobins-sweep.py"
SEED_CATALOG = PROJECT_ROOT / "scripts" / "gtfobins-catalog-seed.yaml"

# ── module loading ─────────────────────────────────────────────────

_spec = importlib.util.spec_from_file_location("gtfobins_sweep", SWEEP_SCRIPT)
assert _spec is not None and _spec.loader is not None
sweep_mod = importlib.util.module_from_spec(_spec)
sys.modules["gtfobins_sweep"] = sweep_mod
_spec.loader.exec_module(sweep_mod)


@pytest.fixture(scope="module")
def engine():
    """The live engine module the sweep imports."""
    return sweep_mod.load_engine()


@pytest.fixture(scope="module")
def seed_rows():
    """The shipped seed catalog, validated by the loader."""
    return sweep_mod.load_catalog(SEED_CATALOG)


@pytest.fixture(scope="module")
def seed_report(seed_rows):
    """The shipped seed catalog swept against the live engine."""
    return sweep_mod.SweepReport(
        catalog_path=str(SEED_CATALOG), results=sweep_mod.sweep(seed_rows)
    )


def write_catalog(tmp_path: Path, text: str) -> Path:
    """Write a catalog fixture and return its path."""
    path = tmp_path / "catalog.yaml"
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL_ENTRY = """
schema_version: 1
entries:
  - name: "sudo"
    rationale: "escalator"
    classes:
      - class: "shell"
        invocation: "sudo /bin/sh"
        expected: "blocked"
"""


# ── engine contract ────────────────────────────────────────────────


class TestEngineContract:
    """The sweep's assumptions about the engine must match the engine."""

    def test_action_constants_mirror_engine_vocabulary(self, engine):
        """The report's action columns are the engine's own Action values."""
        assert sweep_mod.ACTION_ALLOW == engine.Action.ALLOW
        assert sweep_mod.ACTION_BLOCK == engine.Action.BLOCK
        assert sweep_mod.ACTION_MODIFY == engine.Action.MODIFY
        assert sweep_mod.ACTION_WARN == engine.Action.WARN

    def test_verdict_action_is_a_plain_str(self, engine):
        """The foreman's verified fact: .action is a str, not an Enum."""
        result = engine.intercept("sudo -l", config=sweep_mod.hermetic_config(engine))
        assert isinstance(result.action, str)
        assert repr(result.action) == "'block'"

    def test_hermetic_config_ignores_host_rule_dirs(self, engine):
        """The sweep measures shipped built-ins, not a host's rules.d."""
        config = sweep_mod.hermetic_config(engine)
        assert not Path(config.system_rules_dir).exists()
        assert not Path(config.user_rules_dir).exists()


# ── live verdict computation ───────────────────────────────────────


class TestVerdictComputation:
    """Rows are swept through the live engine; postures classify against it."""

    def test_conscious_allow_row_classifies_as_match(self, seed_report):
        """`git status` is allowlisted and consciously allowed → match."""
        rows = [r for r in seed_report.results if r.binary == "git"]
        assert len(rows) == 2
        status = next(r for r in rows if r.function_class == "file-read")
        assert status.action == sweep_mod.ACTION_ALLOW
        assert status.rule_id == "allow-git-read"
        assert status.classification == sweep_mod.CLASS_MATCH
        assert status.drifted is False

    def test_blocked_row_matches_with_block_rule_provenance(self, seed_report):
        """sudo is the accepted block: block verdict, builtin-sudo provenance."""
        sudo = next(r for r in seed_report.results if r.binary == "sudo")
        assert sudo.expected == sweep_mod.POSTURE_BLOCKED
        assert sudo.action == sweep_mod.ACTION_BLOCK
        assert sudo.rule_id == "builtin-sudo"
        assert sudo.classification == sweep_mod.CLASS_MATCH

    def test_allow_rule_provenance_is_non_none_but_default_allow_is_none(
        self, seed_report
    ):
        """A conscious allow carries a rule id; a default ALLOW carries None.

        This is the distinction the report exists to make visible: `git status`
        matched the allow-git-read allowlist rule, while `less /etc/hostname`
        simply matched no rule at all (default-allow posture).
        """
        git_status = next(
            r
            for r in seed_report.results
            if r.binary == "git" and r.function_class == "file-read"
        )
        less_read = next(
            r
            for r in seed_report.results
            if r.binary == "less" and r.function_class == "file-read"
        )
        assert git_status.rule_id is not None
        assert less_read.rule_id is None
        assert git_status.action == less_read.action == sweep_mod.ACTION_ALLOW

    def test_sweep_returns_one_result_per_row_in_order(self, seed_rows):
        """Sweeping is a pure per-row evaluation, order preserved."""
        results = sweep_mod.sweep(seed_rows)
        assert len(results) == len(seed_rows)
        assert [r.invocation for r in results] == [
            row.invocation for row in seed_rows
        ]

    def test_modify_verdict_is_recorded_verbatim(self, seed_report):
        """`env /bin/sh` is auto-sandboxed (modify), not allowed."""
        env_shell = next(
            r
            for r in seed_report.results
            if r.binary == "env" and r.function_class == "shell"
        )
        assert env_shell.action == sweep_mod.ACTION_MODIFY
        assert env_shell.rule_id == "builtin-net-fetch-pipe-qualified"

    def test_wrapper_does_not_hide_a_blocked_inner_command(self, seed_report):
        """`nice sudo -l` still blocks: the escalator is read through the wrapper."""
        wrappers = [
            r
            for r in seed_report.results
            if r.function_class == "sudo"
            and r.binary in {"env", "nice", "time", "timeout"}
        ]
        assert len(wrappers) == 4
        assert {r.action for r in wrappers} == {sweep_mod.ACTION_BLOCK}


# ── classification ─────────────────────────────────────────────────


class TestClassification:
    """Every (posture, action) pair maps to exactly one label."""

    @pytest.mark.parametrize(
        "expected,action,label",
        [
            ("blocked", "block", sweep_mod.CLASS_MATCH),
            ("blocked", "allow", sweep_mod.CLASS_DRIFT_UNPROTECTED),
            ("blocked", "modify", sweep_mod.CLASS_DRIFT_UNPROTECTED),
            ("allowed-conscious", "allow", sweep_mod.CLASS_MATCH),
            ("allowed-conscious", "block", sweep_mod.CLASS_DRIFT_OVERBLOCKED),
            ("review", "allow", sweep_mod.CLASS_REVIEW),
            ("review", "block", sweep_mod.CLASS_REVIEW),
            ("review", "modify", sweep_mod.CLASS_REVIEW),
        ],
    )
    def test_classify_matrix(self, expected, action, label):
        assert sweep_mod.classify(expected, action) == label

    def test_review_rows_are_never_drift(self):
        """A review row carries no expectation, so it can never be drift."""
        for action in sweep_mod.ACTION_COLUMNS:
            assert (
                sweep_mod.classify(sweep_mod.POSTURE_REVIEW, action)
                == sweep_mod.CLASS_REVIEW
            )

    def test_classify_is_total_over_postures_and_actions(self):
        """No unhandled branch: every posture/action pair yields a label."""
        for expected in sweep_mod.POSTURES:
            for action in sweep_mod.ACTION_COLUMNS:
                assert isinstance(sweep_mod.classify(expected, action), str)


# ── coverage math ──────────────────────────────────────────────────


def row_with(expected: str, action: str) -> object:
    """Build a RowResult with a chosen live action (no engine needed)."""
    return sweep_mod.RowResult(
        binary="x",
        function_class="shell",
        invocation="x",
        expected=expected,
        rationale="test",
        note="",
        action=action,
        rule_id=None,
        classification=sweep_mod.classify(expected, action),
    )


class TestCoverage:
    """coverage counts definitive postures only; review rows are excluded."""

    def test_perfect_coverage(self):
        results = [
            row_with("blocked", "block"),
            row_with("allowed-conscious", "allow"),
        ]
        assert sweep_mod.coverage(results) == (2, 2, 100.0)

    def test_zero_coverage(self):
        results = [
            row_with("blocked", "allow"),
            row_with("allowed-conscious", "block"),
        ]
        assert sweep_mod.coverage(results) == (0, 2, 0.0)

    def test_partial_coverage(self):
        results = [
            row_with("blocked", "block"),
            row_with("blocked", "allow"),
            row_with("allowed-conscious", "allow"),
            row_with("allowed-conscious", "block"),
        ]
        matched, total, percent = sweep_mod.coverage(results)
        assert (matched, total, percent) == (2, 4, 50.0)

    def test_review_rows_are_excluded_from_the_denominator(self):
        results = [
            row_with("blocked", "block"),
            row_with("review", "allow"),
            row_with("review", "allow"),
        ]
        assert sweep_mod.coverage(results) == (1, 1, 100.0)

    def test_empty_results_do_not_divide_by_zero(self):
        assert sweep_mod.coverage([]) == (0, 0, 0.0)

    def test_review_only_results_report_zero_total(self):
        results = [row_with("review", "allow")]
        assert sweep_mod.coverage(results) == (0, 0, 0.0)

    def test_seed_catalog_coverage_is_perfect(self, seed_report):
        """The shipped seed must match the live engine (the CI gate's premise)."""
        matched, total, percent = sweep_mod.coverage(seed_report.results)
        assert total > 0
        assert matched == total
        assert percent == 100.0
        assert sweep_mod.drifted(seed_report.results) == []


# ── action counts / matrix ─────────────────────────────────────────


class TestMatrix:
    """The matrix aggregates live verdicts per function class."""

    def test_action_counts_include_every_column(self):
        counts = sweep_mod.action_counts([row_with("blocked", "block")])
        assert set(counts) == set(sweep_mod.ACTION_COLUMNS)
        assert counts["block"] == 1
        assert counts["allow"] == 0

    def test_matrix_counts_and_binaries_per_class(self):
        results = [
            sweep_mod.RowResult(
                binary="a",
                function_class="shell",
                invocation="a",
                expected="blocked",
                rationale="t",
                note="",
                action="block",
                rule_id=None,
                classification=sweep_mod.CLASS_MATCH,
            ),
            sweep_mod.RowResult(
                binary="b",
                function_class="shell",
                invocation="b",
                expected="review",
                rationale="t",
                note="",
                action="allow",
                rule_id=None,
                classification=sweep_mod.CLASS_REVIEW,
            ),
        ]
        cell = sweep_mod.matrix(results)["shell"]
        assert cell["block"] == 1
        assert cell["allow"] == 1
        assert cell["binaries"] == ["a(block)", "b(allow)"]

    def test_matrix_does_not_duplicate_a_binary_with_one_verdict(self):
        """A class is one row per binary per verdict — not per catalog row."""
        results = [
            sweep_mod.RowResult(
                binary="nice",
                function_class="shell",
                invocation=i,
                expected="review",
                rationale="t",
                note="",
                action="allow",
                rule_id=None,
                classification=sweep_mod.CLASS_REVIEW,
            )
            for i in ("nice /bin/sh", "nice -n 5 /bin/sh -p")
        ]
        cell = sweep_mod.matrix(results)["shell"]
        assert cell["allow"] == 2
        assert cell["binaries"] == ["nice(allow)"]


# ── catalog integrity ──────────────────────────────────────────────


class TestSeedCatalogIntegrity:
    """Every seed seed entry is complete, unique and posture-valid."""

    def test_loads_from_the_default_path(self):
        """The default path constant points at the shipped seed."""
        assert seed_catalog_matches_default()

    def test_every_entry_has_the_required_fields(self, seed_rows):
        assert seed_rows
        for row in seed_rows:
            assert row.binary.strip()
            assert row.function_class.strip()
            assert row.invocation.strip()
            assert row.expected in sweep_mod.POSTURES
            assert row.rationale.strip()

    def test_binary_names_are_unique(self):
        """Duplicate names are rejected at load, so the shipped set is unique."""
        raw = _raw_seed_entries()
        names = [entry["name"] for entry in raw]
        assert len(set(names)) == len(names)

    def test_duplicate_binary_name_is_rejected_before_use(self, tmp_path, capsys):
        """The loader's duplicate check is what keeps names unique."""
        path = write_catalog(
            tmp_path,
            "schema_version: 1\nentries:\n"
            "  - name: 'x'\n"
            "    rationale: 'r'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'x'\n"
            "        expected: 'blocked'\n"
            "  - name: 'x'\n"
            "    rationale: 'r'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'y'\n"
            "        expected: 'blocked'\n",
        )
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--catalog", str(path)])
        assert excinfo.value.code == sweep_mod.EXIT_CATALOG_ERROR
        assert "duplicate" in capsys.readouterr().err

    def test_every_binary_carries_a_rationale(self):
        for entry in _raw_seed_entries():
            assert entry["rationale"].strip(), entry["name"]

    def test_seed_covers_the_named_binary_set(self):
        """The seed must include the binaries the task named."""
        required = {
            "sudo",
            "vim",
            "less",
            "git",
            "tar",
            "find",
            "awk",
            "env",
            "nmap",
            "openssl",
            "python3",
            "perl",
            "ruby",
            "php",
            "bash",
            "nice",
            "time",
            "timeout",
        }
        assert {entry["name"] for entry in _raw_seed_entries()} == required

    def test_seed_size_in_the_stated_range(self):
        assert 15 <= len(_raw_seed_entries()) <= 25

    def test_review_posture_is_present(self):
        """Review marks what has NOT been consciously accepted yet."""
        postures = {
            cls["expected"]
            for entry in _raw_seed_entries()
            for cls in entry["classes"]
        }
        assert sweep_mod.POSTURE_REVIEW in postures
        assert sweep_mod.POSTURE_BLOCKED in postures
        assert sweep_mod.POSTURE_ALLOWED_CONSCIOUS in postures

    def test_invocations_are_single_line(self, seed_rows):
        for row in seed_rows:
            assert "\n" not in row.invocation

    def test_duplicate_invocation_within_a_binary_class_is_absent(self, seed_rows):
        seen = set()
        for row in seed_rows:
            key = (row.binary, row.function_class, row.invocation)
            assert key not in seen, key
            seen.add(key)


def _raw_seed_entries() -> list[dict]:
    """The seed catalog's raw entries (for structural assertions)."""
    import yaml

    data = yaml.safe_load(SEED_CATALOG.read_text(encoding="utf-8"))
    return data["entries"]


def seed_catalog_matches_default() -> bool:
    """The module's default catalog path is the shipped seed file."""
    return Path(sweep_mod.DEFAULT_CATALOG) == SEED_CATALOG


# ── malformed catalog error paths ──────────────────────────────────


class TestCatalogValidation:
    """Malformed catalogs fail closed, naming the offending path."""

    def test_missing_file_raises_system_exit_naming_the_path(self, tmp_path, capsys):
        missing = tmp_path / "nope.yaml"
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--catalog", str(missing)])
        assert excinfo.value.code == sweep_mod.EXIT_CATALOG_ERROR
        assert str(missing) in capsys.readouterr().err

    def test_bad_yaml_raises_system_exit_naming_the_path(self, tmp_path, capsys):
        path = write_catalog(tmp_path, "entries: [\n  - name: 'x'\n")
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--catalog", str(path)])
        assert excinfo.value.code == sweep_mod.EXIT_CATALOG_ERROR
        assert str(path) in capsys.readouterr().err

    def test_non_list_entries_raises_system_exit_naming_the_path(
        self, tmp_path, capsys
    ):
        path = write_catalog(tmp_path, "schema_version: 1\nentries: not-a-list\n")
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--catalog", str(path)])
        assert excinfo.value.code == sweep_mod.EXIT_CATALOG_ERROR
        err = capsys.readouterr().err
        assert str(path) in err
        assert "entries" in err

    def test_missing_required_field_raises_system_exit_naming_the_path(
        self, tmp_path, capsys
    ):
        path = write_catalog(
            tmp_path,
            "schema_version: 1\nentries:\n"
            "  - name: 'x'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'x'\n"
            "        expected: 'blocked'\n",
        )
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--catalog", str(path)])
        assert excinfo.value.code == sweep_mod.EXIT_CATALOG_ERROR
        err = capsys.readouterr().err
        assert str(path) in err
        assert "rationale" in err

    def test_invalid_posture_raises_system_exit_naming_the_path(
        self, tmp_path, capsys
    ):
        path = write_catalog(
            tmp_path,
            "schema_version: 1\nentries:\n"
            "  - name: 'x'\n"
            "    rationale: 'r'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'x'\n"
            "        expected: 'probably-fine'\n",
        )
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--catalog", str(path)])
        assert excinfo.value.code == sweep_mod.EXIT_CATALOG_ERROR
        err = capsys.readouterr().err
        assert str(path) in err
        assert "expected" in err

    def test_duplicate_binary_name_is_rejected(self, tmp_path, capsys):
        path = write_catalog(
            tmp_path,
            "schema_version: 1\nentries:\n"
            "  - name: 'x'\n"
            "    rationale: 'first'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'x'\n"
            "        expected: 'blocked'\n"
            "  - name: 'x'\n"
            "    rationale: 'second'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'y'\n"
            "        expected: 'blocked'\n",
        )
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--catalog", str(path)])
        assert excinfo.value.code == sweep_mod.EXIT_CATALOG_ERROR
        err = capsys.readouterr().err
        assert str(path) in err
        assert "duplicate" in err

    def test_unknown_top_level_key_is_rejected(self, tmp_path, capsys):
        path = write_catalog(tmp_path, "entries: []\nfreestyle: true\n")
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--catalog", str(path)])
        assert excinfo.value.code == sweep_mod.EXIT_CATALOG_ERROR
        err = capsys.readouterr().err
        assert str(path) in err
        assert "freestyle" in err

    def test_catalog_error_carries_the_path_in_the_message(self, tmp_path):
        missing = tmp_path / "ghost.yaml"
        with pytest.raises(sweep_mod.CatalogError) as excinfo:
            sweep_mod.load_catalog(missing)
        assert str(missing) in str(excinfo.value)

    def test_valid_catalog_is_not_rejected(self, tmp_path):
        path = write_catalog(tmp_path, MINIMAL_ENTRY)
        rows = sweep_mod.load_catalog(path)
        assert len(rows) == 1
        assert rows[0].binary == "sudo"


# ── rendering ──────────────────────────────────────────────────────


class TestRendering:
    """Both formats carry the same data, and the coverage line is greppable."""

    def test_text_report_contains_the_coverage_line(self, seed_report):
        text = sweep_mod.render_text(seed_report)
        assert "gtfobins-coverage" in text

    def test_text_report_names_every_function_class(self, seed_report):
        text = sweep_mod.render_text(seed_report)
        for function_class in sweep_mod.matrix(seed_report.results):
            assert function_class in text

    def test_text_report_lists_drift_and_review_sections(self, seed_report):
        text = sweep_mod.render_text(seed_report)
        assert "POSTURE-DRIFT" in text
        assert "REVIEW" in text

    def test_json_parses_and_matches_the_text_data(self, seed_report):
        payload = json.loads(sweep_mod.render_json(seed_report))
        matched, total, percent = sweep_mod.coverage(seed_report.results)
        assert payload["coverage"]["matched"] == matched
        assert payload["coverage"]["total"] == total
        assert payload["coverage"]["percent"] == percent
        assert len(payload["rows"]) == len(seed_report.results)
        assert payload["entries"]["binaries"] == len(
            {r.binary for r in seed_report.results}
        )

    def test_json_is_byte_stable(self, seed_report):
        assert sweep_mod.render_json(seed_report) == sweep_mod.render_json(
            seed_report
        )

    def test_json_matrix_matches_the_row_data(self, seed_report):
        payload = json.loads(sweep_mod.render_json(seed_report))
        for row in payload["rows"]:
            cell = payload["matrix"][row["class"]]
            assert cell[row["action"]] >= 1


# ── CLI behaviour ──────────────────────────────────────────────────


class TestCli:
    """Exit codes: 0 advisory, 1 on drift under --check, 2 on catalog errors."""

    def test_advisory_mode_exits_zero(self, capsys):
        assert sweep_mod.main([]) == sweep_mod.EXIT_OK
        assert "gtfobins-coverage" in capsys.readouterr().out

    def test_check_mode_exits_zero_on_the_seed_catalog(self, capsys):
        """The seed must not fail --check: no definitive drift may exist."""
        assert sweep_mod.main(["--check"]) == sweep_mod.EXIT_OK
        out = capsys.readouterr().out
        assert "gtfobins-coverage" in out
        assert "[check] OK" in out

    def test_check_mode_exits_one_on_definitive_drift(self, tmp_path, capsys):
        """A blocked posture that the engine allows is the regression signal."""
        path = write_catalog(
            tmp_path,
            "schema_version: 1\nentries:\n"
            "  - name: 'vim'\n"
            "    rationale: 'drifted on purpose'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'vim -c q'\n"
            "        expected: 'blocked'\n",
        )
        assert sweep_mod.main(["--catalog", str(path), "--check"]) == (
            sweep_mod.EXIT_DRIFT
        )
        out = capsys.readouterr().out
        assert "DRIFT-UNPROTECTED" in out
        assert "[check] FAIL" in out

    def test_check_mode_ignores_review_drift(self, tmp_path, capsys):
        """review rows have no posture to defend; they never fail --check."""
        path = write_catalog(
            tmp_path,
            "schema_version: 1\nentries:\n"
            "  - name: 'vim'\n"
            "    rationale: 'no posture yet'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'vim -c q'\n"
            "        expected: 'review'\n",
        )
        assert sweep_mod.main(["--catalog", str(path), "--check"]) == (
            sweep_mod.EXIT_OK
        )
        out = capsys.readouterr().out
        assert "REVIEW" in out
        assert "[check] OK" in out

    def test_check_mode_flags_an_allow_posture_that_now_blocks(
        self, tmp_path, capsys
    ):
        """Over-blocking is drift too: a conscious allow must stay allowed."""
        path = write_catalog(
            tmp_path,
            "schema_version: 1\nentries:\n"
            "  - name: 'sudo'\n"
            "    rationale: 'pretend this was consciously allowed'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'sudo -l'\n"
            "        expected: 'allowed-conscious'\n",
        )
        assert sweep_mod.main(["--catalog", str(path), "--check"]) == (
            sweep_mod.EXIT_DRIFT
        )
        assert "DRIFT-OVERBLOCKED" in capsys.readouterr().out

    def test_format_json_emits_parseable_json(self, capsys):
        assert sweep_mod.main(["--format", "json"]) == sweep_mod.EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert "coverage" in payload and "matrix" in payload

    def test_format_json_check_drift_still_exits_one(self, tmp_path, capsys):
        path = write_catalog(
            tmp_path,
            "schema_version: 1\nentries:\n"
            "  - name: 'vim'\n"
            "    rationale: 'drifted'\n"
            "    classes:\n"
            "      - class: 'shell'\n"
            "        invocation: 'vim -c q'\n"
            "        expected: 'blocked'\n",
        )
        code = sweep_mod.main(["--catalog", str(path), "--check", "--format", "json"])
        assert code == sweep_mod.EXIT_DRIFT
        payload = json.loads(capsys.readouterr().out)
        assert payload["drift"]

    def test_stdout_flag_is_accepted(self, capsys):
        assert sweep_mod.main(["--stdout"]) == sweep_mod.EXIT_OK
        assert "gtfobins-coverage" in capsys.readouterr().out

    def test_help_documents_the_check_exit_rule(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            sweep_mod.main(["--help"])
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert "--check exit rule" in out
        assert "review" in out
