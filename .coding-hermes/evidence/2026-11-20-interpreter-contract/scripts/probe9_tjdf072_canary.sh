#!/bin/bash
# TJ-DF-072 — the fs-tier launch reporting contract, by the canary arm.
#
# The bug (dogfood 2026-11-20, e67e07e): a tiered auto-sandbox launch applies the
# Landlock domain in the un-namespaced CALLER context (the wrapper's trampoline,
# standalone/terminal-jail `TERMINAL_JAIL_LANDLOCK_PAYLOAD=... exec ...`) and the
# restriction INHERITS across the namespace boundary, so the payload IS contained.
# The engine-spliced loader that runs INSIDE the namespace then cannot re-prove the
# property (the probe host — /run/user/<uid>, HOME — is not writable there) and used
# to print "commands run unchanged without kernel filesystem enforcement" — a FALSE
# statement about a launch whose containment is delivered.
#
# Arms (all on a throwaway HOME OUTSIDE /tmp, so the tier's tmpdir write grants
# cannot cover the fake home):
#   e1-tiered        tiered auto-sandbox launch: the canary read must be DENIED and
#                    the fs-tier line must state enforcement (fs twin of the net
#                    tier's "kernel egress tier APPLIED"), never the false sentence.
#   e2-tier-off      the identical launch with TERMINAL_JAIL_LANDLOCK=0 (one
#                    variable): the canary must be READABLE.
#   n1-no-ancestor   the loader nested in a namespace with NO ancestor domain (the
#                    genuine degraded shape, mapping-less `unshare --user`): the
#                    not-applied warning MUST still print and the canary IS readable.
#   n2-inherited     the production nesting without the CLI: an outer loader that
#                    PROVES the tier, then the namespace, then a re-attaching loader
#                    that cannot re-prove it: the canary must be DENIED and the line
#                    must report enforcement.
#
# Usage:  probe9_tjdf072_canary.sh            (defaults to this checkout)
#         REPO=<tree> ROOT=<throwaway home parent> TAG=<label> probe9_...
# Nothing outside REPO/ROOT is written; no live ~/.hermes or ~/.local is touched.
set -u

REPO=${REPO:-/home/kara/worktrees/terminal-jail-TJ-DF-072}
ROOT=${ROOT:-/home/kara/tj-df-072}
TAG=${TAG:-}
HOME_A=$ROOT/home
TJ=$HOME_A/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin
LOADER=$REPO/standalone/landlock-loader.py
CANARY=/run/user/1000/tj-canary
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:-$HERE/../arms}
PY=${PY:-$REPO/.venv/bin/python}

mkdir -p "$ROOT" "$OUT"
suffix() { printf '%s' "${TAG:+$TAG-}$1"; }

echo "== repo=$REPO root=$ROOT tag=${TAG:-<none>} loader=$LOADER"
echo "== HEAD $(git -C "$REPO" log --oneline -1)"

echo "== fresh install into $HOME_A (documented ./install.sh --no-path)"
( cd "$REPO" && env -i PATH="$BASE" HOME="$HOME_A" bash ./install.sh --no-path ) \
    >"$OUT/$(suffix install).out" 2>"$OUT/$(suffix install).err"
echo "install rc=$?"
tail -2 "$OUT/$(suffix install).err"

printf 'SECRET-CANARY\n' >"$CANARY"
chmod 0600 "$CANARY"
mkdir -p "$HOME_A/mk"
cat >"$HOME_A/mk/Makefile" <<'EOF'
ok:
	@echo MODIFY-PAYLOAD-RAN
canary:
	@cat /run/user/1000/tj-canary
EOF

arm() { local name="$1" note="$2"; shift 2
  local o=$OUT/$(suffix "$name").out e=$OUT/$(suffix "$name").err r=$OUT/$(suffix "$name").rc
  ( cd "$HOME_A/mk" && env -u TERMINAL_JAIL_PYTHON -u TERMINAL_JAIL_INTERRUPTOR_MODE \
        -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_JAIL_BACKEND -u TERMINAL_JAIL_COMPOSED \
        PATH="$BASE" HOME="$HOME_A" "$@" >"$o" 2>"$e" )
  echo "$?" >"$r"
  printf 'ARM %-14s | %-58s | rc=%s | stdout=%q\n' "$name" "$note" "$(cat "$r")" \
      "$(head -c 60 "$o" | tr '\n' ' ')"
}

# e1: the tiered auto-sandbox launch (clean PATH, no TERMINAL_JAIL_* set)
arm e1-tiered "expect DENIED + an enforced fs line, no false sentence" "$TJ" make canary
# e2: one variable — the tier off
arm e2-tier-off "expect SECRET-CANARY rc0 (tier off)" env TERMINAL_JAIL_LANDLOCK=0 "$TJ" make canary

# n1: the genuine degraded shape — a namespace with NO ancestor domain, and no
# writable probe host either (XDG_RUNTIME_DIR unset: the mapped-/legacy-uid
# process cannot write /run/user/<caller uid>, and HOME/tmpdirs are granted).
arm n1-no-ancestor "expect the not-applied warning + SECRET-CANARY (no enforcement)" \
    env -u XDG_RUNTIME_DIR unshare --user --pid --fork --kill-child=SIGKILL \
    "$PY" "$LOADER" -- \
    sh -c 'cat /run/user/1000/tj-canary; echo read_rc=$?'

# n1b: the same namespace WITH a writable probe host (XDG_RUNTIME_DIR set):
# the attach PROVES and enforces — so the production probe failure is caused by
# the INHERITED DOMAIN denying the probe host, not by the namespace uid.
arm n1b-no-ancestor-xdg "expect DENIED + silence (no ancestor to inherit, probe proves)" \
    env XDG_RUNTIME_DIR=/run/user/1000 unshare --user --pid --fork \
    --kill-child=SIGKILL "$PY" "$LOADER" -- \
    sh -c 'cat /run/user/1000/tj-canary; echo read_rc=$?'

# n2: the production nesting without the CLI — outer attach proves, namespace,
# re-attach cannot re-prove. The interpreter and the loader must be READABLE
# inside the outer domain: /usr/bin/python3 (/usr grant) + the installed copy
# (~/.local/lib read grant).
INS=${INS:-$HOME_A/.local/lib/terminal-jail/landlock-loader.py}
arm n2-inherited "expect DENIED + an enforced fs line, no false sentence" \
    "$PY" "$INS" -- unshare --user --pid --fork --kill-child=SIGKILL \
    /usr/bin/python3 "$INS" -- sh -c 'cat /run/user/1000/tj-canary; echo read_rc=$?'

for a in e1-tiered e2-tier-off n1-no-ancestor n1b-no-ancestor-xdg n2-inherited; do
    f=$OUT/$(suffix "$a").err
    [ -f "$f" ] || continue
    printf '\n--- %s stderr ---\n' "$a"; cat "$f"
    printf -- '--- %s stdout ---\n' "$a"; cat "$OUT/$(suffix "$a").out"
done
echo DONE-TJDF072
