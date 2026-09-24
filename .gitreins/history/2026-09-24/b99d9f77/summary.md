# Verdict: TJ-DF-024

**Task:** Interruptor matcher regex backtracking on long args — length fastpath
**Evaluated:** 2026-09-24T20:21:27.229172
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ bridge verdict on an 8000-char-arg echo returns in under 200ms or an explicit over-length verdict; a 20KB-arg command returns within 1s instead of hanging; regression tests with 8KB and 200KB payloads exist and pass; repro and before/after numbers recorded in docs/dogfood/2026-09-24-firewall-library-integration.md; the full plugin suite stays green: All five sub-parts verified with fresh command output. (a) 8000-char echo through the real bridge subprocess (plugin/terminal_jail/interruptor_bridge.py): wall=0.091s, action=allow, rule_id=allow-echo — well under 200ms. (b) 20KB: wall=0.132s; 200KB: wall=0.661s — under 1s, no hang. (c) plugin/test_tjdf024_prefilter.py exists with 18 tests covering both payload classes (test_benign_8kb_under_half_second, test_benign_200kb_does_not_hang); `.venv/bin/python -m pytest test_tjdf024_prefilter.py -v` → '18 passed in 0.83s'. (d) docs/dogfood/2026-09-24-firewall-library-integration.md contains 'Finding 1 — long commands hang the engine (P1)' with a runnable repro snippet (lines 69-79) and before/after tables (lines 156-161 and 219-223). I independently reproduced the numbers: base commit 9d00d52 8KB intercept()=8.726s (docs claim 9.22s bridge / 10.5s intercept); after fix 8KB=0.022s (docs 0.024s), 20KB=0.053s (docs 0.053s), 200KB=0.513s (docs 0.495s), 8KB pad + 'rm -rf /'=0.006s block (docs 0.006s) — the documented table is accurate. (e) Full plugin suite: `.venv/bin/python -m pytest -x --tb=short -q` → '1436 passed, 7 skipped in 65.85s' — green. Soundness also confirmed: the rejected attempt-1 length fastpath is absent from the engine (grep finds 'over-length-fastpath' only in docs/tests; test_no_length_based_skip_exists and test_config_has_no_length_budget_knob pass), and 8KB-padded destructive commands (rm -rf /, fork bomb, socket reverse shell, urlopen exfil, kill -9 -1, curl|sh, sudo rm, chmod 777, dd, mkfs, nc, base64|sh, python exec, curl upload) all still return block. LSP diagnostics: 0 findings. [resolution 0.11; docs/dogfood/2026-09-24-firewall-library-integration.md]
The required-substring prefilter fix in matcher.py delivers sub-200ms 8KB and sub-1s 20KB/200KB bridge verdicts, ships 18 passing regression tests, documents accurate before/after numbers with a repro, and keeps the full plugin suite green (1436 passed / 7 skipped).

## Summary

Judge Result: TJ-DF-024

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ bridge verdict on an 8000-char-arg echo returns in under 200ms or an explicit over-length verdict; a 20KB-arg command returns within 1s instead of hanging; regression tests with 8KB and 200KB payloads exist and pass; repro and before/after numbers recorded in docs/dogfood/2026-09-24-firewall-library-integration.md; the full plugin suite stays green: All five sub-parts verified with fresh command output. (a) 8000-char echo through the real bridge subprocess (plugin/terminal_jail/interruptor_bridge.py): wall=0.091s, action=allow, rule_id=allow-echo — well under 200ms. (b) 20KB: wall=0.132s; 200KB: wall=0.661s — under 1s, no hang. (c) plugin/test_tjdf024_prefilter.py exists with 18 tests covering both payload classes (test_benign_8kb_under_half_second, test_benign_200kb_does_not_hang); `.venv/bin/python -m pytest test_tjdf024_prefilter.py -v` → '18 passed in 0.83s'. (d) docs/dogfood/2026-09-24-firewall-library-integration.md contains 'Finding 1 — long commands hang the engine (P1)' with a runnable repro snippet (lines 69-79) and before/after tables (lines 156-161 and 219-223). I independently reproduced the numbers: base commit 9d00d52 8KB intercept()=8.726s (docs claim 9.22s bridge / 10.5s intercept); after fix 8KB=0.022s (docs 0.024s), 20KB=0.053s (docs 0.053s), 200KB=0.513s (docs 0.495s), 8KB pad + 'rm -rf /'=0.006s block (docs 0.006s) — the documented table is accurate. (e) Full plugin suite: `.venv/bin/python -m pytest -x --tb=short -q` → '1436 passed, 7 skipped in 65.85s' — green. Soundness also confirmed: the rejected attempt-1 length fastpath is absent from the engine (grep finds 'over-length-fastpath' only in docs/tests; test_no_length_based_skip_exists and test_config_has_no_length_budget_knob pass), and 8KB-padded destructive commands (rm -rf /, fork bomb, socket reverse shell, urlopen exfil, kill -9 -1, curl|sh, sudo rm, chmod 777, dd, mkfs, nc, base64|sh, python exec, curl upload) all still return block. LSP diagnostics: 0 findings. [resolution 0.11; docs/dogfood/2026-09-24-firewall-library-integration.md]
The required-substring prefilter fix in matcher.py delivers sub-200ms 8KB and sub-1s 20KB/200KB bridge verdicts, ships 18 passing regression tests, documents accurate before/after numbers with a repro, and keeps the full plugin suite green (1436 passed / 7 skipped).

Overall: PASS ✓
