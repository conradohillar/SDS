#!/usr/bin/env bash
# Análisis 1.4 – Perfiles radiales de partículas frescas.
# Corre EventDrivenMD (Java) con frames para cada N y realización, luego grafica.
set -euo pipefail

N_VALUES=(100 200 300 400 500)
REALIZATIONS=1
TF=2000.0
FRAME_EVERY=5
MAX_FRAMES=10000
BASE_SEED=$(date +%s)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp3-sim"
BIN_DIR="$REPO_ROOT/tp3-bin"
RAD_ROOT="$BIN_DIR/radial"

echo "Building tp3-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

for N in "${N_VALUES[@]}"; do
    for ((r=0; r<REALIZATIONS; r++)); do
        SEED=$((BASE_SEED + N * 100 + r))
        OUT="$RAD_ROOT/N${N}/r${r}"
        rm -rf "$OUT" && mkdir -p "$OUT"
        echo "  N=$N  r=$r  seed=$SEED"
        (cd "$SIM_DIR" && mvn -q exec:java -Dexec.mainClass=EventDrivenMD \
            "-Dexec.args=--n $N --seed $SEED --tf $TF \
             --max-frames $MAX_FRAMES --frame-every $FRAME_EVERY --bin $OUT")
    done
done

echo ""
echo "Generating plots …"
python3 "$REPO_ROOT/tp3-vis/src/main/python/analysis_radial.py" \
    --bin-dir "$BIN_DIR" --n-values "${N_VALUES[@]}"
