"""Packaging contract tests (TJ-DF-006).

Fast, network-free guard that ``pip install -e .`` exposes ``terminal_jail``
as the installed TOP-LEVEL package. Parses pyproject.toml directly via
tomllib (stdlib) — no subprocess, no venv, no network — so it runs in CI in
well under 2s.

If this test fails, the packaging config was reverted or drifted. The
consequences of that are concrete:

- standalone/terminal-jail L97 bridge fallback #4
  (``import terminal_jail.interruptor_bridge``) can never resolve via pip;
- standalone/seccomp-loader.py:61 (``from terminal_jail.seccomp import ...``)
  can never resolve via pip;
- ``[tool.setuptools.package-data] "terminal_jail" = ["rules/*.yaml"]`` is
  keyed on a package that is not installed, so rules/*.yaml never ships in a
  wheel.

The full fresh-venv install probe lives in test_install.py as an integration
test; this module is the fast guard that runs on every CI pass.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
PROBE_SCRIPT = PROJECT_ROOT / "scripts" / "pidns-capability-probe.py"


@pytest.fixture(scope="module")
def pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_packages_find_exposes_terminal_jail_as_top_level(pyproject: dict) -> None:
    """The finder must discover terminal_jail as a TOP-LEVEL package.

    ``where = ["plugin"]`` + ``include = ["terminal_jail*"]`` makes the
    package at plugin/terminal_jail/ install as top-level ``terminal_jail``
    (not ``plugin.terminal_jail``), which is what the standalone bridge
    fallback and seccomp-loader import.
    """
    find = pyproject["tool"]["setuptools"]["packages"]["find"]
    assert find["where"] == ["plugin"], (
        f"packages.find.where = {find['where']!r}; expected ['plugin'] so "
        "plugin/terminal_jail is discovered as top-level terminal_jail"
    )
    include = find["include"]
    assert "terminal_jail*" in include, (
        f"packages.find.include = {include!r}; expected it to contain "
        "'terminal_jail*'"
    )


def test_package_data_keyed_on_terminal_jail(pyproject: dict) -> None:
    """rules/*.yaml must be keyed on the package that actually ships."""
    package_data = pyproject["tool"]["setuptools"]["package-data"]
    assert "terminal_jail" in package_data, (
        "package-data must be keyed on 'terminal_jail' (the installed "
        "top-level package)"
    )
    assert "rules/*.yaml" in package_data["terminal_jail"]


def test_package_data_rules_exist_on_disk() -> None:
    """The rules dir the package-data glob refers to must exist."""
    rules = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules"
    assert rules.is_dir(), f"rules dir missing: {rules}"
    assert list(rules.glob("*.yaml")), f"no rules/*.yaml under {rules}"


def test_terminal_jail_package_exists_at_plugin_dir() -> None:
    """The package the finder must discover actually exists."""
    pkg = PROJECT_ROOT / "plugin" / "terminal_jail"
    assert (pkg / "__init__.py").is_file(), (
        f"plugin/terminal_jail/__init__.py missing: {pkg}"
    )


def test_shipped_rules_yaml_mirrors_engine_builtin_ids() -> None:
    """The shipped default rules file must mirror the engine's BUILTIN_* rules.

    TJ-GAP-032: 00-builtins.yaml shipped 28 ids while the engine documents 29
    (11 blocklist / 8 sandbox / 10 allow) — builtin-killpg-pid1 was missing
    from the YAML mirror, so an operator installing the default rules package
    got counts contradicting the README and a blocklist that didn't match the
    documented engine. The YAML and the Python BUILTIN_* constants must stay
    in sync (same rule IDs, same per-layer counts).
    """
    import yaml
    from terminal_jail.interruptor.allowlist import BUILTIN_ALLOWLIST
    from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST
    from terminal_jail.interruptor.sandbox import BUILTIN_SANDBOX
    rules_yaml = (
        PROJECT_ROOT / "plugin" / "terminal_jail" / "rules" / "00-builtins.yaml"
    )
    data = yaml.safe_load(rules_yaml.read_text())
    yaml_ids = {rule["id"] for rule in data["rules"]}

    engine_ids = {
        rule.id
        for rule in (
            list(BUILTIN_BLOCKLIST)
            + list(BUILTIN_SANDBOX)
            + list(BUILTIN_ALLOWLIST)
        )
    }

    assert yaml_ids == engine_ids, (
        "YAML mirror drifted from engine BUILTIN_* constants; "
        f"only-in-yaml: {sorted(yaml_ids - engine_ids)}, "
        f"only-in-engine: {sorted(engine_ids - yaml_ids)}"
    )

    # Per-layer counts must match the documented engine (31/13/10).
    block_ids = {r["id"] for r in data["rules"] if r.get("action") == "block"}
    sandbox_ids = {r["id"] for r in data["rules"] if r.get("action") == "sandbox"}
    allow_ids = {r["id"] for r in data["rules"] if r.get("action") == "allow"}
    assert len(block_ids) == len(BUILTIN_BLOCKLIST), (
        f"blocklist count {len(block_ids)} != engine {len(BUILTIN_BLOCKLIST)}"
    )
    assert len(sandbox_ids) == len(BUILTIN_SANDBOX), (
        f"sandbox count {len(sandbox_ids)} != engine {len(BUILTIN_SANDBOX)}"
    )
    assert len(allow_ids) == len(BUILTIN_ALLOWLIST), (
        f"allowlist count {len(allow_ids)} != engine {len(BUILTIN_ALLOWLIST)}"
    )


def test_shipped_rules_yaml_patterns_match_engine_builtins() -> None:
    """Every shipped YAML pattern must equal its engine builtin pattern.

    TJ-GAP-051: install.sh copies 00-builtins.yaml into
    ~/.config/terminal-jail/rules.d/, the engine loads that dir as USER rules,
    and same-id override REPLACES the builtin in its layer. So the YAML
    patterns ARE the live engine on any host that ran the documented install
    path. Three patterns (auto-script, builtin-fork-bomb, builtin-mkfs) had
    drifted WEAKER than their Python counterparts and flipped 12 verdicts from
    block/modify to allow — invisible to the id/count assertions above.

    The comparison is done on values produced by the engine's own RuleLoader
    (PyYAML escaping applied once, by the loader). Never compare by manually
    un-escaping YAML source: double-unescaping fabricates false mismatches.
    """
    from terminal_jail.interruptor.allowlist import BUILTIN_ALLOWLIST
    from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST
    from terminal_jail.interruptor.rules import RuleLoader
    from terminal_jail.interruptor.sandbox import BUILTIN_SANDBOX
    engine_rules = {
        rule.id: rule
        for rule in (
            list(BUILTIN_BLOCKLIST)
            + list(BUILTIN_SANDBOX)
            + list(BUILTIN_ALLOWLIST)
        )
    }
    rules_dir = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules"
    # user_dir is pinned to a non-existent path so this probe can never be
    # fooled by a stale copy in the host's real user rules dir.
    loaded = RuleLoader(system_dir=str(rules_dir), user_dir="/nonexistent").load_all()

    missing = sorted(set(engine_rules) - {r.id for r in loaded.rules})
    assert not missing, f"shipped YAML is missing engine rule ids: {missing}"
    assert len(loaded.rules) == len(engine_rules), (
        f"shipped YAML loaded {len(loaded.rules)} rules, engine has "
        f"{len(engine_rules)}"
    )

    drift = []
    for rule_id in sorted(engine_rules):
        engine_pattern = engine_rules[rule_id].match.get("pattern", "")
        yaml_rule = loaded.by_id(rule_id)
        assert yaml_rule is not None  # covered by `missing` above
        yaml_pattern = yaml_rule.match.get("pattern", "")
        if yaml_pattern != engine_pattern:
            drift.append(
                f"{rule_id}:\n"
                f"      engine={engine_pattern!r}\n"
                f"      yaml  ={yaml_pattern!r}"
            )
    assert not drift, (
        "shipped YAML pattern drift vs engine BUILTIN_* constants — the YAML "
        "same-id override replaces the builtin, so a weaker mirror silently "
        "weakens live verdicts:\n  " + "\n  ".join(drift)
    )


def test_pidns_capability_probe_is_host_agnostic() -> None:
    """The battery's capability classifier must run on ANY host (TJ-GAP-042).

    It is a classifier, not a gate: exit 0 always, and the verdict is exactly
    one of FULL / DEGRADED / UNKNOWN. A capable host (CI runner) prints FULL,
    a host that refuses unprivileged PID namespaces prints DEGRADED, and any
    unexpected state must still be reported as UNKNOWN rather than crashing.
    """
    assert PROBE_SCRIPT.is_file(), f"probe script missing: {PROBE_SCRIPT}"
    result = subprocess.run(
        ["python3", str(PROBE_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"probe must always exit 0; rc={result.returncode}, "
        f"stderr={result.stderr.strip()!r}"
    )
    verdict = result.stdout.strip()
    assert verdict in ("FULL", "DEGRADED") or verdict.startswith("UNKNOWN"), (
        f"probe printed unexpected verdict: {verdict!r}"
    )


RULES_SOURCE = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor" / "rules.py"
SHIPPED_RULES = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules" / "00-builtins.yaml"


def test_rules_loader_prefers_libyaml_c_loader() -> None:
    """The rules loader must use yaml.CSafeLoader when libyaml is available.

    Regression guard for E2E-001-GAP-07: install.sh ships the full builtins
    file into the user rules dir, and every intercept() call re-parses it.
    The pure-Python safe_load costs ~9ms per call (warm-start benchmark
    threshold is 5ms); the C loader parses the same document in <1ms with
    identical safe-load semantics.
    """
    yaml = pytest.importorskip("yaml")
    if not hasattr(yaml, "CSafeLoader"):
        pytest.skip("libyaml not available in this environment")

    source = RULES_SOURCE.read_text()
    assert "CSafeLoader" in source, (
        "rules.py must prefer yaml.CSafeLoader when available (E2E-001-GAP-07)"
    )

    # Behavioral parity: the fast path must construct identical rules.
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "plugin"))
    from terminal_jail.interruptor.rules import RuleLoader

    via_loader = RuleLoader()._parse_file(str(SHIPPED_RULES))
    import yaml as _yaml

    via_reference = _yaml.safe_load(SHIPPED_RULES.read_text())["rules"]
    assert [r.id for r in via_loader] == [r["id"] for r in via_reference]


# ── TJ-GAP-055: bubblewrap stays an external, unvendored dependency ──────────
#
# Spec row specs/cli.md §9 CLI-27. Two verdicts, both offline and
# host-independent:
#   1. the TRACKED tree ships no bubblewrap source/vendor artifact and no
#      submodule — the only supported install path is the distro package;
#   2. README.md and specs/cli.md keep stating the optional/external/
#      no-vendoring/no-legal-advice boundary and the fail-closed contract.

_PROJECT_ROOT_STR = str(PROJECT_ROOT)
_VENDOR_DIR_SEGMENTS = frozenset(
    {
        "vendor",
        "vendored",
        "third_party",
        "third-party",
        "thirdparty",
        "subprojects",
    }
)
_BWRAP_DIR_NAMES = frozenset({"bwrap", "bubblewrap"})
_BWRAP_SOURCE_SUFFIXES = frozenset(
    {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".rs", ".go", ".mk", ".am", ".ac"}
)
_MD_EMPHASIS_RE = re.compile(r"[`*_]")
# A denial anywhere on the line makes a "vendoring bubblewrap" mention a
# statement that this repository does NOT do it.
_DENIAL_RE = re.compile(r"\b(no|not|never|none|without|neither)\b", re.I)


def _tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=_PROJECT_ROOT_STR,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, (
        "git ls-files failed — the tracked-tree audit cannot run: "
        f"{result.stderr.decode('utf-8', 'replace')!r}"
    )
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def _plain_markdown(text: str) -> str:
    """Strip markdown emphasis so claims can be asserted as plain prose."""
    return _MD_EMPHASIS_RE.sub("", text)


def test_tracked_tree_ships_no_vendored_bubblewrap() -> None:
    """TJ-GAP-055: bubblewrap must remain an external distro package — no
    vendored source tree, no submodule, no bundled binary, no C source."""
    paths = _tracked_paths()
    assert paths, "git ls-files returned nothing — the audit would be vacuous"
    # Positive control: the audit really is looking at this repository.
    assert "install.sh" in paths and "README.md" in paths, paths[:20]

    vendor_paths = sorted(
        p for p in paths if _VENDOR_DIR_SEGMENTS & set(Path(p).parts[:-1])
    )
    assert vendor_paths == [], (
        f"tracked vendor/third-party paths (vendoring would break the "
        f"packaging boundary): {vendor_paths}"
    )

    bwrap_paths = sorted(
        p for p in paths if _BWRAP_DIR_NAMES & {part.lower() for part in Path(p).parts}
    )
    assert bwrap_paths == [], (
        f"tracked bubblewrap directory/artifact (bubblewrap is installed from "
        f"the distro, never shipped here): {bwrap_paths}"
    )

    bwrap_sources = sorted(
        p
        for p in paths
        if "bwrap" in Path(p).name.lower()
        and Path(p).suffix.lower() in _BWRAP_SOURCE_SUFFIXES
    )
    assert bwrap_sources == [], f"tracked bubblewrap source file: {bwrap_sources}"

    gitmodules = PROJECT_ROOT / ".gitmodules"
    if gitmodules.exists():
        content = gitmodules.read_text(encoding="utf-8")
        assert not re.search(r"bubblewrap|bwrap", content, re.I), (
            "bubblewrap must not be vendored as a git submodule"
        )


def test_docs_state_bubblewrap_packaging_boundary() -> None:
    """TJ-GAP-055: README/spec must state the narrow, honest boundary —
    optional, distro package, external executable, not vendored or
    redistributed, unshare fallback, explicit bwrap demand fails closed, and
    explicitly NOT legal advice."""
    readme = _plain_markdown((PROJECT_ROOT / "README.md").read_text(encoding="utf-8"))
    spec = _plain_markdown(
        (PROJECT_ROOT / "specs" / "cli.md").read_text(encoding="utf-8")
    )

    for name, doc in (("README.md", readme), ("specs/cli.md", spec)):
        for phrase in (
            "apt install bubblewrap",
            "dnf install bubblewrap",
            "LGPL-2.1-or-later",
            "not legal advice",
            "advisory note",
            "fails closed",
        ):
            assert phrase in doc, f"{name} is missing the packaging claim {phrase!r}"

    # The optional dependency must be labeled optional where it is introduced.
    optional_lines = [
        line
        for line in readme.splitlines()
        if "bubblewrap" in line.lower() and "optional" in line.lower()
    ]
    assert optional_lines, "README.md never labels bubblewrap as optional"

    for phrase in (
        "does not vendor, bundle, download, build, or redistribute bubblewrap",
        "resolved from PATH",
        "only prints an advisory note",
    ):
        assert phrase in readme, f"README.md is missing {phrase!r}"

    for phrase in (
        "optional runtime dependency",
        "never vendored",
        "resolved from PATH",
    ):
        assert phrase in spec, f"specs/cli.md is missing {phrase!r}"

    # Negative: a line that mentions vendoring bubblewrap must be a denial —
    # this is what catches the claim being flipped to "we vendor it".
    claiming_lines = [
        (name, line)
        for name, doc in (("README.md", readme), ("specs/cli.md", spec))
        for line in doc.splitlines()
        if any(
            claim in line.lower()
            for claim in ("vendor bubblewrap", "vendoring bubblewrap", "vendored bubblewrap")
        )
    ]
    assert claiming_lines, (
        "no document line mentions vendoring bubblewrap — the negative check "
        "would be vacuous"
    )
    for name, line in claiming_lines:
        assert _DENIAL_RE.search(line), (
            f"{name} mentions vendoring bubblewrap without denying it: {line.strip()!r}"
        )
