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

## Pass 2 — 2026-11-09 (re-delivery, premise CORRECTED; v1.3.2 CUT)

Same tick id re-delivered. The standing record was re-verified in full and its
**central premise was refuted**, so this pass records a decision CHANGE, not a
refreshed no-cut.

### Standing record re-verification (before anything else)

- Artifact hash from the FETCHED remote equals the canonical row's last
  evidence entry: `git show origin/main:releng-readiness-2026-11-09-0456.md |
  sha256sum` = `817a6cc821ab9f4d80ec2956294097371642c07b013a2d10c766c01af776e620`
  = `RELEASE-TJ-016.detail.evidence[-1].tree_fp` (2 entries). Bytes intact.
- Row readback: `RELEASE-TJ-016` status=pending, updated 2026-11-09T05:15:54Z.
- Both prior passes' carriers are green on their own exact SHAs:
  03641d9 = run 42564157843 success; 007d9d2 = 42565668859; 6246023 =
  42566096780; 9862357 = 42566294325 (all six jobs success).

### The refuted premise (this pass's finding of record)

Pass 1 stated: *"The only material source change in the 33-commit range is
4f64a206 fix(packaging), already shipped in v1.3.1 … already reachable from
v1.3.1."* That is FALSE. Receipts:

    $ git merge-base --is-ancestor 4f64a206 v1.3.1 ; echo rc=$?
    rc=1                                   # NOT in v1.3.1
    $ git merge-base --is-ancestor v1.3.1 4f64a206 ; echo rc=$?
    rc=0                                   # v1.3.1 predates the fix
    $ git log -1 --format='%ci' 4f64a206      -> 2026-11-08 11:34:00 -0500
    $ git log -1 --format='%ci' e4741912      -> 2026-11-04 10:08:27 -0500
    $ git diff v1.3.1 4f64a206^ -- <the 4 loaders> | wc -l
    0                                      # v1.3.1 == the PRE-fix content
    $ git diff --stat v1.3.1 4f64a206 -- plugin/terminal_jail/_bundled/ \
        standalone/landlock-loader.py standalone/landlock-net-loader.py
     4 files changed, 36 insertions(+), 4 deletions(-)   (+2 test files, +288 total)

Classification: the fix landed **four days after** the v1.3.1 tag, so no
published artifact contains it, and the published v1.3.1 wheel still degrades
both Landlock tiers. This is a material fix (Decision-1 rule 5 → PATCH), not
rule 3.

### Carrier advance (not new product content)

`03641d9..4d3bd7e` = 4 commits, path delta
`.coding-hermes/board/{events,tasks}.jsonl` + this artifact — bookkeeping only.
Per the standing rule this does not re-open the census by itself; it is
superseded here because the **decision** changed, not because the carrier moved.

### Rebuilt census — v1.3.1..f7ce3ef (the CUT commit)

    38 commits = 20 chore + 8 docs + 5 release + 2 pm + 1 fix + 1 board
                 + 1 merge;  BREAKING CHANGE: 0;  type! subjects: 0
    material: 1 fix (4f64a206) + the version-prep commit f7ce3ef
    bookkeeping: 35 (reconciles: 38 total)

### Gates at the cut

- Version-prep commit `f7ce3ef` — pyproject 1.3.1→1.3.2, plugin/plugin.yaml
  1.3.1→1.3.2, new `## [1.3.2] — 2026-11-09` CHANGELOG section ([Unreleased]
  untouched). `tests/test_version.py` 3 passed; `scripts/docs-check.py`
  overall PASS (`standalone --version` → 1.3.2).
- Hosted CI on `f7ce3ef` — run **42569431104** completed **success**, all six
  jobs: Lint (ruff), Drift guards, Audit (pip-audit), Python 3.11/3.12/3.13.
- `scripts/release-cut-check.sh v1.3.2` (repo's own driver, clean detached
  worktree at the certified SHA): tag absent OK, tree clean OK, version match
  OK, CI green on HEAD OK → `READY: 0 failure(s)`. The only initial dirt was
  `.vfs/graph/edges.jsonl` regenerated by the commit hook; restored to the
  certified tree's bytes before the check.

### Release leg (tag, publisher, publication)

- Annotated tag `v1.3.2` → `f7ce3ef593e112cb2adff0db659d9486c3fc5c9f`
  (tag object `5e6d675`, pushed, remote-verified; no existing tag moved).
- Tag-triggered `Release` run **42569796687** = **failure**, and NOT on the
  tree: it fails its own first step, `GITHUB_TOKEN for
  terminal-jail/terminal-jail lacks push (contents:write) permission`. That is
  **RELCI-001**, still open and owner/org-admin scoped. No artifact was built
  by the run and no Release object was created by it.
