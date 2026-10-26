# Verdict: TJ-GAP-087

**Task:** install.sh BASH_SOURCE checkout resolution + containment tier report
**Evaluated:** 2026-10-04T05:46:47.786621
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ Absolute-path install.sh invocation from a foreign cwd installs from the checkout; installer reports the enforced containment tier via fs-isolation-probe; suite green: install.sh:432-460 resolves SCRIPT_DIR from $0 for absolute-path invocation (case * branch, honors TERMINAL_JAIL_USE_RELEASE=1 suppression), so a foreign-cwd absolute invocation installs from the checkout; install.sh:1339-1350 reports the enforced containment tier via scripts/fs-isolation-probe.py. Suite green: plugin/test_install.py 77 passed in 26.62s. Note: no test asserts the positive foreign-cwd checkout-install case or the containment-tier report string (test_release_mode_requires_opt_in at line 395 only asserts refusal), but the criterion's implementation and green suite are verified. [resolution 0.15; install.sh]
install.sh resolves the checkout via $0 for absolute-path foreign-cwd invocation and reports the containment tier via fs-isolation-probe, with the install suite green (77 passed).

## Summary

Judge Result: TJ-GAP-087

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ Absolute-path install.sh invocation from a foreign cwd installs from the checkout; installer reports the enforced containment tier via fs-isolation-probe; suite green: install.sh:432-460 resolves SCRIPT_DIR from $0 for absolute-path invocation (case * branch, honors TERMINAL_JAIL_USE_RELEASE=1 suppression), so a foreign-cwd absolute invocation installs from the checkout; install.sh:1339-1350 reports the enforced containment tier via scripts/fs-isolation-probe.py. Suite green: plugin/test_install.py 77 passed in 26.62s. Note: no test asserts the positive foreign-cwd checkout-install case or the containment-tier report string (test_release_mode_requires_opt_in at line 395 only asserts refusal), but the criterion's implementation and green suite are verified. [resolution 0.15; install.sh]
install.sh resolves the checkout via $0 for absolute-path foreign-cwd invocation and reports the containment tier via fs-isolation-probe, with the install suite green (77 passed).

Overall: PASS ✓
