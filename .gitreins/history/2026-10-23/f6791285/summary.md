# Verdict: TJ-GAP-095

**Task:** installer states what its release-version default means
**Evaluated:** 2026-10-23T04:34:34.124176
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ install.sh keeps its TERMINAL_JAIL_VERSION default value unchanged and introduces no version bump or git tag: install.sh:21 still reads TERMINAL_JAIL_VERSION="${TERMINAL_JAIL_VERSION:-1.2.0}" — the diff at that line is context only (comment lines added above it). Commit f914b7b stat: 'install.sh | 12 +++++++++++- / 1 file changed, 11 insertions(+), 1 deletion(-)', no version literal changed. `git tag --list` => v1.0.0, v1.2.0 only; `git tag --list '*1.3.0*'` => empty, so no new tag was created. [resolution 0.00; install.sh]
  ✓ install.sh documents at the assignment and in its usage text that the default is the last released tag (it builds the release download URL) and that a checkout install uses the pyproject version: install.sh:13-20 comment block immediately above the assignment: 'The default below is the last released tag, not the version of this tree... This value builds the release-mode download URL (TERMINAL_JAIL_BASE_URL, below)... v1.3.0 is not tagged yet... A normal checkout install never uses it: the LOCAL_VERSION block in the install section reads the version out of pyproject.toml'. Usage text install.sh:311-313: 'TERMINAL_JAIL_VERSION  release version to download (default: 1.2.0, the last released tag; a checkout install uses the pyproject version)'. Both required facts are stated in both places. [resolution 0.00; install.sh]
  ✓ bash -n install.sh succeeds and a scratch-prefix local install still reports the pyproject version 1.3.0: `bash -n install.sh` => exit_code 0, no output. Scratch-prefix install: `TERMINAL_JAIL_INSTALL_DIR=/tmp/tjprefix/bin TERMINAL_JAIL_TEST=1 ./install.sh --no-path` => exit_code 0 with output 'terminal-jail installer: installing v1.3.0...' and 'terminal-jail installer: repository checkout detected — installing local wrapper (..., version 1.3.0)'. Installed binary check: `/tmp/tjprefix/bin/terminal-jail --version` => 'terminal-jail 1.3.0' (exit 0). pyproject.toml:7 is version = "1.3.0". [resolution 0.00; install.sh]
  ✓ The change touches only install.sh against base 8730de5: `git show --name-only --format="" f914b7b` (the TJ-GAP-095 commit) lists exactly one file: install.sh. `git show --stat f914b7b` => '1 file changed, 11 insertions(+), 1 deletion(-)'. The install.sh portion of `git diff 8730de5` is identical to that commit's diff (14 +/- lines, all comment/usage text). [resolution 0.00; install.sh]
install.sh's TERMINAL_JAIL_VERSION default stays 1.2.0 with no bump or tag, the assignment comment and usage text both explain the last-released-tag/download-URL semantics and the pyproject-version checkout path, bash -n passes and a scratch-prefix install reports 1.3.0, and the commit touches only install.sh.

## Summary

Judge Result: TJ-GAP-095

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ install.sh keeps its TERMINAL_JAIL_VERSION default value unchanged and introduces no version bump or git tag: install.sh:21 still reads TERMINAL_JAIL_VERSION="${TERMINAL_JAIL_VERSION:-1.2.0}" — the diff at that line is context only (comment lines added above it). Commit f914b7b stat: 'install.sh | 12 +++++++++++- / 1 file changed, 11 insertions(+), 1 deletion(-)', no version literal changed. `git tag --list` => v1.0.0, v1.2.0 only; `git tag --list '*1.3.0*'` => empty, so no new tag was created. [resolution 0.00; install.sh]
  ✓ install.sh documents at the assignment and in its usage text that the default is the last released tag (it builds the release download URL) and that a checkout install uses the pyproject version: install.sh:13-20 comment block immediately above the assignment: 'The default below is the last released tag, not the version of this tree... This value builds the release-mode download URL (TERMINAL_JAIL_BASE_URL, below)... v1.3.0 is not tagged yet... A normal checkout install never uses it: the LOCAL_VERSION block in the install section reads the version out of pyproject.toml'. Usage text install.sh:311-313: 'TERMINAL_JAIL_VERSION  release version to download (default: 1.2.0, the last released tag; a checkout install uses the pyproject version)'. Both required facts are stated in both places. [resolution 0.00; install.sh]
  ✓ bash -n install.sh succeeds and a scratch-prefix local install still reports the pyproject version 1.3.0: `bash -n install.sh` => exit_code 0, no output. Scratch-prefix install: `TERMINAL_JAIL_INSTALL_DIR=/tmp/tjprefix/bin TERMINAL_JAIL_TEST=1 ./install.sh --no-path` => exit_code 0 with output 'terminal-jail installer: installing v1.3.0...' and 'terminal-jail installer: repository checkout detected — installing local wrapper (..., version 1.3.0)'. Installed binary check: `/tmp/tjprefix/bin/terminal-jail --version` => 'terminal-jail 1.3.0' (exit 0). pyproject.toml:7 is version = "1.3.0". [resolution 0.00; install.sh]
  ✓ The change touches only install.sh against base 8730de5: `git show --name-only --format="" f914b7b` (the TJ-GAP-095 commit) lists exactly one file: install.sh. `git show --stat f914b7b` => '1 file changed, 11 insertions(+), 1 deletion(-)'. The install.sh portion of `git diff 8730de5` is identical to that commit's diff (14 +/- lines, all comment/usage text). [resolution 0.00; install.sh]
install.sh's TERMINAL_JAIL_VERSION default stays 1.2.0 with no bump or tag, the assignment comment and usage text both explain the last-released-tag/download-URL semantics and the pyproject-version checkout path, bash -n passes and a scratch-prefix install reports 1.3.0, and the commit touches only install.sh.

Overall: PASS ✓
