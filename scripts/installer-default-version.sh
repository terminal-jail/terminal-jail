#!/bin/sh
# installer-default-version.sh — print install.sh's default TERMINAL_JAIL_VERSION.
#
# Usage: installer-default-version.sh [path-to-install.sh]   (default: ./install.sh)
#
# Prints the version the pin line
#   TERMINAL_JAIL_VERSION="${TERMINAL_JAIL_VERSION:-X.Y.Z}"
# defaults to, with an optional leading 'v' stripped (the installer accepts a
# leading 'v' for overrides). Exits non-zero with a named reason when the file
# is missing or carries no parseable default-form pin line — it never guesses.
#
# Consumed by the pre-tag gate (scripts/release-cut-check.sh) and the publish
# workflow (.github/workflows/release.yml) so a tag whose installer default
# lags the tag itself can neither be cut nor published (RELEASE-TJ-030:
# v1.3.4's installer shipped defaulting to the v1.3.3 assets).
set -u

FILE="${1:-install.sh}"
if [ ! -f "${FILE}" ]; then
    echo "installer-default-version.sh: no such file: ${FILE}" >&2
    exit 1
fi
line="$(grep -E '^TERMINAL_JAIL_VERSION=' "${FILE}" | head -n 1)"
if [ -z "${line}" ]; then
    echo "installer-default-version.sh: ${FILE} carries no TERMINAL_JAIL_VERSION= pin line" >&2
    exit 1
fi
default="${line#*TERMINAL_JAIL_VERSION:-}"
if [ "${default}" = "${line}" ]; then
    echo "installer-default-version.sh: ${FILE} pin line is not the \"\${TERMINAL_JAIL_VERSION:-...}\" default form: ${line}" >&2
    exit 1
fi
default="${default%%\}*}"
default="${default#v}"
case "${default}" in
    '' | *[!0-9A-Za-z._+-]*)
        echo "installer-default-version.sh: could not parse a version out of the pin line: ${line}" >&2
        exit 1
        ;;
esac
printf '%s\n' "${default}"
