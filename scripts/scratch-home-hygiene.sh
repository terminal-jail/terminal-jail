#!/usr/bin/env bash
#
# scratch-home-hygiene.sh — structural guard for the DF-TERMINAL-JAIL-27 gap.
#
# A dogfood leg that redirects HOME into a /tmp scratch tree can let a tool write
# its own credential file (observed: /tmp/dogfood-tj/home/.bunker/config.yaml,
# mode 644, holding a live bunkerd token) into that tree. Group/world-readable
# scratch trees therefore turn /tmp into a key store. This checker scans a root
# for `dogfood-*` scratch directories and flags the ones that are readable beyond
# their owner AND carry a credential-shaped file.
#
# Usage:  scripts/scratch-home-hygiene.sh [SCAN_ROOT]      (default: /tmp)
# Exit:   0 = clean, 1 = finding(s), 2 = usage / scan-root error
#
# Privacy contract: only PATHS and MODE STRINGS are ever printed. A matched file
# is opened for a content test (`grep -q`, output discarded) but its contents and
# credential values are never echoed, logged, or returned.
#
# See docs/dogfood/diagnostics.md §8.6 and docs/dogfood/checklist.md.

set -u

SCAN_ROOT="${1:-/tmp}"

if [ ! -d "$SCAN_ROOT" ]; then
  printf 'scratch-home-hygiene: ERROR scan root is not a directory: %s\n' \
    "$SCAN_ROOT" >&2
  exit 2
fi

# Credential-shaped file NAME (case-insensitive): config.yaml | config.yml |
# *.env | *token* | *secret* | *credentials*. The two trailing families are
# matched as infixes so prefixed names (e.g. my_secret.txt) count too.
is_credential_name() {
  local base lower
  base="${1##*/}"
  lower="$(printf '%s' "$base" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    config.yaml | config.yml | *.env | *token* | *secret* | *credential*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Credential-shaped CONTENT: a credential-assignment line, e.g.
# `token: abc`, `TOKEN=abc`, `  api_key: abc` (case-insensitive).
CREDENTIAL_LINE_RE='^[[:space:]]*[A-Za-z0-9_]*(token|secret|password|api_?key)[A-Za-z0-9_]*:?[[:space:]]*[=:][[:space:]]*[^[:space:]]+'

has_credential_line() {
  # -q silences the match, -I skips binary files ("Binary file matches" noise).
  grep -q -I -i -E -- "$CREDENTIAL_LINE_RE" -- "$1" 2>/dev/null
}

mode_of() {
  stat -c '%a' -- "$1" 2>/dev/null || true
}

# Owner-only means "no mode bits beyond rwx------": no group, no other bits.
is_owner_only() {
  local mode
  mode="$(mode_of "$1")"
  [ -n "$mode" ] || return 1
  [ "$((8#$mode & 8#077))" -eq 0 ]
}

findings=0
scanned=0

while IFS= read -r -d '' scratch_dir; do
  scanned=$((scanned + 1))

  # Tight scratch tree: nothing loose, nothing to report.
  if is_owner_only "$scratch_dir"; then
    continue
  fi

  dir_mode="$(mode_of "$scratch_dir")"
  [ -n "$dir_mode" ] || dir_mode='unknown'

  while IFS= read -r -d '' file; do
    [ -f "$file" ] || continue
    if is_credential_name "$file" || has_credential_line "$file"; then
      file_mode="$(mode_of "$file")"
      [ -n "$file_mode" ] || file_mode='unknown'
      printf 'scratch-home-hygiene: FINDING dir=%s dir-mode=%s credential-file=%s file-mode=%s\n' \
        "$scratch_dir" "$dir_mode" "$file" "$file_mode"
      findings=$((findings + 1))
    fi
  done < <(find "$scratch_dir" -type f -print0 2>/dev/null)
done < <(
  find "$SCAN_ROOT" -mindepth 1 -maxdepth 1 -name 'dogfood-*' -type d -print0 \
    2>/dev/null
)

printf 'scratch-home-hygiene: scanned %d scratch dir(s) under %s; %d finding(s)\n' \
  "$scanned" "$SCAN_ROOT" "$findings"

if [ "$findings" -gt 0 ]; then
  printf 'scratch-home-hygiene: FAIL — credential file(s) inside a group/world-readable scratch tree; keep scratch HOMEs at mode 0700 and keep credentials out of them (DF-TERMINAL-JAIL-27)\n' >&2
  exit 1
fi

printf 'scratch-home-hygiene: OK — no loose scratch tree carries a credential file\n'
exit 0
