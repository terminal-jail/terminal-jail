#!/usr/bin/env bash
# release-cut-check.sh — pre-flight validation for cutting a terminal-jail release.
#
# Usage: ./scripts/release-cut-check.sh v1.3.0
#
# Verifies, in order, that the tree is ready for the release tag:
#   1. the tag argument is well-formed (vX.Y.Z) and does not already exist,
#   2. the working tree is clean (nothing staged, nothing modified),
#   3. pyproject.toml [project].version equals the tag being cut,
#   4. CI is green on HEAD (gh run list for the HEAD sha).
#
# Every failure is named and the script exits non-zero. It NEVER creates the
# tag, bumps the version, or touches the tree — read-only by design. The tag
# itself is cut manually after this passes (owner-authorized: RELEASE-TJ-008,
# see docs/releasing.md).
set -u

TAG="${1:-}"
failures=0

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

echo "== release-cut-check =="

# --- 0. argument ---------------------------------------------------------
if [ -z "${TAG}" ]; then
  echo "usage: $0 vX.Y.Z   (e.g. $0 v1.3.0)" >&2
  exit 2
fi

case "${TAG}" in
  v[0-9]*.[0-9]*.[0-9]*) ;;
  *)
    echo "FAIL: tag '${TAG}' is not vX.Y.Z — refusing to validate." >&2
    exit 2
    ;;
esac

# --- 1. tag must not already exist ---------------------------------------
# Probe the LOCAL refs first; fall back to `git ls-remote origin` because
# CI checkouts (actions/checkout@v4) do not fetch tags. A failed remote
# probe (network/auth) counts as NOT existing — the script is read-only and
# the tag push itself is the authoritative guard against reuse.
tag_exists=""
if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null 2>&1; then
  tag_exists=local
elif git ls-remote --exit-code origin "refs/tags/${TAG}" >/dev/null 2>&1; then
  tag_exists=remote
fi
if [ -n "${tag_exists}" ]; then
  fail "tag '${TAG}' already exists (${tag_exists}) — a release tag is never reused. Pick the next version."
else
  echo "OK: tag '${TAG}' does not exist yet"
fi

# --- 2. clean tree --------------------------------------------------------
DIRTY="$(git status --porcelain)"
if [ -n "${DIRTY}" ]; then
  echo "${DIRTY}" >&2
  fail "working tree is dirty (listing above) — commit or stash before cutting a release"
else
  echo "OK: working tree clean"
fi

# --- 3. pyproject version == tag ------------------------------------------
PYPROJECT="$(git rev-parse --show-toplevel)/pyproject.toml"
if [ ! -f "${PYPROJECT}" ]; then
  fail "pyproject.toml not found at repo root"
else
  VERSION="$(python3 - "${PYPROJECT}" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as fh:
    print(tomllib.load(fh)["project"]["version"])
PY
)"
  WANT="${TAG#v}"
  if [ -z "${VERSION}" ]; then
    fail "could not read [project].version from pyproject.toml"
  elif [ "${VERSION}" != "${WANT}" ]; then
    fail "pyproject.toml version is ${VERSION} but tag is ${TAG} (expected ${WANT}) — land the version-prep commit first"
  else
    echo "OK: pyproject.toml version ${VERSION} == tag ${TAG}"
  fi
fi

# --- 4. CI green on HEAD ---------------------------------------------------
# Seam: TJ_RELEASE_CI_JSON (env, test/CI use only) supplies the `gh run list
# --json status,conclusion` payload directly, so the green path is verifiable
# in a scratch checkout that has no CI runs of its own. Unset (production) it
# is inert and gh is queried live; malformed seam data fails the check loudly.
RUNS="${TJ_RELEASE_CI_JSON:-}"
if [ -n "${RUNS}" ]; then
  echo "(seam) TJ_RELEASE_CI_JSON set — using supplied CI run data instead of gh"
elif ! command -v gh >/dev/null 2>&1; then
  fail "gh CLI not found on PATH — cannot verify CI status on HEAD (or supply TJ_RELEASE_CI_JSON)"
elif ! gh auth status >/dev/null 2>&1; then
  # gh present but unauthenticated (e.g. Actions runs): `gh run list` would
  # print an error to stderr and emit no JSON, which must not leak a stack
  # trace into this script's output. Fail with a NAMED reason instead.
  fail "gh CLI is present but not authenticated — cannot verify CI status on HEAD (on CI, supply TJ_RELEASE_CI_JSON or run this check off-runner)"
else
  HEAD_SHA="$(git rev-parse HEAD)"
  # Prefer a run for exactly this sha; fall back to branch-scoped runs when
  # the API returns no per-sha rows (e.g. brand-new pushes still queued).
  RUNS="$(gh run list --commit "${HEAD_SHA}" --limit 10 --json status,conclusion 2>/dev/null)"
  if [ -z "${RUNS}" ] || [ "${RUNS}" = "[]" ]; then
    BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    RUNS="$(gh run list --branch "${BRANCH}" --limit 10 --json status,conclusion,headSha 2>/dev/null |
      python3 -c 'import json,sys; runs=json.load(sys.stdin); print(json.dumps([r for r in runs if r.get("headSha","").startswith(sys.argv[1])]))' "${HEAD_SHA}")"
  fi
fi
if [ -z "${RUNS}" ] || [ "${RUNS}" = "[]" ]; then
  fail "no CI runs found for HEAD $(git rev-parse --short HEAD 2>/dev/null || echo '?') — push the version-prep commit and wait for CI before cutting"
else
  PENDING="$(printf '%s' "${RUNS}" | python3 -c 'import json,sys; runs=json.load(sys.stdin); print(sum(1 for r in runs if r.get("status")!="completed"))')" || true
  FAILED="$(printf '%s' "${RUNS}" | python3 -c 'import json,sys; runs=json.load(sys.stdin); print(sum(1 for r in runs if r.get("status")=="completed" and r.get("conclusion") not in ("success","skipped","neutral")))')" || true
  case "${PENDING}${FAILED}" in
    *[!0-9]*|"")
      fail "could not parse CI run data — refusing to guess (data was: $(printf '%s' "${RUNS}" | cut -c1-120)...)"
      ;;
    *)
      if [ "${PENDING}" != "0" ]; then
        fail "CI still running on HEAD (${PENDING} run(s) in progress) — wait for green"
      fi
      if [ "${FAILED}" != "0" ]; then
        fail "CI is red on HEAD (${FAILED} failed run(s)) — fix before cutting"
      fi
      if [ "${PENDING}" = "0" ] && [ "${FAILED}" = "0" ]; then
        echo "OK: CI green on HEAD $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
      fi
      ;;
  esac
fi

echo "== release-cut-check: ${failures} failure(s) =="
if [ "${failures}" -ne 0 ]; then
  exit 1
fi
echo "READY: tree validated for cutting ${TAG} — cut it manually: git tag -a ${TAG} && git push origin ${TAG}"
exit 0
