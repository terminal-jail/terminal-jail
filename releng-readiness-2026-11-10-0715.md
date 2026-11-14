# Releng readiness — terminal-jail — 2026-11-10 (pass 2, 07:15Z)

Certified candidate (latest pass): `98db469e372d42f831bc4794966ec44389e4650d` (`origin/main`, pass 7); baseline remains `v1.3.3` at `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. Pass 6 certified `46a218fa` — superseded by board/evidence-only carriers; product tree is unchanged across the bookkeeping interval.

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


## Pass 6 — 2026-11-14 releng tick (`terminal-jail-releng-2026-11-14-11-09-38`)

Certified candidate: `46a218fa33e2482db39db6fc4bbe3912254e5a13` (`origin/main`); baseline `v1.3.3` at `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. The checkout carrier was behind by two board-only commits and had unrelated dirty shared-checkout paths, so all release evidence below was measured from a clean detached worktree at the fetched forge tip. Product paths are byte-identical to the earlier certified tree: `git diff --name-only 8fb5e4b5ad56bd55e1a112684b70476f46300311..origin/main` excluding `.coding-hermes/`, `.gitreins/`, `docs/`, and `releng-readiness-*.md` is empty.

Decision: **NO CUT / NOT READY — v1.3.4 proposed, not tagged.** The post-v1.3.3 range is 57 non-merge commits (58 including the merge count used by the remote comparison); the exact non-merge census is `fix=5`, `feat=0`, `perf=0`, `docs=11`, `test=0`, `ci=0`, `chore=19`, `refactor=0`, `other=22`, with no `BREAKING CHANGE` footer and no bang subject. Five conventional fixes touch shipped code or tests: `88cf92f` and `a48809c` suppress the false mapped Landlock warning; `34bdb22` resynchronizes the bundled wrapper; `9020095` exposes unknown user-rule actions; `ae8524e` adjusts Landlock launch-reachability warning behavior. The semver proposal is PATCH `v1.3.4`; no major confirmation is needed, but version-prep and all release gates remain required.

Candidate CI is green: GitHub Actions run `43590604168` on the exact full SHA is completed/success, with six successful jobs: Audit (pip-audit), Python 3.11, Python 3.12, Python 3.13, Drift guards, and Lint (ruff). The preceding candidate `8aad6df` also has exact-head CI run `43589012810` completed/success with six successful checks. The release workflow is active and tag-triggered (`.github/workflows/release.yml`, `push.tags: ["v*"]`), so tagging is the publication switch, not a harmless staging action.

Release surface is healthy for the previous cut: remote tag `v1.3.3` is immutable at `290d9b0770bd826b2f188ea245e8fdae38da9c9f`; Release is published, non-draft, non-prerelease at `https://github.com/terminal-jail/terminal-jail/releases/tag/v1.3.3`, with exactly `SHA256SUMS` (196 B), `terminal_jail-1.3.3-py3-none-any.whl` (192272 B), and `terminal_jail-1.3.3.tar.gz` (282056 B). Fresh download verification passed: both artifacts returned `OK` under `sha256sum -c SHA256SUMS`.

Repository-owned tooling is present and authoritative: `docs/releasing.md`, `scripts/release-cut-check.sh`, `.github/workflows/release.yml`, and `.github/release.yml`. The release driver is read-only and requires a version-prep tree; `bash scripts/release-cut-check.sh v1.3.4` on the clean candidate exited 1 with four named failures: remote absent-tag probe is treated as unverifiable (the known `RELEASE-TJ-020` defect), `pyproject.toml` remains 1.3.3, `plugin/plugin.yaml` remains 1.3.3, and `CHANGELOG.md` lacks `[1.3.4]`. It confirms CI green on the candidate but cannot authorize this cut. A real candidate artifact strategy probe with `uv build` succeeded from the detached tree, producing sdist/wheel metadata version 1.3.3; this is strategy evidence only, not a v1.3.4 release artifact and was not published. Fresh scratch venv install succeeded from that wheel: `terminal-jail --version` and `importlib.metadata.version("terminal-jail")` both report 1.3.3.

GitReins: **UNVERIFIED for candidate `46a218fa33e2482db39db6fc4bbe3912254e5a13`** — no verdict file is bound to that full SHA. The newest stored verdict is `TJ-DF-064-R2`, run `79b49738`, bound to `8c8097e`, `passed=false` (stale marker binding plus a full-suite failure); the latest stored PASS is `INT-CI-019-V-20261113`, run `f4c607eb`, bound to `f3f3763`, not this candidate. A stale PASS is not inherited.

