# Verdict: QA-TERMINAL-JAIL-15

**Task:** Fix rule-pack-file test timeout under load
**Evaluated:** 2026-10-01T09:34:19.989633
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_install.py::test_installed_binary_blocks_with_shipped_bridge [first failing id])
- ✗ **tier2**
  - INCOMPLETE
  ✗ plugin/test_install.py::test_rule_pack_file_install_then_uninstall_round_trip and ::test_rule_pack_file_never_shadows_an_installed_pack_name pass at loadavg 30+ without TimeoutExpired; _run_repo_install timeout raised to 90s or made configurable via env var; full suite green at loadavg 30+: PARTIAL: INSTALL_TIMEOUT_S = int(os.environ.get("TERMINAL_JAIL_TEST_TIMEOUT", "90")) at plugin/test_install.py:27 — 90s default AND env-configurable. Used at :1299 (_run_repo_install) and :1322 (_run_checkout_install). Both target tests exist at :1659 and :1760 and use _run_repo_install. Live run at loadavg 30-40 was still in progress when time cap hit; no TimeoutExpired observed in partial output but no final PASS/FAIL line captured.
Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: QA-TERMINAL-JAIL-15

Stage tier1: FAIL
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (plugin/test_install.py::test_installed_binary_blocks_with_shipped_bridge [first failing id])

Stage tier2: FAIL
  INCOMPLETE
  ✗ plugin/test_install.py::test_rule_pack_file_install_then_uninstall_round_trip and ::test_rule_pack_file_never_shadows_an_installed_pack_name pass at loadavg 30+ without TimeoutExpired; _run_repo_install timeout raised to 90s or made configurable via env var; full suite green at loadavg 30+: PARTIAL: INSTALL_TIMEOUT_S = int(os.environ.get("TERMINAL_JAIL_TEST_TIMEOUT", "90")) at plugin/test_install.py:27 — 90s default AND env-configurable. Used at :1299 (_run_repo_install) and :1322 (_run_checkout_install). Both target tests exist at :1659 and :1760 and use _run_repo_install. Live run at loadavg 30-40 was still in progress when time cap hit; no TimeoutExpired observed in partial output but no final PASS/FAIL line captured.
Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
