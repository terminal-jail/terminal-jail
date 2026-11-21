# Cutting a terminal-jail release

This is the operator runbook for publishing a terminal-jail release (sdist +
wheel + checksums as GitHub Release assets). The only publish path is a
pushed `v*` tag: `.github/workflows/release.yml` builds the artifacts and
creates the Release. Nothing publishes without a tag, and nothing here is
automatic — every step below is a deliberate, ordered action.

**Authorization gate:** the standing release charter authorizes **patch and
minor** cuts on a readiness tick; only a **major/breaking** cut, a new
distribution channel, or a destructive tag operation needs explicit owner
authorization. The historical v1.3.0 hold (board row **RELEASE-TJ-008**) was
satisfied on 2026-11-03 — v1.3.0 is tagged and published, so do not re-hold
an authorized patch/minor cut against it. Release history: v1.0.0; v1.2.0
(whose Release object carries **zero assets**); v1.3.0 (assets present, but
its wheel predates the RELPKG-001 packaging fix — install v1.3.1 or later);
v1.3.1 (2026-11-04, patch fixes); v1.3.2 (2026-11-09, patch fix: Landlock
tier resolution inside installed wheels, TJ-DF-060); v1.3.3 (2026-11-10,
wheel-install bridge interpreter + release-mode installs); v1.3.4
(2026-11-16) — the current version, published by hand while RELCI-001 blocks
the workflow preflight. Every cut from v1.3.1 onward was hand-published per
step 5b for the same RELCI-001 reason. Step-7 snapshots live under
`docs/releases/` for v1.3.1, v1.3.3 and v1.3.4; v1.3.2's
`v1.3.2-published.json` sidecar was backfilled 2026-11-18 from the live
Release object and carries the `body_sha256`/`body_bytes` pinning the
published body, which is not otherwise committed in-repo for that release.

## The exact ordered steps

1. **Version-prep commit.** Land a single commit that changes exactly the
   `version = "X.Y.Z"` line in `pyproject.toml`, the matching `version:` in
   `plugin/plugin.yaml`, and its matching CHANGELOG section. Run
   `scripts/release-cut-check.sh vX.Y.Z` to validate that all three version
   surfaces agree; the checker validates content consistency, not commit
   atomicity. The one-commit rule remains the operator/CI contract. The
   workflow never bumps versions; if you push a tag whose version does not
   match `pyproject.toml`, the workflow fails loudly at its `Verify pyproject
   version matches the tag` step. `tests/test_version.py::test_plugin_manifest_version_matches_pyproject`
   pins the manifest to `pyproject.toml`, so bumping only `pyproject.toml`
   turns the CI matrix red before the tag.

   Also run `python3 scripts/check_version_parity.py` (stdlib only) before
   tagging: it fails with `file:line` on any hand-written version literal left
   behind in the plugin load banners, `scripts/metrics-export.py` or
   `plugin/terminal_jail/plugin.py`, and otherwise proves that
   `plugin/plugin.yaml`, `scripts/metrics-export.py --json` and
   `standalone/terminal-jail --version` all agree with `pyproject.toml`.

2. **CI green on that SHA.** Push to `main` and wait for the `CI` workflow
   to go green on the version-prep SHA (`gh run list --commit <sha>`).
   Never cut from a red or running tree.

3. **Run the pre-cut check.** From a clean checkout of that SHA:

   ```bash
   ./scripts/release-cut-check.sh vX.Y.Z
   ```

   It verifies, naming any failure: the tag is well-formed (`vX.Y.Z`) and
   does not already exist, the working tree is clean, `pyproject.toml`'s
   version equals the tag, and CI is green on HEAD. Exit 0 = safe to cut;
   exit 1 = fix the named failures; exit 2 = usage/argument error.

4. **Tag.** Create an **annotated** tag and push it. The push is what
   triggers the workflow — this is the point of no return:

   ```bash
   git tag -a vX.Y.Z -m "terminal-jail vX.Y.Z"
   git push origin vX.Y.Z
   ```

5. **The workflow publishes.** On the tag push, `Release` runs: it checks
   out the tag's tree, verifies the GITHUB_TOKEN can create releases (a
   missing token or missing `contents: write` permission fails the run with
   a named `::error::` — never a silent no-op), re-verifies the version/tag
   match, builds the sdist + wheel with `python -m build` on Python 3.11,
   writes `SHA256SUMS` over the artifacts, creates the Release with
   `gh release create --verify-tag`, and then **verifies the Release object
   carries every artifact** before reporting success.

