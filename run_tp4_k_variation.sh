#!/usr/bin/env bash
# TP4 Análisis 1.4 – Variación de la constante elástica k.
# Runs scanning rate + radial analysis for each k value.
#
# For each k, picks an appropriate dt to resolve the elastic collision
# (dt << pi*sqrt(m/k)).  Then runs multiple N values with several
# realizations and calls analysis_k_variation.py.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp4-sim"
BIN_DIR="${TP4_BIN_PATH:-$REPO_ROOT/tp4-bin}"
VIS_DIR="$REPO_ROOT/tp4-vis/src/main/python"

# ── Parameters ────────────────────────────────────────────────────────────────
# k values to sweep (space-separated). Set K_VALUES env to override.
K_VALUES="${K_VALUES:-100 1000 10000}"
# Uncomment or set env to include k=100000 (requires smaller dt, much slower):
# K_VALUES="${K_VALUES:-100 1000 10000 100000}"

N_VALUES="${N_VALUES:-100 200 300 400 500 600 700 800}"
REALIZATIONS="${REALIZATIONS:-3}"
TF="${TF:-2000.0}"
DT2="${DT2:-50.0}"
MAX_FRAMES="${MAX_FRAMES:-0}"  # 0 = unlimited (needed for radial analysis)

echo "Building tp4-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

# ── Function: choose dt based on k ────────────────────────────────────────────
# Collision time ~ pi*sqrt(m/k).  We use dt = collision_time / 50.
# k=100   → tc≈0.314  → dt=0.006
# k=1000  → tc≈0.099  → dt=0.002
# k=10000 → tc≈0.031  → dt=0.0006
# k=100000→ tc≈0.010  → dt=0.0002
choose_dt() {
    local k_val=$1
    python3 -c "
import math
k = float('$k_val')
tc = math.pi * math.sqrt(1.0 / k)   # m=1
dt = tc / 50.0
# Round to a nice value
exp = math.floor(math.log10(dt))
mantissa = dt / (10**exp)
if mantissa < 1.5:
    nice = 1.0
elif mantissa < 3.5:
    nice = 2.0
elif mantissa < 7.5:
    nice = 5.0
else:
    nice = 10.0
dt_nice = nice * (10**exp)
print(f'{dt_nice:.0e}')
"
}

# ── Main sweep ────────────────────────────────────────────────────────────────
for k in $K_VALUES; do
    DT=$(choose_dt "$k")
    echo ""
    echo "========================================"
    echo "  k = $k  N/m   (dt = $DT)"
    echo "========================================"

    for n in $N_VALUES; do
        for r in $(seq 0 $((REALIZATIONS - 1))); do
            RUN_ID="k_variation/k${k}/N${n}/r${r}"
            echo "  k=$k  N=$n  r=$r  dt=$DT  →  $RUN_ID"
            (cd "$SIM_DIR" && mvn -q exec:java \
                -Dexec.mainClass=TimeDrivenMD \
                "-Dexec.args=--n $n --seed $r --dt $DT --tf $TF --dt2 $DT2 \
                             --k $k --max-frames $MAX_FRAMES --bin $BIN_DIR --run-id $RUN_ID")
        done
    done
done

echo ""
echo "Generating k-variation analysis plots …"
python3 "$VIS_DIR/analysis_k_variation.py" --bin-dir "$BIN_DIR"
echo "Done. Images → $BIN_DIR/images/"