- Published ONCE, by hand, per `docs/releasing.md` step 5b — from a clean
  checkout at the tag, never competing with the workflow:
  `uv build --out-dir …` → sdist + wheel; `sha256sum` → SHA256SUMS;
  `gh release create v1.3.2 … --verify-tag`.
  Release: https://github.com/terminal-jail/terminal-jail/releases/tag/v1.3.2
- Assets (verified independently on the Release object, non-draft,
  non-prerelease): `terminal_jail-1.3.2.tar.gz` 279418 B,
  `terminal_jail-1.3.2-py3-none-any.whl` 191566 B, `SHA256SUMS` 196 B.

    d1a1c51f70d39d1a543c55eb3ebbd107958ef196a6bc0fd7771b9a8f2581fe49  terminal_jail-1.3.2.tar.gz
    266ca3ab7d21c8d6acefd6c1ec4a095cdff188b9a087f1bcb79d0f1fb4acbdd1  terminal_jail-1.3.2-py3-none-any.whl

- Shipped-artifact proof, from the DOWNLOADED bytes (not the build dir):
  `gh release download` → `sha256sum -c SHA256SUMS` both OK → fresh venv
  `pip install terminal_jail-1.3.2-py3-none-any.whl` → `terminal-jail
  --version` prints `1.3.2` rc=0 → loader probe on the installed tree:

    landlock-loader.py:     _find_landlock_module()     -> .../site-packages/terminal_jail/interruptor/landlock.py
    landlock-net-loader.py: _find_landlock_net_module() -> .../site-packages/terminal_jail/interruptor/landlock_net.py
    PROBE: RESOLVED

  i.e. the TJ-DF-060 defect ("tier module not found next to the loader") is
  gone in the published wheel — the effect, not just the version string.

### Carried blockers, re-probed at this tip (not carried on trust)

- **RELEASE-TJ-014** (deployed artifacts stale) — STILL LIVE, and the gap
  WIDENED: `/home/kara/.local/bin/terminal-jail` → `terminal-jail 1.2.0`
  (mtime 2026-10-13); `~/.hermes/plugins/terminal-jail/plugin.yaml` → 1.2.0.
  It is now three releases behind: missing 1.3.0, 1.3.1, 1.3.2.
- **RELEASE-TJ-015** (v1.2.0 Release carries zero assets) — STILL LIVE,
  re-measured: v1.2.0=0 assets, v1.3.0=3, v1.3.1=3, v1.3.2=3.
- **TJ-DF-062** (release-mode installer asset mismatch) — STILL LIVE:
  `install.sh:21` still defaults `TERMINAL_JAIL_VERSION=1.2.0` and
  `install.sh:1343` still downloads `terminal-jail.sha256`, which no release
  (including v1.3.2) publishes. The release notes name it so no installer user
  is misled.
- **RELCI-001** (tag workflow cannot publish) — STILL LIVE, re-proved on this
  very cut by run 42569796687 rather than quoted from history.
- **RELEASE-TJ-013** (v1.3.1 notes/version-prep hygiene) — historical record,
  not re-opened; the v1.3.2 notes disclose their own red run explicitly
  instead of citing it as green.

### Row disposition