5b. **While RELCI-001 is open, publish by hand from the tagged tree.**
   The preflight above fails today because the repository's Actions
   workflow-permission default caps `permissions: contents: write`, so the
   tag run goes red at step 5 with no artifacts. That is a token-scope
   defect, not a verdict on the tree: build the identical artifact set from
   a clean checkout of the tag and publish it yourself, keep the tag
   immutable, and leave RELCI-001 open for the owner/app-admin setting.

   ```bash
   git checkout --detach vX.Y.Z && git status --porcelain   # must be empty
   python3 -m venv /tmp/tj-build-venv && /tmp/tj-build-venv/bin/pip install -q build
   /tmp/tj-build-venv/bin/python -m build --outdir /tmp/tj-dist
   (cd /tmp/tj-dist && sha256sum -- *.tar.gz *.whl > SHA256SUMS && sha256sum -c SHA256SUMS)
   gh release create vX.Y.Z /tmp/tj-dist/* --verify-tag \
     --title "terminal-jail vX.Y.Z" --notes-file /tmp/tj-notes.md
   ```

   Then run step 6 **and** the manual artifact verification below against the
   published assets; a Release whose wheel installs but ships no
   `terminal-jail` command is the RELPKG-001 relapse, and it is not a release.

6. **Verify assets on the Release object.** Confirm independently:

   ```bash
   gh release view vX.Y.Z --json assets --jq '.assets[].name'
   ```

   Expect exactly: the `.tar.gz` sdist, the `.whl`, and `SHA256SUMS`.

7. **Snapshot the published body into the repo.** The release body is part
   of the release: copy it out of the Release object and commit it under
   `docs/releases/`, so a later edit to the body can be diffed and audited.

   ```bash
   # jq -j writes the raw string with no trailing newline: this is the body
   # byte for byte. (`gh release view -q .body > file` appends a newline and
   # silently changes the hash — do not use it for the snapshot.)
   curl -s -H "Authorization: token $(gh auth token)" \
     https://api.github.com/repos/OWNER/REPO/releases/tags/vX.Y.Z \
     | jq -j .body > docs/releases/vX.Y.Z-notes.md

   sha256sum docs/releases/vX.Y.Z-notes.md   # record this in the json sidecar
   ```

   Commit the notes file plus `docs/releases/vX.Y.Z-published.json` carrying
   `body_sha256`, `body_bytes`, the capture command and the URL, so a later
   edit to the body can be diffed against what was actually published.

   Cite CI evidence by the run that actually ran on the **tag** commit. A
   prep commit whose matrix went red is not a receipt; say so explicitly if
   it has to be mentioned at all.

8. **Bump the installer's release pin.** `install.sh` decides which tag's
   assets a release-mode install downloads (`TERMINAL_JAIL_VERSION`), and that
   pin is a **wheel selector, not a version label**: it must name the tag you
   just published. Set its default to `X.Y.Z` in both places it appears — the
   `TERMINAL_JAIL_VERSION="${TERMINAL_JAIL_VERSION:-X.Y.Z}"` assignment and the
   `--help` text (`default: X.Y.Z`) — and update the release-mode paragraph and
   `# default: X.Y.Z` line in `docs/quickstart.md` plus the matching sentence
   in `README.md`. Re-capture the release fixture
   (`plugin/fixtures/github-release-vX.Y.Z.json`) from the published Release and
   commit it together with the pin, then prove the three asset names resolve
   for that tag:

   ```bash
   grep -n 'TERMINAL_JAIL_VERSION="\|default: X\.Y\.Z' install.sh
   gh release view vX.Y.Z --repo OWNER/REPO --json assets --jq '.assets[].name'
   ```

   Expect exactly the sdist (`terminal_jail-X.Y.Z.tar.gz`), the wheel
   (`terminal_jail-X.Y.Z-py3-none-any.whl`), and `SHA256SUMS`, and expect the
   installer's default to equal that tag. `plugin/test_install.py` enforces the
   second half: `test_release_asset_names_match_captured_github_release` fails
   against the captured fixture and
   `test_release_assets_and_default_match_live_github_release` fails against the
   live Release when the pin lags.

   **Failure mode if skipped:** nothing goes red. The asset URLs of the previous
   tag still resolve, so the documented install (`TERMINAL_JAIL_USE_RELEASE=1
   ./install.sh`) and the `--help` text keep naming the superseded release —
   every operator following the docs gets the old build with no error. v1.3.4
   shipped with exactly this gap (the installer still served v1.3.3 assets,
   RELEASE-TJ-026), which is why this step exists.

