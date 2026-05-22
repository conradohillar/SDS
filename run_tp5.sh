#!/usr/bin/env bash
# TP5 Sistema 3 – Single smoke-test run then optional visualizer.
# Override params via env vars.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp5-sim"
BIN_DIR="${TP5_BIN_PATH:-$REPO_ROOT/tp5-bin}"
VIS_DIR="$REPO_ROOT/tp5-vis/src/main/python"

N="${N:-20}"
SEED="${SEED:-42}"
MODE="${MODE:-quiral}"
DT="${DT:-0.01}"
TF="${TF:-200.0}"
DT2="${DT2:-0.1}"
RUN_ID="${RUN_ID:-runs/$MODE/N${N}/r${SEED}}"
VISUALIZE="${VISUALIZE:-1}"
RENDER_MP4="${RENDER_MP4:-0}"

echo "Building tp5-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

echo "Running TimeDrivenActive (N=$N, seed=$SEED, mode=$MODE, dt=$DT, tf=$TF) …"
(cd "$SIM_DIR" && mvn -q exec:java \
    -Dexec.mainClass=TimeDrivenActive \
    "-Dexec.args=--n $N --seed $SEED --mode $MODE --dt $DT --tf $TF --dt2 $DT2 \
                 --bin $BIN_DIR --run-id $RUN_ID")

echo "Output → $BIN_DIR/$RUN_ID/"
ls -lh "$BIN_DIR/$RUN_ID/"

if [[ "$VISUALIZE" == "1" ]]; then
    echo "Launching visualizer …"
    python3 "$VIS_DIR/visualizer5.py" \
        --bin "$BIN_DIR" --mode "$MODE" --n "$N" --r "$SEED"
fi

if [[ "$RENDER_MP4" == "1" ]]; then
    echo "Rendering MP4 …"
    python3 "$VIS_DIR/render_tp5_mp4.py" \
        --bin "$BIN_DIR" --mode "$MODE" --n "$N" --r "$SEED"
fi
