#!/bin/sh
# terminal-jail installer — POSIX sh, usable as: curl -fsSL <url> | sh
# or from a repository checkout: ./install.sh
set -eu

# --- defaults ----------------------------------------------------------------
# Release mode is EXPLICITLY OPTED IN via TERMINAL_JAIL_USE_RELEASE=1 — no
# release assets are published yet, so the default curl | sh path must not
# silently 404 (see TJ-GAP-023). Local mode (./install.sh from a checkout) is
# the supported install path; it ships the wrapper, the plugin bridge tree,
# and the seccomp loader together.
TERMINAL_JAIL_USE_RELEASE="${TERMINAL_JAIL_USE_RELEASE:-0}"
TERMINAL_JAIL_VERSION="${TERMINAL_JAIL_VERSION:-1.1.0}"
TERMINAL_JAIL_INSTALL_DIR="${TERMINAL_JAIL_INSTALL_DIR:-$HOME/.local/bin}"
# Rules target for the shipped default rules file (DF-TERMINAL-JAIL-8). Empty
# (default) = derive from the install scope: the live user rules dir
# ($HOME/.config/terminal-jail/rules.d) for the default install
# ($HOME/.local/bin), or <install prefix>/config/terminal-jail/rules.d for any
# other TERMINAL_JAIL_INSTALL_DIR. A non-empty value is used verbatim and
# always wins, even outside the selected prefix.
TERMINAL_JAIL_RULES_DIR="${TERMINAL_JAIL_RULES_DIR:-}"

