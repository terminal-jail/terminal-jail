# Verdict: DF-TERMINAL-JAIL-32

**Task:** Record 2026-09-19 fresh-machine install re-verification as the DF-21/DF-26 regression evidence
**Evaluated:** 2026-09-21T11:44:18.780240
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ docs/dogfood/2026-09-19-evening-integration.md exists and names agent fb251522 on bunker-las-03 (Debian 13, PyYAML-less, PEP 668) at HEAD d80c0bf: docs/dogfood/2026-09-19-evening-integration.md exists (57 lines). Line 3: 'Target: terminal-jail @ d80c0bf.' Lines 24-26: 'Fresh-machine install leg on bunker-las-03 agent fb251522 (Debian 13, PyYAML-less, pip present under PEP 668): documented https clone OK (HEAD d80c0bf)'. All required elements present.
  ✓ That doc records: documented https clone OK, ./install.sh rc=0, ./install.sh --rule-pack db correctly SKIPPED with the remediation message and 'base install completed', rc=0, 00-builtins.yaml intact (DF-TERMINAL-JAIL-21 fix live on a fresh machine): Doc lines 24-28: 'documented https clone OK (HEAD d80c0bf), ./install.sh rc=0, --rule-pack db correctly skipped with remediation message (DF-21 fix live), smoke PASS'. Board row .coding-hermes/board/tasks.jsonl:163 detail spells out the full chain: 'git clone of the documented https origin URL succeeded (HEAD d80c0bf, ~4s); ./install.sh rc=0 in 0s; ./install.sh --rule-pack db on PyYAML-less pip-present PEP-668 host correctly SKIPPED the pack with the exact remediation message and 'base install completed' summary, rc=0, 00-builtins.yaml intact (DF-21 fix live).'
  ✓ The doc records the DF-15 auto-sandbox warning intact, --version ok, pidns probe FULL, --user ns inode differs from host, fdisk block rc=126, and bridge allow with rule_id provenance: Doc lines 24-28: 'smoke PASS (FULL probe, containment inode, block rc=126, bridge provenance)'; doc lines 36-40 'Re-verified live, still fixed ... DF-15 (loud mapped-launch fallback warning), default-allow provenance (rule_id null vs named)'. Board row tasks.jsonl:163 detail enumerates each: '--version ok, pidns probe FULL, --user ns inode differs from host, fdisk block rc=126, bridge allow with rule_id provenance, DF-15 auto-sandbox warning intact.'
  ✓ The doc and the closed board row DF-TERMINAL-JAIL-32 record the leaked-user growth 17 -> 33 on las-03 as active DF-TERMINAL-JAIL-26 evidence; the row is complete with reasoning citing the evening dogfood doc: Doc lines 33-34: 'DF-TERMINAL-JAIL-32 [P2] fresh-install regression evidence (PASS) + las-03 leaked-user count now 33 (DF-26 leak growing).' Board row .coding-hermes/board/tasks.jsonl:163: status='complete', detail 'las-03 now holds 33 leaked bunker-* users (17 at last count) — DF-TERMINAL-JAIL-26 leak is growing', reasoning 'docs/dogfood/2026-09-19-evening-integration.md is the durable record', foreman_note 'Closed from docs/dogfood/2026-09-19-evening-integration.md (findings section names DF-TERMINAL-JAIL-32)'. Row is complete with reasoning citing the doc.
  ✓ Full plugin suite green on the merged tree (pytest plugin -q) and uvx ruff check . clean: Ran fresh: `.venv/bin/python -m pytest plugin -q -p no:cacheprovider` -> '1357 passed, 7 skipped in 44.43s' (exit 0). `uvx ruff check .` -> 'All checks passed!' with RUFF_EXIT=0. Matches the board row's recorded '1357 passed / 7 skipped; uvx ruff clean'.
All five criteria verified: the evening dogfood doc and the closed DF-TERMINAL-JAIL-32 board row record the fresh-machine install re-verification (agent fb251522 on bunker-las-03 at d80c0bf), the DF-21 pack-skip fix, the DF-15/probe/rc=126/provenance smoke results, and the 17->33 leaked-user DF-26 evidence, with the plugin suite (1357 passed, 7 skipped) and ruff both green.

