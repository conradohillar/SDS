#!/usr/bin/env bash
# TP4 – dt validation: run simulations for different N and dt values,
# then plot total energy vs time to verify integration step adequacy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp4-sim"
BIN_DIR="${TP4_BIN_PATH:-$REPO_ROOT/tp4-bin}"
VIS_DIR="$REPO_ROOT/tp4-vis/src/main/python"

TF=200.0
DT2=0.5        # output every 0.5 s → 200 data points per curve
K=1000.0
SEED=42

# N values to test
N_VALUES=(100)

# dt values to sweep — spans the Velocity Verlet stability limit (2/ω ≈ 0.063 s for k=1000, m=1)
DT_VALUES=(0.1 0.05 0.01 0.001)

echo "Building tp4-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

DT_VAL_DIR="$BIN_DIR/dt_validation"
mkdir -p "$DT_VAL_DIR"

for N in "${N_VALUES[@]}"; do
    for DT in "${DT_VALUES[@]}"; do
        RUN_ID="dt_val_N${N}_dt${DT}"
        echo "────────────────────────────────────────"
        echo "Running N=$N  dt=$DT  tf=$TF  (run-id=$RUN_ID)"
        rm -rf "$DT_VAL_DIR/$RUN_ID"
        (cd "$SIM_DIR" && mvn -q exec:java \
            -Dexec.mainClass=TimeDrivenMD \
            "-Dexec.args=--n $N --seed $SEED --dt $DT --tf $TF --dt2 $DT2 \
                         --k $K --no-frames --bin $DT_VAL_DIR --run-id $RUN_ID")
    done
done

echo ""
echo "════════════════════════════════════════"
echo "All simulations done. Generating plots …"
source "$REPO_ROOT/.venv/bin/activate" 2>/dev/null || true
N_ARG=$(IFS=,; echo "${N_VALUES[*]}")
DT_ARG=$(IFS=,; echo "${DT_VALUES[*]}")
python3 "$VIS_DIR/analysis_dt_validation.py" --bin-dir "$DT_VAL_DIR" \
    --n-values "$N_ARG" --dt-values "$DT_ARG"
echo "Done. Images → $DT_VAL_DIR/images/"
