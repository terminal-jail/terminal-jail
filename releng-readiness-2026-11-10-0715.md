# Releng readiness — terminal-jail — 2026-11-10 (pass 2, 07:15Z)

Certified candidate (latest pass): `5c9b9d6af67b57b9aa3d7595c3bde0c8b9d1db74` (`origin/main`, pass 5); baseline remains `v1.3.3` at `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. Pass 4 certified `8b28074` — superseded by the docs-only carrier commit above, tree identity unchanged for product paths.

**Supersedes** `releng-readiness-2026-11-10-0541.md` (pass 1 of the same tick).
Pass 1 set NO CUT because the version-prep commit was absent. That premise was
correct for a *read-only* pass and wrong for a release-engineering pass: the
charter authorises a patch cut, the census was already complete, and CI was
green at the tip. Pass 2 executed the cut.

## Decision

**CUT v1.3.3 (PATCH).** Version prep written, validated, tagged and pushed.
**Publication is NOT done** — the tag-triggered workflow is blocked by
`RELCI-001` (Actions token lacks `contents: write`), and the documented 5b
hand-publish step was interrupted by an unattended consent gate before the
build ran. The tag is immutable at `290d9b0`; the Release object does not
exist yet.

## Census — v1.3.2 (`f7ce3ef`) .. `290d9b0`

60 commits. Semver driver is **material-only**, per the release contract;
release/QA tooling fixes do not change an installed artifact and must not
earn a patch.

| Commit | Prefix | Material to installed artifact | Note |
|---|---|---|---|
| `6c7ec92` | fix | **yes** | wheel CLI bridge interpreter (`TJ-DF-061`) — unactivated-venv install blocked every command |
| `c42e01a` | fix | **yes** | `install.sh --release` asset names 404 against published assets (`TJ-DF-062`) |
| `dcac6fd` | fix | no | `scripts/release-cut-check.sh` atomic version-prep surfaces |
| `224e743` | fix | no | composed-mode battery gates on the Docker daemon |
| `dfec1d4` | fix | no | battery: Docker probe timeout classified as daemon-unavailable (`INT-CI-018`) |

Material commits: **2, both `fix` → PATCH.** No `feat`, no `!`, no
`BREAKING CHANGE`. Remaining 55 commits are board/harness bookkeeping and
release-artifact commits.

Note for the record: pass 1 counted five material fixes. That overcounted —
three of the five land only in release/QA tooling. The patch is still due,
but it is driven by two fixes, not five.

## Version prep (this pass)

Commit `290d9b0` — `release: bump version to 1.3.3 and open its changelog section`

- `pyproject.toml` 1.3.2 → 1.3.3
- `plugin/plugin.yaml` 1.3.2 → 1.3.3
- `CHANGELOG.md` new `[1.3.3]` section with categorized notes; the existing
  `[Unreleased]` material is untouched

Three surfaces move together, as `dcac6fd` now enforces.

## Gates

| Gate | Evidence | Verdict |
|---|---|---|
| Hosted CI on prep commit | run `42773935428` @ `290d9b0` — Audit(pip-audit), Drift guards, Lint(ruff), Python 3.11/3.12/3.13 all `success` | **GREEN** |
| `scripts/release-cut-check.sh v1.3.3` | 0 failures, `READY` (verdict reached with the documented `TJ_RELEASE_TAG_EXISTS=absent` seam after independent absence proof: 0 remote tags, 0 local tags, 0 releases matching 1.3.3) | **READY** |
| gitreins Tier-1 guard | `gitreins guard` on the prep commit: secrets clean; lint/tests/static_analysis **skipped — DEGRADED PASS** (worktree has no `.venv` at commit time). Compensated by the hosted CI full matrix on the exact same SHA. | **DEGRADED, covered by CI** |
| Tag immutability | annotated `v1.3.3` → `290d9b0`, pushed; `git ls-remote` confirms | **OK** |
| Tag-triggered Release run | run `42774392420` — **failure at preflight**: `GITHUB_TOKEN for terminal-jail/terminal-jail lacks push (contents:write)` | **RED (RELCI-001)** |
| Published assets | `gh release view v1.3.3` → `release not found` | **ABSENT** |

## Open blockers

1. **RELCI-001 (P1, blocked, owner action).** Actions workflow-permission
   default caps `permissions: contents: write`. Repo Settings → Actions →
   General → Workflow permissions. Until then every tag runs red at preflight
   and every release is hand-published.
2. **v1.3.3 publication (P0, new).** Tag exists, Release object missing.
   Remaining steps are exactly the runbook's 5b plus steps 6–7: build
   sdist+wheel from the tag, `SHA256SUMS`, `gh release create v1.3.3
   --verify-tag`, verify assets, install the wheel in a fresh venv and check
   `terminal_jail.__version__`, then snapshot the body into
   `docs/releases/v1.3.3-notes.md` + `-published.json`.
3. **New gate defect (P2).** `scripts/release-cut-check.sh` cannot pass its
   own tag-absence check: `git ls-remote --exit-code origin refs/tags/<tag>`
   exits **2 when the ref is absent** (verified: absent → 2, present → 0), so
   the happy path always hits `fail "could not verify whether tag ... exists
   remotely"`. The gate proves nothing for a fresh tag; the seam masks it.
   Fix needs a distinction between "absent" (ls-remote exit 0, empty output)
   and "probe failed" (non-zero).
