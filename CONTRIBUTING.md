# Contributing to Terminal Jail

Thanks for helping make Hermes agent commands safer.

## Development Setup

```bash
git clone https://github.com/terminal-jail/terminal-jail.git
cd terminal-jail
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Dependencies: Python 3.11+, `unshare` (util-linux 2.32+), `bash`.

## Running Tests

```bash
# All tests (unit + integration where unshare is available)
python3 -m pytest plugin/ -v

# Unit tests only (no kernel requirement)
python3 -m pytest plugin/ -v -m "not integration"

# Integration tests (requires unshare --mount-proc support)
python3 -m pytest plugin/ -v -m integration

# With coverage
python3 -m pytest plugin/ -v --cov=plugin/terminal_jail --cov-report=term-missing
```

Integration tests gate on `_unshare_works()` which probes `unshare --user --pid --fork --mount-proc` with the exact flags the plugin uses. On hosts where unprivileged user namespaces can't mount `/proc` (Ubuntu 26.04 with kernel 7.0+), integration tests skip automatically. This is a kernel policy limitation, not a test defect.

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting:

```bash
pip install ruff
ruff check plugin/
```

Rules enforced:
- Formatting via `ruff format`
- Import sorting (I001)
- Unused imports/variables (F401, F841)
- Line length: 100 characters

No other formatters (black, isort, flake8) — ruff covers everything.

## Project Structure

```
terminal-jail/
├── plugin/                    # Hermes plugin (Python)
│   ├── __init__.py           # Hook registration manifest
│   ├── terminal_jail/
│   │   ├── __init__.py
│   │   └── plugin.py         # Core plugin: hooks, metrics, transform
│   ├── test_plugin.py        # Unit tests (31 tests + 1 skipped)
│   ├── test_integration.py   # Real unshare integration tests (25 tests)
│   ├── test_install.py       # install.sh tests (11 tests)
│   ├── test_standalone_cli.py # CLI tests (15 tests)
│   └── test_metrics_export.py # Metrics export tests (21 tests)
├── standalone/terminal-jail   # Portable CLI wrapper (bash)
├── systemd/                   # systemd hardening drop-in files
├── scripts/                   # Utility scripts
├── specs/                     # Architecture specifications
├── docs/adr/                  # Architecture Decision Records
└── install.sh                 # POSIX-compatible installer
```

## Adding New Hardening Directives

When adding a new systemd hardening directive to `systemd/90-terminal-jail-hardening.conf`:

1. **Research the directive** — read the systemd.exec(5) man page. Understand what it blocks and what breaks.
2. **Test on a staging gateway** — never test new directives on production. Use a throwaway VM or container.
3. **Document the failure mode** — add a troubleshooting entry in the ROLLBACK PROCEDURE section of the drop-in file. Every directive must have a known failure mode and recovery path.
4. **Update the compatibility matrix** — if the directive requires a minimum kernel or systemd version, document it.
5. **Graduated cutover** — follow the project's principle of gradual production cutover. Deploy the new directive disabled first (`=false`), observe for 24h, then enable.

Directive template:
```ini
# DirectiveName=
# Purpose: one-line description
# Risk: what breaks if this is too aggressive
# Kernel minimum: x.y
# systemd minimum: vXXX
DirectiveName=true
```

## Pull Request Process

1. **Open an issue first** — describe what you're fixing or adding. Bug reports must include kernel version, distribution, and `unshare --version`.
2. **Branch from `main`** — `git checkout -b feat/my-feature` or `fix/my-bug`.
3. **Write tests** — no PR merges without tests. Unit tests for logic, integration tests for kernel behavior.
4. **Run the full suite** — `python3 -m pytest plugin/ -v`. All tests must pass.
5. **Lint** — `ruff check plugin/` must be clean.
6. **Update the board** — if your PR addresses an item in `.coding-hermes/board/tasks.jsonl`, mark it complete.
7. **Signed commits** — all commits must include `Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>`.

## Security Considerations

This project handles process isolation. Changes to any of these areas require extra scrutiny:

- **PID namespace creation** (`unshare` flags, `clone(2)` parameters)
- **Signal handling** (`--kill-child=SIGKILL`, cleanup on namespace exit)
- **systemd directives** (anything under `systemd/`)
- **Plugin observability** (pre_tool_call observer, output annotation, metrics export)
- **Plugin hook registration** (what Hermes hooks are subscribed to)

If your change touches any of these, tag the PR with `security` and request review from a maintainer.

For vulnerability disclosures, email the maintainer directly. Do not open a public issue.

## Architecture Decision Records

Significant technical decisions are documented in `docs/adr/`. Before making architectural changes:

1. Read existing ADRs to understand past decisions
2. If your change conflicts with an ADR, explain why in your PR
3. For new architectural decisions, add an ADR following the existing format

Current ADRs: `docs/adr/0001-architecture-decisions.md` (ADR-001 through ADR-005).

## Release Process

Releases are tagged by maintainers:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
4. `git push origin main --tags`
5. GitHub release is created from the tag

## License

MIT. By contributing, you agree that your contributions will be licensed under the MIT License.
