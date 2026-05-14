#!/usr/bin/env bash
# TP4 Análisis – Tasa de escaneo J(N) + perfiles radiales (runs compartidos).
# Un único set de simulaciones alimenta tanto analysis_scanning_rate.py
# como analysis_radial.py.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp4-sim"
BIN_DIR="${TP4_BIN_PATH:-$REPO_ROOT/tp4-bin}"
VIS_DIR="$REPO_ROOT/tp4-vis/src/main/python"

N_VALUES="${N_VALUES:-100 200 300 400 500 600 700 800 900 1000}"
REALIZATIONS="${REALIZATIONS:-10}"
TF="${TF:-5000.0}"
DT="${DT:-0.001}"
DT2="${DT2:-50.0}"
K="${K:-1000.0}"

echo "Building tp4-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

for n in $N_VALUES; do
    for r in $(seq 0 $((REALIZATIONS - 1))); do
        RUN_ID="runs/N${n}/r${r}"
        echo "N=$n  realization=$r  run-id=$RUN_ID"
        SEED=$(( RANDOM * 32768 + RANDOM ))
        (cd "$SIM_DIR" && mvn -q exec:java \
            -Dexec.mainClass=TimeDrivenMD \
            "-Dexec.args=--n $n --seed $SEED --dt $DT --tf $TF --dt2 $DT2 \
                         --k $K --cim --bin $BIN_DIR --run-id $RUN_ID")
    done
done

echo ""
echo "Generating scanning-rate plot …"
python3 "$VIS_DIR/analysis_scanning_rate.py" --bin-dir "$BIN_DIR"

echo ""
echo "Generating radial profile plots …"
python3 "$VIS_DIR/analysis_radial.py" --bin-dir "$BIN_DIR" \
    --n-values $N_VALUES

echo "Done. Images → $BIN_DIR/images/"
