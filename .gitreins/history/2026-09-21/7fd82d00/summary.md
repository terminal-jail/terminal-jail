# Verdict: TJ-GAP-071

**Task:** install.sh --uninstall removal path + docs
**Evaluated:** 2026-09-21T13:31:27.872220
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ ./install.sh --uninstall on a scratch-HOME install leaves zero terminal-jail files under HOME and command -v terminal-jail finds nothing; round-trip install->uninstall->install works; user-authored rules.d files preserved and listed; only marker-matched rc PATH lines removed; systemd drop-in removed only behind explicit flag; idempotent no-op on never-installed HOME; docs Removal section in README + docs/quickstart.md; tests added; full suite green: All sub-requirements verified by live probes + test runs. (1) Zero files: default-scope install then `HOME=/tmp/tjprobe2/home sh install.sh --uninstall` -> `find /tmp/tjprobe2/home -name '*terminal-jail*' -type f` returns nothing (only empty .config/terminal-jail dirs remain, which the test at plugin/test_uninstall.py:70-82 documents as intentionally preserved); `command -v terminal-jail` with scratch bin on PATH -> rc=127. (2) Round-trip: install.sh:832 appends marker; uninstall removes it; reinstall re-appends exactly once (probe /tmp/tjrt2: 1 marker -> 0 -> 1) and wrapper runs `terminal-jail 1.1.0`. (3) User-authored preservation: install.sh:558-570 census prints 'left in place (user-authored): /tmp/tjrt/rules.d/my-own-rule.yaml' and file content intact. (4) Marker-only rc removal: install.sh:505-529 awk deletes only the '# terminal-jail' block; probe /tmp/tjprobe showed the user's own `export PATH="$HOME/.local/bin:$PATH"` line SURVIVED. (5) systemd: install.sh:534-556 removes drop-in only when UNINSTALL_SYSTEMD=1 (probe: drop-in still present after no-flag run; with flag it attempts removal and prints WARNING without root); `--uninstall-systemd` alone exits 2 (install.sh:324-327). (6) Idempotent no-op: never-installed HOME -> rc=0, 'nothing to uninstall'. (7) Docs: README.md:628 '## Removal / Uninstall'; docs/quickstart.md:339 '### 3g. Removal / Uninstall'. (8) Tests: plugin/test_uninstall.py (344 lines, 13 tests) -> `.venv/bin/python -m pytest plugin/test_uninstall.py -x --tb=short` = '13 passed in 1.46s'. (9) Full suite: `.venv/bin/python -m pytest -x --tb=short -p no:cacheprovider` = '1392 passed, 7 skipped in 73.30s (0:01:13)', exit 0. Also `sh -n install.sh` OK, ruff 'All checks passed!', LSP diagnostics empty.
install.sh --uninstall fully implements the removal mirror (zero files left, marker-scoped rc removal, user-rule preservation, opt-in systemd, idempotent no-op), docs added to README and quickstart, 13 new tests pass and the full suite is green (1392 passed, 7 skipped).

## Summary

Judge Result: TJ-GAP-071

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ ./install.sh --uninstall on a scratch-HOME install leaves zero terminal-jail files under HOME and command -v terminal-jail finds nothing; round-trip install->uninstall->install works; user-authored rules.d files preserved and listed; only marker-matched rc PATH lines removed; systemd drop-in removed only behind explicit flag; idempotent no-op on never-installed HOME; docs Removal section in README + docs/quickstart.md; tests added; full suite green: All sub-requirements verified by live probes + test runs. (1) Zero files: default-scope install then `HOME=/tmp/tjprobe2/home sh install.sh --uninstall` -> `find /tmp/tjprobe2/home -name '*terminal-jail*' -type f` returns nothing (only empty .config/terminal-jail dirs remain, which the test at plugin/test_uninstall.py:70-82 documents as intentionally preserved); `command -v terminal-jail` with scratch bin on PATH -> rc=127. (2) Round-trip: install.sh:832 appends marker; uninstall removes it; reinstall re-appends exactly once (probe /tmp/tjrt2: 1 marker -> 0 -> 1) and wrapper runs `terminal-jail 1.1.0`. (3) User-authored preservation: install.sh:558-570 census prints 'left in place (user-authored): /tmp/tjrt/rules.d/my-own-rule.yaml' and file content intact. (4) Marker-only rc removal: install.sh:505-529 awk deletes only the '# terminal-jail' block; probe /tmp/tjprobe showed the user's own `export PATH="$HOME/.local/bin:$PATH"` line SURVIVED. (5) systemd: install.sh:534-556 removes drop-in only when UNINSTALL_SYSTEMD=1 (probe: drop-in still present after no-flag run; with flag it attempts removal and prints WARNING without root); `--uninstall-systemd` alone exits 2 (install.sh:324-327). (6) Idempotent no-op: never-installed HOME -> rc=0, 'nothing to uninstall'. (7) Docs: README.md:628 '## Removal / Uninstall'; docs/quickstart.md:339 '### 3g. Removal / Uninstall'. (8) Tests: plugin/test_uninstall.py (344 lines, 13 tests) -> `.venv/bin/python -m pytest plugin/test_uninstall.py -x --tb=short` = '13 passed in 1.46s'. (9) Full suite: `.venv/bin/python -m pytest -x --tb=short -p no:cacheprovider` = '1392 passed, 7 skipped in 73.30s (0:01:13)', exit 0. Also `sh -n install.sh` OK, ruff 'All checks passed!', LSP diagnostics empty.
install.sh --uninstall fully implements the removal mirror (zero files left, marker-scoped rc removal, user-rule preservation, opt-in systemd, idempotent no-op), docs added to README and quickstart, 13 new tests pass and the full suite is green (1392 passed, 7 skipped).

Overall: PASS ✓
