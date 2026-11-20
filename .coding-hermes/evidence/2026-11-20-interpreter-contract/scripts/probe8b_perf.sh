#!/bin/bash
# Step 2b perf v2 — hyperfine with full PATH (hyperfine in ~/.cargo/bin), interleaved tier A/B.
ROOT=/home/kara/tj-df-1120
HOME_B=$ROOT/home-b
TJ=$HOME_B/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin:/home/kara/.cargo/bin
OUT=/tmp/tj-df-1120/arms
HYPER=/home/kara/.cargo/bin/hyperfine

echo "loadavg: $(cat /proc/loadavg)"
echo "== plain allow tier ON n=20 =="
( cd "$HOME_B/mk" && env -u TERMINAL_JAIL_LANDLOCK PATH=$BASE HOME=$HOME_B \
  "$HYPER" --warmup 3 -r 20 --style basic "$TJ /bin/true" ) 2>&1 | tee "$OUT/perf2-allow-on.txt" | tail -6
echo "== plain allow tier OFF n=20 =="
( cd "$HOME_B/mk" && env PATH=$BASE HOME=$HOME_B TERMINAL_JAIL_LANDLOCK=0 \
  "$HYPER" --warmup 3 -r 20 --style basic "$TJ /bin/true" ) 2>&1 | tee "$OUT/perf2-allow-off.txt" | tail -6
echo "== modify path make ok n=10 =="
( cd "$HOME_B/mk" && env -u TERMINAL_JAIL_LANDLOCK PATH=$BASE HOME=$HOME_B \
  "$HYPER" --warmup 2 -r 10 --style basic "$TJ make ok" ) 2>&1 | tee "$OUT/perf2-modify.txt" | tail -6
echo "loadavg after: $(cat /proc/loadavg)"
echo DONE-PERF2
