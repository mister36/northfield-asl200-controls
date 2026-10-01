#!/usr/bin/env bash
# Build the firmware for the host and run the full variant x scenario SIL matrix.
#   ./scripts/run_sil.sh                         # everything
#   ./scripts/run_sil.sh asl200_electric_mack    # one variant
set -euo pipefail
cd "$(dirname "$0")/.."
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build build -j >/dev/null
args=()
for v in "$@"; do args+=(--variant "$v"); done
status=0
python3 -m sil.matrix --out out "${args[@]}" || status=$?
python3 viz/build.py --out out >/dev/null
echo "dashboard: out/matrix.html   summary: out/summary.md"
exit $status
