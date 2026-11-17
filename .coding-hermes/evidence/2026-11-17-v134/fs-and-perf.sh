#!/usr/bin/env bash
# Dogfood 2026-11-17 arm 6: (a) is the fs-tier degrade layout-specific or host-wide?
#                        (b) Step 2b timing of the headline operation.
set -u
REPO=/home/kara/terminal-jail
P=/tmp/tj-1117-pub/connect_probe.py
echo "=== (a) fs-tier message with a NORMAL home and the CHECKOUT CLI ==="
for H in /home/kara /tmp/tj-1117-pub/home; do
  echo "--- HOME=$H ---"
  env -u TERMINAL_JAIL_INTERRUPTOR_RULES -u TERMINAL_JAIL_INTERRUPTOR_RULE_DIR \
      -u TERMINAL_JAIL_LANDLOCK -u TERMINAL_JAIL_LANDLOCK_NET_ALLOW \
      TERMINAL_JAIL_LANDLOCK_NET=1 HOME="$H" "$REPO/standalone/terminal-jail" python3 "$P" \
      > /tmp/tj-1117-pub/fs-$RANDOM.out 2> /tmp/tj-1117-pub/fs-last.err
  echo "rc=$?"
  grep -c 'filesystem tier not applied' /tmp/tj-1117-pub/fs-last.err | sed 's/^/fs_warning_lines=/'
  grep -m1 'filesystem tier not applied' /tmp/tj-1117-pub/fs-last.err | cut -c1-260
done
echo
echo "=== (b) timing: headline op = one wrapped allow command ==="
command -v hyperfine >/dev/null && echo "hyperfine: $(hyperfine --version)" || echo "hyperfine: ABSENT"
BIN=/tmp/tj-1117-pub/home/.local/bin/terminal-jail
if command -v hyperfine >/dev/null; then
  echo "--- warm, n=20, tier default ---"
  env -u TERMINAL_JAIL_INTERRUPTOR_RULES HOME=/tmp/tj-1117-pub/home hyperfine --warmup 3 -r 20 \
    "$BIN echo hello" --export-json /tmp/tj-1117-pub/perf-warm.json 2>&1 | tail -6
  echo "--- floor: /bin/true (no wrapper) ---"
  hyperfine --warmup 3 -r 20 "/bin/true" --export-json /tmp/tj-1117-pub/perf-floor.json 2>&1 | tail -4
  echo "--- net tier ON (the flagship opt-in) n=20 ---"
  env -u TERMINAL_JAIL_INTERRUPTOR_RULES TERMINAL_JAIL_LANDLOCK_NET=1 HOME=/tmp/tj-1117-pub/home hyperfine --warmup 3 -r 20 \
    "$BIN echo hello" --export-json /tmp/tj-1117-pub/perf-net.json 2>&1 | tail -4
fi
echo "--- cold-ish: first run after install, 5 sequential fresh shells ---"
for i in 1 2 3 4 5; do
  /usr/bin/time -f "run$i=%es" env HOME=/tmp/tj-1117-pub/home "$BIN" echo hello >/dev/null 2>>/tmp/tj-1117-pub/perf-cold.txt
done
cat /tmp/tj-1117-pub/perf-cold.txt
