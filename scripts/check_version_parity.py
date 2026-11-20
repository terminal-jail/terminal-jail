#!/usr/bin/env python3
"""check_version_parity.py — release gate: no version surface may drift.

A version bump touches ``pyproject.toml`` and ``plugin/plugin.yaml``; every
other surface must DERIVE the value at runtime (``package_version()``) rather
than restate it. A hand-written ``x.y.z`` literal in a banner, an exporter or
the derivation module itself survives a bump silently and starts lying — that
is the TJ-REVIEW-072 defect this gate exists to prevent.

Checks (each one is named in the output):

* ``pyproject.toml`` is the source of truth for the version.
* ``plugin/plugin.yaml`` ``version:`` equals it (a manifest field must be a
  literal, so it is validated by equality instead of by derivation).
* ``plugin/__init__.py``, ``plugin/terminal_jail/__init__.py``,
  ``plugin/terminal_jail/plugin.py`` and ``scripts/metrics-export.py`` contain
  NO hand-written version literal — every quoted ``x.y.z`` token is an
  offender, reported as ``file:line``.
* Both plugin load banners interpolate ``package_version()``; the metrics
  exporter assigns ``d["version"] = package_version()``.
* Runtime agreement: ``scripts/metrics-export.py --json`` reports the
  pyproject version, and ``standalone/terminal-jail --version`` prints it.

Stdlib only, so it runs in CI (and on a bare host) without extras.

Usage:
    python3 scripts/check_version_parity.py            # check this checkout
    python3 scripts/check_version_parity.py --root DIR # check another tree

Exit 0 = every surface agrees/derives; exit 1 = named offenders; exit 2 =
usage error (unreadable pyproject / bad arguments).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import token
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# A version token, not part of a longer dotted run (so "0.0.0.0" is not a hit),
# optionally carrying the conventional "v" prefix ("v1.3.4" is the shape a
# banner restatement takes: the first draft of this guard missed it because the
# leading "v" is a word character).
VERSION_TOKEN = re.compile(r"(?<![\w.])v?\d+\.\d+\.\d+(?![\w.])")

# Surfaces that must DERIVE the version, never restate it.
DERIVED_SURFACES = (
    "plugin/__init__.py",
    "plugin/terminal_jail/__init__.py",
    "plugin/terminal_jail/plugin.py",
    "scripts/metrics-export.py",
)

# Surfaces carrying a "loaded" banner that must interpolate package_version().
BANNER_SURFACES = (
    "plugin/__init__.py",
    "plugin/terminal_jail/__init__.py",
)

MANIFEST = "plugin/plugin.yaml"
METRICS_SCRIPT = "scripts/metrics-export.py"
STANDALONE_CLI = "standalone/terminal-jail"


def project_version(root: Path) -> str:
    """Read the version from pyproject.toml (the single source of truth)."""
    pyproject = root / "pyproject.toml"
    try:
        import tomllib
    except ImportError as exc:  # pragma: no cover - py311+ is the floor
        raise SystemExit(f"FAIL: {exc}: python 3.11+ is required")
    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise SystemExit(f"FAIL: cannot read {pyproject}: {exc}")
    try:
        return str(data["project"]["version"])
    except KeyError:
        raise SystemExit(f"FAIL: {pyproject} declares no [project] version")


def string_literals(path: Path) -> list[tuple[int, str]]:
    """Return every string-literal token in a Python file as (line, text).

    ``tokenize`` is used instead of a quote-matching regex so apostrophes in
    comments and nested quoting cannot produce phantom matches. F-string parts
    are included on both tokenizers: 3.11 emits one STRING token, while 3.12+
    emits FSTRING_START / FSTRING_MIDDLE / FSTRING_END. The f-string constants
    live in ``token`` (not re-exported by ``tokenize``), so they are looked up
    there — an anonymous numeric fallback would silently stop scanning the
    banner that this gate exists to protect.
    """
    kinds = {tokenize.STRING}
    for name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
        constant = getattr(token, name, None)
        if isinstance(constant, int):
            kinds.add(constant)
    literals: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"FAIL: cannot read {path}: {exc}")
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in kinds:
                literals.append((tok.start[0], tok.string))
    except tokenize.TokenError as exc:
        raise SystemExit(f"FAIL: cannot tokenize {path}: {exc}")
    return literals


def version_literals(path: Path) -> list[tuple[int, str]]:
    """Return (line, literal) for every string literal holding an x.y.z token."""
    offenders: list[tuple[int, str]] = []
    for lineno, literal in string_literals(path):
        for match in VERSION_TOKEN.finditer(literal):
            offenders.append((lineno, match.group(0)))
    return offenders


def manifest_version(path: Path) -> str | None:
    """Extract the ``version:`` value from plugin.yaml (flat manifest)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"FAIL: cannot read {path}: {exc}")
    match = re.search(r"^version:\s*[\"']?([^\"'\s]+)", text, re.MULTILINE)
    return match.group(1) if match else None


