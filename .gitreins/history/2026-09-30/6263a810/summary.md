# Verdict: DOC-7

**Task:** audit tooling doc pointer
**Evaluated:** 2026-09-30T13:37:24.546688
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✗ **tier2**
  - INCOMPLETE
  ✗ gtfobins-sweep.py and e2e-battery-live-probe.py are reachable from README in one hop: README.md:261-262 do name both scripts, but the pointer table is trapped inside an UNCLOSED bash code fence: the fence opens at README.md:251 (```bash) and closes at README.md:271, so the '### Audit tooling' heading (line 257) and the table (lines 259-262) sit inside the code block. CommonMark/GFM render (markdown-it-py, matching GitHub) confirms: the rendered <h3> list jumps from 'Verifying a deploy' straight to 'Scripting the firewall' with NO 'Audit tooling' heading, no rendered <table> contains 'gtfobins', and the whole section renders as literal text inside <pre><code class="language-bash">; 'audit-tooling anchor present: False'. The section is also absent from the README Contents TOC (README.md:24-31). Root cause: commit e3819ef inserted the section mid-code-block (diff hunk @@ -252,6 +252,14 @@ added lines after the fs-isolation-probe.py line, before the fence close). The scripts exist (scripts/gtfobins-sweep.py, scripts/e2e-battery-live-probe.py) but are not reachable as navigable pointers from the README. No test suite applies (docs-only change); verified via markdown render + fence analysis.
The DOC-7 fix inserted the 'Audit tooling' pointer table inside an unclosed bash code fence, so it renders as literal code text with no heading/anchor/table and the two scripts are not reachable from the README in one hop.

## Summary

Judge Result: DOC-7

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: FAIL
  INCOMPLETE
  ✗ gtfobins-sweep.py and e2e-battery-live-probe.py are reachable from README in one hop: README.md:261-262 do name both scripts, but the pointer table is trapped inside an UNCLOSED bash code fence: the fence opens at README.md:251 (```bash) and closes at README.md:271, so the '### Audit tooling' heading (line 257) and the table (lines 259-262) sit inside the code block. CommonMark/GFM render (markdown-it-py, matching GitHub) confirms: the rendered <h3> list jumps from 'Verifying a deploy' straight to 'Scripting the firewall' with NO 'Audit tooling' heading, no rendered <table> contains 'gtfobins', and the whole section renders as literal text inside <pre><code class="language-bash">; 'audit-tooling anchor present: False'. The section is also absent from the README Contents TOC (README.md:24-31). Root cause: commit e3819ef inserted the section mid-code-block (diff hunk @@ -252,6 +252,14 @@ added lines after the fs-isolation-probe.py line, before the fence close). The scripts exist (scripts/gtfobins-sweep.py, scripts/e2e-battery-live-probe.py) but are not reachable as navigable pointers from the README. No test suite applies (docs-only change); verified via markdown render + fence analysis.
The DOC-7 fix inserted the 'Audit tooling' pointer table inside an unclosed bash code fence, so it renders as literal code text with no heading/anchor/table and the two scripts are not reachable from the README in one hop.

Overall: FAIL ✗
