#!/usr/bin/env bash
# Dogfood 2026-11-17: source install into a fresh HOME (documented channel).
set -u
HOME_DIR="$1"
cd /home/kara/terminal-jail || exit 9
mkdir -p "$HOME_DIR"
env HOME="$HOME_DIR" /usr/bin/time -f 'INSTALL_WALL=%es rc=%x' ./install.sh --no-path \
  > "$HOME_DIR/install.out" 2> "$HOME_DIR/install.err"
echo "install_rc=$?"
tail -6 "$HOME_DIR/install.out"
echo "--- stderr tail ---"
tail -4 "$HOME_DIR/install.err"
echo "--- installed binary ---"
ls -l "$HOME_DIR/.local/bin/terminal-jail" 2>&1
env HOME="$HOME_DIR" "$HOME_DIR/.local/bin/terminal-jail" --version 2>&1 | head -3
