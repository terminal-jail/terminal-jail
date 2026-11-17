#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 12: RED-prove the fresh-host premise of the failing test.
# Dev host has unzip; a clean host does not, and _link_tools() silently skips absent tools.
set -u
REPO=/home/kara/terminal-jail
NB=/tmp/tj-1117-pub/nozip-bin
mkdir -p "$NB"
for t in sh bash python3 uname unshare head awk mkdir mv chmod cat grep rm cp sha256sum \
         basename dirname sed env mktemp id printf test cat unzip; do
  if [ "$t" != unzip ] && [ -x "/usr/bin/$t" ]; then ln -sf "/usr/bin/$t" "$NB/$t"; fi
done
echo "nozip-bin has unzip? [$(ls "$NB" | grep -c '^unzip$')]"
echo
echo "=== ARM GREEN: host PATH (has /usr/bin/unzip) ==="
cd "$REPO" || exit 9
.venv/bin/python -m pytest plugin/test_install.py::test_release_wheel_install_without_unzip_uses_python_zipfile -x -q 2>&1 | tail -4
echo
echo "=== ARM RED: PATH without unzip (a clean machine's premise) ==="
env PATH="$NB" "$REPO/.venv/bin/python" -m pytest plugin/test_install.py::test_release_wheel_install_without_unzip_uses_python_zipfile -x -q 2>&1 | tail -12
