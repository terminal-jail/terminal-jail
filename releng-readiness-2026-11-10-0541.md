# terminal-jail releng readiness — terminal-jail-releng-2026-11-10-05-41-03

Target: terminal-jail/terminal-jail
Certified candidate: 1b6241ada07a48b98c24a81e330dbe97fa2e77fa (origin/main and ls-remote agree)
Baseline: v1.3.2 -> f7ce3ef593e112cb2adff0db659d9486c3fc5c9f

## Decision

NO CUT / NOT READY. A patch release is due by the commit census, but the candidate is not releaseable. Do not tag v1.3.3 in this tick.

The newest real tag is v1.3.2. The range v1.3.2..1b6241a contains 58 commits: 5 conventional `fix` commits, 0 `feat`, 0 `perf`, 0 breaking declarations, and 53 non-material/bookkeeping/docs/merge commits. The five material fixes are 6c7ec92 (wheel CLI interpreter), c42e01a (release-mode assets), dcac6fd (atomic version-prep enforcement), 224e743 (Docker-daemon guard), and dfec1d4 (Docker timeout classification). This is a PATCH candidate, not a major release.

The candidate cannot be tagged because version-prep is absent: pyproject.toml and plugin/plugin.yaml remain 1.3.2, CHANGELOG has an [Unreleased] section, and no [1.3.3] section exists. The working checkout is also dirty/diverged (main is 3 commits ahead and 13 behind; `.gitreins/tasks.yaml` is modified), so it is not a release candidate. The repository-owned release contract requires a clean atomic version-prep commit, exact-SHA CI, and the repository's pre-cut check before tagging.

## Evidence table

| Surface | Receipt | Result |
|---|---|---|
| Identity | `git remote`: git@github.com:terminal-jail/terminal-jail.git; certified SHA 1b6241ada07a48b98c24a81e330dbe97fa2e77fa | PASS |
| Commit census | `git log v1.3.2..origin/main`: 58 total; 5 fix, 0 feat, 0 perf, 0 breaking, 53 non-material | PATCH DUE, not cut-ready |
| Version hygiene | pyproject.toml=1.3.2; plugin/plugin.yaml=1.3.2; CHANGELOG has [Unreleased], [1.3.2], no [1.3.3] | BLOCKED: version prep required |
| Candidate CI | Run 42766096354 on 1b6241a, CI push, completed success; six jobs all success: Lint, Audit, Drift guards, Python 3.11/3.12/3.13 | PASS for current candidate |
| Recent CI | Runs 42766034757 and 42765238213 failed only at `Validate canonical board task IDs` on their intermediate board carriers; run 42741572421 on 4abde83 success | Intermediate carrier failures, not candidate evidence |
| Tag CI | v1.3.2 tag commit f7ce3ef: CI run 42569431104 success; Release run 42569796687 failed at token preflight | Existing RELCI-001; manual publish was used |
| GitReins | Latest candidate-bound verdicts: none. PASS verdicts exist for TJ-DF-062 at 284e346 (4a78143f), TJ-DF-061 at 6951c0a5 (b43b4a8f), and release tooling at ebd98b0 (ed8d35b0); none evaluates 1b6241a. A prior TJ-DF-061 cap/incomplete verdict 4883f178 is not evidence against this candidate. | UNVERIFIED for candidate |
| Dogfood | Latest release-artifact note `docs/dogfood/2026-11-08-release-artifact-integration.md`: PROMISING-BUT-ROUGH; tests 1 failed, 1920 passed, 65 skipped; fresh-machine install proven but isolation unverified; historical TJ-DF-060..063 findings. TJ-DF-062 fix is now present at c42e01a and TJ-DF-063 code fix is present at 224e743/dfec1d4, but no fresh candidate-bound dogfood proof is recorded. | PARTIAL / UNVERIFIED |
| Release tooling | Repository-owned docs/releasing.md, scripts/release-cut-check.sh, .github/workflows/release.yml and .github/release.yml | PASS: use repo path; manual fallback remains required if RELCI-001 persists |
| Previous artifact | v1.3.2 is non-draft/non-prerelease with exactly SHA256SUMS, sdist, and wheel; remote tag peels to f7ce3ef | PASS |
| Deployed surfaces | `/home/kara/.local/bin/terminal-jail` reports 1.2.0; `/home/kara/.hermes/plugins/terminal-jail/plugin.yaml` declares 1.2.0 | BLOCKED: RELEASE-TJ-014 remains live, three releases stale |
| Release history gap | v1.2.0 Release has zero assets; v1.3.0, v1.3.1, v1.3.2 have three each | BLOCKED: RELEASE-TJ-015 remains live |
| Release workflow | RELCI-001 remains blocked; v1.3.2 tag run 42569796687 failed `Preflight — verify the token may create releases` because GITHUB_TOKEN lacks contents:write | BLOCKED: owner/app-admin action; no unattended publisher |
| Board state | Canonical origin/main has RELEASE-TJ-018 pending, plus RELCI-001 blocked, RELEASE-TJ-014/015 pending, TJ-DF-062/063 pending | Existing rows own blockers; no duplicate row |

## Required unblock path

1. Land one version-prep commit for v1.3.3 changing pyproject.toml, plugin/plugin.yaml, and CHANGELOG together; preserve [Unreleased] material and add categorized notes for the five fixes.
2. Run exact-SHA CI on that commit and require all six jobs completed successfully and not skipped.
3. Run `scripts/release-cut-check.sh v1.3.3` from a clean detached checkout; require exit 0.
4. Obtain a fresh, non-degraded candidate-bound GitReins guard/verdict and fresh dogfood evidence, or explicitly carry the partial/unverified dogfood state as a release blocker.
5. Only then tag and publish using docs/releasing.md. If the tag workflow still fails RELCI-001, use the documented manual fallback once; never move or reuse an existing tag.
6. Re-measure RELEASE-TJ-014, RELEASE-TJ-015, RELCI-001, and the TJ-DF-062/063 rows at cut time.