## Summary

Judge Result: DF-TERMINAL-JAIL-32

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ docs/dogfood/2026-09-19-evening-integration.md exists and names agent fb251522 on bunker-las-03 (Debian 13, PyYAML-less, PEP 668) at HEAD d80c0bf: docs/dogfood/2026-09-19-evening-integration.md exists (57 lines). Line 3: 'Target: terminal-jail @ d80c0bf.' Lines 24-26: 'Fresh-machine install leg on bunker-las-03 agent fb251522 (Debian 13, PyYAML-less, pip present under PEP 668): documented https clone OK (HEAD d80c0bf)'. All required elements present.
  ✓ That doc records: documented https clone OK, ./install.sh rc=0, ./install.sh --rule-pack db correctly SKIPPED with the remediation message and 'base install completed', rc=0, 00-builtins.yaml intact (DF-TERMINAL-JAIL-21 fix live on a fresh machine): Doc lines 24-28: 'documented https clone OK (HEAD d80c0bf), ./install.sh rc=0, --rule-pack db correctly skipped with remediation message (DF-21 fix live), smoke PASS'. Board row .coding-hermes/board/tasks.jsonl:163 detail spells out the full chain: 'git clone of the documented https origin URL succeeded (HEAD d80c0bf, ~4s); ./install.sh rc=0 in 0s; ./install.sh --rule-pack db on PyYAML-less pip-present PEP-668 host correctly SKIPPED the pack with the exact remediation message and 'base install completed' summary, rc=0, 00-builtins.yaml intact (DF-21 fix live).'
  ✓ The doc records the DF-15 auto-sandbox warning intact, --version ok, pidns probe FULL, --user ns inode differs from host, fdisk block rc=126, and bridge allow with rule_id provenance: Doc lines 24-28: 'smoke PASS (FULL probe, containment inode, block rc=126, bridge provenance)'; doc lines 36-40 'Re-verified live, still fixed ... DF-15 (loud mapped-launch fallback warning), default-allow provenance (rule_id null vs named)'. Board row tasks.jsonl:163 detail enumerates each: '--version ok, pidns probe FULL, --user ns inode differs from host, fdisk block rc=126, bridge allow with rule_id provenance, DF-15 auto-sandbox warning intact.'
  ✓ The doc and the closed board row DF-TERMINAL-JAIL-32 record the leaked-user growth 17 -> 33 on las-03 as active DF-TERMINAL-JAIL-26 evidence; the row is complete with reasoning citing the evening dogfood doc: Doc lines 33-34: 'DF-TERMINAL-JAIL-32 [P2] fresh-install regression evidence (PASS) + las-03 leaked-user count now 33 (DF-26 leak growing).' Board row .coding-hermes/board/tasks.jsonl:163: status='complete', detail 'las-03 now holds 33 leaked bunker-* users (17 at last count) — DF-TERMINAL-JAIL-26 leak is growing', reasoning 'docs/dogfood/2026-09-19-evening-integration.md is the durable record', foreman_note 'Closed from docs/dogfood/2026-09-19-evening-integration.md (findings section names DF-TERMINAL-JAIL-32)'. Row is complete with reasoning citing the doc.
  ✓ Full plugin suite green on the merged tree (pytest plugin -q) and uvx ruff check . clean: Ran fresh: `.venv/bin/python -m pytest plugin -q -p no:cacheprovider` -> '1357 passed, 7 skipped in 44.43s' (exit 0). `uvx ruff check .` -> 'All checks passed!' with RUFF_EXIT=0. Matches the board row's recorded '1357 passed / 7 skipped; uvx ruff clean'.
All five criteria verified: the evening dogfood doc and the closed DF-TERMINAL-JAIL-32 board row record the fresh-machine install re-verification (agent fb251522 on bunker-las-03 at d80c0bf), the DF-21 pack-skip fix, the DF-15/probe/rc=126/provenance smoke results, and the 17->33 leaked-user DF-26 evidence, with the plugin suite (1357 passed, 7 skipped) and ruff both green.

Overall: PASS ✓
