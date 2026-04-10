#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_tp3_sims.sh – Run all TP3 Java simulations and save output for analysis.
#
# Directory structure produced:
#   tp3-bin/scanning_rate/N{n}/r{r}/stats.txt
#   tp3-bin/radial/N{n}/r{r}/frames/  +  metadata.txt
#   tp3-bin/benchmark/results.txt
#
# After running this script, use the Python analysis scripts:
#   python3 tp3-vis/src/main/python/analysis_benchmark.py
#   python3 tp3-vis/src/main/python/analysis_scanning_rate.py
#   python3 tp3-vis/src/main/python/analysis_radial.py
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
# Scanning rate (análisis 1.2 / 1.3)
SR_N_VALUES=(100 200 300 400 500 600 700 800)
SR_REALIZATIONS=5
SR_TF=200.0

# Radial profiles (análisis 1.4)
RAD_N_VALUES=(25 50 100 200)
RAD_REALIZATIONS=3
RAD_TF=200.0
RAD_FRAME_EVERY=5
RAD_MAX_FRAMES=5000

# Benchmark (análisis 1.1)
BENCH_TF=5.0
BENCH_RUNS=3

# Base seed for deterministic reproducibility: seed = BASE_SEED + N*100 + r
BASE_SEED=12345

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$REPO_ROOT/tp3-sim"
BIN_DIR="$REPO_ROOT/tp3-bin"

# ── Build once ────────────────────────────────────────────────────────────────
echo "Building tp3-sim …"
(cd "$SIM_DIR" && mvn -q package -DskipTests 2>/dev/null || true)

# ── Helper ────────────────────────────────────────────────────────────────────
run_sim() {
    local OUT="$1"; shift
    mkdir -p "$OUT"
    (cd "$SIM_DIR" && mvn -q exec:java -Dexec.mainClass=EventDrivenMD \
        "-Dexec.args=$*")
}

# ── Scanning rate simulations (no frames, stats only) ─────────────────────────
echo ""
echo "=== Scanning rate simulations ==="
for N in "${SR_N_VALUES[@]}"; do
    for ((r=0; r<SR_REALIZATIONS; r++)); do
        SEED=$((BASE_SEED + N * 100 + r))
        OUT="$BIN_DIR/scanning_rate/N${N}/r${r}"
        echo "  N=$N  r=$r  seed=$SEED → $OUT"
        run_sim "$OUT" \
            --n "$N" --seed "$SEED" --tf "$SR_TF" \
            --max-frames 0 --bin "$OUT"
    done
done

# ── Radial profile simulations (with frames) ───────────────────────────────────
echo ""
echo "=== Radial profile simulations ==="
for N in "${RAD_N_VALUES[@]}"; do
    for ((r=0; r<RAD_REALIZATIONS; r++)); do
        SEED=$((BASE_SEED + N * 100 + r))
        OUT="$BIN_DIR/radial/N${N}/r${r}"
        echo "  N=$N  r=$r  seed=$SEED → $OUT"
        run_sim "$OUT" \
            --n "$N" --seed "$SEED" --tf "$RAD_TF" \
            --max-frames "$RAD_MAX_FRAMES" --frame-every "$RAD_FRAME_EVERY" \
            --bin "$OUT"
    done
done

# ── Benchmark ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Benchmark ==="
BENCH_OUT="$BIN_DIR/benchmark"
mkdir -p "$BENCH_OUT"
echo "  Running BenchmarkRunner (tf=${BENCH_TF}s, runs=${BENCH_RUNS} per N) …"
(cd "$SIM_DIR" && mvn -q exec:java -Dexec.mainClass=BenchmarkRunner \
    "-Dexec.args=--tf $BENCH_TF --runs $BENCH_RUNS") \
    | tee "$BENCH_OUT/results.txt"

echo ""
echo "Done. Data saved to $BIN_DIR"
echo "Run Python analysis scripts to generate plots in $BIN_DIR/images/"