# --- path normalization (DF-TERMINAL-JAIL-24) --------------------------------
# Derived prefix paths (<prefix>/config/... rules dir, <prefix>/lib/... lib
# dir) must print as normalized absolute paths: no embedded ".." segments, and
# no raw sh error when the prefix's parent does not exist yet. readlink -m /
# realpath -m canonicalize textually without touching the filesystem; the
# final fallback is a pure-POSIX walk for hosts without either tool. The walk
# treats leading "/.." as "/" (per POSIX), collapses "./", and folds away
# ".." against the preceding non-".." segment; symlinked ancestors beyond the
# last existing component are left as-is, matching what the cd+pwd idiom
# resolved before.
path_normalize() {
    # path_normalize <path> -> prints the normalized absolute path
    if command -v readlink >/dev/null 2>&1 \
        && normalized="$(readlink -m -- "$1" 2>/dev/null)" \
        && [ -n "$normalized" ]; then
        printf '%s\n' "$normalized"
        return 0
    fi
    if command -v realpath >/dev/null 2>&1 \
        && normalized="$(realpath -m -- "$1" 2>/dev/null)" \
        && [ -n "$normalized" ]; then
        printf '%s\n' "$normalized"
        return 0
    fi
    if [ "${1#/}" = "$1" ]; then
        input="$(pwd -P 2>/dev/null || pwd)/$1"
    else
        input="$1"
    fi
    # Textual segment walk: no IFS games, no glob expansion, no filesystem
    # access. "/tmp/t/../x" -> "/x", "/.." -> "/", "./a" -> cwd/a. Absolute
    # inputs anchor output at "/" up front (the first empty segment must not
    # be folded away), so a fold can never drop the root; a relative path
    # that folds to nothing prints ".". The readlink/realpath branches cover
    # every realistic installer input — this walk only runs on stripped hosts
    # without either tool (the curated-PATH tests).
    output=""
    case "$input" in
        /*)
            output="/"
            input="${input#/}"
            ;;
    esac
    rest="$input"
    while [ -n "$rest" ]; do
        segment="${rest%%/*}"
        case "$rest" in
            */*) rest="${rest#*/}" ;;
            *) rest="" ;;
        esac
        case "$segment" in
            "" | ".") continue ;;
            "..")
                case "$output" in
                    "/" | "") ;;
                    *)
                        output="${output%/}"
                        case "$output" in
                            */*) output="${output%/*}/" ;;
                            *) output="" ;;
                        esac
                        ;;
                esac
                ;;
            *)
                case "$output" in
                    "/") output="/$segment/" ;;
                    *) output="$output$segment/" ;;
                esac
                ;;
        esac
    done
    case "$output" in
        "") output="." ;;
        "/") ;;
        *) output="${output%/}" ;;
    esac
    printf '%s\n' "$output"
}
TERMINAL_JAIL_BASE_URL="${TERMINAL_JAIL_BASE_URL:-https://github.com/totalwindupflightsystems/terminal-jail/releases/download/v${TERMINAL_JAIL_VERSION}}"

# --- installer flags (TJ-GAP-061) --------------------------------------------
# The installer stays env-var driven; these flags only add the opt-in rule-pack
# knobs. Every flag is parsed BEFORE anything is created or written, so an
# unknown flag leaves the filesystem untouched. A pack the validator refuses
# (or an unknown pack name) writes nothing FOR THAT PACK, but no longer aborts
# the base install — a skipped pack is reported and the script exits 2 at the
# end (DF-TERMINAL-JAIL-21). Pack names are restricted to [a-z0-9-] so the
# derived file name (terminal-jail-pack-<name>.yaml) can neither escape the
# rules directory nor be read as a glob.
RULE_PACKS=""
UNRULE_PACKS=""
LIST_RULE_PACKS=0
UNINSTALL=0
UNINSTALL_SYSTEMD=0

valid_pack_name() {
    case "$1" in
        ""|-*) return 1 ;;
        *[!a-z0-9-]*) return 1 ;;
    esac
    return 0
}

add_rule_pack() {
    if ! valid_pack_name "$1"; then
        echo "terminal-jail installer: --rule-pack: invalid pack name '$1' (expected [a-z0-9-]+)" >&2
        exit 2
    fi
    case " $RULE_PACKS " in
        *" $1 "*) ;; # already queued — installing a pack twice is a no-op
        *) RULE_PACKS="${RULE_PACKS:+$RULE_PACKS }$1" ;;
    esac
}

add_unrule_pack() {
    if ! valid_pack_name "$1"; then
        echo "terminal-jail installer: --unrule-pack: invalid pack name '$1' (expected [a-z0-9-]+)" >&2
        exit 2
    fi
    case " $UNRULE_PACKS " in
        *" $1 "*) ;;
        *) UNRULE_PACKS="${UNRULE_PACKS:+$UNRULE_PACKS }$1" ;;
    esac
}

usage() {
    cat <<'USAGE'
terminal-jail installer — POSIX sh

Usage: install.sh [options]

Options:
  --rule-pack <name>    Install an opt-in rule pack from this repository
                        checkout (repeatable, e.g. --rule-pack db). The pack is
                        validated BEFORE anything is written: an unknown pack, a
                        malformed or invalid pack, a rule id outside the
                        pack-<name>-* namespace, or an id colliding with an
                        engine builtin id or an already-installed rule file is
                        SKIPPED (base install continues; exit 2 at the end).
                        Installing a YAML pack requires python3 + PyYAML (a
                        plain-JSON pack needs PyYAML only if the validator
                        would fall back to json — see README).
  --unrule-pack <name>  Remove an installed rule pack. Only
                        terminal-jail-pack-<name>.yaml is touched — the default
                        rules file and every other pack are never modified.
  --list-rule-packs     List the rule packs this checkout ships (exit 0).
  --uninstall           Remove everything the installer wrote: the wrapper
                        (TERMINAL_JAIL_INSTALL_DIR), the lib tree, the rules
                        files it installed (00-builtins.yaml, installed packs
                        terminal-jail-pack-*.yaml and their .bak-* backups),
                        and its '# terminal-jail' PATH block in the rc file.
                        USER-AUTHORED files in rules.d are PRESERVED and
                        listed. User data (rules you wrote, other files in the
                        install dir) is never touched. Idempotent: rerunning
                        on an already-clean host exits 0.
  --uninstall-systemd   With --uninstall: also remove the gateway systemd
                        drop-in (90-terminal-jail-hardening.conf,
                        95-terminal-jail-shell.conf) and run
                        'systemctl daemon-reload'. Needs root for /etc.
  -h, --help            Print this help and exit 0.

Environment (all optional):
  TERMINAL_JAIL_INSTALL_DIR    install directory (default: $HOME/.local/bin)
  TERMINAL_JAIL_RULES_DIR      target rules directory; when set it always wins
                               (default: derived from the install scope)
  TERMINAL_JAIL_USE_RELEASE=1  download release assets instead of using the
                               local checkout (rule packs need the checkout)
  TERMINAL_JAIL_VERSION        version to install (default: 1.1.0)
  TERMINAL_JAIL_BASE_URL       release base URL for TERMINAL_JAIL_USE_RELEASE=1
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --rule-pack)
            if [ $# -lt 2 ]; then
                echo "terminal-jail installer: --rule-pack requires a pack name" >&2
                exit 2
            fi
            add_rule_pack "$2"
            shift 2
            ;;
        --rule-pack=*)
            add_rule_pack "${1#--rule-pack=}"
            shift
            ;;
        --unrule-pack)
            if [ $# -lt 2 ]; then
                echo "terminal-jail installer: --unrule-pack requires a pack name" >&2
                exit 2
            fi
            add_unrule_pack "$2"
            shift 2
            ;;
        --unrule-pack=*)
            add_unrule_pack "${1#--unrule-pack=}"
            shift
            ;;
        --list-rule-packs)
            LIST_RULE_PACKS=1
            shift
            ;;
        --uninstall)
            UNINSTALL=1
            shift
            ;;
        --uninstall-systemd)
            UNINSTALL_SYSTEMD=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "terminal-jail installer: unknown argument '$1' (see --help)" >&2
            exit 2
            ;;
    esac
done

# --- source vs release mode --------------------------------------------------
# When run from a repository checkout — invoked relatively (./install.sh or
# install.sh) with standalone/terminal-jail present next to this script —
# install the local wrapper instead of downloading release assets. This keeps
# the documented install path working before (and without) published release
# assets. Any other invocation (curl | sh, absolute path) requires an explicit
# TERMINAL_JAIL_USE_RELEASE=1 opt-in — release mode never happens implicitly.
SCRIPT_DIR=""
LOCAL_WRAPPER=""
case "${0:-}" in
    ./*install.sh|install.sh)
        if [ -n "$0" ] && [ -f "$0" ]; then
            SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd 2>/dev/null || true)"
        fi
        if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/standalone/terminal-jail" ]; then
            LOCAL_WRAPPER="$SCRIPT_DIR/standalone/terminal-jail"
        fi
        ;;
esac

# Rule packs (TJ-GAP-061) ship in the repository checkout only: the pack files
# and the YAML validator live next to install.sh. Release mode has no pack
# source, so --rule-pack/--unrule-pack are refused there (see below) and
# PACKS_SOURCE_DIR stays empty — every pack path is guarded on it.
PACKS_SOURCE_DIR=""
if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/plugin/terminal_jail/rules/packs" ]; then
    PACKS_SOURCE_DIR="$SCRIPT_DIR/plugin/terminal_jail/rules/packs"
fi

# --- preflight ---------------------------------------------------------------
if [ -z "${HOME:-}" ]; then
    echo "terminal-jail installer: HOME is not set; cannot determine install directory" >&2
    exit 1
fi

if [ "$(uname -s)" != "Linux" ]; then
    echo "terminal-jail installer: Terminal Jail requires Linux (detected: $(uname -s))" >&2
    exit 1
fi

ARCH="$(uname -m)"
echo "terminal-jail installer: detected architecture ${ARCH}"

# --- release-mode gate -------------------------------------------------------
# No release assets are published yet. Without a local checkout wrapper and
# without an explicit TERMINAL_JAIL_USE_RELEASE=1 opt-in, refuse instead of
# downloading from a dead URL (curl | sh would otherwise 404 silently).
# --uninstall is exempt (TJ-GAP-071): it downloads nothing, so the dead-URL
# hazard does not apply and removal must work from any invocation shape.
if [ -z "$LOCAL_WRAPPER" ] && [ "$TERMINAL_JAIL_USE_RELEASE" != "1" ] && [ "$UNINSTALL" -eq 0 ]; then
    echo "terminal-jail installer: no local checkout detected and release mode is not enabled." >&2
    echo "  Release assets are not published yet (the default download URL returns 404)." >&2
    echo "  Supported install: run ./install.sh from a repository checkout." >&2
    echo "  To opt into release mode anyway, set TERMINAL_JAIL_USE_RELEASE=1" >&2
    echo "  (with TERMINAL_JAIL_BASE_URL if you host assets yourself)." >&2
    exit 1
fi

# --- rule packs need the checkout (TJ-GAP-061) -------------------------------
# A pack is a repository artifact (rules/packs/<name>.yaml) validated by a
# repository script, so both knobs are refused in release mode rather than
# half-working: nothing is written.
if [ -z "$LOCAL_WRAPPER" ]; then
    if [ -n "$RULE_PACKS" ] || [ -n "$UNRULE_PACKS" ]; then
        echo "terminal-jail installer: --rule-pack/--unrule-pack need the repository checkout (local mode); release mode ships no rule-pack source — nothing was written" >&2
        exit 2
    fi
fi

# --- --uninstall refuses pack/flag mixing (TJ-GAP-071) -----------------------
# Parse-time refusals: nothing has been created or written yet, so a rejected
# combination leaves the filesystem untouched. Pack flags belong to an install
# run; mixing them with uninstall is a caller error, not a best-effort.
if [ "$UNINSTALL" -eq 1 ]; then
    if [ -n "$RULE_PACKS" ] || [ -n "$UNRULE_PACKS" ] || [ "$LIST_RULE_PACKS" -eq 1 ]; then
        echo "terminal-jail installer: --uninstall cannot be combined with --rule-pack/--unrule-pack/--list-rule-packs — run them separately (nothing was written)" >&2
        exit 2
    fi
fi
if [ "$UNINSTALL_SYSTEMD" -eq 1 ] && [ "$UNINSTALL" -eq 0 ]; then
    echo "terminal-jail installer: --uninstall-systemd only means something together with --uninstall (nothing was written)" >&2
    exit 2
fi

# --- rule-pack listing (TJ-GAP-061) ------------------------------------------
# Informational only: name the packs this checkout ships and exit 0 without
# touching anything. A missing checkout/packs directory is refused loudly —
# an empty list would read as "this project has no packs".
if [ "$LIST_RULE_PACKS" -eq 1 ]; then
    if [ -z "$PACKS_SOURCE_DIR" ]; then
        echo "terminal-jail installer: --list-rule-packs needs a repository checkout (no plugin/terminal_jail/rules/packs next to ${0:-install.sh})" >&2
        exit 2
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        echo "terminal-jail installer: --list-rule-packs requires python3 (rule packs are YAML; the lister counts the rules)" >&2
        exit 2
    fi
    echo "terminal-jail installer: rule packs available in this checkout (opt in with --rule-pack <name>):"
    python3 "$SCRIPT_DIR/scripts/rule-pack-tool.py" list
    exit 0
fi

# --- downloader / checksum verifier (release mode only) ----------------------
has_curl=0
has_wget=0
has_sha256sum=0
has_shasum=0
if [ -z "$LOCAL_WRAPPER" ]; then
    if command -v curl >/dev/null 2>&1; then
        has_curl=1
    elif command -v wget >/dev/null 2>&1; then
        has_wget=1
    else
        echo "terminal-jail installer: requires curl or wget (neither found)" >&2
        exit 1
    fi

    if command -v sha256sum >/dev/null 2>&1; then
        has_sha256sum=1
    elif command -v shasum >/dev/null 2>&1; then
        has_shasum=1
    else
        echo "terminal-jail installer: requires sha256sum or shasum (neither found)" >&2
        exit 1
    fi
fi

download() {
    url="$1"
    out="$2"
    if [ "$has_curl" -eq 1 ]; then
        curl -fsSL "$url" -o "$out"
    else
        wget -qO "$out" "$url"
    fi
}

# --- checksum verifier -------------------------------------------------------
# (functions defined for release mode; local-mode installs skip checksum
# verification because the wrapper comes from the trusted checkout)

check_sha256() {
    file="$1"
    expected="$2"
    if [ "$has_sha256sum" -eq 1 ]; then
        echo "${expected}  ${file}" | sha256sum -c >/dev/null 2>&1
    else
        actual="$(shasum -a 256 "$file" | awk '{print $1}')"
        [ "$actual" = "$expected" ]
    fi
}

# --- dependency warnings (non-fatal) -----------------------------------------
if ! command -v bash >/dev/null 2>&1; then
    echo "terminal-jail installer: WARNING — bash is required to run terminal-jail but was not found"
fi
if ! command -v unshare >/dev/null 2>&1; then
    echo "terminal-jail installer: WARNING — unshare (util-linux) is required to run terminal-jail but was not found"
fi
# Bubblewrap is an OPTIONAL external runtime dependency (TJ-GAP-055). The CLI
# resolves bwrap from PATH at run time and falls back to util-linux unshare when
# it is absent, so a missing bwrap must NEVER fail an install: this is an
# advisory NOTE, not a preflight error. This installer never downloads, builds,
# installs as a package, or vendors bubblewrap — it only names the distro
# system package the user may install themselves. The package-manager examples
# below match the README and specs/cli.md wording.
if ! command -v bwrap >/dev/null 2>&1; then
    echo "terminal-jail installer: NOTE — optional bubblewrap (bwrap) not found. The CLI will use the util-linux unshare backend, and installation continues normally. To enable the private-/proc bwrap backend, install the distro system package (Debian/Ubuntu: apt install bubblewrap, Fedora/RHEL: dnf install bubblewrap). bubblewrap is an external dependency — this installer never downloads, builds, or redistributes it."
fi

# --- rules target resolution (DF-TERMINAL-JAIL-8) ----------------------------
# Resolved ONCE, here, so the shipped default rules file and any opt-in rule
# pack land in the SAME directory: the installer has exactly one notion of
# "rules dir". Assigns RESOLVED_RULES_DIR and RULES_SCOPE (plain call, never
# via command substitution, so the assignments reach the rest of the script).
resolve_user_rules_dir() {
    #   explicit: TERMINAL_JAIL_RULES_DIR set -> used verbatim (caller opted in;
    #             any path allowed, even outside the prefix)
    #   live:     default install dir ($HOME/.local/bin) -> the live user rules
    #             dir $HOME/.config/terminal-jail/rules.d (unchanged behavior;
    #             the engine does NOT honor XDG_CONFIG_HOME)
    #   engine:   custom prefix + the engine's own user-rules knob
    #             TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR set -> that exact
    #             directory (DF-TERMINAL-JAIL-22: the engine reads this env var
    #             verbatim — interruptor/config.py — so rules installed there
    #             are LOADED, and the installer's single rules dir IS the
    #             engine's rules dir)
    #   prefix:   anything else -> <install prefix>/config/terminal-jail/
    #             rules.d, with the parent resolved like LIB_DIR below. The
    #             engine does not scan prefix-local config: requested packs
    #             skip loudly in this scope (DF-TERMINAL-JAIL-22, below) and
    #             the shipped default rules file carries its own WARNING.
    if [ -n "$TERMINAL_JAIL_RULES_DIR" ]; then
        RESOLVED_RULES_DIR="$TERMINAL_JAIL_RULES_DIR"
        RULES_SCOPE="explicit"
    elif [ "$TERMINAL_JAIL_INSTALL_DIR" = "$HOME/.local/bin" ]; then
        RESOLVED_RULES_DIR="$HOME/.config/terminal-jail/rules.d"
        RULES_SCOPE="live"
    elif [ -n "${TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR:-}" ]; then
        RESOLVED_RULES_DIR="$TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR"
        RULES_SCOPE="engine-env"
    else
        # DF-TERMINAL-JAIL-24: normalize textually — the old
        # `cd <dir>/.. && pwd` idiom emitted a raw sh error when the parent
        # did not exist yet and fell back to a literal "<dir>/.." that
        # leaked un-normalized ".." into every printed rules path.
        rules_prefix="$(path_normalize "${TERMINAL_JAIL_INSTALL_DIR}/..")"
        RESOLVED_RULES_DIR="${rules_prefix}/config/terminal-jail/rules.d"
        RULES_SCOPE="prefix"
    fi
}
resolve_user_rules_dir

# --- uninstall (TJ-GAP-071) ---------------------------------------------------
# The exact mirror of the install section below. Every removal is PRINTED
# ("removed: <path>" / "removed rc-line: <file>"); everything the installer
# did NOT write is preserved and, inside the rules dir, explicitly listed at
# the end ("left in place (user-authored): <path>"). System paths
# (/etc/terminal-jail, the gateway systemd drop-in) are NEVER touched
# implicitly — the drop-in goes only behind --uninstall-systemd, and /etc/
# terminal-jail rules are root-managed policy this user-level uninstall must
# not delete. Idempotent: on an already-clean host every step no-ops and the
# script exits 0.
if [ "$UNINSTALL" -eq 1 ]; then
    removed_count=0

    # (1) rules dir contents — resolved with the SAME four-way resolution the
    # install used (explicit TERMINAL_JAIL_RULES_DIR > default install scope
    # live dir > engine-env > prefix-local config). Pack files are removed
    # FIRST so the user-authored census below cannot mistake one for a
    # user file.
    if [ -d "$RESOLVED_RULES_DIR" ]; then
        for rules_file in "$RESOLVED_RULES_DIR"/*; do
            [ -f "$rules_file" ] || continue
            base="$(basename "$rules_file")"
            case "$base" in
                00-builtins.yaml|terminal-jail-pack-*.yaml|*.bak-*)
                    rm -f "$rules_file"
                    echo "terminal-jail installer: removed: $rules_file"
                    removed_count=$((removed_count + 1))
                    ;;
            esac
        done
    fi

    # (2) wrapper binary — respect TERMINAL_JAIL_INSTALL_DIR (install.sh:621).
    if [ -f "${TERMINAL_JAIL_INSTALL_DIR}/terminal-jail" ]; then
        rm -f "${TERMINAL_JAIL_INSTALL_DIR}/terminal-jail"
        echo "terminal-jail installer: removed: ${TERMINAL_JAIL_INSTALL_DIR}/terminal-jail"
        removed_count=$((removed_count + 1))
    fi

    # (3) lib tree — the mirror of the install's LIB_DIR layout (install.sh:552).
    uninstall_lib_dir="$(path_normalize "${TERMINAL_JAIL_INSTALL_DIR}/..")/lib/terminal-jail"
    if [ -d "$uninstall_lib_dir" ]; then
        rm -rf "$uninstall_lib_dir"
        echo "terminal-jail installer: removed: $uninstall_lib_dir"
        removed_count=$((removed_count + 1))
    fi

    # (4) rc PATH block — remove ONLY the marker-scoped block the installer
    # wrote (install.sh:654-658 / 669-673). A line is installer-written when
    # it is 'export PATH="<resolved install dir>:$PATH"' (any occurrence after
    # a marker, or one standing alone) OR the classic default line that only
    # the DEFAULT scope ever appends.
    for rc_file in "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bashrc" "$HOME/.zshrc"; do
        [ -f "$rc_file" ] || continue
        path_line="export PATH=\"${TERMINAL_JAIL_INSTALL_DIR}:\$PATH\""
        default_path_line='export PATH="$HOME/.local/bin:$PATH"'
        if grep -qF '# terminal-jail' "$rc_file" 2>/dev/null \
            && { grep -qF "$path_line" "$rc_file" 2>/dev/null \
                 || grep -qF "$default_path_line" "$rc_file" 2>/dev/null; }; then
            rc_tmp="${rc_file}.terminal-jail-uninstall.$$"
            awk -v marker="# terminal-jail" -v pline="$path_line" -v dline="$default_path_line" '
                $0 == marker { skip=3; deleted=1; next }
                skip > 0 {
                    if ($0 == pline || $0 == dline) { skip=0; deleted=1; next }
                    skip--
                    print
                    next
                }
                { print }
                END { exit deleted ? 0 : 1 }
            ' "$rc_file" > "$rc_tmp" && mv "$rc_tmp" "$rc_file"
            echo "terminal-jail installer: removed rc-line: $rc_file"
            removed_count=$((removed_count + 1))
        fi
    done

    # (5) gateway systemd drop-in — explicit opt-in ONLY (never implied).
    if [ "$UNINSTALL_SYSTEMD" -eq 1 ]; then
        for drop_in in \
            /etc/systemd/system/hermes-gateway.service.d/90-terminal-jail-hardening.conf \
            /etc/systemd/system/hermes-gateway.service.d/95-terminal-jail-shell.conf
        do
            if [ -f "$drop_in" ]; then
                if rm -f "$drop_in" 2>/dev/null; then
                    echo "terminal-jail installer: removed: $drop_in"
                    removed_count=$((removed_count + 1))
                else
                    echo "terminal-jail installer: WARNING — could not remove $drop_in (root required?); remove it manually" >&2
                fi
            fi
        done
        if command -v systemctl >/dev/null 2>&1; then
            systemctl daemon-reload 2>/dev/null || echo "terminal-jail installer: WARNING — systemctl daemon-reload failed; run it manually" >&2
        fi
    elif [ -d /etc/systemd/system/hermes-gateway.service.d ] \
        && ls /etc/systemd/system/hermes-gateway.service.d/*terminal-jail*.conf >/dev/null 2>&1; then
        echo "terminal-jail installer: NOTE — a terminal-jail systemd drop-in exists under /etc/systemd/system/hermes-gateway.service.d/; re-run with --uninstall-systemd to remove it (needs root)"
    fi

    # (6) user-authored rules census — anything left in the rules dir that the
    # installer never wrote is named explicitly, never silently deleted.
    if [ -d "$RESOLVED_RULES_DIR" ]; then
        for rules_file in "$RESOLVED_RULES_DIR"/*; do
            [ -f "$rules_file" ] || continue
            base="$(basename "$rules_file")"
            case "$base" in
                00-builtins.yaml|terminal-jail-pack-*.yaml|*.bak-*) ;;
                *) echo "terminal-jail installer: left in place (user-authored): $rules_file" ;;
            esac
        done
    fi

    if [ "$removed_count" -eq 0 ]; then
        echo "terminal-jail installer: nothing to uninstall — no terminal-jail files found"
    fi
    echo "terminal-jail installer: uninstall done. System rules under /etc/terminal-jail (if any) are root-managed and were NOT touched."
    exit 0
fi

# --- opt-in rule packs (TJ-GAP-061, DF-TERMINAL-JAIL-21) ----------------------
# Packs are per-host policy: the default rule set stays lean and a pack is
# installed only when the operator asks for it (--rule-pack <name>), landing as
# terminal-jail-pack-<name>.yaml in the SAME resolved rules dir as the default
# rules file.
# DF-TERMINAL-JAIL-21: a pack-level failure is a loud SKIP, never an abort of
# the base install. Every requested pack is attempted independently; an unknown
# name, a missing python3, a missing PyYAML, or a validator refusal (bad
# schema, malformed YAML, id outside the pack namespace, id collision) skips
# that pack with a one-line reason on stderr and writes NOTHING for it — while
# the base install (wrapper, lib tree, default rules) always completes. If any
# requested pack was skipped, the installer prints a final summary at the very
# end and exits 2; with all requested packs installed (or none requested) the
# behavior and exit 0 are unchanged.
# scripts/rule-pack-tool.py is authoritative for every check; packs are
# validated one at a time IN THE ORDER REQUESTED, so a pack that collides with
# one requested earlier in the same invocation is refused when it is reached
# (the earlier pack stays installed — skipping cannot un-install it).
PACK_FAILURES=""

skip_rule_pack() {
    # DF-TERMINAL-JAIL-21: print the skip reason now and remember it (one line
    # per skipped pack) for the end-of-run summary.
    echo "$1" >&2
    PACK_FAILURES="${PACK_FAILURES:+$PACK_FAILURES
}$1"
}

if [ -n "$RULE_PACKS" ] || [ -n "$UNRULE_PACKS" ]; then
    pack_tool="$SCRIPT_DIR/scripts/rule-pack-tool.py"
    if [ ! -f "$pack_tool" ]; then
        # DF-TERMINAL-JAIL-21: a checkout missing its validator skips every
        # requested pack instead of aborting the install.
        for pack in $RULE_PACKS; do
            skip_rule_pack "terminal-jail installer: skipped: pack '${pack}' — rule packs need ${pack_tool}, which is missing from this checkout"
        done
    else
    install_rule_pack() {
        pack="$1"
        # DF-TERMINAL-JAIL-22: a requested pack may only be reported as
        # installed when the engine will actually LOAD it. The pack lands in
        # the one resolved rules dir; in the prefix scope that directory is
        # prefix-local config the engine never scans, so installing there
        # would be silent inertness. Refuse the PACK — never the base install
        # — with the exact remediation, reusing the DF-TERMINAL-JAIL-21
        # skip/exit-2 contract. Every engine-loaded scope (live, explicit
        # TERMINAL_JAIL_RULES_DIR, engine-env) installs normally.
        if [ "$RULES_SCOPE" = "prefix" ]; then
            echo "terminal-jail installer: rules target is ${RESOLVED_RULES_DIR} (prefix-local config, custom TERMINAL_JAIL_INSTALL_DIR) — the engine does not read prefix-local config, so installing '${pack}' there would be silently inert." >&2
            skip_rule_pack "terminal-jail installer: skipped: pack '${pack}' — the resolved rules dir ${RESOLVED_RULES_DIR} is prefix-local config the engine does NOT load (it reads /etc/terminal-jail/rules.d and ~/.config/terminal-jail/rules.d only). Nothing was written for this pack. Remediation, pick one: (1) re-run with TERMINAL_JAIL_RULES_DIR=<engine-loaded dir> (explicit target, always wins); (2) re-run with TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=<engine-loaded dir> exported when BOTH installing and running the CLI (the engine reads this env var at run time); (3) re-run with the default install dir (no custom TERMINAL_JAIL_INSTALL_DIR) so the live ~/.config/terminal-jail/rules.d is targeted."
            return 0
        fi
        pack_src="${PACKS_SOURCE_DIR}/${pack}.yaml"
        pack_dest="${RESOLVED_RULES_DIR}/terminal-jail-pack-${pack}.yaml"
        if [ -z "$PACKS_SOURCE_DIR" ] || [ ! -f "$pack_src" ]; then
            if [ -n "$PACKS_SOURCE_DIR" ]; then
                skip_rule_pack "terminal-jail installer: skipped: pack '${pack}' — unknown pack name (no ${pack_src}); run --list-rule-packs to list the packs this checkout ships"
            else
                skip_rule_pack "terminal-jail installer: skipped: pack '${pack}' — unknown pack name (this checkout ships no plugin/terminal_jail/rules/packs directory); run --list-rule-packs to list the packs this checkout ships"
            fi
            return 0
        fi
        if ! command -v python3 >/dev/null 2>&1; then
            skip_rule_pack "terminal-jail installer: skipped: pack '${pack}' — python3 is required to validate a pack BEFORE installing it and was not found; install python3 and re-run this installer"
            return 0
        fi
        # DF-TERMINAL-JAIL-21 PyYAML preflight: without PyYAML the validator
        # can only parse plain JSON (its stdlib json fallback), so a YAML pack
        # would be refused with a misleading JSONDecodeError. Name the missing
        # dependency and both remedies instead, and skip without running the
        # validator. A pack that parses as plain JSON is NOT refused here: the
        # validator's json fallback handles it and the pack installs normally.
        if ! python3 -c 'import yaml' >/dev/null 2>&1; then
            if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$pack_src" >/dev/null 2>&1; then
                skip_rule_pack "terminal-jail installer: skipped: pack '${pack}' — PyYAML is required to parse YAML rule packs and was not found; install the distro package (Debian/Ubuntu: apt install python3-yaml, Fedora/RHEL: dnf install python3-yaml) or run pip install pyyaml, then re-run this installer"
                return 0
            fi
        fi
        # FAIL CLOSED: validate before writing anything. The validator refuses
        # invalid schema, malformed YAML, ids outside the pack's namespace, and
        # id collisions (engine builtins / installed rule files).
        if ! python3 "$pack_tool" validate "$pack_src" --pack-name "$pack" --rules-dir "$RESOLVED_RULES_DIR"; then
            skip_rule_pack "terminal-jail installer: skipped: pack '${pack}' — REFUSED by the validator, nothing was written (see the validator reason above)"
            return 0
        fi
        mkdir -p "$RESOLVED_RULES_DIR"
        cp "$pack_src" "$pack_dest"
        echo "terminal-jail installer: installed rule pack '${pack}' to ${pack_dest}"
    }

    remove_rule_pack() {
        pack="$1"
        # Exactly one file: terminal-jail-pack-<name>.yaml. The default rules
        # file and every other pack are never touched (the name is shell-safe:
        # [a-z0-9-] only, quoted, never globbed).
        pack_dest="${RESOLVED_RULES_DIR}/terminal-jail-pack-${pack}.yaml"
        if [ -f "$pack_dest" ]; then
            rm -f "$pack_dest"
            echo "terminal-jail installer: removed rule pack '${pack}' (${pack_dest})"
        else
            echo "terminal-jail installer: rule pack '${pack}' is not installed at ${pack_dest} — nothing was removed"
        fi
    }

    for pack in $RULE_PACKS; do
        install_rule_pack "$pack"
    done
    fi
    for pack in $UNRULE_PACKS; do
        remove_rule_pack "$pack"
    done
fi

# --- install -----------------------------------------------------------------
mkdir -p "$TERMINAL_JAIL_INSTALL_DIR"

tmpdir="${TERMINAL_JAIL_INSTALL_DIR}"
tmp_payload="${tmpdir}/.terminal-jail.$$"
tmp_checksum="${tmpdir}/.terminal-jail.$$.sha256"

cleanup() {
    rm -f "$tmp_payload" "$tmp_checksum"
}
trap cleanup EXIT INT TERM

echo "terminal-jail installer: installing v${TERMINAL_JAIL_VERSION}..."

if [ -n "$LOCAL_WRAPPER" ]; then
    echo "terminal-jail installer: repository checkout detected — installing local wrapper (${LOCAL_WRAPPER})"
    cp "$LOCAL_WRAPPER" "$tmp_payload"

    # Ship the runtime support tree next to the binary so the installed CLI
    # finds the interruptor bridge and seccomp loader (fail-closed: a binary
    # without its bridge BLOCKS in enforce mode — see TJ-GAP-021).
    LIB_DIR="$(path_normalize "${TERMINAL_JAIL_INSTALL_DIR}/..")/lib/terminal-jail"
    if [ -d "$SCRIPT_DIR/plugin/terminal_jail" ]; then
        mkdir -p "$LIB_DIR/plugin"
        cp -R "$SCRIPT_DIR/plugin/terminal_jail" "$LIB_DIR/plugin/"
        echo "terminal-jail installer: installed plugin bridge tree to ${LIB_DIR}/plugin/"
    else
        echo "terminal-jail installer: WARNING — plugin tree not found next to installer; installed binary will fail closed (bridge missing)" >&2
    fi
    if [ -f "$SCRIPT_DIR/standalone/seccomp-loader.py" ]; then
        mkdir -p "$LIB_DIR"
        cp "$SCRIPT_DIR/standalone/seccomp-loader.py" "$LIB_DIR/"
        echo "terminal-jail installer: installed seccomp loader to ${LIB_DIR}/seccomp-loader.py"
    fi
    # Ship the default rules file to the user rules directory so user rules
    # actually load (the engine reads ~/.config/terminal-jail/rules.d — see
    # README Rule Loader row; /etc/terminal-jail/rules.d stays the system
    # override path for root-managed deployments).
    if [ -f "$SCRIPT_DIR/plugin/terminal_jail/rules/00-builtins.yaml" ]; then
        # DF-TERMINAL-JAIL-8: the three-way rules-target resolution lives in
        # resolve_user_rules_dir() above, called ONCE before the install — the
        # default rules file and any opt-in rule pack share that one answer.
        user_rules_dir="$RESOLVED_RULES_DIR"
        rules_scope="$RULES_SCOPE"
        if [ "$rules_scope" = "prefix" ]; then
            echo "terminal-jail installer: WARNING — non-default install prefix; installing default rules to ${user_rules_dir}. The engine loads /etc/terminal-jail/rules.d and ~/.config/terminal-jail/rules.d only; set TERMINAL_JAIL_RULES_DIR explicitly to target the live rules directory, or export TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=${user_rules_dir} when running the CLI to load this directory (DF-TERMINAL-JAIL-22: requested rule packs are NOT installed in this scope)."
        fi
        shipped_rules="$SCRIPT_DIR/plugin/terminal_jail/rules/00-builtins.yaml"
        installed_rules="${user_rules_dir}/00-builtins.yaml"
        mkdir -p "$user_rules_dir"
        # These rules are user-editable config (the engine loads rules.d with
        # SAME-ID OVERRIDE — see interruptor/decider.py), so an unconditional
        # copy silently destroys user edits on re-install. Back up first when
        # the installed file differs from the shipped default. Non-interactive:
        # never prompt, never read stdin.
        if [ -f "$installed_rules" ] && ! cmp -s "$shipped_rules" "$installed_rules"; then
            rules_backup="${installed_rules}.bak-$(date -u +%Y%m%dT%H%M%SZ)"
            cp "$installed_rules" "$rules_backup"
            echo "terminal-jail installer: WARNING — existing user rules differed; backed up to ${rules_backup} before installing defaults"
        fi
        cp "$shipped_rules" "$installed_rules"
        echo "terminal-jail installer: installed default rules to ${installed_rules}"
    else
        echo "terminal-jail installer: WARNING — default rules file not found next to installer; user rules directory left empty" >&2
    fi
else
    echo "terminal-jail installer: downloading v${TERMINAL_JAIL_VERSION}..."
    download "${TERMINAL_JAIL_BASE_URL}/terminal-jail" "$tmp_payload"
    download "${TERMINAL_JAIL_BASE_URL}/terminal-jail.sha256" "$tmp_checksum"

    expected="$(awk '{print $1}' "$tmp_checksum")"
    if ! check_sha256 "$tmp_payload" "$expected"; then
        echo "terminal-jail installer: checksum verification FAILED — aborting" >&2
        exit 1
    fi
    echo "terminal-jail installer: checksum OK"
fi

# Integrity sanity check — first line must be the expected shebang.
first_line="$(head -n1 "$tmp_payload")"
if [ "$first_line" != "#!/usr/bin/env bash" ]; then
    echo "terminal-jail installer: downloaded file does not look like terminal-jail (bad shebang)" >&2
    exit 1
fi
if [ ! -s "$tmp_payload" ]; then
    echo "terminal-jail installer: downloaded file is empty" >&2
    exit 1
fi

chmod 0755 "$tmp_payload"
mv "$tmp_payload" "${TERMINAL_JAIL_INSTALL_DIR}/terminal-jail"

echo "terminal-jail installer: installed to ${TERMINAL_JAIL_INSTALL_DIR}/terminal-jail"

# --- PATH setup --------------------------------------------------------------
case ":${PATH}:" in
    *:"${TERMINAL_JAIL_INSTALL_DIR}":*)
        echo "terminal-jail installer: ${TERMINAL_JAIL_INSTALL_DIR} is already on PATH"
        ;;
    *)
        startup_file=""
        for candidate in "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bashrc" "$HOME/.zshrc"; do
            if [ -f "$candidate" ]; then
                startup_file="$candidate"
                break
            fi
        done
        if [ -z "$startup_file" ] && [ "$TERMINAL_JAIL_INSTALL_DIR" = "$HOME/.local/bin" ]; then
            startup_file="$HOME/.profile"
        fi

        if [ -n "$startup_file" ]; then
            if [ "$TERMINAL_JAIL_INSTALL_DIR" = "$HOME/.local/bin" ]; then
                # Default install dir: the historical behavior, unchanged
                # (TJ-GAP-065 criterion: default installs keep appending the
                # $HOME/.local/bin entry, idempotently).
                if grep -qF '# terminal-jail' "$startup_file" 2>/dev/null; then
                    : # already present
                elif grep -qF "PATH=\"$HOME/.local/bin:\$PATH\"" "$startup_file" 2>/dev/null; then
                    : # equivalent entry exists
                elif grep -qF "export PATH=\"$HOME/.local/bin:\$PATH\"" "$startup_file" 2>/dev/null; then
                    : # equivalent entry exists
                else
                    cat >> "$startup_file" <<'SHELLRC'

# terminal-jail
export PATH="$HOME/.local/bin:$PATH"
SHELLRC
                    echo "terminal-jail installer: added PATH entry to ${startup_file}"
                fi
            else
                # TJ-GAP-065: a non-default install dir must never grow the
                # hardcoded $HOME/.local/bin entry — the binary is not there,
                # so that line leaves "command not found" after relogin while
                # the installer claims it configured PATH. Append (once) a
                # line pointing at the ACTUAL dir; the idempotency check greps
                # the exact rendered line, so re-runs never duplicate even
                # when an old marker or a stale default-scope block exists.
                path_line="export PATH=\"${TERMINAL_JAIL_INSTALL_DIR}:\$PATH\""
                if grep -qF "$path_line" "$startup_file" 2>/dev/null; then
                    : # correct entry already present
                else
                    printf '\n# terminal-jail\n%s\n' "$path_line" >> "$startup_file"
                    echo "terminal-jail installer: added PATH entry to ${startup_file}"
                fi
            fi
            echo "terminal-jail installer: to use immediately, run: export PATH=\"${TERMINAL_JAIL_INSTALL_DIR}:\$PATH\""
        else
            echo "terminal-jail installer: could not identify a shell startup file."
            echo "  Add the following line to your shell profile:"
            echo "  export PATH=\"${TERMINAL_JAIL_INSTALL_DIR}:\$PATH\""
        fi
        ;;
esac

echo "terminal-jail installer: done."

# --- DF-TERMINAL-JAIL-21 exit-code contract ----------------------------------
# The base install has completed. If any requested rule pack was skipped, print
# the final summary (what installed, what skipped and why) and exit 2 — the
# summary is the last thing the operator reads, and the nonzero exit keeps
# install automation honest without ever aborting the base install.
if [ -n "$PACK_FAILURES" ]; then
    echo "terminal-jail installer: SUMMARY — installed: wrapper at ${TERMINAL_JAIL_INSTALL_DIR}/terminal-jail" >&2
    printf '%s\n' "$PACK_FAILURES" >&2
    echo "terminal-jail installer: SUMMARY — at least one requested rule pack was skipped; base install completed" >&2
    exit 2
fi