## Dependency-CVE coverage (pip-audit in CI)

Dependency-vulnerability scanning has exactly one channel in this project: the
`Audit (pip-audit)` job in the `CI` workflow (`.github/workflows/ci.yml`). It
installs `pip-audit` and runs it, and a known advisory makes that job exit
non-zero, which turns the run red. No other dependency-CVE tooling exists in
the tree.

Cadence is event-driven, per push: `CI` triggers on `push` to `main` and on
`pull_request` targeting `main`. There is no `schedule:` trigger, so an
advisory published against an unchanged dependency is first observed at the
next push or pull request, never by a periodic scan.

Scope, stated so the channel is not read as wider than it is: the job audits
the runner's interpreter environment, which holds `pip-audit` and its own
resolved dependencies. The project is not installed in that job, so its only
declared runtime dependency (`dependencies = ["PyYAML>=6.0"]` in
`pyproject.toml`) is not audited there. The channel covers dependency CVEs for
the audit toolchain's tree; a project-dependency audit is not part of CI.

GitHub's own alerting is not a channel: Dependabot alerts are disabled on this
public repository. Re-check that status with:

```bash
gh api repos/terminal-jail/terminal-jail/dependabot/alerts?state=open
# -> HTTP 403: Dependabot alerts are disabled for this repository.
```

Evidence that the job actually executes — CI run **44906831648**
(2026-11-21T13:02:14Z, `main`, conclusion success) ran job `Audit (pip-audit)`,
whose `Run pip-audit` step logged `No known vulnerabilities found`. Confirm the
same job on any run id:

```bash
gh run view 44906831648 --repo terminal-jail/terminal-jail --json jobs \
  --jq '.jobs[] | select(.name=="Audit (pip-audit)") | "\(.name) \(.conclusion)"'
```

## Manual verification of the artifacts (optional but recommended)

```bash
gh release download vX.Y.Z --dir /tmp/tj-release-check
cd /tmp/tj-release-check
sha256sum -c SHA256SUMS
python3 -m venv /tmp/tj-release-venv && /tmp/tj-release-venv/bin/pip install ./terminal_jail-*.whl
/tmp/tj-release-venv/bin/python -c 'import terminal_jail; print(terminal_jail.__version__)'
```

## Re-running a failed cut

If a workflow run failed after the tag exists (for example the version
mismatch fired), fix the cause on `main`, re-tag a **new** version — never
reuse or move a published tag — and follow the steps again. To retry the
publish itself for an existing tag (e.g. a transient asset-upload failure),
use **Run workflow** on the `Release` workflow (`workflow_dispatch`) with
the `tag` input set to the existing tag: the workflow re-checks out that
tag's tree and republishes.

## Self-checks

`tests/test_release_workflow.py` pins the release tooling cheaply: it
parses `.github/workflows/release.yml` (and `ci.yml`) with PyYAML and runs
`scripts/release-cut-check.sh` against the tree, including its wrong-tag
failure paths.

### Documented dry-run proof (validation of the workflow, per RELEASE-TJ-008 gate)

The workflow is validated statically rather than by running `act` (the
publish step cannot run outside GitHub without a real token by design):

1. YAML + schema check: `tests/test_release_workflow.py` parses both
   workflows and asserts the trigger (`tags: ["v*"]`), permissions
   (`contents: write`), build step (`python -m build`), checksum step
   (`sha256sum -c`) and publish step (`gh release create`) are present —
   this is the act-style structural dry-run and it runs in CI on every PR.
2. Versioned pre-cut check: `scripts/release-cut-check.sh vX.Y.Z` on a clean
   tree exercises every pre-cut gate (tag absence, version match, CI
   green) end to end without touching anything. The script accepts only a
   positional tag (no flags) and is read-only by construction, so running
   this versioned invocation is the dry run.
3. The publish step itself is proven only by a real tag push (see steps
   above: `gh release view vX.Y.Z` then `sha256sum -c` on the downloaded
   assets). Nothing else counts — the workflow fails loudly rather than
   silently no-op when permissions are missing.
