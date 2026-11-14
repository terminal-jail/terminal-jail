# Releng readiness — terminal-jail — 2026-11-14 (pass 12)

Certified candidate (latest pass): `5a51e0f8dc5cbfbb277be62af0512602dcc6a731` (`origin/main`, pass 12); baseline remains `v1.3.3` at `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. Pass 11 certified `889abcba` — superseded only by board/evidence bookkeeping (`5a51e0f` moves no product path). Pass 10 certified `6b12f620` — superseded by later board/evidence-only carriers and the current fresh candidate.

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

## Pass 8 — 2026-11-14T12:27Z (third fire over an unchanged product tree)

Premise stated before the sweep: passes 6 and 7 fired within the previous 45 minutes
against the same product tree and both returned NO CUT. This pass re-derived every gate
at the live tip `b31e286` rather than carrying either result. It does not change the
verdict — it changes the shape of the outcome. The blocker all three of those passes
name, the absent version-prep commit, had no board row requesting it, so no foreman
could ever have executed it. Every prior pass wrote the requirement into a document and
left the board untouched. Pass 8 files it as `RELEASE-TJ-023`.

### Interval measurement

| Layer | Evidence | Verdict |
|---|---|---|
| Last product-path commit | `8aad6df` 2026-11-14 06:13:29 -05 `docs(dogfood): fire 4` | baseline |
| Commits since, all bookkeeping | 6: `c098846`, `46a218f`, `54d5994`, `98db469`, `774f220`, `b31e286` | zero product delta |
| Releng fires in that interval | pass 6 11:49Z, pass 7 12:13Z, pass 8 12:27Z (this) | 3 fires, ~45 min |
| Product tree delta across fires | `git diff --name-only 98db469..HEAD` minus board/docs/gitreins paths is empty | IDENTICAL |

### Decision

**NO CUT / NOT READY — the `v1.3.4` PATCH proposal is unchanged and still not tagged.**
Re-derived, not inherited: `v1.3.3..b31e286` is 61 non-merge commits with `fix=4`
(`88cf92f`, `a48809c`, `34bdb22`, `9020095`), `feat=0`, `perf=0`, `chore=19`, `docs=13`,
and 25 non-conventional subjects; there is no bang subject and no real breaking footer
(the single `BREAKING CHANGE` string in the range is the prose negation inside commit
`7789fb3`'s own body: "feat/fix/perf/bang 0, no BREAKING CHANGE"). Class sum reconciles
to 61. PATCH is the correct magnitude; no major confirmation is owed.

Nothing in the four gates moved since pass 7. `release-cut-check.sh v1.3.4` still exits
1 on the clean detached candidate with the same four named failures: the absent-tag probe
(`RELEASE-TJ-020`), `pyproject.toml=1.3.3`, `plugin/plugin.yaml=1.3.3`, and no `[1.3.4]`
CHANGELOG section. The first of those is the checker defect, not a release condition —
this pass observed the checker printing both "FAIL: could not verify whether tag
'v1.3.4' exists remotely" and "OK: tag 'v1.3.4' does not exist yet" in one run, which is
the defect stated as plainly as it can be: `git ls-remote --exit-code` returns 2 for an
absent ref and the script treats that as an unverifiable probe. Do not buy a green here
with the `TJ_RELEASE_TAG_EXISTS` seam; fix the probe.

### New this pass: the version-prep requirement is now dispatchable

`RELEASE-TJ-023` is filed pending with executable acceptance criteria: land the version-prep
commit (`pyproject.toml` 1.3.4, `plugin/plugin.yaml` 1.3.4, `CHANGELOG.md` `[1.3.4]` section
opened from the four `fix:` commits above), proven by `bash scripts/release-cut-check.sh
v1.3.4` reporting the three version surfaces OK. It deliberately does not require
`RELCI-001` — that row is P1, blocked, and owner-gated on the publisher; a worker can close
version-prep without touching publication. Precedent for landing a version bump ahead of its
tag is the repository's own: `290d9b0` bumped to 1.3.3 and opened its changelog section
before `v1.3.3` was cut.

### Why this lane should be gated

Three passes in 45 minutes over a byte-identical product tree produced three decision
documents and zero executed changes. The blockers are not discovered by more sweeps: one
is a checker bug already tracked (`RELEASE-TJ-020`), one is owner-gated (`RELCI-001`), one
needed a board row and now has it (`RELEASE-TJ-023`). Recommendation: gate this lane on a
material product commit (or a 24h floor) rather than its current cadence, and treat a fire
with no material delta as a no-op that appends nothing.

| Layer | Evidence (pass 8) | Verdict |
|---|---|---|
| Remote identity | `git@github.com:terminal-jail/terminal-jail.git`; default branch `main`; candidate `b31e286`; remote tags stop at `v1.3.3`; no `v1.3.4` tag or Release | PASS / absent as expected |
| Candidate CI | run `43593982061` on exact SHA `b31e286`, completed/success; runs `43592218327` (`98db469`) and `43593725366` (`774f220`) also success | GREEN |
| Version hygiene | `pyproject.toml=1.3.3`, `plugin/plugin.yaml=1.3.3`, no `[1.3.4]` CHANGELOG, `install.sh:15` still defaults to `1.3.1`; checker rc 1, four failures | BLOCKED |
| GitReins | no verdict bound to `b31e286`; latest stored PASS `f4c607eb` binds `f3f3763`; stale PASS not inherited | UNVERIFIED |
| Dogfood | committed 24-cell ledger 12 OK / 7 N/A / 4 FAIL / 1 UNVERIFIED, unchanged; FAIL cluster is `plugin/test_install.py::test_successful_install` under `QA-TERMINAL-JAIL-32` | PARTIAL |
| Deployed surfaces | `~/.local/bin/terminal-jail --version` = 1.3.3; `~/.hermes/plugins/terminal-jail/plugin.yaml` = 1.3.3 | CURRENT for v1.3.3 |
| Board state | 394 rows at the candidate: 348 complete, 32 pending, 13 blocked, 1 unstatused; `RELEASE-TJ-023` next free id, now filed (HEAD after this pass: 397 rows, 35 pending) | HEALTHY |

No tag, Release, remote ref, artifact, deployment, or shared-checkout path was mutated by
this pass. `WAVE_BUDGET=2`; no worker was dispatched — the one worker-ready unit is now a
board row for the foreman, which is the correct owner for it.

## Pass 9 — 2026-11-14T12:52Z (re-anchored final tip; no-cut readiness sweep)

The forge default branch advanced from the prior recorded candidate `b31e286` to
`8dd90ab` through two board-only commits. The product tree is unchanged across
that interval, but all exact-head receipts were refreshed against the new full SHA.
The shared checkout `/home/kara/terminal-jail` remains behind `origin/main` by two
commits and has unrelated dirty files; it was not used for release writes.

### Decision

**NO CUT / NOT READY — propose patch `v1.3.4`; do not create a tag or Release.**
The post-v1.3.3 range is 64 non-merge commits. The reconciled conventional buckets
are `fix=4`, `feat=0`, `perf=0`, `docs=14`, `test=0`, `ci=0`, `chore=19`,
`refactor=0`, `other=27`; the sum is 64. The four shipped-code fixes remain
`88cf92f`, `a48809c`, `34bdb22`, and `9020095`. There are no bang subjects and no
breaking footer. This is a PATCH proposal; no major confirmation is owed.

The no-cut decision is not inherited from an older SHA. The final candidate has
completed exact-SHA CI, but version preparation is absent, GitReins is not proven on
this candidate, dogfood is partial with known failures, and tagging is the publication
switch.

### Evidence table

| Layer | Evidence | Verdict |
|---|---|---|
| Identity | Release remote `origin` = `git@github.com:terminal-jail/terminal-jail.git`; forge repo `terminal-jail/terminal-jail`; default branch `main`; candidate `8dd90ab22cc7681606365838ae0df99936deeea5`; baseline `v1.3.3` peels to `290d9b0770bd826b2f188ea2455e5f1bac67` | PASS |
| Release surface | `git ls-remote origin refs/tags/v1.3.4` returned empty with rc 0; `gh release view v1.3.4` returned `release not found`; existing v1.3.3 remains published, immutable, non-draft/non-prerelease with exactly three assets: `SHA256SUMS`, wheel, sdist | NO v1.3.4 mutation |
| Commit census | `v1.3.3..8dd90ab`: 64 non-merge commits; `fix=4`, `feat=0`, `perf=0`, `breaking=0`; PATCH proposal | PATCH |
| Candidate CI | GitHub Actions run `43596146807` on exact SHA `8dd90ab22cc7681606365838ae0df99936deeea5`, completed/success; check-runs total 6, all six completed/success: Python 3.11/3.12/3.13, Lint, Audit, Drift guards | GREEN |
| Release tooling | Repository-owned `docs/releasing.md`, `scripts/release-cut-check.sh`, `.github/workflows/release.yml`, `.github/release.yml`; tag workflow triggers on `push.tags: ["v*"]`, builds sdist/wheel/checksums, creates Release; a tag is publication, not staging | PRESENT; withheld |
| Version hygiene | Candidate still has `pyproject.toml=1.3.3`, `plugin/plugin.yaml=1.3.3`, no `[1.3.4]` changelog section; release-mode default remains `install.sh:15=1.3.1`, usage line 306 repeats it, quickstart repeats 1.3.1 and stale 1.3.0 examples | BLOCKED; rows `RELEASE-TJ-023`, `RELEASE-TJ-022` |
| Release checker | `bash scripts/release-cut-check.sh v1.3.4` was not a valid candidate probe from the detached worktree because the command was invoked outside its repository and returned rc 1 with `not a git repository`; independently, the known production defect remains: the checker uses `git ls-remote --exit-code`, while the direct absence probe returned rc 0 with empty output. Do not treat the invalid invocation as release evidence; row `RELEASE-TJ-020` remains open | UNVERIFIED for checker run |
| GitReins | No verdict file is bound to exact candidate `8dd90ab`; latest exact stored PASS is `INT-CI-019-V-20261113`, run `f4c607eb`, bound to `f3f3763`; latest stored verdict `TJ-DF-064-R2`, run `79b49738`, is FAIL on `8c8097e`; stale PASS is not inherited | UNVERIFIED |
| Dogfood | Latest committed 24-cell ledger: 12 OK, 7 N/A, 4 FAIL, 1 UNVERIFIED; shared root `plugin/test_install.py::test_successful_install` remains owned by `QA-TERMINAL-JAIL-32`; fire 5 skipped install proof because `bunkerd` was unreachable and the on-file proof predates the product changes; open product-use findings include `TJ-DF-066`, `TJ-DF-067`, `TJ-DF-068`, `TJ-DF-069` | PARTIAL / BLOCKED |
| Deployed surfaces | `/home/kara/.local/bin/terminal-jail --version` = `terminal-jail 1.3.3`; `/home/kara/.hermes/plugins/terminal-jail/plugin.yaml` = `1.3.3`; PATH shadow/legacy residue remains owned by `OPS-TJ-001`; no host mutation | Current for v1.3.3; residual open |
| Prior release | `gh release view v1.3.3` confirmed published, non-draft/non-prerelease, exact assets: `SHA256SUMS` 196 B, `terminal_jail-1.3.3-py3-none-any.whl` 192272 B, `terminal_jail-1.3.3.tar.gz` 282056 B | VERIFIED |

### Known issues

- `RELCI-001` remains blocked: tag-triggered publisher fails its `contents:write` preflight; manual publishing is required until owner/app-admin changes Actions permissions.
- `RELEASE-TJ-020` remains open: the checker’s tag-absence implementation is not production-safe; fix it before relying on the pre-cut gate.
- `RELEASE-TJ-021` remains open: in-jail Landlock/seccomp trampoline still hardcodes `python3` for the off-PATH case.
- `RELEASE-TJ-022` remains open: release-mode install defaults to 1.3.1 while v1.3.3 is current; explicit `TERMINAL_JAIL_VERSION` is the workaround.
- `QA-TERMINAL-JAIL-32` remains open: clean-machine install battery fails at `plugin/test_install.py::test_successful_install`; this is not cleared by the partial ledger.
- `TJ-DF-069` remains open: install proof was skipped/unverified because `bunkerd` was unreachable and the prior proof predates the current product tree.
- `TJ-DF-066`, `TJ-DF-067`, and `TJ-DF-068` remain open product-use findings.

### Release authorization and mutations

No tag, Release object, remote tag, artifact, deployment, or host surface was mutated.
No worker wave was dispatched (`WAVE_BUDGET=2`); this is a verification-only pass and
`RELEASE-TJ-023` already owns the dispatchable version-prep work. Memory persistence is
UNVERIFIED: the only DuckBrain call sent during this tick was an unscoped empty
`list_keys` invocation, which returned unrelated default-namespace keys; no project
scoped release record was read or written.

## Pass 10 — 2026-11-14T11:09 tick (re-anchored final tip)

Certified candidate: `6b12f6207d72ba7b049ccbb863715faac1075e6d` (`origin/main`); baseline `v1.3.3` peels to `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. The shared checkout `/home/kara/terminal-jail` is behind origin/main by 9 commits and carries unrelated dirty paths; it was used for reads only. No tag, Release, artifact publication, deployment, or host mutation was performed.

