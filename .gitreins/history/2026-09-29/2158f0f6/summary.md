# Verdict: REVIEW-TJ-006

**Task:** FAQ 4 uid 65534 claim is backend-dependent
**Evaluated:** 2026-09-29T13:44:11.125567
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ docs/quickstart.md FAQ states under which backend --user id shows 65534 vs caller uid: docs/quickstart.md:676-682, FAQ §4 entry 'Does `--user` isolate the filesystem?': 'A mapping-less `--user` namespace is an identity display only: `id` shows 65534 — but **only under the `unshare` backend** (`TERMINAL_JAIL_JAIL_BACKEND=unshare`, or `auto` on hosts where bwrap is absent/unusable); under the `bubblewrap` backend `--user` keeps the caller's uid (`id` shows 1000, not 65534), since bwrap re-labels rather than maps.' This explicitly names both backends and their uid display. Corroborated by code: standalone/terminal-jail:508-523 (unshare --user without mapping shows 65534), BWRAP_FLAGS at line 620 contains no --map-users/-S/-G so bwrap keeps caller uid, and comment at line 641 ('its --uid only re-labels the sandbox uid'). Tests green: `.venv/bin/python -m pytest plugin/test_backend_selection.py` → 16 passed; `plugin/test_userns.py plugin/test_standalone_cli.py` → 49 passed, 1 skipped. [resolution 0.25; docs/quickstart.md]
The FAQ §4 entry in docs/quickstart.md explicitly documents that --user shows uid 65534 only under the unshare backend while the bubblewrap backend keeps the caller's uid (1000), matching the implementation.

## Summary

Judge Result: REVIEW-TJ-006

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ docs/quickstart.md FAQ states under which backend --user id shows 65534 vs caller uid: docs/quickstart.md:676-682, FAQ §4 entry 'Does `--user` isolate the filesystem?': 'A mapping-less `--user` namespace is an identity display only: `id` shows 65534 — but **only under the `unshare` backend** (`TERMINAL_JAIL_JAIL_BACKEND=unshare`, or `auto` on hosts where bwrap is absent/unusable); under the `bubblewrap` backend `--user` keeps the caller's uid (`id` shows 1000, not 65534), since bwrap re-labels rather than maps.' This explicitly names both backends and their uid display. Corroborated by code: standalone/terminal-jail:508-523 (unshare --user without mapping shows 65534), BWRAP_FLAGS at line 620 contains no --map-users/-S/-G so bwrap keeps caller uid, and comment at line 641 ('its --uid only re-labels the sandbox uid'). Tests green: `.venv/bin/python -m pytest plugin/test_backend_selection.py` → 16 passed; `plugin/test_userns.py plugin/test_standalone_cli.py` → 49 passed, 1 skipped. [resolution 0.25; docs/quickstart.md]
The FAQ §4 entry in docs/quickstart.md explicitly documents that --user shows uid 65534 only under the unshare backend while the bubblewrap backend keeps the caller's uid (1000), matching the implementation.

Overall: PASS ✓
