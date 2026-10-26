# Verdict: DF-TERMINAL-JAIL-24

**Task:** Prefix install output clean and normalized
**Evaluated:** 2026-09-19T20:53:52.427134
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh with a custom TERMINAL_JAIL_INSTALL_DIR whose parent does not exist prints no raw cd error; every printed path is normalized (no embedded ..); default-install behavior unchanged; install tests cover the missing-parent prefix case: All four sub-claims verified live. (1) No raw cd error: install.sh:33-105 adds path_normalize() (readlink -m -> realpath -m -> pure-POSIX segment walk) replacing the old `cd <dir>/.. && pwd` idiom at install.sh:411 (rules prefix) and install.sh:552 (LIB_DIR). Live run `HOME=/tmp/tj24/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj24/opt/tj sh install.sh` (parent opt/ absent) -> rc=0, stderr EMPTY, no "can't cd". RED-proof: the pre-fix script (git show 4a34035^:install.sh) printed `install.sh: 327: cd: can't cd to /tmp/tj24red2/opt/tj/..` on stderr. (2) Normalized paths: grep '/\.\./' on the fixed run's stdout+stderr = no match; printed paths are /tmp/tj24/opt/config/terminal-jail/rules.d/00-builtins.yaml and /tmp/tj24/opt/lib/terminal-jail/seccomp-loader.py. Pre-fix leaked `/tmp/tj24red2/opt/tj/../config/terminal-jail/rules.d/...` in 2 output lines. (3) Default install unchanged: `TERMINAL_JAIL_INSTALL_DIR=$HOME/.local/bin sh install.sh` -> rc=0, rules at $HOME/.config/terminal-jail/rules.d/00-builtins.yaml, PATH entry appended to .profile, no prefix warning (live-rules branch, rules_prefix never derived). (4) Test coverage: plugin/test_install.py:595 test_prefix_install_missing_parent_no_cd_error_no_dotdot (added in commit 4a34035) asserts rc=0, no "can't cd" in stdout/stderr, no "/../" anywhere, and wrapper+rules+lib at the normalized prefix targets. Command output: `python -m pytest plugin/test_install.py::test_prefix_install_missing_parent_no_cd_error_no_dotdot -q` -> `1 passed in 0.16s`; `python -m pytest plugin/test_install.py -q` -> `50 passed in 3.18s`; full suite `python -m pytest -q` -> `897 passed, 5 skipped in 21.13s` (exit 0).
install.sh now normalizes derived prefix paths via path_normalize (no raw cd error, no embedded ..), default install behavior is byte-for-byte unchanged, and the missing-parent prefix case is pinned by a passing regression test with the full 897-test suite green.

## Summary

Judge Result: DF-TERMINAL-JAIL-24

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ install.sh with a custom TERMINAL_JAIL_INSTALL_DIR whose parent does not exist prints no raw cd error; every printed path is normalized (no embedded ..); default-install behavior unchanged; install tests cover the missing-parent prefix case: All four sub-claims verified live. (1) No raw cd error: install.sh:33-105 adds path_normalize() (readlink -m -> realpath -m -> pure-POSIX segment walk) replacing the old `cd <dir>/.. && pwd` idiom at install.sh:411 (rules prefix) and install.sh:552 (LIB_DIR). Live run `HOME=/tmp/tj24/home TERMINAL_JAIL_INSTALL_DIR=/tmp/tj24/opt/tj sh install.sh` (parent opt/ absent) -> rc=0, stderr EMPTY, no "can't cd". RED-proof: the pre-fix script (git show 4a34035^:install.sh) printed `install.sh: 327: cd: can't cd to /tmp/tj24red2/opt/tj/..` on stderr. (2) Normalized paths: grep '/\.\./' on the fixed run's stdout+stderr = no match; printed paths are /tmp/tj24/opt/config/terminal-jail/rules.d/00-builtins.yaml and /tmp/tj24/opt/lib/terminal-jail/seccomp-loader.py. Pre-fix leaked `/tmp/tj24red2/opt/tj/../config/terminal-jail/rules.d/...` in 2 output lines. (3) Default install unchanged: `TERMINAL_JAIL_INSTALL_DIR=$HOME/.local/bin sh install.sh` -> rc=0, rules at $HOME/.config/terminal-jail/rules.d/00-builtins.yaml, PATH entry appended to .profile, no prefix warning (live-rules branch, rules_prefix never derived). (4) Test coverage: plugin/test_install.py:595 test_prefix_install_missing_parent_no_cd_error_no_dotdot (added in commit 4a34035) asserts rc=0, no "can't cd" in stdout/stderr, no "/../" anywhere, and wrapper+rules+lib at the normalized prefix targets. Command output: `python -m pytest plugin/test_install.py::test_prefix_install_missing_parent_no_cd_error_no_dotdot -q` -> `1 passed in 0.16s`; `python -m pytest plugin/test_install.py -q` -> `50 passed in 3.18s`; full suite `python -m pytest -q` -> `897 passed, 5 skipped in 21.13s` (exit 0).
install.sh now normalizes derived prefix paths via path_normalize (no raw cd error, no embedded ..), default install behavior is byte-for-byte unchanged, and the missing-parent prefix case is pinned by a passing regression test with the full 897-test suite green.

Overall: PASS ✓