## Decision

**NO CUT / NOT READY — propose patch `v1.3.4`; no tag or Release.** The exact non-merge census is 71 commits. The reconciled primary buckets are `fix=4`, `feat=0`, `perf=0`, `docs=15`, `test=0`, `ci=0`, `chore=19`, `refactor=0`, `other=33`; sum 71. No bang subjects or `BREAKING CHANGE` footers were found. PATCH is the correct semver magnitude; no major confirmation is required.

The candidate CI is now terminal green, but the release remains blocked by missing version preparation, GitReins not bound to this candidate, and partial/open dogfood evidence. The repository-owned release workflow makes a tag the publication switch, so tagging is not a staging action.

## Evidence table

| Layer | Evidence | Verdict |
|---|---|---|
| Identity | `origin` = `git@github.com:terminal-jail/terminal-jail.git`; forge repo `terminal-jail/terminal-jail`; default branch `main`; candidate `6b12f6207d72ba7b049ccbb863715faac1075e6d`; baseline tag `v1.3.3` | PASS |
| Commit census | `v1.3.3..6b12f62`: 71 non-merge commits; `fix=4`, `feat=0`, `perf=0`, `breaking=0`; primary sum reconciles to 71 | PATCH proposal |
| Candidate CI | GitHub Actions run `43597991326` on exact candidate SHA; completed/success; Python 3.11/3.12/3.13, Lint, Audit, Drift guards all success | GREEN |
| Version hygiene | candidate `pyproject.toml=1.3.3`, `plugin/plugin.yaml=1.3.3`, no `[1.3.4]` CHANGELOG section; release-mode `install.sh` defaults to 1.3.1 at lines 15 and 306 | BLOCKED; `RELEASE-TJ-022` and `RELEASE-TJ-023` |
| Release tooling | candidate contains `docs/releasing.md`, `scripts/release-cut-check.sh`, `.github/workflows/release.yml`, `.github/release.yml`; tag workflow triggers on `push.tags: ["v*"]`, builds sdist/wheel/checksums and creates/verifies a GitHub Release | PRESENT; withheld |
| Repository pre-cut check | In a clean detached candidate worktree, `bash scripts/release-cut-check.sh v1.3.4` exited 1: 4 failures — absent-tag probe defect (`RELEASE-TJ-020`), pyproject mismatch, plugin manifest mismatch, missing CHANGELOG section; it independently printed `OK: CI green on HEAD 6b12f62` | BLOCKED |
| Build strategy | `uv build --out-dir` completed 0 on the candidate and produced `terminal_jail-1.3.3.tar.gz` (282351 B) and `terminal_jail-1.3.3-py3-none-any.whl` (192533 B); this is strategy evidence only, not a v1.3.4 artifact; the build emitted setuptools license deprecation warnings | PASS for current package build; not release evidence |
| Previous release | `v1.3.3` is published, non-draft/non-prerelease, with `SHA256SUMS` 196 B, wheel 192272 B, sdist 282056 B; no v1.3.4 tag or Release was created | VERIFIED / no new mutation |
| GitReins | No stored verdict is bound to candidate `6b12f62`; latest stored verdict `79b49738` is a FAIL bound to `8c8097e`; latest stored PASS `f4c607eb` is bound to `f3f3763`; stale verdicts are not inherited | UNVERIFIED |
| Dogfood/QA | Open findings at candidate include `TJ-DF-066` (unknown match.type silently no-ops), `TJ-DF-067` (stale quarterly CLI checklist), `TJ-DF-068` (seccomp `--`/traceback contract), `TJ-DF-069` (fresh-machine install proof skipped on current tree), `QA-TERMINAL-JAIL-32` (install battery red), plus other pending/blocked QA rows; the latest committed install ledger is partial rather than a clean product-use PASS | PARTIAL / BLOCKED |
| Deployed binary | `/home/kara/.local/bin/terminal-jail --version` reports `terminal-jail 1.3.3`, mtime `2026-11-10 05:13:36 -0500`, matching the last published release; no host refresh was performed | CURRENT for v1.3.3 |

