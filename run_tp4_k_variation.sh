#!/usr/bin/env bash
# TP4 Análisis 1.4 – Variación de la constante elástica k.
#
# Parallelizes over realizations: one background job per realization,
# each job runs all N values sequentially. This balances load perfectly
# because every job has the same set of N values.
#
# Seeds: unique per (N, r, k) using BASHPID to avoid collisions across
# parallel subshells.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp4-sim"
BIN_DIR="${TP4_BIN_PATH:-$REPO_ROOT/tp4-bin}"
VIS_DIR="$REPO_ROOT/tp4-vis/src/main/python"

K_VALUES="${K_VALUES:-100 1000 10000}"
N_VALUES="${N_VALUES:-100 200 300 400 500 600 700 800 900 1000}"
REALIZATIONS="${REALIZATIONS:-10}"
TF="${TF:-5000.0}"
DT="${DT:-0.001}"
DT2="${DT2:-50.0}"

echo "Building tp4-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

for k in $K_VALUES; do
    echo ""
    echo "========================================"
    echo "  k = $k N/m   tf=$TF  dt=$DT  realizations=$REALIZATIONS"
    echo "========================================"

    for r in $(seq 0 $((REALIZATIONS - 1))); do
        (
            # Seed base unique to this subshell: BASHPID * prime + r
            SEED_BASE=$(( BASHPID * 10007 + r * 9973 ))
            for n in $N_VALUES; do
                SEED=$(( (SEED_BASE + n * 97) % 2147483647 ))
                RUN_ID="k_variation/k${k}/N${n}/r${r}"
                echo "  [r=$r] k=$k  N=$n  seed=$SEED  →  $RUN_ID"
                (cd "$SIM_DIR" && mvn -q exec:java \
                    -Dexec.mainClass=TimeDrivenMD \
                    "-Dexec.args=--n $n --seed $SEED --dt $DT --tf $TF --dt2 $DT2 \
                                 --k $k --cim --bin $BIN_DIR --run-id $RUN_ID")
            done
            echo "  [r=$r] k=$k done."
        ) &
    done

    echo "  Waiting for all $REALIZATIONS parallel realization jobs (k=$k) …"
    wait
    echo "  k=$k complete."
done

echo ""
echo "Generating k-variation analysis plots …"
python3 "$VIS_DIR/analysis_k_variation.py" --bin-dir "$BIN_DIR"
echo "Done. Images → $BIN_DIR/images/"
