#!/usr/bin/env bash
# Sistema 1 – Oscilador amortiguado.
# Runs trajectory (default dt=1e-4) and ECM study, then plots both.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp4-sim"
BIN_DIR="$REPO_ROOT/tp4-bin"
VIS_DIR="$REPO_ROOT/tp4-vis/src/main/python"

DT="${DT:-1e-4}"
TF="${TF:-5.0}"

echo "Building tp4-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

echo "Running trajectory (dt=$DT, tf=$TF) …"
(cd "$SIM_DIR" && mvn -q exec:java \
    -Dexec.mainClass=OscilladorAmortiguado \
    "-Dexec.args=--mode trajectory --dt $DT --tf $TF --bin $BIN_DIR")

echo "Running ECM study …"
(cd "$SIM_DIR" && mvn -q exec:java \
    -Dexec.mainClass=OscilladorAmortiguado \
    "-Dexec.args=--mode ecm --tf $TF --bin $BIN_DIR")

echo ""
echo "Generating plots …"
python3 "$VIS_DIR/analysis_oscillator.py" --bin-dir "$BIN_DIR"
echo "Done. Images → $BIN_DIR/images/"
