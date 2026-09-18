# Verdict: TJ-GAP-055

**Task:** License-clean bubblewrap install path
**Evaluated:** 2026-09-18T12:38:31.690554
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m7:37AM[0m [32mINF[0m [1mscanned ~3608713 bytes (3.61 MB) in 234ms[0m
[90m7:37AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ Install documentation and tests prove bubblewrap is an optional external runtime dependency, not vendored, and the MIT repository contains no bubblewrap source; cite the distro package/license guidance and preserve current installer behavior.: No bubblewrap source/vendor in MIT repo: `git ls-files | grep -iE 'bwrap|bubblewrap|vendor|third.party|subprojects'` returns no matches (exit 1), no .gitmodules exists, LICENSE='MIT License'. install.sh:128-137 adds only an advisory NOTE block; diff vs parent 54414e6 is purely additive (10 lines, comment+echo, no download/build/package-install/vendor); `sh -n` and `dash -n` OK. Behavior preserved: running `sh install.sh` with a curated PATH lacking bwrap exits 0, prints the NOTE ('optional bubblewrap (bwrap) not found ... apt install bubblewrap ... dnf install bubblewrap ... never downloads, builds, or redistributes it'), and installs the binary; silent when bwrap present. Docs cite distro package + license guidance: README.md:323,335 ('apt install bubblewrap'/'dnf install bubblewrap', 'LGPL-2.1-or-later', 'not legal advice', 'does not vendor, bundle, download, build, or redistribute', 'advisory note', 'fails closed'); specs/cli.md:251 ('optional runtime dependency', 'never vendored', 'resolved from PATH', 'LGPL-2.1-or-later', 'not legal advice'); docs/quickstart.md, docs/dependency-audit.md, CHANGELOG.md updated. Tests added: plugin/test_install.py (advisory note + exit 0, silent when present, no artifact written, source invariant) and plugin/test_packaging.py (tracked-tree no-vendor verdict via git ls-files, docs-claim contract with denial-aware negative check). Fresh test runs (no cache): `pytest plugin/test_install.py plugin/test_packaging.py -q -p no:cacheprovider` → 38 passed in 1.25s; `pytest -x --tb=short -q -p no:cacheprovider` (config test_command) → 567 passed, 5 skipped in 13.86s. LSP diagnostics: 0.
Bubblewrap is documented and tested as an optional external distro dependency with no vendored source in the MIT repo, distro/license guidance cited, and installer behavior preserved (advisory-only, exit 0 without bwrap); full suite passes 567 passed/5 skipped.

## Summary

Judge Result: TJ-GAP-055

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m7:37AM[0m [32mINF[0m [1mscanned ~3608713 bytes (3.61 MB) in 234ms[0m
[90m7:37AM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ Install documentation and tests prove bubblewrap is an optional external runtime dependency, not vendored, and the MIT repository contains no bubblewrap source; cite the distro package/license guidance and preserve current installer behavior.: No bubblewrap source/vendor in MIT repo: `git ls-files | grep -iE 'bwrap|bubblewrap|vendor|third.party|subprojects'` returns no matches (exit 1), no .gitmodules exists, LICENSE='MIT License'. install.sh:128-137 adds only an advisory NOTE block; diff vs parent 54414e6 is purely additive (10 lines, comment+echo, no download/build/package-install/vendor); `sh -n` and `dash -n` OK. Behavior preserved: running `sh install.sh` with a curated PATH lacking bwrap exits 0, prints the NOTE ('optional bubblewrap (bwrap) not found ... apt install bubblewrap ... dnf install bubblewrap ... never downloads, builds, or redistributes it'), and installs the binary; silent when bwrap present. Docs cite distro package + license guidance: README.md:323,335 ('apt install bubblewrap'/'dnf install bubblewrap', 'LGPL-2.1-or-later', 'not legal advice', 'does not vendor, bundle, download, build, or redistribute', 'advisory note', 'fails closed'); specs/cli.md:251 ('optional runtime dependency', 'never vendored', 'resolved from PATH', 'LGPL-2.1-or-later', 'not legal advice'); docs/quickstart.md, docs/dependency-audit.md, CHANGELOG.md updated. Tests added: plugin/test_install.py (advisory note + exit 0, silent when present, no artifact written, source invariant) and plugin/test_packaging.py (tracked-tree no-vendor verdict via git ls-files, docs-claim contract with denial-aware negative check). Fresh test runs (no cache): `pytest plugin/test_install.py plugin/test_packaging.py -q -p no:cacheprovider` → 38 passed in 1.25s; `pytest -x --tb=short -q -p no:cacheprovider` (config test_command) → 567 passed, 5 skipped in 13.86s. LSP diagnostics: 0.
Bubblewrap is documented and tested as an optional external distro dependency with no vendored source in the MIT repo, distro/license guidance cited, and installer behavior preserved (advisory-only, exit 0 without bwrap); full suite passes 567 passed/5 skipped.

Overall: PASS ✓
