#!/usr/bin/env bash
# TP4 Benchmark – wall-clock time vs N.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp4-sim"
BIN_DIR="${TP4_BIN_PATH:-$REPO_ROOT/tp4-bin}"
VIS_DIR="$REPO_ROOT/tp4-vis/src/main/python"

BENCH_TF="${BENCH_TF:-500.0}"
BENCH_DT="${BENCH_DT:-0.01}"
BENCH_RUNS="${BENCH_RUNS:-10}"
BENCH_K="${BENCH_K:-1000.0}"
BENCH_OUT="$BIN_DIR/benchmark"

echo "Building tp4-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

mkdir -p "$BENCH_OUT"
echo "Running BenchmarkRunner (tf=$BENCH_TF, dt=$BENCH_DT, runs=$BENCH_RUNS) …"
(cd "$SIM_DIR" && mvn -q exec:java -Dexec.mainClass=BenchmarkRunner \
    "-Dexec.args=--tf $BENCH_TF --dt $BENCH_DT --runs $BENCH_RUNS --k $BENCH_K \
                 --bin $BENCH_OUT") \
    | tee "$BENCH_OUT/stdout.txt"

echo ""
echo "Generating plot …"
python3 "$VIS_DIR/analysis_benchmark.py" --bin-dir "$BIN_DIR"
echo "Done. Image → $BIN_DIR/images/tp4_benchmark.png"
