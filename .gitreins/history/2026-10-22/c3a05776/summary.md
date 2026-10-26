# Verdict: TJ-DF-048

**Task:** Add Landlock tier-ON overhead row to README performance table
**Evaluated:** 2026-10-22T10:16:58.486291
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ Verify that README.md performance table includes a row for tier-ON wrapper overhead measurement; grep -c 'tier-ON' README.md exits 0 with count >= 1: Ran `grep -c 'tier-ON' README.md` -> output "1", exit_code=0 (count >= 1 satisfied). README.md:366 contains the table row `| **Landlock fs-tier ON** | ~1036 ms | — | — | — | ~6.7× |` inside the performance table whose header is at README.md:362 (`| payload | one-shot p50 | one-shot p99 | resident p50 | resident p99 | speedup |`). README.md:368-371 adds the overhead note: 'Interleaved 12-run measurement (TERMINAL_JAIL_LANDLOCK_FS=1 vs =0 ...): tier-ON median 1036 ms vs tier-OFF 915 ms, delta ~121 ms per invocation (~13% overhead)'. Commit aae182a ('docs(readme): add Landlock tier-ON overhead row to perf table. Addresses TJ-DF-048') shows the 7 added lines (README.md +363..+369). Docs-only task — no test suite applies. [resolution 0.28; README.md]
README.md performance table now has a Landlock fs-tier ON overhead row (line 366) plus a tier-ON vs tier-OFF measurement note, and `grep -c 'tier-ON' README.md` returns 1 with exit code 0.

## Summary

Judge Result: TJ-DF-048

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ Verify that README.md performance table includes a row for tier-ON wrapper overhead measurement; grep -c 'tier-ON' README.md exits 0 with count >= 1: Ran `grep -c 'tier-ON' README.md` -> output "1", exit_code=0 (count >= 1 satisfied). README.md:366 contains the table row `| **Landlock fs-tier ON** | ~1036 ms | — | — | — | ~6.7× |` inside the performance table whose header is at README.md:362 (`| payload | one-shot p50 | one-shot p99 | resident p50 | resident p99 | speedup |`). README.md:368-371 adds the overhead note: 'Interleaved 12-run measurement (TERMINAL_JAIL_LANDLOCK_FS=1 vs =0 ...): tier-ON median 1036 ms vs tier-OFF 915 ms, delta ~121 ms per invocation (~13% overhead)'. Commit aae182a ('docs(readme): add Landlock tier-ON overhead row to perf table. Addresses TJ-DF-048') shows the 7 added lines (README.md +363..+369). Docs-only task — no test suite applies. [resolution 0.28; README.md]
README.md performance table now has a Landlock fs-tier ON overhead row (line 366) plus a tier-ON vs tier-OFF measurement note, and `grep -c 'tier-ON' README.md` returns 1 with exit code 0.

Overall: PASS ✓
