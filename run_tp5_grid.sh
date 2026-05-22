#!/usr/bin/env bash
# TP5 Sistema 3 – Full grid run via ActiveRunner (parallel, all modes × N × realizations).
# Intended to be run on macmini via SSH.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp5-sim"
BIN_DIR="${TP5_BIN_PATH:-$REPO_ROOT/tp5-bin}"
VIS_DIR="$REPO_ROOT/tp5-vis/src/main/python"

TF="${TF:-10000.0}"
DT="${DT:-0.01}"
DT2="${DT2:-0.1}"
RUNS="${RUNS:-5}"
NO_FRAMES="${NO_FRAMES:-}"   # set to "--no-frames" to skip frame files

echo "Building tp5-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests)

echo "Launching ActiveRunner (mode×N×r = 2×8×$RUNS = $((2*8*RUNS)) tasks) …"
echo "Output base → $BIN_DIR"

(cd "$SIM_DIR" && mvn -q exec:java \
    -Dexec.mainClass=ActiveRunner \
    "-Dexec.args=--tf $TF --dt $DT --dt2 $DT2 --runs $RUNS --bin $BIN_DIR $NO_FRAMES") \
    2>&1 | tee "$BIN_DIR/active_runner.log"

echo ""
echo "Grid complete. Generating analysis plots …"

python3 "$VIS_DIR/analysis_pressure_vel.py" --bin-dir "$BIN_DIR" --n-runs "$RUNS"
python3 "$VIS_DIR/analysis_jamming.py"      --bin-dir "$BIN_DIR" --n-runs "$RUNS"

echo "Done. Images → $BIN_DIR/images/"
