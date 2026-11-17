#!/usr/bin/env bash
# Stage venvs for the three CI-matrix interpreters (3.11, 3.12, 3.13).
set -u
BASE=/home/kara/.hermes/cache/scratch/tj-1117f
UVPY=/home/kara/.local/share/uv/python
cd "$BASE" || exit 3

for pair in "3.11.15:venv311" "3.13.13:venv313"; do
  ver="${pair%%:*}"
  tag="${pair##*:}"
  minor="${ver%.*}"
  py="$UVPY/cpython-$ver-linux-x86_64-gnu/bin/python$minor"
  if [ ! -x "$py" ]; then echo "MISSING $py"; continue; fi
  if [ ! -x "$BASE/$tag/bin/python" ]; then
    "$py" -m venv "$BASE/$tag"
  fi
  "$BASE/$tag/bin/pip" install -q --disable-pip-version-check pytest pyyaml
  printf '%s | %s | %s\n' "$tag" "$("$BASE/$tag/bin/python" -V 2>&1)" "$("$BASE/$tag/bin/python" -m pytest --version 2>&1 | head -1)"
done
