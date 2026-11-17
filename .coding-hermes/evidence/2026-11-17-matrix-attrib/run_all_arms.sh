#!/usr/bin/env bash
# Run the unzip A/B on all three CI-matrix interpreters, sequentially.
set -u
BASE=/home/kara/.hermes/cache/scratch/tj-1117f
for pair in "3.11:311" "3.12:312" "3.13:313"; do
  ver="${pair%%:*}"; tag="${pair##*:}"
  PY="$BASE/venv$tag/bin/python" TAG="$ver" bash "$BASE/ab_matrix2.sh"
  echo "########## done $ver ##########"
done
cat /proc/loadavg