- `RELEASE-TJ-016` — its acceptance criterion 3 ("No tag, GitHub Release,
  deployment … is changed") is now unreachable by construction and its
  reasoning carries the refuted premise. Closed as **superseded** with the
  reasoning corrected to name the refutation; the record it delivered
  (artifact + hash) stands.
- `RELEASE-TJ-017` — new row: the **v1.3.2 cut record** (tag, Release, assets,
  shipped-artifact proof, carried blockers).
- No duplicate readiness row was minted for the same range.

## Pass 3 — 2026-11-09T06:35Z (third delivery; standing record re-verified, decision unchanged)

Same tick id delivered a third time. The delta since the certified cut is
bookkeeping only, so this pass re-verifies the standing record in full and
records one **measurement correction** found by re-probing a carried blocker.
Decision unchanged: **NOT DUE** (Decision-1 rule 3); the v1.3.2 cut recorded in
`RELEASE-TJ-017` stands verified.

### Converged tip and re-verification receipts

- Tip `4d1c2a7a7c304c21f02e6336cc08f34e53a31ccd` — `git fetch`, `git ls-remote
  origin refs/heads/main` and the provider API agree.
- Remote artifact hash: `git show origin/main:releng-readiness-2026-11-09-0456.md
  | sha256sum` = `ff430d123fc445dfa0c85bd519f63148452554c78d29d770f62d9fcd3af4ff94`,
  178 lines = `RELEASE-TJ-017.detail.evidence[0].tree_fp`. Bytes intact. That
  entry's `artifacts[]` path names a scratch carrier
  (`…/tj-releng-wt-2026-11-09-0456/releng-readiness-2026-11-09-0456.md`) while
  the identical bytes are tracked at the same repo-relative path — a path nit,
  not an unverified record.
- Row readback: `RELEASE-TJ-017` status=complete, evidence entries=2,
  `evidence[0].run_id=42569431104`, `completed_at=2026-11-09T06:12:00Z`.
- Delta since the cut commit `f7ce3ef`: 4 commits; path delta
  `.coding-hermes/board/{tasks,events}.jsonl` + this artifact only. No product
  source, no release surface.

### Rebuilt census — v1.3.2..4d1c2a7 (4 commits)

feat 0 · fix 0 · perf 0 · breaking 0 · bookkeeping 4 (docs 1, board 3 —
including the non-conventional `PM dispatchability pass` board commit).
Classified classes plus remainder reconcile to `git rev-list --count` = 4.
Zero material commits ⇒ **rule 3, not due**.

### Exact-SHA hosted CI

`4d1c2a7` = run **42572230717** `completed/success`, all six jobs success:
Lint (ruff), Audit (pip-audit), Drift guards, Python 3.11 / 3.12 / 3.13.

### Carried blockers, re-probed at this tip

- **RELEASE-TJ-014 — STILL LIVE, and the gap WIDENS to three releases.** Explicit
  path `/home/kara/.local/bin/terminal-jail --version` → `terminal-jail 1.2.0`
  (mtime 2026-10-13 11:49); `~/.hermes/plugins/terminal-jail/plugin.yaml` →
  `version: "1.2.0"`. Missing 1.3.0, 1.3.1, 1.3.2.
- **MEASUREMENT CORRECTION on that surface (this pass's finding of record).** A
  bare `terminal-jail` in an agent shell does NOT resolve to the install
  surface. The harness shell wrapper re-injects QA-battery residue directories
  ahead of `~/.local/bin`:

      command -v terminal-jail            -> /tmp/tjtest/bin/terminal-jail -> 1.3.0  (mtime 2026-10-15 07:43)
      /tmp/tj-test-pack2/terminal-jail    -> 1.2.0                                    (mtime 2026-10-01 02:07)
      /tmp/tj-test-pack, /tmp/tj-stranger-bin -> PATH entries with no binary

  Consequence: a version probe taken from the bare command inside an agent
  session reports **1.3.0**, the residue copy, and would read as a one-release
  gap instead of three. Every probe in this record uses explicit absolute paths.
  No row filed for the injection: the injector is the harness session
  environment, not a defect in this repository, and a row here would dispatch
  work its foreman cannot perform. Carried as a note on RELEASE-TJ-014.
- **RELEASE-TJ-015 — STILL LIVE.** Asset census: v1.2.0=0, v1.3.0=3, v1.3.1=3,
  v1.3.2=3.
- **TJ-DF-062 — STILL LIVE at the tip.** `install.sh:21` still defaults
  `TERMINAL_JAIL_VERSION:-1.2.0`; `install.sh:1343` still downloads
  `terminal-jail.sha256`, which no release publishes.
- **RELCI-001 — STILL LIVE, re-proved on this very cut.** Tag-triggered `Release`
  run **42569796687** on `f7ce3ef5` = `completed/failure`, failing step
  `Preflight — verify the token may create releases`. No artifact built, no
  Release object created by it; the Release was published once by hand per
  `docs/releasing.md` 5b.
- **RELEASE-TJ-013** — historical (v1.3.1 era), not re-opened.

### GitReins and dogfood

- TJ-DF-061 latest verdict **b43b4a8f**, PASS, `evaluated_at 2026-11-09T02:35:36Z`,
  commit `6951c0a5` — this supersedes the commit number pass 2 quoted (383f260).
  It ran in the canonical checkout with `working_tree_dirty_path_count=3`, so it
  is not candidate evidence; no fresh candidate-bound verdict exists at `4d1c2a7`.
- Dogfood: newest note remains `docs/dogfood/2026-11-08-release-artifact-integration.md`;
  no dogfood run since pass 2.

### Posture (unchanged)

public=true, archived=false, license=MIT; branch-protection API 404
(unprotected); `security_and_analysis` absent (UNVERIFIED, not asserted enabled).

### Row census (pre-filing snapshot, 06:35Z)

Scope: every row whose status is in {pending, blocked, in_progress, review} =
**25** (9 pending, 16 blocked, 0 in_progress, 0 review) against 336 complete.
One row carries `status: null` (`QA-TERMINAL-JAIL-21`) — pre-existing board
hygiene, not an `in_progress` state; nothing filed.

### Row disposition

- `RELEASE-TJ-014` — title corrected to the published line (v1.3.2) and
  acceptance refreshed from 1.3.1 to 1.3.2 with an explicit-path probe, so the
  foreman can neither close it against a superseded artifact nor against the
  PATH-shadowed binary. Status and priority untouched (pending, P2).
- No new RELEASE-* row: no new range, no new decision, and no duplicate
  readiness row for a line that already has its cut record.