## Release blockers

1. `RELEASE-TJ-023` — version-prep worker row is pending; it must land 1.3.4 in pyproject, plugin manifest and CHANGELOG, then prove the repository checker and full suite. It must not tag or publish.
2. `RELEASE-TJ-020` — `release-cut-check.sh` uses `git ls-remote --exit-code` and treats an absent tag as an unverifiable failure; current candidate check reproduces the defect.
3. `RELCI-001` — tag-triggered publisher lacks effective `contents:write`; the workflow's preflight has previously red. The owner/app-admin fix or an explicitly authorized manual publish is required for a future tag.
4. `RELEASE-TJ-022` — release-mode default remains 1.3.1 while v1.3.3 is latest, independent of the 1.3.4 cut.
5. Dogfood/QA remains partial with open product-use and harness rows; no clean full dogfood verdict is available for this candidate.

## Authorization and wave

No major confirmation is needed because the measured bump is PATCH. No worker wave was dispatched (`WAVE_BUDGET=2`); version prep is already owned by `RELEASE-TJ-023`, and this satellite verifies rather than develops.

Memory leg: UNVERIFIED. The lane metadata resolved namespace `releases`, but this assistant submitted empty, unscoped list_keys and recall arguments. Those calls returned unrelated default-namespace records and are unusable as project history. This was an invocation error, not evidence of a transport mutation or unavailable namespace. No scoped memory read or write succeeded; the memory leg was stopped.


