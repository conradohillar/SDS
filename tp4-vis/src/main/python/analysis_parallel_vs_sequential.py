#!/usr/bin/env python3
"""
TP4 – Parallel vs Sequential benchmark (CIM).

Runs N=[100..1000] for tf=50 s, dt=0.001, 1 realization each.
Measures individual run times, sequential wall time, and actual parallel
wall time using a thread pool (one thread per N).

Also extrapolates to the full simulation (tf=5000 s, dt=0.01, 10 realizations).

Usage:
    python3 analysis_parallel_vs_sequential.py [--bin-dir PATH]
"""
import argparse, os, subprocess, time, concurrent.futures
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


N_VALUES = list(range(100, 1001, 100))
TF   = 50.0
DT   = 0.001
K    = 1000.0
SEED = 0

# Full-simulation parameters for extrapolation
FULL_TF   = 5000.0
FULL_DT   = 0.01
FULL_REAL = 10


def _paths(bin_dir_arg):
    script = Path(__file__).resolve()
    repo   = script.parents[4]
    sim    = repo / "tp4-sim"
    bd     = Path(os.path.abspath(bin_dir_arg)) if bin_dir_arg else \
             Path(os.environ.get("TP4_BIN_PATH", repo / "tp4-bin"))
    return sim, bd


def run_sim(sim_dir, bench_dir, n, run_id):
    """Run one simulation, return wall-clock seconds."""
    args = (f"--n {n} --seed {SEED} --dt {DT} --tf {TF} "
            f"--dt2 {TF+1} --k {K} --no-frames --no-stats --cim "
            f"--bin {bench_dir} --run-id {run_id}")
    cmd = ["mvn", "-q", "exec:java", "-Dexec.mainClass=TimeDrivenMD",
           f"-Dexec.args={args}"]
    t0 = time.perf_counter()
    subprocess.run(cmd, cwd=sim_dir, check=True, capture_output=True)
    return time.perf_counter() - t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    a = ap.parse_args()

    sim_dir, bin_dir = _paths(a.bin_dir)
    bench_dir = bin_dir / "parallel_bench"
    img_dir   = bin_dir / "images"
    bench_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    # ── Sequential ────────────────────────────────────────────────────────────
    print("=== Sequential ===")
    seq_times = {}
    t_seq_start = time.perf_counter()
    for n in N_VALUES:
        t = run_sim(sim_dir, bench_dir, n, f"seq/N{n}")
        seq_times[n] = t
        print(f"  N={n:4d}  {t:.3f} s")
    seq_wall = time.perf_counter() - t_seq_start
    print(f"  → total wall: {seq_wall:.2f} s  (sum of runs: {sum(seq_times.values()):.2f} s)\n")

    # ── Parallel ──────────────────────────────────────────────────────────────
    print("=== Parallel ===")
    par_times = {}
    t_par_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(N_VALUES)) as pool:
        futures = {pool.submit(run_sim, sim_dir, bench_dir, n, f"par/N{n}"): n
                   for n in N_VALUES}
        for fut in concurrent.futures.as_completed(futures):
            n = futures[fut]
            par_times[n] = fut.result()
            print(f"  N={n:4d}  {par_times[n]:.3f} s  (finished)")
    par_wall = time.perf_counter() - t_par_start
    print(f"  → total wall: {par_wall:.2f} s  (slowest N: {max(par_times, key=par_times.get)}"
          f" at {max(par_times.values()):.3f} s)\n")

    # ── Save raw results ──────────────────────────────────────────────────────
    with open(bench_dir / "results.txt", "w") as f:
        f.write(f"sequential_wall {seq_wall:.4f}\n")
        f.write(f"parallel_wall   {par_wall:.4f}\n")
        for n in N_VALUES:
            f.write(f"N{n}_seq {seq_times[n]:.4f}\n")
            f.write(f"N{n}_par {par_times[n]:.4f}\n")

    # ── Extrapolation ─────────────────────────────────────────────────────────
    step_scale = (FULL_TF / TF) * (DT / FULL_DT)   # step-count ratio
    total_scale = step_scale * FULL_REAL             # × realizations

    seq_full_h = seq_wall * total_scale / 3600
    par_full_h = par_wall * total_scale / 3600       # assumes same parallelism

    # For parallel with full realizations: all 10 realizations per N can be
    # distributed across cores; wall time ≈ max_N(t_N) * step_scale * FULL_REAL
    slowest_n  = max(par_times, key=par_times.get)
    par_full_serial_real_h = par_times[slowest_n] * step_scale * FULL_REAL / 3600

    print("=== Extrapolation to tf=5000 s, dt=0.01, 10 realizations ===")
    print(f"  Step-count scale factor:        {step_scale:.0f}×")
    print(f"  Realizations scale factor:      {FULL_REAL}×")
    print(f"  Sequential total:               {seq_full_h:.1f} h")
    print(f"  Parallel (N in parallel,        {par_full_h:.2f} h")
    print(f"    realizations sequential):")
    print(f"  Parallel (N in parallel,        {par_full_serial_real_h:.2f} h")
    print(f"    realizations also sequential):")

    # ── Plot ──────────────────────────────────────────────────────────────────
    ns      = np.array(N_VALUES)
    seq_arr = np.array([seq_times[n] for n in N_VALUES])
    par_arr = np.array([par_times[n] for n in N_VALUES])
    cum_seq = np.cumsum(seq_arr)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Left: per-N bar chart + horizontal total lines
    ax = axes[0]
    w = 35
    ax.bar(ns - w/2, seq_arr, width=w, color="#e74c3c", label="Secuencial (run individual)")
    ax.bar(ns + w/2, par_arr, width=w, color="#3498db", label="Paralelo (run individual)")
    ax.axhline(seq_wall, color="#922b21", ls="--", lw=1.5,
               label=f"Secuencial pared = {seq_wall:.1f} s")
    ax.axhline(par_wall, color="#1a5276", ls="--", lw=1.5,
               label=f"Paralelo pared = {par_wall:.2f} s")
    ax.set_xlabel("N", fontsize=12)
    ax.set_ylabel("Tiempo [s]", fontsize=12)
    ax.set_title(f"Tiempo por N  (tf={TF} s, dt={DT}, CIM)", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, ls="--", alpha=0.4)

    # Right: cumulative sequential vs parallel wall
    ax2 = axes[1]
    ax2.step(ns, cum_seq, where="mid", color="#e74c3c", lw=2,
             label="Secuencial (acumulado)")
    ax2.axhline(par_wall, color="#2980b9", ls="-", lw=2,
                label=f"Paralelo pared = {par_wall:.2f} s")
    ax2.set_xlabel("N", fontsize=12)
    ax2.set_ylabel("Tiempo de pared [s]", fontsize=12)
    ax2.set_title("Tiempo acumulado: secuencial vs paralelo", fontsize=12)
    ax2.legend(fontsize=10)
    ax2.grid(True, ls="--", alpha=0.4)

    speedup = seq_wall / par_wall
    fig.suptitle(
        f"TP4 – Paralelo vs Secuencial  (tf={TF} s, dt={DT}, CIM)  "
        f"| Speedup = {speedup:.1f}×  "
        f"| Extrapolación full: seq={seq_full_h:.1f} h, par={par_full_h:.2f} h",
        fontsize=11)
    plt.tight_layout()
    out = img_dir / "tp4_parallel_vs_sequential.png"
    plt.savefig(out, dpi=150)
    print(f"\nSaved → {out}")
