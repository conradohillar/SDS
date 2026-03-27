#!/usr/bin/env bash
set -euo pipefail

# ---- Configuración (editar acá) ----
MAX_FRAMES=1000
ETA=3
LEADER_MODE="none"   # "none" | "fixed" | "circular"
RENDER_MP4=true      # true | false
MACRO_BLOCK_SIZE=1  # 1 avoids resizing warning; higher values improve compatibility

FPS=50
ARROW_LEN=0.35

# ---- Paths ----
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TP1_SIM_DIR="$REPO_ROOT/tp1-sim"
TP2_SIM_DIR="$REPO_ROOT/tp2-sim"
TP2_VIS_PY="$REPO_ROOT/tp2-vis/src/main/python/visualizer2.py"
TP2_BIN_DIR="$REPO_ROOT/tp2-bin"

export TP2_BIN_PATH="$TP2_BIN_DIR"

leader_sim_flag=""
leader_vis_args=()
leader_vis_eta_arg=()

case "$LEADER_MODE" in
  none)
    ;;
  fixed)
    leader_sim_flag="--leader-fixed"
    leader_vis_args+=(--leader-id 1)
    ;;
  circular)
    leader_sim_flag="--leader-circular"
    leader_vis_args+=(--leader-id 1)
    ;;
  *)
    echo "Invalid LEADER_MODE='$LEADER_MODE'. Use: none | fixed | circular" >&2
    exit 1
    ;;
esac

leader_vis_eta_arg=(--eta "$ETA")

TP1_JAR="$TP1_SIM_DIR/target/tp1-sim-1.0-SNAPSHOT.jar"
if [[ ! -f "$TP1_JAR" ]]; then
  echo "Building tp1-sim (missing jar): $TP1_JAR"
  (cd "$TP1_SIM_DIR" && mvn package -DskipTests)
fi

echo "Running tp2-sim..."
sim_args=(--max-frames "$MAX_FRAMES" --eta "$ETA")
if [[ -n "$leader_sim_flag" ]]; then
  sim_args+=("$leader_sim_flag")
fi

# Run from tp2-sim dir so Maven resolves paths consistently.
(cd "$TP2_SIM_DIR" && mvn exec:java -Dexec.args="${sim_args[*]}")

if [[ "$RENDER_MP4" == "true" ]]; then
  echo "Rendering MP4..."
  MP4_OUT="$TP2_BIN_DIR/animations/tp2_eta_${ETA}_${LEADER_MODE}.mp4"
  python3 "$REPO_ROOT/tp2-vis/src/main/python/render_tp2_mp4.py" \
    --bin "$TP2_BIN_DIR" \
    --output "$MP4_OUT" \
    --fps "$FPS" \
    --macro-block-size "$MACRO_BLOCK_SIZE" \
    --arrow-len "$ARROW_LEN" \
    "${leader_vis_args[@]}" \
    "${leader_vis_eta_arg[@]}"
  echo "MP4 written to: $MP4_OUT"
fi

echo "Running visualizer..."
python3 "$TP2_VIS_PY" \
  --bin "$TP2_BIN_DIR" \
  --fps "$FPS" \
  --arrow-len "$ARROW_LEN" \
  "${leader_vis_args[@]}" \
  "${leader_vis_eta_arg[@]}"

