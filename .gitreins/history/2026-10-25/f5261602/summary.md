# Verdict: DOC-20

**Task:** Document benchmark interruptor in README
**Evaluated:** 2026-10-25T16:32:57.509180
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ README names scripts/benchmark-interruptor.py and the exact command exits 0: README.md:340 (Audit tooling table) names `scripts/benchmark-interruptor.py` with the run command `python3 scripts/benchmark-interruptor.py`; README.md:893 also lists it in the repo layout. Ran the exact documented command: exit_code=0, output 'Cold start ... 6.16ms PASS', 'Warm start ... 4.219ms PASS', '1KB parse ... 0.392ms PASS', '500-rule eval ... 0.147ms PASS'. [resolution 0.19; scripts/benchmark-interruptor.py]
README documents scripts/benchmark-interruptor.py with the exact command, which was executed and exited 0 with all metrics passing.

## Summary

Judge Result: DOC-20

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ README names scripts/benchmark-interruptor.py and the exact command exits 0: README.md:340 (Audit tooling table) names `scripts/benchmark-interruptor.py` with the run command `python3 scripts/benchmark-interruptor.py`; README.md:893 also lists it in the repo layout. Ran the exact documented command: exit_code=0, output 'Cold start ... 6.16ms PASS', 'Warm start ... 4.219ms PASS', '1KB parse ... 0.392ms PASS', '500-rule eval ... 0.147ms PASS'. [resolution 0.19; scripts/benchmark-interruptor.py]
README documents scripts/benchmark-interruptor.py with the exact command, which was executed and exited 0 with all metrics passing.

Overall: PASS ✓