Dogfood: latest committed 2026-11-14 continuation records are partial, not a clean PASS. The 24-cell battery reports 12 OK, 7 N/A, 4 FAIL, and 1 UNVERIFIED; fresh installation is proven, but `plugin/test_install.py::test_successful_install` remains the root of four FAIL cells owned by `QA-TERMINAL-JAIL-32`, and the isolation cell is explicitly unverified because bunker-mvp uses shared networking. Product-use fire 4 additionally filed `TJ-DF-066` (silent unknown `match.type` no-op), `TJ-DF-067` (stale quarterly CLI checklist), and `TJ-DF-068` (seccomp loader traceback/usage mismatch). These are not release waivers.

Version hygiene is not ready: `pyproject.toml` and `plugin/plugin.yaml` are 1.3.3; no `[1.3.4]` changelog section exists; release-mode `install.sh` defaults to 1.3.1 at line 15 and its usage text repeats 1.3.1 at line 306; `docs/quickstart.md` repeats 1.3.1 at lines 76–77 and older 1.3.0 examples at lines 101, 702, and 735. The canonical row `RELEASE-TJ-022` owns the release-mode default drift. Existing open blockers remain distinct: `RELCI-001` (tag publisher token preflight), `RELEASE-TJ-015` (assetless v1.2.0 Release), `RELEASE-TJ-020` (tag-absence checker), `RELEASE-TJ-021` (hardcoded python3 trampoline), `RELEASE-TJ-022` (release-mode default), `TJ-DF-062`, `TJ-DF-066`, `TJ-DF-067`, `TJ-DF-068`, `QA-TERMINAL-JAIL-11`, `QA-TERMINAL-JAIL-19-R2`, and `QA-TERMINAL-JAIL-32`.

Deployed staleness: the primary `~/.local/bin/terminal-jail` and Hermes plugin manifest both report 1.3.3, so the formerly reported 1.2.0 primary-install finding is resolved. PATH-shadow and legacy `/usr/local` residue remain owned by `OPS-TJ-001`; this sweep did not mutate host installs or PATH configuration.

No tag, Release, remote ref, or deployed surface was mutated. Memory write/readback was not verified in this pass. The board carrier and any final CI receipt remain pending; this pass is the readiness evidence that must be carried by the canonical rolling row, not a release authorization.


## Pass 7 — 2026-11-14 releng tick (`terminal-jail-releng-2026-11-14-11-09-38`) — re-anchored final tip

