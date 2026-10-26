# Verdict: TJ-DF-054

**Task:** Document resident bridge single-client serialization in README
**Evaluated:** 2026-10-24T01:20:52.379037
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ 1. sed -n '346,412p' README.md | grep -Eiq 'one client at a time|single client|seriali(z|s)ed|clients queue|queue behind' exits 0 with count >= 1. 2. The documented behaviour is reproducible: concurrent clients queue (dogfood run 22 verified 2x5 queries, all OK, wall 58.8ms vs ~15ms serial).: Criterion 1: README.md:357 reads '**Single-client serialization.** The resident daemon serves one client at a time; concurrent clients queue behind each other (no parallelism).' Running `sed -n '346,412p' README.md | grep -Eic 'one client at a time|single client|seriali(z|s)ed|clients queue|queue behind'` returned count=1 with EXIT=0 (line 357 falls inside the 346-412 window; it matches three of the alternatives). Criterion 2: behaviour empirically reproduced against a live daemon (`plugin/terminal_jail/interruptor_resident.py --serve --sock <tmp>`): 10 concurrent clients (2x5 queries, payload `ls -la`) all returned action=allow rule_id=allow-ls, wall=55.5ms; the serial baseline of the same 10 queries was wall=54.8ms — concurrent wall ~= serial wall, i.e. no parallelism and clients queue, matching the documented '2x5 queries, all OK, wall 58.8ms vs ~15ms serial' claim. Code confirms the mechanism: interruptor_resident.py:199-229 `_accept_loop` calls `handle(conn)` synchronously (single-threaded; no threading/fork/select concurrency) and :325-353 `_serve_connection` reads, answers and closes one connection before returning. Test evidence: `.venv/bin/python -m pytest plugin/test_resident_bridge.py plugin/test_interruptor.py -q` -> exit_code=0, '551 passed in 4.79s' (resident-only: '29 passed in 2.31s'). [resolution 0.23; README.md]
README.md:357 documents single-client serialization (grep count=1, exit 0) and the behaviour is reproducible — 10 concurrent queries all succeeded at 55.5ms wall vs 54.8ms serial, confirming clients queue with no parallelism, backed by a single-threaded accept loop and 551 passing tests.

## Summary

Judge Result: TJ-DF-054

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ 1. sed -n '346,412p' README.md | grep -Eiq 'one client at a time|single client|seriali(z|s)ed|clients queue|queue behind' exits 0 with count >= 1. 2. The documented behaviour is reproducible: concurrent clients queue (dogfood run 22 verified 2x5 queries, all OK, wall 58.8ms vs ~15ms serial).: Criterion 1: README.md:357 reads '**Single-client serialization.** The resident daemon serves one client at a time; concurrent clients queue behind each other (no parallelism).' Running `sed -n '346,412p' README.md | grep -Eic 'one client at a time|single client|seriali(z|s)ed|clients queue|queue behind'` returned count=1 with EXIT=0 (line 357 falls inside the 346-412 window; it matches three of the alternatives). Criterion 2: behaviour empirically reproduced against a live daemon (`plugin/terminal_jail/interruptor_resident.py --serve --sock <tmp>`): 10 concurrent clients (2x5 queries, payload `ls -la`) all returned action=allow rule_id=allow-ls, wall=55.5ms; the serial baseline of the same 10 queries was wall=54.8ms — concurrent wall ~= serial wall, i.e. no parallelism and clients queue, matching the documented '2x5 queries, all OK, wall 58.8ms vs ~15ms serial' claim. Code confirms the mechanism: interruptor_resident.py:199-229 `_accept_loop` calls `handle(conn)` synchronously (single-threaded; no threading/fork/select concurrency) and :325-353 `_serve_connection` reads, answers and closes one connection before returning. Test evidence: `.venv/bin/python -m pytest plugin/test_resident_bridge.py plugin/test_interruptor.py -q` -> exit_code=0, '551 passed in 4.79s' (resident-only: '29 passed in 2.31s'). [resolution 0.23; README.md]
README.md:357 documents single-client serialization (grep count=1, exit 0) and the behaviour is reproducible — 10 concurrent queries all succeeded at 55.5ms wall vs 54.8ms serial, confirming clients queue with no parallelism, backed by a single-threaded accept loop and 551 passing tests.

Overall: PASS ✓