def banner_interpolates_package_version(path: Path) -> bool:
    """True when the 'loaded' banner interpolates package_version()."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"FAIL: cannot read {path}: {exc}")
    for line in text.splitlines():
        if "terminal-jail v" not in line or "loaded" not in line:
            continue
        for expression in re.findall(r"\{([^{}]*)\}", line):
            if "package_version" in expression:
                return True
    return False


def check_static(root: Path, expected: str, problems: list[str]) -> list[str]:
    """Run the file-level checks; return the surface report lines."""
    report: list[str] = []

    manifest = root / MANIFEST
    actual = manifest_version(manifest)
    if actual is None:
        problems.append(f"{MANIFEST}: no 'version:' field declared")
        report.append(f"{MANIFEST:<33} MISSING                  literal, must equal")
    elif actual != expected:
        problems.append(f"{MANIFEST}:1: version '{actual}' != pyproject '{expected}'")
        report.append(f"{MANIFEST:<33} {actual:<24} MISMATCH literal")
    else:
        report.append(f"{MANIFEST:<33} {actual:<24} literal, must equal pyproject")

    for surface in DERIVED_SURFACES:
        path = root / surface
        offenders = version_literals(path)
        for lineno, literal in offenders:
            problems.append(
                f"{surface}:{lineno}: hand-written version literal "
                f"'{literal}' — derive it via package_version()"
            )
        if offenders:
            report.append(f"{surface:<33} {'LITERAL':<24} hand-written version")
        else:
            report.append(f"{surface:<33} {'derived':<24} no literals")

    for surface in BANNER_SURFACES:
        if not banner_interpolates_package_version(root / surface):
            problems.append(
                f"{surface}: no load banner interpolating package_version()"
            )

    metrics_path = root / METRICS_SCRIPT
    try:
        metrics_text = metrics_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"FAIL: cannot read {metrics_path}: {exc}")
    if not re.search(r'd\["version"\]\s*=\s*package_version\(\)', metrics_text):
        problems.append(
            f'{METRICS_SCRIPT}: no d["version"] = package_version() in the '
            "exported payload"
        )
    return report


def _clean_env() -> dict[str, str]:
    """Environment with any operator version override removed."""
    return {k: v for k, v in os.environ.items() if k != "TERMINAL_JAIL_VERSION"}


def _summarize(output: str, limit: int = 300) -> str:
    text = " ".join(output.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def check_metrics_runtime(root: Path, expected: str, problems: list[str]) -> str:
    """Run the exporter and compare its reported version."""
    script = root / METRICS_SCRIPT
    if not script.is_file():
        problems.append(f"{METRICS_SCRIPT}: missing — cannot check its --json version")
        return "ABSENT"
    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(root),
        env=_clean_env(),
        timeout=120,
    )
    if result.returncode != 0:
        problems.append(
            f"{METRICS_SCRIPT} --json: exit {result.returncode}: "
            f"{_summarize(result.stderr or result.stdout)}"
        )
        return f"ERROR({result.returncode})"
    try:
        reported = str(json.loads(result.stdout)["version"])
    except (ValueError, KeyError, TypeError) as exc:
        problems.append(f"{METRICS_SCRIPT} --json: unusable payload ({exc})")
        return "UNPARSED"
    if reported != expected:
        problems.append(
            f"{METRICS_SCRIPT} --json: reports '{reported}' != pyproject "
            f"'{expected}' (if the editable install predates the bump, re-run "
            "`uv pip install -e .`)"
        )
        return f"{reported} MISMATCH"
    return reported


def check_cli_runtime(root: Path, expected: str, problems: list[str]) -> str:
    """Run `standalone/terminal-jail --version` and compare it."""
    cli = root / STANDALONE_CLI
    if not cli.is_file():
        problems.append(f"{STANDALONE_CLI}: missing — cannot check its --version")
        return "ABSENT"
    try:
        result = subprocess.run(
            [str(cli), "--version"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(root),
            env=_clean_env(),
            timeout=60,
        )
    except OSError as exc:
        problems.append(f"{STANDALONE_CLI} --version: {exc}")
        return "ERROR"
    if result.returncode != 0:
        problems.append(
            f"{STANDALONE_CLI} --version: exit {result.returncode}: "
            f"{_summarize(result.stderr or result.stdout)}"
        )
        return f"ERROR({result.returncode})"
    reported = result.stdout.strip()
    if reported != f"terminal-jail {expected}":
        problems.append(
            f"{STANDALONE_CLI} --version: prints '{reported}' != "
            f"'terminal-jail {expected}'"
        )
        return f"{reported!r} MISMATCH"
    return expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail when a terminal-jail version surface drifts.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help="tree to check (default: this checkout's root)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    expected = project_version(root)
    problems: list[str] = []

    print("== version-parity check ==")
    print(f"{'pyproject.toml':<33} {expected:<24} source of truth")

    report = check_static(root, expected, problems)
    for line in report:
        print(line)

    metrics = check_metrics_runtime(root, expected, problems)
    print(f"{METRICS_SCRIPT + ' --json':<33} {metrics:<24} runtime")
    cli = check_cli_runtime(root, expected, problems)
    print(f"{STANDALONE_CLI + ' --version':<33} {cli:<24} runtime")

    if problems:
        sys.stdout.flush()
        print(f"\nRESULT: FAIL — {len(problems)} problem(s)", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"\nRESULT: PASS — 5 surfaces agree with pyproject.toml {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
