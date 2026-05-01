#!/usr/bin/env bash
# Análisis 1.1 – Benchmark: tiempo de cómputo vs N.
# Corre BenchmarkRunner (Java) y luego grafica con analysis_benchmark.py.
set -euo pipefail

BENCH_TF=5.0
BENCH_RUNS=10

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp3-sim"
BIN_DIR="$REPO_ROOT/tp3-bin"
BENCH_OUT="$BIN_DIR/benchmark"

echo "Building tp3-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

mkdir -p "$BENCH_OUT"
echo "Running BenchmarkRunner (tf=${BENCH_TF}s, runs=${BENCH_RUNS} per N) …"
(cd "$SIM_DIR" && mvn -q exec:java -Dexec.mainClass=BenchmarkRunner \
    "-Dexec.args=--tf $BENCH_TF --runs $BENCH_RUNS") \
    | tee "$BENCH_OUT/results.txt"

echo ""
echo "Generating plot …"
python3 "$REPO_ROOT/tp3-vis/src/main/python/analysis_benchmark.py" --bin-dir "$BIN_DIR"
