# Verdict: TJ-GAP-081

**Task:** CI drift-guards job: rule-catalog --check + drift probes wired into ci.yml
**Evaluated:** 2026-09-24T21:39:58.807659
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ ci.yml runs rule-catalog.py --check plus rules-drift-probe.py and yaml-mirror-parity-probe.py on the pinned venv; RED-proof shows --check exit 1 on a mutated rules file and the mutation reverted; all probes exit 0 at HEAD: .github/workflows/ci.yml:76-101 adds a `drift-guards` job (YAML parses; jobs=['test','lint','audit','drift-guards']) with steps `python scripts/rule-catalog.py --check`, `python scripts/yaml-mirror-parity-probe.py`, `python scripts/rules-drift-probe.py --fail-on-drift` (plus backend-parity-battery.py --json), on actions/setup-python@v5 python-version "3.13" + `pip install pyyaml` — the same pinned-interpreter setup style as the existing lint/audit jobs (the repo .venv is gitignored and cannot exist in CI; 3.13 satisfies the repo's 3.11+ tomllib requirement). HEAD green, evaluator-run with .venv/bin/python 3.11.15 / PyYAML 6.0.3 AND with bare `python3` exactly as ci.yml invokes: rule-catalog --check EXIT=0 '[catalog] OK — 55 rules (36 block / 9 sandbox / 10 allow); docs/rule-catalog.md up to date'; yaml-mirror-parity-probe EXIT=0 'ALL PROBES PASS'; rules-drift-probe --fail-on-drift EXIT=0 'RESULT: drift=0'; backend-parity-battery --json EXIT=0. RED-proof independently reproduced: appending a dummy block rule to plugin/terminal_jail/rules/00-builtins.yaml made rule-catalog --check EXIT=1 '[catalog] DRIFT — 56 rules (37 block / 9 sandbox / 10 allow); committed docs/rule-catalog.md is stale' and yaml-mirror-parity-probe EXIT=1 '[totals] block=37/36 ... total=56/55 -> MISMATCH / PROBE FAILURES'; `git checkout --` restored the file byte-identical (md5 65d7516cc95e74d05175d1188223a91b matches pre-mutation backup, git status clean) and --check returned to EXIT=0. [resolution 0.15; ci.yml, rule-catalog.py, rules-drift-probe.py, yaml-mirror-parity-probe.py]
The drift-guards CI job wires all three required probes on a pinned Python 3.13 interpreter, all probes exit 0 at HEAD, and the RED-proof (--check exit 1 on a mutated rules file, then byte-identical revert) reproduces exactly.

## Summary

Judge Result: TJ-GAP-081

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ ci.yml runs rule-catalog.py --check plus rules-drift-probe.py and yaml-mirror-parity-probe.py on the pinned venv; RED-proof shows --check exit 1 on a mutated rules file and the mutation reverted; all probes exit 0 at HEAD: .github/workflows/ci.yml:76-101 adds a `drift-guards` job (YAML parses; jobs=['test','lint','audit','drift-guards']) with steps `python scripts/rule-catalog.py --check`, `python scripts/yaml-mirror-parity-probe.py`, `python scripts/rules-drift-probe.py --fail-on-drift` (plus backend-parity-battery.py --json), on actions/setup-python@v5 python-version "3.13" + `pip install pyyaml` — the same pinned-interpreter setup style as the existing lint/audit jobs (the repo .venv is gitignored and cannot exist in CI; 3.13 satisfies the repo's 3.11+ tomllib requirement). HEAD green, evaluator-run with .venv/bin/python 3.11.15 / PyYAML 6.0.3 AND with bare `python3` exactly as ci.yml invokes: rule-catalog --check EXIT=0 '[catalog] OK — 55 rules (36 block / 9 sandbox / 10 allow); docs/rule-catalog.md up to date'; yaml-mirror-parity-probe EXIT=0 'ALL PROBES PASS'; rules-drift-probe --fail-on-drift EXIT=0 'RESULT: drift=0'; backend-parity-battery --json EXIT=0. RED-proof independently reproduced: appending a dummy block rule to plugin/terminal_jail/rules/00-builtins.yaml made rule-catalog --check EXIT=1 '[catalog] DRIFT — 56 rules (37 block / 9 sandbox / 10 allow); committed docs/rule-catalog.md is stale' and yaml-mirror-parity-probe EXIT=1 '[totals] block=37/36 ... total=56/55 -> MISMATCH / PROBE FAILURES'; `git checkout --` restored the file byte-identical (md5 65d7516cc95e74d05175d1188223a91b matches pre-mutation backup, git status clean) and --check returned to EXIT=0. [resolution 0.15; ci.yml, rule-catalog.py, rules-drift-probe.py, yaml-mirror-parity-probe.py]
The drift-guards CI job wires all three required probes on a pinned Python 3.13 interpreter, all probes exit 0 at HEAD, and the RED-proof (--check exit 1 on a mutated rules file, then byte-identical revert) reproduces exactly.

Overall: PASS ✓
