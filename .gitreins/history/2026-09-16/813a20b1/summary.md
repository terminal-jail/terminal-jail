# Verdict: TJ-GAP-052

**Task:** Per-host systemd directive verification harness
**Evaluated:** 2026-09-16T01:19:51.217201
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m8:18PM[0m [32mINF[0m [1mscanned ~4161718 bytes (4.16 MB) in 454ms[0m
[90m8:18PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ python3 scripts/systemd-directive-probe.py --json prints one JSON record per staged directive and exits 0: Ran `python3 scripts/systemd-directive-probe.py --json` -> exit=0, stderr empty, valid JSON with 13 records (one per staged directive: ProtectProc, NoNewPrivileges, ProtectControlGroups, TasksMax, PrivateUsers, RestrictNamespaces, CapabilityBoundingSet, RestrictAddressFamilies, ProtectSystem, ProtectHome, MemoryMax, ReadWritePaths, CloseOnExec).
  ✓ On this host the probe classifies the invalid CloseOnExec=true control as unsupported and reports at least 4 staged directives as ENFORCED with non-empty evidence: JSON output: CloseOnExec verdict=UNSUPPORTED with evidence "'Unknown assignment: CloseOnExec=true' — rejected at load"; ENFORCED count=7 (>=4) all with non-empty evidence (NoNewPrivs: 1; pids.max = 256; uid_map '1000 1000 1'; unshare --user --pid denied rc=1; AF_INET socket denied rc=1; memory.max = 1073741824; ReadWritePaths carve-out writable).
  ✓ Plain-text mode python3 scripts/systemd-directive-probe.py exits 0 and prints a per-directive verdict line plus a summary line: Ran plain mode -> exit=0, 13 per-directive verdict lines (e.g. 'ENFORCED      NoNewPrivileges=true (user): NoNewPrivs: 1') plus final 'SUMMARY: scope=user enforced=7 not_enforced=5 unsupported=1 unknown=0 of=13'.
  ✓ The script never references hermes-gateway.service nor systemctl restart or stop, and writes nothing under /etc: grep of scripts/systemd-directive-probe.py: no 'hermes', no '/etc', no 'restart'/'stop'; only match for 'systemctl' is line 54 docstring 'systemctl verb of any kind is used.' No open()/write()/tee/shutil.copy/os.mkdir write paths found. Test test_source_has_no_etc_write_path_no_gateway_unit_no_daemon_reload also asserts this and passes.
  ✓ plugin/test_systemd_directive_probe.py passes offline with an injected fake systemd-run shim: .venv/bin/python -m pytest plugin/test_systemd_directive_probe.py -q -> 11 passed in 0.73s. Offline tests inject a fake systemd-run shell script via write_fake_systemd_run(tmp_path) (line 67) passed as --systemd-run (lines 130-241); only test_live_host_close_on_exec_control_and_enforcement touches real systemd.
  ✓ Full suite has 0 failures: .venv/bin/python -m pytest -q: Ran `.venv/bin/python -m pytest -q` -> '359 passed, 14 skipped in 8.89s', 0 failures.
  ✓ specs/systemd.md and docs/deploy-to-karahermes.md both reference scripts/systemd-directive-probe.py: specs/systemd.md:203,208-210 reference scripts/systemd-directive-probe.py (with usage examples); docs/deploy-to-karahermes.md:53 references /home/kara/terminal-jail/scripts/systemd-directive-probe.py --json.
  ✓ uvx ruff check plugin/ scripts/systemd-directive-probe.py reports no errors: Ran `uvx ruff check plugin/ scripts/systemd-directive-probe.py` -> 'All checks passed!' exit=0.
All 8 criteria verified: probe exits 0 in both modes with 13 records, CloseOnExec=UNSUPPORTED and 7 ENFORCED, no forbidden references, offline+full suites green (359 passed/0 failures), docs reference the script, and ruff is clean.

## Summary

Judge Result: TJ-GAP-052

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m8:18PM[0m [32mINF[0m [1mscanned ~4161718 bytes (4.16 MB) in 454ms[0m
[90m8:18PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ python3 scripts/systemd-directive-probe.py --json prints one JSON record per staged directive and exits 0: Ran `python3 scripts/systemd-directive-probe.py --json` -> exit=0, stderr empty, valid JSON with 13 records (one per staged directive: ProtectProc, NoNewPrivileges, ProtectControlGroups, TasksMax, PrivateUsers, RestrictNamespaces, CapabilityBoundingSet, RestrictAddressFamilies, ProtectSystem, ProtectHome, MemoryMax, ReadWritePaths, CloseOnExec).
  ✓ On this host the probe classifies the invalid CloseOnExec=true control as unsupported and reports at least 4 staged directives as ENFORCED with non-empty evidence: JSON output: CloseOnExec verdict=UNSUPPORTED with evidence "'Unknown assignment: CloseOnExec=true' — rejected at load"; ENFORCED count=7 (>=4) all with non-empty evidence (NoNewPrivs: 1; pids.max = 256; uid_map '1000 1000 1'; unshare --user --pid denied rc=1; AF_INET socket denied rc=1; memory.max = 1073741824; ReadWritePaths carve-out writable).
  ✓ Plain-text mode python3 scripts/systemd-directive-probe.py exits 0 and prints a per-directive verdict line plus a summary line: Ran plain mode -> exit=0, 13 per-directive verdict lines (e.g. 'ENFORCED      NoNewPrivileges=true (user): NoNewPrivs: 1') plus final 'SUMMARY: scope=user enforced=7 not_enforced=5 unsupported=1 unknown=0 of=13'.
  ✓ The script never references hermes-gateway.service nor systemctl restart or stop, and writes nothing under /etc: grep of scripts/systemd-directive-probe.py: no 'hermes', no '/etc', no 'restart'/'stop'; only match for 'systemctl' is line 54 docstring 'systemctl verb of any kind is used.' No open()/write()/tee/shutil.copy/os.mkdir write paths found. Test test_source_has_no_etc_write_path_no_gateway_unit_no_daemon_reload also asserts this and passes.
  ✓ plugin/test_systemd_directive_probe.py passes offline with an injected fake systemd-run shim: .venv/bin/python -m pytest plugin/test_systemd_directive_probe.py -q -> 11 passed in 0.73s. Offline tests inject a fake systemd-run shell script via write_fake_systemd_run(tmp_path) (line 67) passed as --systemd-run (lines 130-241); only test_live_host_close_on_exec_control_and_enforcement touches real systemd.
  ✓ Full suite has 0 failures: .venv/bin/python -m pytest -q: Ran `.venv/bin/python -m pytest -q` -> '359 passed, 14 skipped in 8.89s', 0 failures.
  ✓ specs/systemd.md and docs/deploy-to-karahermes.md both reference scripts/systemd-directive-probe.py: specs/systemd.md:203,208-210 reference scripts/systemd-directive-probe.py (with usage examples); docs/deploy-to-karahermes.md:53 references /home/kara/terminal-jail/scripts/systemd-directive-probe.py --json.
  ✓ uvx ruff check plugin/ scripts/systemd-directive-probe.py reports no errors: Ran `uvx ruff check plugin/ scripts/systemd-directive-probe.py` -> 'All checks passed!' exit=0.
All 8 criteria verified: probe exits 0 in both modes with 13 records, CloseOnExec=UNSUPPORTED and 7 ENFORCED, no forbidden references, offline+full suites green (359 passed/0 failures), docs reference the script, and ruff is clean.

Overall: PASS ✓
