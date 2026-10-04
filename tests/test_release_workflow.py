"""Pins for the tag-triggered release tooling (RELEASE-TJ-008).

Cheap structural checks, no network:

- ``.github/workflows/release.yml`` exists and parses as YAML; the
  tag/workflow_dispatch triggers, the ``contents: write`` permission, the
  ``python -m build`` + ``gh release create`` steps, the sha256 checksum
  step, and the loud-failure postures are all pinned.
- ``scripts/release-cut-check.sh`` passes on a prepared clean tree (a
  scratch ``git clone --shared`` with the version bumped the way the real
  version-prep commit will, CI results supplied through the documented
  ``TJ_RELEASE_CI_JSON`` seam) and fails, naming the failure, on an
  existing tag, a wrong-version tag, red CI, and malformed CI data.
- The workflow never touches the ``pyproject.toml`` version and never
  creates a tag.

The live publish path itself (real tag push -> real Release with assets)
is intentionally NOT exercised here: it only ever fires on a real,
owner-authorized tag cut (witness=none:workflow-publishes-only-on-real-tag).
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
CHECK_SCRIPT = PROJECT_ROOT / "scripts" / "release-cut-check.sh"


def _yaml_load(path: pathlib.Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _run_script(cwd: pathlib.Path, *args: str, env_extra: dict | None = None):
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [str(cwd / "scripts" / "release-cut-check.sh"), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )


# --------------------------------------------------------------------------
# workflow structure
# --------------------------------------------------------------------------


def test_release_workflow_parses_as_yaml() -> None:
    _yaml_load(WORKFLOW)  # raises on malformed YAML


def test_release_workflow_triggers_on_v_tags_and_dispatch() -> None:
    doc = _yaml_load(WORKFLOW)
    triggers = doc[True] if True in doc else doc[False]  # YAML 1.1 'on' bool
    assert "push" in triggers, f"missing push trigger: {list(triggers)}"
    assert triggers["push"] == {"tags": ["v*"]}, triggers["push"]
    assert "workflow_dispatch" in triggers
    assert "tag" in triggers["workflow_dispatch"]["inputs"]


def test_release_workflow_declares_contents_write() -> None:
    doc = _yaml_load(WORKFLOW)
    assert doc["permissions"] == {"contents": "write"}


def test_release_workflow_builds_with_python_m_build_on_311() -> None:
    doc = _yaml_load(WORKFLOW)
    steps = doc["jobs"]["release"]["steps"]
    py_versions = [
        s.get("with", {}).get("python-version")
        for s in steps
        if (s.get("uses") or "").startswith("actions/setup-python")
    ]
    assert "3.11" in py_versions, py_versions
    scripts = [s.get("run", "") for s in steps]
    assert any("python -m build" in s for s in scripts)


def test_release_workflow_checksums_and_creates_release() -> None:
    doc = _yaml_load(WORKFLOW)
    scripts = "\n".join(s.get("run", "") for s in doc["jobs"]["release"]["steps"])
    assert "sha256sum" in scripts
    assert "gh release create" in scripts
    # publish targets the resolved tag, not whatever ref the run started on
    assert "--verify-tag" in scripts


def test_release_workflow_fails_loudly_without_secrets_or_permissions() -> None:
    doc = _yaml_load(WORKFLOW)
    scripts = "\n".join(s.get("run", "") for s in doc["jobs"]["release"]["steps"])
    assert "::error::" in scripts, "workflow must emit named errors, not no-op"
    assert "exit 1" in scripts
    # the token preflight must consult the actual permission state
    assert "repos/${GITHUB_REPOSITORY}" in scripts
    assert ".permissions.push" in scripts


def test_release_workflow_never_bumps_version_or_creates_tags() -> None:
    doc = _yaml_load(WORKFLOW)
    scripts = "\n".join(s.get("run", "") for s in doc["jobs"]["release"]["steps"])
    # never creates or moves a tag, never pushes, never edits pyproject.toml
    assert "git tag" not in scripts
    assert "git push" not in scripts
    assert "sed -i" not in scripts
    assert not re.search(r">\s*pyproject\.toml", scripts), scripts


# --------------------------------------------------------------------------
# release-cut-check.sh
# --------------------------------------------------------------------------


def test_check_script_exists_and_is_executable() -> None:
    assert CHECK_SCRIPT.is_file()
    import os

    assert os.access(CHECK_SCRIPT, os.X_OK), "script must carry the exec bit"


def test_check_script_requires_a_tag_argument() -> None:
    proc = _run_script(PROJECT_ROOT)
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_check_script_rejects_malformed_tag() -> None:
    proc = _run_script(PROJECT_ROOT, "not-a-tag")
    assert proc.returncode == 2
    assert "not vX.Y.Z" in proc.stderr


def test_check_script_green_path_on_prepared_scratch_clone(tmp_path) -> None:
    """GREEN path: new tag, clean tree, matching version, green CI -> exit 0.

    Runs against a scratch ``git clone --shared`` whose pyproject version is
    bumped exactly the way the future version-prep commit will, with CI
    results fed through the documented TJ_RELEASE_CI_JSON seam (a fresh
    clone has no CI runs of its own, and the suite must not depend on gh).
    The repo tree is never touched: the clone commits to its own git dir.
    """
    import tomllib

    with open(PROJECT_ROOT / "pyproject.toml", "rb") as fh:
        version = tomllib.load(fh)["project"]["version"]
    major, minor, _ = (int(p) for p in version.split("."))
    tag = f"v{major}.{minor + 1}.0"

    clone = tmp_path / "scratch"
    subprocess.run(
        ["git", "clone", "--shared", "--quiet", str(PROJECT_ROOT), str(clone)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    # the script under test is always the LIVE working-tree copy, so this
    # test is independent of what the clone's base commit captured; on a
    # base commit that predates the script this stages it as a new file
    shutil.copy2(CHECK_SCRIPT, clone / "scripts" / "release-cut-check.sh")
    subprocess.run(
        ["git", "add", "scripts/release-cut-check.sh"],
        cwd=clone,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )

    pp = clone / "pyproject.toml"
    new_text, n = re.subn(
        r'(?m)^version = ".*"$', f'version = "{tag[1:]}"', pp.read_text(), count=1
    )
    assert n == 1, "expected exactly one top-level version line in pyproject.toml"
    pp.write_text(new_text)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=tj-release-test@example.invalid",
            "-c",
            "user.name=tj-release-test",
            "commit",
            "-q",
            "-am",
            f"version-prep for {tag} (scratch clone only)",
        ],
        cwd=clone,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )

    proc = _run_script(
        clone,
        tag,
        env_extra={
            "TJ_RELEASE_CI_JSON": '[{"status": "completed", "conclusion": "success"}]'
        },
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert f"OK: tag '{tag}' does not exist yet" in proc.stdout
    assert "OK: working tree clean" in proc.stdout
    assert f"OK: pyproject.toml version {tag[1:]} == tag {tag}" in proc.stdout
    assert "OK: CI green on HEAD" in proc.stdout
    assert "READY:" in proc.stdout


def test_check_script_fails_clearly_on_existing_tag() -> None:
    """FAILURE path: an already-existing tag must fail with the reason named.

    CI checkouts do NOT fetch tags (actions/checkout@v4 default) and have no
    network-visible guarantee about historical tags, so the test creates its
    own local tag, asserts the refusal, and removes it. The tag-existence
    check runs BEFORE any network access in the script, so this is hermetic.
    """
    tmp_tag = "v9.9.9-test-existing-refusal"
    make = subprocess.run(
        ["git", "tag", tmp_tag],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert make.returncode == 0, f"failed to create temp tag: {make.stderr}"
    try:
        proc = _run_script(PROJECT_ROOT, tmp_tag)
        assert proc.returncode == 1
        assert "already exists" in proc.stderr
    finally:
        subprocess.run(
            ["git", "tag", "-d", tmp_tag],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            timeout=30,
        )


def test_check_script_fails_clearly_on_wrong_version_tag() -> None:
    """FAILURE path: a well-formed tag that mismatches pyproject's version.

    v9.9.9 does not exist and never matches the live version, so the
    version leg is deterministic; the output must name the mismatch.
    """
    proc = _run_script(PROJECT_ROOT, "v9.9.9")
    assert proc.returncode == 1
    assert "version is" in proc.stderr
    assert "v9.9.9" in proc.stderr


def test_check_script_fails_clearly_on_red_ci_via_seam() -> None:
    """FAILURE path: a completed-but-failed run must be named.

    Also proves the seam actually feeds the parser (mutation control for the
    green-path test, which uses the same seam with conclusion=success).
    """
    proc = _run_script(
        PROJECT_ROOT,
        "v9.9.9",
        env_extra={
            "TJ_RELEASE_CI_JSON": '[{"status": "completed", "conclusion": "failure"}]'
        },
    )
    assert proc.returncode == 1
    assert "CI is red" in proc.stderr


def test_check_script_fails_closed_on_malformed_ci_data() -> None:
    """FAILURE path: unparseable CI data must refuse to guess, never pass."""
    proc = _run_script(
        PROJECT_ROOT,
        "v9.9.9",
        env_extra={"TJ_RELEASE_CI_JSON": "not-json-at-all"},
    )
    assert proc.returncode == 1
    assert "could not parse CI run data" in proc.stderr
