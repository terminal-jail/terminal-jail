# Agent Rules

These rules are given to agentic coding agents operating in this repo.

---

## Repository Shape
- Hermes plugin: `plugin/__init__.py` — observability hooks (metrics, logging); does NOT wrap commands — PID namespace isolation comes from the standalone CLI and systemd layer
- Standalone CLI: `standalone/terminal-jail` — universal bash wrapper
- systemd snippets: `systemd/` — gateway hardening examples
- Product specs: `specs/`
- Long-term memory: `.memory-bank/`
- Task board: `.coding-hermes/board/tasks.jsonl`

## Process
- Make the smallest meaningful change. Validate after every step.
- Document what changed and why.

## Secrets and Privacy
- Never write secrets to `specs/`, `.memory-bank/`, git history, or logs.

## Git and Workspace Hygiene
- All commits MUST include `Co-authored-by: Alexis Okuwa <wojonstech@gmail.com>`.
- Always `git pull --rebase` before committing. Stash first if dirty.
- Use `git mv` for all file and folder moves.
- Never revert unrelated changes unless explicitly requested.
- Never run destructive git commands unless explicitly requested.

## GitReins Quality Harness
```bash
gitreins guard
```
- `gitreins` resolves through the pipx shim (`~/.local/bin/gitreins`). Do NOT put
  `$HOME/gitreins-poc/.venv/bin` on PATH for this: that venv is Python 3.10, and its
  `pytest` shadows the repo interpreter — the tests lane then dies at collection on
  `import tomllib` (3.11+) and falsely FAILs on a clean tree (observed 2026-09-19,
  guard log guard-20260919T005837).
- The tests lane is interpreter-pinned in `.gitreins/config.yaml`
  (`test_command: .venv/bin/python -m pytest -x --tb=short`), so it is independent
  of PATH ordering.
- secrets guard BLOCKS on fail — no exceptions.
- lint and tests BLOCKS on fail.
- Never commit with `--no-verify` for code changes.