4. `RELEASE-TJ-014` (deployed binary stale at 1.2.0) is unchanged and
   independent of this cut.

## Not claimed

- No dogfood PASS is claimed. `TJ-DF-062`/`TJ-DF-063` rows are still not
  closed; the newest released-artifact dogfood note remains
  PROMISING-BUT-ROUGH with one failing test. This cut ships code fixes, it
  does not claim a clean dogfood verdict.
- No release notes snapshot was written, because no release body exists yet.
  Writing one now would mean snapshotting a body nobody published.

## Pass 3 — post-release sweep — 2026-11-10 08:17Z

The earlier publication-pending conclusion is superseded by the landed release
commit `96dcc0f03f04d34db3d14d55d362560341e77a59`. This is a post-release sweep,
not a second cut.

Decision: NOT DUE for another release. The baseline is now `v1.3.3`, whose
annotated tag peels to `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. Three commits
landed after the tag, all non-material release/board bookkeeping; no new `feat`,
`fix`, `perf`, breaking declaration, or shipped-source path was added. The next
release decision therefore remains governed by the next material change.

Release verification:

- `gh release view v1.3.3` reports release `440076088`, published, non-draft,
  non-prerelease, with exactly `terminal_jail-1.3.3.tar.gz`,
  `terminal_jail-1.3.3-py3-none-any.whl`, and `SHA256SUMS`.
- The remote tag is immutable and still resolves to `290d9b0`.
- Re-downloaded artifacts passed `sha256sum -c SHA256SUMS`; a fresh venv install
  reports `terminal-jail 1.3.3`.
- The tag-triggered Release run `42774392420` and manual-dispatch retry
  `42778106840` remain red on `RELCI-001`; the documented hand-publish path was
  used once and was not raced with a functioning publisher.

Current candidate evidence at `origin/main` `96dcc0f`:

- Exact-SHA CI run `42779786182` is completed success. All six check-runs ran and
  passed: Lint, Python 3.11, Python 3.12, Python 3.13, Drift guards, and Audit.
- A fresh GitReins guard is DEGRADED PASS only: secrets and lint passed, while
  tests and static analysis were skipped because the clean candidate worktree had
  no `.venv` and the guard selected no Python analyzer. This is not represented
  as a non-degraded release gate. The prior publication evidence records
  GitReins run `016644a0` PASS for the release artifact verification.
- Dogfood remains PROMISING-BUT-ROUGH/partial rather than PASS. `TJ-DF-062` and
  `TJ-DF-063` remain pending, and `RELEASE-TJ-021` carries the measured
  `python3` trampoline residual.

Carried findings remain open and distinct: `RELCI-001` (workflow token scope),
`RELEASE-TJ-014` (host deployment still reports 1.2.0), `RELEASE-TJ-015`
(v1.2.0 Release has zero assets), `RELEASE-TJ-020` (tag-absence checker),
`RELEASE-TJ-021`, `TJ-DF-062`, and `TJ-DF-063`. Public posture remains public/MIT;
branch-protection lookup returned 404 and security-analysis metadata was null,
so those controls are UNVERIFIED rather than PASS. The readiness row is closed
as superseded by the published `RELEASE-TJ-019` record; no tag or Release was
created or moved by this pass.

## Pass 4 — 2026-11-11 10:08Z

Certified candidate: `8b28074a463b82fd8303e4e171712f635b730204` (`origin/main`),
with baseline `v1.3.3` at `290d9b0770bd826b2f188ea245e8fdae38da9c9f`.

Decision: **NO CUT / NOT DUE.** The range contains 23 commits, but all are
non-material board, documentation, dogfood, QA, ops, PM, or release-record
changes. The independent counts agree (`git rev-list --count` = 23 and
`git log --format=%H | wc -l` = 23); conventional categories are feat 0, fix 0,
perf 0, breaking 0, and `git diff --name-only` outside the bookkeeping/docs
exclusion set is empty. No version-prep, tag, Release, or artifact mutation was
made.

Exact candidate CI is green: run `42972306976` on the full SHA, completed success,
with all six jobs and their real steps successful. No GitReins verdict is bound to
this candidate; historical PASS verdicts remain historical. The latest dogfood
ledger is partial (12 OK, 7 N/A, 4 FAIL, 1 UNVERIFIED of 24): fresh install is
OK, while the tests/CI-pass/chaos-resource cells fail on
`plugin/test_install.py::test_successful_install` and chaos-disconnect is
UNVERIFIED. Existing pending rows own those findings.

Open release rows remain `RELEASE-TJ-020` (tag-absence check), `RELEASE-TJ-021`
(in-jail `python3` trampoline), and `RELEASE-TJ-022` (release-mode default 1.3.1).
The installed `/home/kara/.local/bin/terminal-jail` reports 1.3.3. The project
release tooling remains present: `docs/releasing.md`,
`scripts/release-cut-check.sh`, and the active tag workflow. No duplicate release
row was filed.

This pass supersedes the prior candidate header for this artifact; the earlier
pass remains historical evidence. The new standalone evidence report was delivered
in the scheduler thread as message `252175`; the report file was
`/home/kara/.hermes/cache/scratch/tj-releng-20261111-pbTl3T/report-pass2.txt`.

## Pass 5 — 2026-11-11 releng tick (`terminal-jail-releng-2026-11-11-10-08-38`, duplicate fire)

Certified candidate: `5c9b9d6af67b57b9aa3d7595c3bde0c8b9d1db74`; `git rev-parse
origin/main`, `git ls-remote origin refs/heads/main`, and the fast-forwarded
checkout all agree on that SHA. Baseline `v1.3.3` at
`290d9b0770bd826b2f188ea245e8fdae38da9c9f`.

Decision: **NO CUT / NOT DUE.** Re-derived at the live tip, not carried.

- **Census (3-way agreement).** `git rev-list --count v1.3.3..5c9b9d6` = 24,
  `git log --format=%H | wc -l` = 24, `git describe --tags --always` =
  `v1.3.3-24-g5c9b9d6`. Class sum reconciles: docs 8, ops 4, chore 4, board 3,
  qa 2, PM 2, dogfood 1 = 24. feat 0, fix 0, perf 0, type-bang 0, and a
  record-delimited body scan found zero `BREAKING CHANGE` declarations.
- **Materiality from the shipped diff.** Eleven non-bookkeeping paths changed,
  all documentation or `.gitreins/` records: `docs/deploy-to-karahermes.md`,
  three `docs/dogfood/*.md`, `docs/releases/v1.3.3-*.{md,json}`,
  `releng-readiness-2026-11-10-0715.md`, `.gitreins/{tasks.yaml,usage.jsonl}`.
  Zero `.py`, `plugin/`, `tests/`, `standalone/`, `build/`, `pyproject.toml`, or
  `install.sh` changes — nothing installed moved, so no patch is earned.
- **Exact-SHA CI.** Run `43006333285` on the full SHA: completed/success, all six
  jobs green with named steps — Python 3.11/3.12/3.13 (install, unit tests,
  coverage upload, board ID validation, GTFOBins sweep), Drift guards (rule
  catalog, YAML mirror parity, installed-rules probe, README docs check, backend
  parity battery, TJ-DF-043 orphan gate), pip-audit, ruff + format check.
- **Release artifact reality.** `v1.3.3` is the latest Release (published
  2026-11-10T07:53:18Z, not draft, not prerelease) carrying three assets:
  `terminal_jail-1.3.3-py3-none-any.whl` (192272 B),
  `terminal_jail-1.3.3.tar.gz` (282056 B), `SHA256SUMS` (196 B). Tag peeled to
  `290d9b0`.
- **Version hygiene.** `pyproject.toml` version = 1.3.3; `CHANGELOG.md` carries a
  `## [1.3.3] — 2026-11-10` section and its `[Unreleased]` block explicitly says
  nothing is unreleased. Remaining stale surfaces are already owned:
  README at-a-glance Version cell (`README-14`, `DOC-14-R2`), quickstart version
  examples (`DOC-27`), release runbook stopping at v1.3.1 (`DOC-28`), and
  `install.sh` release-mode default 1.3.1 (`RELEASE-TJ-022`).
- **Deployed staleness.** `/home/kara/.local/bin/terminal-jail --version` reports
  `1.3.3`, matching the tag — not stale. `which -a` also returns
  `/tmp/tj-test-pack2/terminal-jail` ahead of it, the PATH-shadow/legacy residue
  already filed as `OPS-TJ-001`.
- **GitReins.** No verdict is bound to `5c9b9d6` or `8b28074`; the newest
  `.gitreins/history` day is 2026-11-09, so release-gate verdict status here is
  UNVERIFIED rather than PASS or FAIL. `INT-CI-018` remains `in_progress`.
- **Dogfood.** Latest ledger (2026-11-11, 24 cells) is partial: 12 OK, 7 N/A,
  4 FAIL, 1 UNVERIFIED. Fresh install is OK (`terminal-jail-1.3.3` installs on a
  clean box); tests, ci-pass, and upgrade cells fail on
  `plugin/test_install.py::test_successful_install`, and chaos-disconnect is
  UNVERIFIED. Owned by `QA-TERMINAL-JAIL-32`/`-33`.
- **Release tooling present.** `docs/releasing.md`, `scripts/release-cut-check.sh`,
  and `.github/workflows/release.yml` triggered on `tags: ["v*"]` with
  `--verify-tag` plus an asset-set verification step. No generic fallback was
  needed and nothing was tagged.
- **Board.** 347 complete / 25 pending / 13 blocked. Open release rows unchanged:
  `RELEASE-TJ-020`, `RELEASE-TJ-021`, `RELEASE-TJ-022`, `RELEASE-TJ-015`.

No tag, Release, artifact, or board row was created or moved by this pass; no
duplicate readiness row was filed. Delivery of this pass is reported in the
scheduler thread.


