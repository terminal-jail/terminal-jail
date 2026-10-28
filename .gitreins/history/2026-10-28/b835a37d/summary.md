# Verdict: DOC-26

**Task:** Remove stale User rules (future) label from integration specification
**Evaluated:** 2026-10-28T02:28:50.529976
**Result:** ✗ FAIL

## Pipeline Stages

- ✗ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (tests/test_release_workflow.py::test_check_script_fails_clearly_on_existing_tag [first failing
- ✓ **tier2**
  - COMPLETE
  ✓ Update specs/integration.md:187 to state shipped/wired user and system rules with current directories and lexical/override semantics; targeted grep must not find the present-tense User rules (future) claim while source RuleLoader and tests remain referenced.: specs/integration.md:187 now reads '- **User rules (shipped):** Loaded from `/etc/terminal-jail/rules.d/` and `~/.config/terminal-jail/rules.d/` in lexical order with user rules overriding system rules. Shipped and wired: the Decider instantiates `RuleLoader.load_all()` at construction, so these directories are live on every command evaluation (same-ID user rules replace the built-in entry).' Targeted grep `grep -rn "User rules (future)|rules (future)|future)" --include=*.md .` returns only docs/pentest-plan.md:303 (an unrelated seccomp note) — the present-tense 'User rules (future)' claim is gone. Every documented claim matches source: config.py:41 system_rules_dir='/etc/terminal-jail/rules.d' and config.py:50 user_rules_dir=~/.config/terminal-jail/rules.d; rules.py:356 iterates [system_dir, user_dir] and rules.py:381 uses `sorted(path.iterdir())` (lexical); rules.py:360-369 replaces a same-id earlier rule so user rules override system rules; decider.py:131-134 calls `RuleLoader(system_dir=config.system_rules_dir, user_dir=config.user_rules_dir).load_all()` inside Decider.__init__ (wired at construction). Tests remain referenced: RuleLoader appears 33x across plugin/test_interruptor.py, test_rule_packs.py, test_bridge_fail_closed.py, test_install.py, test_packaging.py. Test evidence: `.venv/bin/python -m pytest plugin/test_interruptor.py -x -q` => exit_code 0, '522 passed in 2.60s'; `.venv/bin/python -m pytest plugin/test_rule_packs.py plugin/test_bridge_fail_closed.py -x -q` => exit_code 0, '111 passed in 3.80s' (the full-suite run exceeded the 30s tool wall, so the RuleLoader-referencing suites were run directly and are green). [resolution 0.22; specs/integration.md:187]
specs/integration.md:187 now documents shipped/wired user and system rules with the correct directories, lexical ordering and override semantics, the stale 'User rules (future)' claim is absent from all markdown, and the referenced RuleLoader source and tests are present and passing.

## Summary

Judge Result: DOC-26

Stage tier1: FAIL
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✗ tests: FAIL (tests/test_release_workflow.py::test_check_script_fails_clearly_on_existing_tag [first failing

Stage tier2: PASS
  COMPLETE
  ✓ Update specs/integration.md:187 to state shipped/wired user and system rules with current directories and lexical/override semantics; targeted grep must not find the present-tense User rules (future) claim while source RuleLoader and tests remain referenced.: specs/integration.md:187 now reads '- **User rules (shipped):** Loaded from `/etc/terminal-jail/rules.d/` and `~/.config/terminal-jail/rules.d/` in lexical order with user rules overriding system rules. Shipped and wired: the Decider instantiates `RuleLoader.load_all()` at construction, so these directories are live on every command evaluation (same-ID user rules replace the built-in entry).' Targeted grep `grep -rn "User rules (future)|rules (future)|future)" --include=*.md .` returns only docs/pentest-plan.md:303 (an unrelated seccomp note) — the present-tense 'User rules (future)' claim is gone. Every documented claim matches source: config.py:41 system_rules_dir='/etc/terminal-jail/rules.d' and config.py:50 user_rules_dir=~/.config/terminal-jail/rules.d; rules.py:356 iterates [system_dir, user_dir] and rules.py:381 uses `sorted(path.iterdir())` (lexical); rules.py:360-369 replaces a same-id earlier rule so user rules override system rules; decider.py:131-134 calls `RuleLoader(system_dir=config.system_rules_dir, user_dir=config.user_rules_dir).load_all()` inside Decider.__init__ (wired at construction). Tests remain referenced: RuleLoader appears 33x across plugin/test_interruptor.py, test_rule_packs.py, test_bridge_fail_closed.py, test_install.py, test_packaging.py. Test evidence: `.venv/bin/python -m pytest plugin/test_interruptor.py -x -q` => exit_code 0, '522 passed in 2.60s'; `.venv/bin/python -m pytest plugin/test_rule_packs.py plugin/test_bridge_fail_closed.py -x -q` => exit_code 0, '111 passed in 3.80s' (the full-suite run exceeded the 30s tool wall, so the RuleLoader-referencing suites were run directly and are green). [resolution 0.22; specs/integration.md:187]
specs/integration.md:187 now documents shipped/wired user and system rules with the correct directories, lexical ordering and override semantics, the stale 'User rules (future)' claim is absent from all markdown, and the referenced RuleLoader source and tests are present and passing.

Overall: FAIL ✗
