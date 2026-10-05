# Cutting a terminal-jail release

This is the operator runbook for publishing a terminal-jail release (sdist +
wheel + checksums as GitHub Release assets). The only publish path is a
pushed `v*` tag: `.github/workflows/release.yml` builds the artifacts and
creates the Release. Nothing publishes without a tag, and nothing here is
automatic — every step below is a deliberate, ordered action.

**Authorization gate:** a **v1.3.0 cut still requires explicit owner
authorization** (board row **RELEASE-TJ-008**, gate 1 of 3). Do not tag
v1.3.0 — or bump the version — without it. This repo's release history:
v1.0.0, v1.2.0 (whose Release object currently carries **zero assets**; the
tag-triggered workflow exists so the next cut does not repeat that).

## The exact ordered steps

1. **Version-prep commit.** Land a single commit that changes exactly the
   `version = "X.Y.Z"` line in `pyproject.toml` (plus its CHANGELOG entry,
   if any). The workflow never bumps versions; if you push a tag whose
   version does not match `pyproject.toml`, the workflow fails loudly at its
   `Verify pyproject version matches the tag` step.

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

6. **Verify assets on the Release object.** Confirm independently:

   ```bash
   gh release view vX.Y.Z --json assets --jq '.assets[].name'
   ```

   Expect exactly: the `.tar.gz` sdist, the `.whl`, and `SHA256SUMS`.

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
2. Live script dry-run: `scripts/release-cut-check.sh v1.3.0` on a clean
   tree exercises every pre-cut gate (tag absence, version match, CI
   green) end to end without touching anything — its `--dry-run` behaviour
   is the whole script: it is read-only by construction.
3. The publish step itself is proven only by a real tag push (see steps
   above: `gh release view vX.Y.Z` then `sha256sum -c` on the downloaded
   assets). Nothing else counts — the workflow fails loudly rather than
   silently no-op when permissions are missing.
