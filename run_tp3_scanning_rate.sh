#!/usr/bin/env bash
# Análisis 1.2 + 1.3 – Scanning rate J vs N y evolución Fu(t).
# Corre EventDrivenMD (Java) para cada N y realización, luego grafica.
set -euo pipefail

N_VALUES=(100 200 300 400)
REALIZATIONS=10
TF=1000.0
BASE_SEED=$(date +%s)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp3-sim"
BIN_DIR="$REPO_ROOT/tp3-bin"
SR_ROOT="$BIN_DIR/scanning_rate"

echo "Building tp3-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

for N in "${N_VALUES[@]}"; do
    for ((r=0; r<REALIZATIONS; r++)); do
        SEED=$((BASE_SEED + N * 100 + r))
        OUT="$SR_ROOT/N${N}/r${r}"
        rm -rf "$OUT" && mkdir -p "$OUT"
        echo "  N=$N  r=$r  seed=$SEED"
        (cd "$SIM_DIR" && mvn -q exec:java -Dexec.mainClass=EventDrivenMD \
            "-Dexec.args=--n $N --seed $SEED --tf $TF --max-frames 0 --bin $OUT")
    done
done

echo ""
echo "Generating plots …"
python3 "$REPO_ROOT/tp3-vis/src/main/python/analysis_scanning_rate.py" --bin-dir "$BIN_DIR"