Certified candidate: `98db469e372d42f831bc4794966ec44389e4650d` (`origin/main`); baseline `v1.3.3` at `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. The earlier Pass 6 candidate `46a218fa` was superseded by four board/evidence-only commits; the product diff from `46a218fa` to this candidate is empty, so the product census and build strategy carry. Candidate-specific hosted CI was re-derived rather than carried: GitHub Actions run `43592218327` is completed/success on this exact SHA with the CI workflow.

## Decision

**NO CUT / NOT READY — propose patch `v1.3.4`; do not create a tag or Release.** The material semver proposal remains PATCH: four conventional `fix:` commits are in the post-v1.3.3 range (`88cf92f`, `a48809c`, `34bdb22`, `9020095`); there are zero `feat`, `perf`, breaking footers, or bang subjects. The exact non-merge range contains 59 commits: 4 `fix`, 19 `chore`, 12 `docs`, and 24 non-conventional/other; the class sum reconciles to 59. All release mutations are withheld because the required version-prep surfaces, candidate-bound GitReins evidence, and clean dogfood disposition are absent, and the repository's release workflow is the publication switch on tag push.

## Known issues

- `RELCI-001` remains open: the tag-triggered publisher's effective Actions token lacks `contents:write`; prior tag workflow runs fail at the token preflight. Workaround: owner/app-admin must change repository/org Actions permissions, or an explicitly authorized hand-publish path must be used for a future immutable tag. Tracking row: `RELCI-001`.
- `RELEASE-TJ-020` remains open: `scripts/release-cut-check.sh` treats an absent remote tag as an unverifiable probe (`git ls-remote --exit-code` returns 2 for an absent ref), so the clean `v1.3.4` check exits 1 even though the tag is absent. Workaround: fix the checker before the cut; do not use a seam as production evidence. Tracking row: `RELEASE-TJ-020`.
- `RELEASE-TJ-021` remains open: the in-jail Landlock/seccomp trampoline still hardcodes `python3`; the latest dogfood/release evidence does not close it. Workaround: keep the existing interpreter-availability limitation explicit; tracking row: `RELEASE-TJ-021`.
- `RELEASE-TJ-022` remains open: release-mode install defaults to `1.3.1` while the latest published release is `1.3.3`, and quickstart contains older version examples. Workaround: set `TERMINAL_JAIL_VERSION` explicitly; tracking row: `RELEASE-TJ-022`.
- Dogfood is not clean: the 24-cell battery is `12 OK, 7 N/A, 4 FAIL, 1 UNVERIFIED`; the four FAIL cells share `plugin/test_install.py::test_successful_install`, and the isolation cell is UNVERIFIED on shared networking. Tracking rows: `QA-TERMINAL-JAIL-32`, `QA-TERMINAL-JAIL-11`, `QA-TERMINAL-JAIL-19-R2`.
- Product-use fire 4 found `TJ-DF-066` (silent unknown `match.type` no-op), `TJ-DF-067` (stale quarterly CLI checklist), and `TJ-DF-068` (seccomp loader traceback/usage mismatch). These remain open and are not release waivers.

## Evidence table

| Layer | Evidence | Verdict |
|---|---|---|
| Remote identity | `git@github.com:terminal-jail/terminal-jail.git`; forge default branch `main`; candidate `98db469e`; no `v1.3.4` remote tag; no `v1.3.4` Release | PASS / absent as expected |
| Commit census | `v1.3.3..98db469e`: 59 non-merge commits; `fix=4`, `feat=0`, `perf=0`, `breaking=0`; PATCH proposed | PATCH proposal |
| Candidate CI | run `43592218327`, exact SHA `98db469e`, completed/success; six CI jobs are represented in the candidate run history | GREEN |
| Repository release tooling | `docs/releasing.md`, `scripts/release-cut-check.sh`, `.github/workflows/release.yml`, `.github/release.yml`; workflow triggers on `push.tags: ["v*"]` and publishes sdist/wheel/checksums | PRESENT; tag is publication |
| Version hygiene | `pyproject.toml=1.3.3`, `plugin/plugin.yaml=1.3.3`, no `[1.3.4]` CHANGELOG section, `install.sh` defaults to `1.3.1`; clean `release-cut-check.sh v1.3.4` returned rc 1 with four failures | BLOCKED |
| Build strategy | `uv build` previously succeeded on the carried product tree and produced 1.3.3 artifacts; `python3 -m build` is unavailable in this environment (`No module named build`); no v1.3.4 artifact was built or published | UNVERIFIED for v1.3.4; no mutation |
| Previous release | remote `v1.3.3` tag immutable at `290d9b0`; published, non-draft/non-prerelease; assets `SHA256SUMS` 196 B, wheel 192272 B, sdist 282056 B; downloaded checksums previously returned `OK` | VERIFIED |
| GitReins | no verdict bound to `98db469e`; latest stored PASS `f4c607eb` is bound to `f3f3763`; a stale PASS is not inherited | UNVERIFIED |
| Dogfood | committed 24-cell ledger: 12 OK, 7 N/A, 4 FAIL, 1 UNVERIFIED; fire 4 adds three open findings | PARTIAL / BLOCKED |
| Deployed surfaces | primary `~/.local/bin/terminal-jail` and Hermes plugin manifest previously report 1.3.3; PATH-shadow/legacy residue remains with `OPS-TJ-001`; this pass did not mutate host state | primary current; residual open |

## Release authorization and mutations

No explicit new owner authorization for `v1.3.4` was present in the triggering metadata or the canonical row. Regardless, this pass does not require authorization to refuse the cut: the version-prep, GitReins, dogfood, and publisher gates are not all green. No tag, Release, remote ref, artifact, deployment, or shared-checkout dirty path was mutated by this pass. `WAVE_BUDGET=2`; no worker wave was dispatched because this is a verification-only releng sweep and the blockers are not worker-ready from this lane.

The canonical rolling row is `RELEASE-TJ-022`; this pass updates the existing evidence record rather than creating a duplicate readiness row. The board carrier and its final carrier CI receipt remain pending until the row/artifact correction is landed through the repository's normal writer path.