### Pass 10 correction of record

The header baseline was malformed in the initial pass-10 evidence; it is now read directly from `git rev-parse v1.3.3^{commit}`: `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. Earlier historical sections are retained verbatim. The exact NUL-delimited subject/body census was re-run: 71 accepted full-SHA records, zero breaking footers or bang subjects. Non-conventional shipped-code commit `ae8524e` (`fix landlock launch reachability warning`) is material even though it is in the `other` bucket; the four conventional fixes are `88cf92f`, `a48809c`, `34bdb22`, `9020095`. Five fix-like commits do not imply five independent behavioral changes; the patch proposal is unchanged.

The board status census at candidate is 397 rows: 348 complete, 35 pending, 13 blocked, 1 without status. Existing RELEASE-TJ-023 is dispatchable version-prep work; no duplicate finding was filed. The public-state/dependency audit, fresh full local suite, and new candidate-bound GitReins judge were not completed this pass; no release-grade PASS is claimed for them.

Event 1019 supersedes event 1018's premature evidence-as-carrier field. Final carrier identity and its exact-SHA CI are reported outside the row to avoid a self-referential commit loop. The row's original installer-default acceptance contract remains unchanged. The guard-generated `.vfs/graph/edges.jsonl` change accidentally entered carrier cb0df26; it is restored byte-for-byte to the certified candidate in this correction.

## Pass 11 — 2026-11-14T13:30Z (fresh readiness sweep; no cut)

Certified candidate: `889abcba26c73f77fb8a39870236a88dadd0b7d9` (`origin/main`); forge default branch `main`; baseline `v1.3.3` peels to `290d9b0770bd826b2f188ea245e8fdae38da9c9f`. The product checkout `/home/kara/terminal-jail` is a shared, dirty carrier behind the forge tip; all write-intended work used the detached candidate worktree `/home/kara/.hermes/cache/scratch/tj-releng-wt`.

## Decision

**NO CUT / NOT READY — propose patch `v1.3.4`; no tag or Release created.** The patch proposal is driven by four conventional `fix:` commits that change shipped code; there are no `feat`, `perf`, bang, or `BREAKING CHANGE` markers. Tagging is withheld because the version-prep surfaces are still 1.3.3, the candidate has no GitReins verdict, and dogfood remains partial with open product findings. The repository-owned tag workflow is the publication switch, not a staging action.

## Known issues

- `RELEASE-TJ-023`: version-prep is still pending; pyproject/plugin remain 1.3.3 and CHANGELOG has no `[1.3.4]` section. It must land before any tag.
- `RELEASE-TJ-020`: `scripts/release-cut-check.sh` still treats `git ls-remote --exit-code` exit 2 for an absent tag as a probe failure. The clean candidate check reproduced this and exited 1 with four failures. Do not use the test seam as production evidence.
- `RELCI-001`: the tag publisher's effective Actions token previously failed its `contents:write` preflight; manual publication remains the documented fallback until the owner/app-admin fixes permissions.
- `RELEASE-TJ-022`: release-mode install defaults to 1.3.1 while v1.3.3 is latest; explicit `TERMINAL_JAIL_VERSION` is the workaround.
- Dogfood remains incomplete: the 24-cell ledger is 12 OK / 7 N/A / 4 FAIL / 1 UNVERIFIED; open product-use findings include `TJ-DF-066`, `TJ-DF-067`, `TJ-DF-068`, and `TJ-DF-069`; `QA-TERMINAL-JAIL-32` owns the install-suite failure.
- `RELEASE-TJ-021`: in-jail Landlock/seccomp trampolines still hardcode `python3` for the off-PATH case.

## Evidence table

| Layer | Evidence | Verdict |
|---|---|---|
| Identity | `origin` = `git@github.com:terminal-jail/terminal-jail.git`; forge repo `terminal-jail/terminal-jail`; default `main`; candidate `889abcba26c73f77fb8a39870236a88dadd0b7d9`; baseline `v1.3.3` -> `290d9b0770bd826b2f188ea245e8fdae38da9c9f` | PASS |
| Commit census | `v1.3.3..889abcba`: 75 non-merge commits; `feat=0`, `fix=4`, `perf=0`, `docs=17`, `test=0`, `ci=0`, `chore=19`, `refactor=0`, `other=35`; sum reconciles to 75; zero breaking footers/bang subjects | PATCH proposal |
| Material fixes | `88cf92f`, `a48809c`, `34bdb22`, `9020095`; ten non-excluded installed-code/test paths changed in the range | PATCH due |
| Candidate CI | GitHub Actions run `43599584529` on exact SHA `889abcba26c73f77fb8a39870236a88dadd0b7d9`; completed/success; six check-runs all success: Python 3.11/3.12/3.13, Lint, Audit, Drift guards | GREEN |
| Release tooling | `docs/releasing.md`, `scripts/release-cut-check.sh`, `.github/workflows/release.yml`, `.github/release.yml`; tag trigger `push.tags: ["v*"]`; workflow builds sdist/wheel/checksums and creates/verifies a GitHub Release | PRESENT; withheld |
| Repository pre-cut check | In the clean candidate worktree, `bash scripts/release-cut-check.sh v1.3.4` exited 1: absent-tag probe defect plus pyproject/plugin mismatch and missing changelog section; it independently printed `OK: CI green on HEAD 889abcb` | BLOCKED |
| Version hygiene | `pyproject.toml=1.3.3`, `plugin/plugin.yaml=1.3.3`, no `[1.3.4]` section; `install.sh:15` and `:306` still name default 1.3.1 | BLOCKED |
| Previous release | Remote `v1.3.3` tag is immutable at `290d9b0`; GitHub Release is published, non-draft/non-prerelease, with exactly `SHA256SUMS`, the 1.3.3 wheel, and the 1.3.3 sdist | VERIFIED |
| GitReins | No stored verdict is bound to candidate `889abcba`; latest stored PASS `f4c607eb` is bound to `f3f3763`, and stored verdicts on older SHAs are not inherited | UNVERIFIED |
| Dogfood/QA | Latest committed install ledger: 24 cells, 12 OK / 7 N/A / 4 FAIL / 1 UNVERIFIED; fire 5 says the modify path is broken on this host and install proof was skipped; open rows own these findings | PARTIAL / BLOCKED |
| Deployed surfaces | Primary `~/.local/bin/terminal-jail` and Hermes plugin manifest report 1.3.3; PATH-shadow/legacy residue remains under `OPS-TJ-001`; no host mutation performed | CURRENT for v1.3.3; residual open |

## Release authorization and mutations

PATCH requires no major confirmation, but no release mutation is authorized by this pass. No tag, Release, artifact publication, deployment, host install, or shared-checkout cleanup was performed. `WAVE_BUDGET=2`; no worker was dispatched because version preparation is already owned by `RELEASE-TJ-023` and this satellite verifies rather than develops. Memory persistence is UNVERIFIED: the required scoped DuckBrain calls could not be dispatched because the wrapper emitted empty/unscoped arguments; the returned default-namespace keys are unusable as project history.

---

## Pass 12 — 2026-11-14T13:42Z — NO NEW DECISION (byte-identical product tree)

This pass re-anchors to the tip and measures **the interval, not the tip**. Since
pass 11 certified `889abcba`, `origin/main` moved by exactly two commits and
**zero product paths**:

| Measure | Value | Verdict |
|---|---|---|
| Interval | `889abcba..5a51e0f` = 2 commits (`6545f1b` docs(releng) pass-11 artifact, `5a51e0f` board(releng) pass-11 row binding); both bookkeeping | NO MATERIAL DELTA |
| Material paths in interval | 0 (the only changed files are `.coding-hermes/board/tasks.jsonl` and `releng-readiness-2026-11-10-0715.md`) | PRODUCT TREE BYTE-IDENTICAL to pass 11 |
| Tip CI | GitHub Actions run `43600771735` on exact SHA `5a51e0f8dc5cbfbb277be62af0512602dcc6a731`; completed / success | GREEN |
| Version hygiene | `pyproject.toml=1.3.3`, `plugin/plugin.yaml=1.3.3`, no `v1.3.4` tag on the remote (`git ls-remote` returned no `refs/tags/v1.3.4`), no `v1.3.4` Release object | UNCHANGED — version prep still absent, owned by `RELEASE-TJ-023` |
| Previous release | `v1.3.3` Release published, non-draft/non-prerelease, exactly 3 assets (`SHA256SUMS` 196 B, wheel 192272 B, sdist 282056 B); tag immutable at `290d9b0` | VERIFIED |
| GitReins | No stored verdict is bound to `5a51e0f`; newest stored record is `.gitreins/history/2026-11-13/f4c607eb` bound to `f3f3763`; verdicts are not inherited across SHAs | UNVERIFIED |
| Dogfood/QA | No new installer ledger since pass 11; `RELEASE-TJ-022` carries the 24-cell ledger (12 OK / 7 N/A / 4 FAIL / 1 UNVERIFIED) | PARTIAL / BLOCKED (unchanged) |
| Deployed surfaces | `~/.local/bin/terminal-jail --version` -> `terminal-jail 1.3.3`; Hermes plugin manifest `version: "1.3.3"` | CURRENT for v1.3.3 |
| Board backlog | 397 rows: 348 complete, 35 pending, 13 blocked; release-family open rows are `RELEASE-TJ-015`, `RELEASE-TJ-020`, `RELEASE-TJ-021`, `RELEASE-TJ-022`, `RELEASE-TJ-023`, plus `RELCI-001` blocked | UNCHANGED |

**Decision: NO CUT, and no new decision is owed.** The v1.3.4 PATCH gate set is
identical to pass 11's: version prep absent (`RELEASE-TJ-023`), GitReins
unverified on any current SHA, dogfood partial. Nothing in the two-commit
interval could have changed any of those three.

### Residue found and published this pass

Pass 11's board **event `1020`** (`task_updated RELEASE-TJ-022`, actor
`foreman`, `13:38:01Z`) was written into its scratch worktree but **never
committed**: the worktree at `.hermes/cache/scratch/tj-releng-wt` carried it as
an uncommitted `M .coding-hermes/board/events.jsonl` while only
`tasks.jsonl` was staged into `5a51e0f`. The row change itself is canonical, so
the audit trail had a hole rather than a wrong value. This pass publishes that
line unchanged, attributed, together with its own event — no mutation of pass
11's row.

### Lane cadence note (repeated, now with numbers)

This tick id has now fired six times against an unchanged product tree
(passes 3, 6, 7, 8, 11, 12), the last carrier landing four minutes before this
fire (pass 11 carried `13:38:22Z`; this pass started `13:42Z`). Each pass costs
one artifact commit, one board carry, and one CI run on a tree that cannot
produce a different verdict. The material-event gate this lane should run under
is: **fire only when `git rev-list --no-merges --count <last-certified>..origin/main`
over non-bookkeeping paths is > 0, when an owner ruling is recorded, or when a
`RELEASE-*`/`RELCI-*` row changes state** — otherwise report `NO MATERIAL
DELTA` from the previous certification instead of publishing a new one.

No mutation was authorized or performed this pass: no tag, no Release, no
artifact publication, no deployment, no host install, no shared-checkout
cleanup. `WAVE_BUDGET=2`, zero workers dispatched — this satellite verifies and
`RELEASE-TJ-023` already owns the only dispatchable work.
