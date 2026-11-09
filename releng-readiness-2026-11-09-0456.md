# terminal-jail releng readiness — terminal-jail-releng-2026-11-09-04-56-18

Target: terminal-jail/terminal-jail
Candidate: 03641d9cd0cf7c506d473899f6a053c20c6db0f6 (origin/main; local carrier was 14a7b3b and was not used)
Baseline: v1.3.1 -> e4741912d6a64923b3099da445375a228032c506
Range: v1.3.1..03641d9 (33 commits; 1 material source commit, 32 bookkeeping/docs/release-surface commits)

## Decision

NO CUT — Decision 1 rule 3: there are no new material commits since v1.3.1. The only material source change in the 33-commit range is 4f64a206 fix(packaging), already shipped in v1.3.1, so no new semver release is due from this range. The live release-channel and dogfood defects remain blockers for release readiness and are carried by existing rows. Release tooling is present and the version surface is 1.3.1; no tag mutation was attempted.

## Commit census

- feat: 0
- fix: 1 (4f64a206, already reachable from v1.3.1 and therefore not new to this release line)
- perf: 0
- breaking: 0 (no BREAKING CHANGE: body and no type! subject)
- non-material: 32 (chore 20, docs 8, release 1, pm 1, board 1, merge 1; parser total reconciles to 33 including the fix)
- source-path delta excluding board, gitreins, vfs, docs, skills, README, CHANGELOG: plugin/*, standalone/* only at 4f64a206; no source delta after v1.3.1 beyond that already-tagged fix

## Hosted CI

Exact candidate SHA 03641d9: run 42564157843, CI, completed success, all six jobs success (Lint, Audit, Drift guards, Python 3.11/3.12/3.13). Recent history has earlier failures on dogfood/bookkeeping commits 372a0d7 through 803b60e, followed by green repairs; no current candidate red.

## Release tooling and version hygiene

Repository-owned path is authoritative: docs/releasing.md, scripts/release-cut-check.sh, .github/release.yml, .github/workflows/release.yml. Python package build is the artifact strategy. The workflow is tag-triggered and owns GitHub Release publication; manual fallback is documented because RELCI-001 remains open. pyproject.toml is 1.3.1; plugin/plugin.yaml is 1.3.1; CHANGELOG has empty [Unreleased]. Existing tags/releases: v1.0.0, v1.2.0, v1.3.0, v1.3.1. v1.3.1 has exactly three assets: sdist, wheel, SHA256SUMS.

## GitReins and dogfood

Latest relevant persisted GitReins verdicts: RELPKG-001 PASS at 4843ffb (artifact/packaging acceptance); TJ-DF-061 latest PASS at 383f260, with an earlier FAIL at 688a1e2; the current candidate has no fresh candidate-bound GitReins verdict. Dogfood 2026-11-08 is PROMISING-BUT-ROUGH, partial/unverified fresh-machine battery, and four open findings TJ-DF-060..063. TJ-DF-062 is a live release-channel defect: release-mode installer requests terminal-jail and terminal-jail.sha256, while published v1.3.1 provides wheel/tar.gz/SHA256SUMS; default installer version remains 1.2.0 and docs still say no assets are published.

## Deployed surfaces

/home/kara/.local/bin/terminal-jail reports 1.2.0; /home/kara/.hermes/plugins/terminal-jail/plugin.yaml declares 1.2.0. This is stale against v1.3.1 and remains owned by RELEASE-TJ-014. No deployment mutation was attempted.

## Previous artifact gap

v1.2.0 GitHub Release is published but has zero assets and no explicit carried-forward explanation; owned by RELEASE-TJ-015. v1.3.0 and v1.3.1 each have three assets.

## Public posture

Repository is public, MIT licensed, not archived. Branch protection API returned 404 Not Found (unprotected or unavailable; classify as unprotected until separately resolved). security_and_analysis was null in the repository API response (UNVERIFIED, not asserted enabled). No release mutation was attempted.

## Open blockers / rows

Existing open release rows RELEASE-TJ-013 (notes cite a red run / split version prep), RELEASE-TJ-014 (deployed 1.2.0), RELEASE-TJ-015 (assetless v1.2.0), and dogfood TJ-DF-062 (release-mode mismatch). This pass does not create a duplicate RELEASE-TJ row: the current no-cut result and live release-channel defect are already owned by those rows. A fresh RELEASE-TJ-016 row is not required.
