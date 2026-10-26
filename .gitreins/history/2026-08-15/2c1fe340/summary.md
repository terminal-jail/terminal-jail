# Verdict: TJ-GAP-033

**Task:** P1 — Shipped default rules file is never actually installed
**Evaluated:** 2026-08-15T10:07:50.915779
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m5:07AM[0m [32mINF[0m [1mscanned ~9629681 bytes (9.63 MB) in 894ms[0m
[90m5:07AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ grep -q 'rules.d' install.sh: install.sh:156-165 contains 'rules.d' — mkdir -p "$HOME/.config/terminal-jail/rules.d" and cp 00-builtins.yaml to user rules dir
  ✓ grep -q 'test_local_install_ships_default_rules_to_user_rules_dir' plugin/test_install.py: plugin/test_install.py:443 defines test_local_install_ships_default_rules_to_user_rules_dir
  ✓ ! grep -q 'Installed to /etc/terminal-jail/rules.d' plugin/terminal_jail/rules/00-builtins.yaml: grep found no 'Installed to /etc/terminal-jail/rules.d' in 00-builtins.yaml; file now documents install to ~/.config/terminal-jail/rules.d/00-builtins.yaml
All three TJ-GAP-033 criteria verified: install.sh ships default rules to the user rules dir, the test exists, and the stale /etc path comment was removed.

## Summary

Judge Result: TJ-GAP-033

Stage tier1: PASS
    ✓ lint: E402 Module level import not at top of file
  --> scripts/benchmark-interruptor.py:32:1
   |
30 | sy
  ✓ secrets: [90m5:07AM[0m [32mINF[0m [1mscanned ~9629681 bytes (9.63 MB) in 894ms[0m
[90m5:07AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ grep -q 'rules.d' install.sh: install.sh:156-165 contains 'rules.d' — mkdir -p "$HOME/.config/terminal-jail/rules.d" and cp 00-builtins.yaml to user rules dir
  ✓ grep -q 'test_local_install_ships_default_rules_to_user_rules_dir' plugin/test_install.py: plugin/test_install.py:443 defines test_local_install_ships_default_rules_to_user_rules_dir
  ✓ ! grep -q 'Installed to /etc/terminal-jail/rules.d' plugin/terminal_jail/rules/00-builtins.yaml: grep found no 'Installed to /etc/terminal-jail/rules.d' in 00-builtins.yaml; file now documents install to ~/.config/terminal-jail/rules.d/00-builtins.yaml
All three TJ-GAP-033 criteria verified: install.sh ships default rules to the user rules dir, the test exists, and the stale /etc path comment was removed.

Overall: PASS ✓
