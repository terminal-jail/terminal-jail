# Verdict: DF-TERMINAL-JAIL-31

**Task:** Pin scoped-secret-source egress shapes in the regression suite
**Evaluated:** 2026-09-20T18:02:47.706849
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✗ **tier2**
  - INCOMPLETE
  ✓ plugin/test_egress_no_delivery.py contains regression tests asserting BLOCK with rule id builtin-net-remote-tree-copy for scp -r and rsync -a of a scoped secret source (~/.ssh, ~/.aws, ~/.gnupg) to a remote sink: PASS: plugin/test_egress_no_delivery.py lines ~455-500: test_scp_scoped_secret_tree_reaches_no_sink and test_rsync_scoped_secret_tree_reaches_no_sink parametrized over _SCOPED_SECRET_SOURCES = ("~/.ssh","~/.aws","~/.gnupg"), assert rc==126, "COMMAND BLOCKED", "builtin-net-remote-tree-copy". Plus engine-level test_engine_verdict_for_scoped_secret_sources asserting rule_id == builtin-net-remote-tree-copy.
  ✓ plugin/test_egress_no_delivery.py contains a regression test asserting BLOCK with rule id builtin-net-file-exfil-ssh for the tar cf - <scoped source> | ssh remote-write shape: PASS: test_tar_scoped_secret_over_ssh_reaches_no_sink (parametrized over ~/.ssh,~/.aws,~/.gnupg) asserts rc==126 and "builtin-net-file-exfil-ssh" in stderr, plus tcp_collector.data == b"". Engine shape tuple also asserts builtin-net-file-exfil-ssh for 'tar cf - {source} | ssh ... "tar xf -"'.
  ✓ A dogfood checklist item exists requiring at least one shape the rule deliberately does not target to be probed before a closure claims a rule class: PASS: docs/dogfood/checklist.md (new file, 9 lines) contains item: "When a closure claims a rule CLASS is covered, probe at least one shape the rule deliberately does not target (scoped source, different client, quoted form) before closing."
  ✓ CHANGELOG.md carries an Unreleased entry naming DF-TERMINAL-JAIL-31: PASS: CHANGELOG.md [Unreleased] section header "### Scoped-secret-source egress shapes pinned in the regression suite (DF-TERMINAL-JAIL-31)" names DF-TERMINAL-JAIL-31.
  ✗ The full suite passes from the repo root (before/after counts reported) and ruff check on the touched test file reports no issues: Not verified — evaluation terminated before this criterion was checked
Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: DF-TERMINAL-JAIL-31

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: FAIL
  INCOMPLETE
  ✓ plugin/test_egress_no_delivery.py contains regression tests asserting BLOCK with rule id builtin-net-remote-tree-copy for scp -r and rsync -a of a scoped secret source (~/.ssh, ~/.aws, ~/.gnupg) to a remote sink: PASS: plugin/test_egress_no_delivery.py lines ~455-500: test_scp_scoped_secret_tree_reaches_no_sink and test_rsync_scoped_secret_tree_reaches_no_sink parametrized over _SCOPED_SECRET_SOURCES = ("~/.ssh","~/.aws","~/.gnupg"), assert rc==126, "COMMAND BLOCKED", "builtin-net-remote-tree-copy". Plus engine-level test_engine_verdict_for_scoped_secret_sources asserting rule_id == builtin-net-remote-tree-copy.
  ✓ plugin/test_egress_no_delivery.py contains a regression test asserting BLOCK with rule id builtin-net-file-exfil-ssh for the tar cf - <scoped source> | ssh remote-write shape: PASS: test_tar_scoped_secret_over_ssh_reaches_no_sink (parametrized over ~/.ssh,~/.aws,~/.gnupg) asserts rc==126 and "builtin-net-file-exfil-ssh" in stderr, plus tcp_collector.data == b"". Engine shape tuple also asserts builtin-net-file-exfil-ssh for 'tar cf - {source} | ssh ... "tar xf -"'.
  ✓ A dogfood checklist item exists requiring at least one shape the rule deliberately does not target to be probed before a closure claims a rule class: PASS: docs/dogfood/checklist.md (new file, 9 lines) contains item: "When a closure claims a rule CLASS is covered, probe at least one shape the rule deliberately does not target (scoped source, different client, quoted form) before closing."
  ✓ CHANGELOG.md carries an Unreleased entry naming DF-TERMINAL-JAIL-31: PASS: CHANGELOG.md [Unreleased] section header "### Scoped-secret-source egress shapes pinned in the regression suite (DF-TERMINAL-JAIL-31)" names DF-TERMINAL-JAIL-31.
  ✗ The full suite passes from the repo root (before/after counts reported) and ruff check on the touched test file reports no issues: Not verified — evaluation terminated before this criterion was checked
Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
