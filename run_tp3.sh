#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_tp3.sh  –  Build, run and (optionally) visualize TP3 Sistema 1.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration (edit here) ─────────────────────────────────────────────────
N=400           # number of particles
SEED=$RANDOM    # random seed (randomized each run)
TF=2200.0        # simulation end time [s]
MAX_FRAMES=10000 # animation frame cap  (0 = no frames)
FRAME_EVERY=50  # write a frame every N events
RENDER_MP4=true
FPS=60
ARROW_LEN=1.5
MACRO_BLOCK_SIZE=1   # set to 2 to avoid ffmpeg rescaling warnings
SKIP_TIME=2000        # skip frames with t < SKIP_TIME in the animation

# ── Paths (auto-resolved, do not normally need editing) ───────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TP3_SIM_DIR="$REPO_ROOT/tp3-sim"
TP3_VIS_PY="$REPO_ROOT/tp3-vis/src/main/python/visualizer3.py"
TP3_BIN_DIR="$REPO_ROOT/tp3-bin"

export TP3_BIN_PATH="$TP3_BIN_DIR"
mkdir -p "$TP3_BIN_DIR"

# ── Build simulation ──────────────────────────────────────────────────────────
echo "Building tp3-sim …"
(cd "$TP3_SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

# ── Run simulation ────────────────────────────────────────────────────────────
echo "Running EventDrivenMD  (N=$N  seed=$SEED  tf=$TF) …"
SIM_ARGS="--n $N --seed $SEED --tf $TF --max-frames $MAX_FRAMES --frame-every $FRAME_EVERY --bin $TP3_BIN_DIR"
(cd "$TP3_SIM_DIR" && mvn -q exec:java -Dexec.args="$SIM_ARGS")

# ── Optional MP4 render ───────────────────────────────────────────────────────
if [[ "$RENDER_MP4" == "true" ]]; then
    mkdir -p "$TP3_BIN_DIR/animations"
    MP4_OUT="$TP3_BIN_DIR/animations/tp3_N${N}_seed${SEED}.mp4"
    echo "Rendering MP4 → $MP4_OUT"
    python3 "$REPO_ROOT/tp3-vis/src/main/python/render_tp3_mp4.py" \
        --bin   "$TP3_BIN_DIR" \
        --output "$MP4_OUT" \
        --fps    "$FPS" \
        --arrow-len "$ARROW_LEN" \
        --macro-block-size "$MACRO_BLOCK_SIZE" \
        --skip-time "$SKIP_TIME"
fi

# ── Interactive visualizer ────────────────────────────────────────────────────
echo "Launching visualizer …"
python3 "$TP3_VIS_PY" \
    --bin       "$TP3_BIN_DIR" \
    --fps       "$FPS" \
    --arrow-len "$ARROW_LEN" \
    --skip-time "$SKIP_TIME"
