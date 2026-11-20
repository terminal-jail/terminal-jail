#!/bin/bash
# Step 2b perf — headline ops at HEAD e67e07e, installed CLI (home-b), warm.
# Allow path (tier default vs off) + modify path (make ok) + verify via CPU time.
ROOT=/home/kara/tj-df-1120
HOME_B=$ROOT/home-b
TJ=$HOME_B/.local/bin/terminal-jail
BASE=/usr/local/bin:/usr/bin:/bin
OUT=/tmp/tj-df-1120/arms
mkdir -p "$OUT"

env P="cat /proc/loadavg" ; echo "loadavg: $(cat /proc/loadavg)"

echo "== warm allow, tier ON, n=20 (hyperfine) =="
( cd "$HOME_B/mk" && env -u TERMINAL_JAIL_LANDLOCK PATH=$BASE HOME=$HOME_B \
  hyperfine --warmup 3 -r 20 --style basic "$TJ /bin/true" ) 2>&1 | tee "$OUT/perf-allow-tier-on.txt"

echo "== warm allow, tier OFF, n=20 =="
( cd "$HOME_B/mk" && env PATH=$BASE HOME=$HOME_B TERMINAL_JAIL_LANDLOCK=0 \
  hyperfine --warmup 3 -r 20 --style basic "$TJ /bin/true" ) 2>&1 | tee "$OUT/perf-allow-tier-off.txt"

echo "== warm modify path (make ok), clean PATH, n=10 =="
( cd "$HOME_B/mk" && env -u TERMINAL_JAIL_LANDLOCK PATH=$BASE HOME=$HOME_B \
  hyperfine --warmup 2 -r 10 --style basic "$TJ make ok" ) 2>&1 | tee "$OUT/perf-modify.txt"

echo "== first-run series (5 sequential, tier on) =="
for i in 1 2 3 4 5; do
  ( cd "$HOME_B/mk" && env -u TERMINAL_JAIL_LANDLOCK PATH=$BASE HOME=$HOME_B \
    /usr/bin/time -f "run$i wall=%e user=%U sys=%S" "$TJ" make ok ) >/dev/null 2>"$OUT/first-run-$i.txt"
  cat "$OUT/first-run-$i.txt" | tail -1
done
echo "loadavg after: $(cat /proc/loadavg)"
echo DONE-PERF
