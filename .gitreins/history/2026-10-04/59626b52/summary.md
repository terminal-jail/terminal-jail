# Verdict: DOC-8

**Task:** Per-host capability matrix doc + probes
**Evaluated:** 2026-10-04T04:43:37.297844
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ docs/capability-matrix.md exists with full layer-by-backend matrix (enforced/degraded/unavailable + reasons); probe commands pidns-capability-probe.py and fs-isolation-probe.py named with real output; README cross-links the matrix; pin test tests/test_capability_matrix_doc.py passes and plugin suite green: docs/capability-matrix.md exists (118 lines): §2 matrix has all 6 layer rows (PID namespace, Identity/env scrub, Private `/proc`, Filesystem isolation, seccomp, egress) × 4 backend columns (bwrap, unshare (bare), unshare --user, composed), every cell marked **enforced**/**degraded**/**unavailable** with a stated reason, and unmeasured cells explicitly say 'unknown (not measured on this host)'. §1 names both probes with real invocation (`python3 scripts/pidns-capability-probe.py`, `python3 scripts/fs-isolation-probe.py`) and quotes verbatim real output; I re-ran both live: pidns -> 'FULL' (exit 0), fs -> 'DEGRADED: mapped launch failed (rc=1, stderr=...setgroups failed: Operation not permitted)...' (exit 0), matching the doc exactly. README cross-links: README.md:272 links docs/capability-matrix.md inside section '### What containment do I get on MY host?' (README.md:269) and names both probes at README.md:257-258. Pin test: `.venv/bin/python -m pytest tests/test_capability_matrix_doc.py -q` -> '10 passed in 0.01s' (exit 0). Plugin suite: `.venv/bin/python -m pytest plugin -q` -> '1547 passed, 7 skipped in 128.89s' (exit 0). [resolution 0.35; docs/capability-matrix.md, pidns-capability-probe.py, fs-isolation-probe.py, tests/test_capability_matrix_doc.py]
docs/capability-matrix.md fully covers all layers × backends with enforced/degraded/unavailable states and reasons, names both probes with verbatim real output reproduced live, is cross-linked from README, and both the pin test (10 passed) and plugin suite (1547 passed, 7 skipped) are green.

## Summary

Judge Result: DOC-8

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ docs/capability-matrix.md exists with full layer-by-backend matrix (enforced/degraded/unavailable + reasons); probe commands pidns-capability-probe.py and fs-isolation-probe.py named with real output; README cross-links the matrix; pin test tests/test_capability_matrix_doc.py passes and plugin suite green: docs/capability-matrix.md exists (118 lines): §2 matrix has all 6 layer rows (PID namespace, Identity/env scrub, Private `/proc`, Filesystem isolation, seccomp, egress) × 4 backend columns (bwrap, unshare (bare), unshare --user, composed), every cell marked **enforced**/**degraded**/**unavailable** with a stated reason, and unmeasured cells explicitly say 'unknown (not measured on this host)'. §1 names both probes with real invocation (`python3 scripts/pidns-capability-probe.py`, `python3 scripts/fs-isolation-probe.py`) and quotes verbatim real output; I re-ran both live: pidns -> 'FULL' (exit 0), fs -> 'DEGRADED: mapped launch failed (rc=1, stderr=...setgroups failed: Operation not permitted)...' (exit 0), matching the doc exactly. README cross-links: README.md:272 links docs/capability-matrix.md inside section '### What containment do I get on MY host?' (README.md:269) and names both probes at README.md:257-258. Pin test: `.venv/bin/python -m pytest tests/test_capability_matrix_doc.py -q` -> '10 passed in 0.01s' (exit 0). Plugin suite: `.venv/bin/python -m pytest plugin -q` -> '1547 passed, 7 skipped in 128.89s' (exit 0). [resolution 0.35; docs/capability-matrix.md, pidns-capability-probe.py, fs-isolation-probe.py, tests/test_capability_matrix_doc.py]
docs/capability-matrix.md fully covers all layers × backends with enforced/degraded/unavailable states and reasons, names both probes with verbatim real output reproduced live, is cross-linked from README, and both the pin test (10 passed) and plugin suite (1547 passed, 7 skipped) are green.

Overall: PASS ✓
