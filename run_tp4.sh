#!/usr/bin/env bash
# Sistema 2 – Single Time-Driven MD run.
# Options passed via environment variables or --args override.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp4-sim"
BIN_DIR="${TP4_BIN_PATH:-$REPO_ROOT/tp4-bin}"
VIS_DIR="$REPO_ROOT/tp4-vis/src/main/python"

N="${N:-1000}"
SEED="${SEED:-42}"
DT="${DT:-0.001}"
TF="${TF:-20.0}"
DT2="${DT2:-0.3}"
K="${K:-1000.0}"
RUN_ID="${RUN_ID:-default}"
MAX_FRAMES="${MAX_FRAMES:-0}"
VISUALIZE="${VISUALIZE:-1}"
RENDER_MP4="${RENDER_MP4:-0}"
SKIP_TIME="${SKIP_TIME:-0.0}"

echo "Building tp4-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

rm -rf "$BIN_DIR/$RUN_ID"

echo "Running TimeDrivenMD (N=$N, seed=$SEED, dt=$DT, tf=$TF, k=$K, run-id=$RUN_ID) …"
(cd "$SIM_DIR" && mvn -q exec:java \
    -Dexec.mainClass=TimeDrivenMD \
    "-Dexec.args=--n $N --seed $SEED --dt $DT --tf $TF --dt2 $DT2 \
                 --k $K --max-frames $MAX_FRAMES --bin $BIN_DIR --run-id $RUN_ID")

if [[ "$VISUALIZE" == "1" ]]; then
    echo "Launching visualizer …"
    python3 "$VIS_DIR/visualizer4.py" \
        --bin "$BIN_DIR" --run-id "$RUN_ID" --skip-time "$SKIP_TIME"
fi

if [[ "$RENDER_MP4" == "1" ]]; then
    echo "Rendering MP4 …"
    python3 "$VIS_DIR/render_tp4_mp4.py" \
        --bin "$BIN_DIR" --run-id "$RUN_ID" \
        --output "$BIN_DIR/animations/${RUN_ID}.mp4" \
        --skip-time "$SKIP_TIME"
fi

echo "Done. Output → $BIN_DIR/$RUN_ID/"
