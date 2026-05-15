#!/usr/bin/env python3
"""
TP4 – Parallel vs Sequential benchmark (CIM), parallelizing by realization.

Runs N=[100..1000], 10 realizations each, tf=50 s, dt=0.001.

Sequential:  100 runs one by one  (wall ≈ 10 × sum_N t_N)
Parallel:    10 threads, each handles one realization across all N values
             (wall ≈ sum_N t_N  →  ~10× speedup if perfectly balanced)

Also extrapolates to the full simulation (tf=5000 s, dt=0.001, 10 realizations).

Usage:
    python3 analysis_parallel_vs_sequential.py [--bin-dir PATH]
"""
import argparse, os, subprocess, time, concurrent.futures
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


N_VALUES    = list(range(100, 1001, 100))
REALIZATIONS = 10
TF   = 50.0
DT   = 0.001
K    = 1000.0

FULL_TF   = 5000.0
FULL_DT   = 0.001
FULL_REAL = 10


def _paths(bin_dir_arg):
    script = Path(__file__).resolve()
    repo   = script.parents[4]
    sim    = repo / "tp4-sim"
    bd     = Path(os.path.abspath(bin_dir_arg)) if bin_dir_arg else \
             Path(os.environ.get("TP4_BIN_PATH", repo / "tp4-bin"))
    return sim, bd


def run_sim(sim_dir, bench_dir, n, r, run_id):
    seed = (hash((n, r, time.time_ns())) % (2**31))
    args = (f"--n {n} --seed {seed} --dt {DT} --tf {TF} "
            f"--dt2 {TF+1} --k {K} --no-frames --no-stats --cim "
            f"--bin {bench_dir} --run-id {run_id}")
    cmd = ["mvn", "-q", "exec:java", "-Dexec.mainClass=TimeDrivenMD",
           f"-Dexec.args={args}"]
    t0 = time.perf_counter()
    subprocess.run(cmd, cwd=sim_dir, check=True, capture_output=True)
    return time.perf_counter() - t0


def run_realization(sim_dir, bench_dir, r):
    """Run all N values for realization r sequentially. Returns (list_of_t_N, total)."""
    times_n = {}
    for n in N_VALUES:
        times_n[n] = run_sim(sim_dir, bench_dir, n, r, f"par_real/r{r}/N{n}")
    return times_n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    a = ap.parse_args()

    sim_dir, bin_dir = _paths(a.bin_dir)
    bench_dir = bin_dir / "parallel_bench2"
    img_dir   = bin_dir / "images"
    bench_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    # ── Sequential: all N × all realizations, one by one ─────────────────────
    print(f"=== Sequential  ({len(N_VALUES)} N × {REALIZATIONS} realizations = "
          f"{len(N_VALUES)*REALIZATIONS} runs) ===")
    seq_times_nr = {}   # (n, r) -> t
    t_seq_start = time.perf_counter()
    for r in range(REALIZATIONS):
        for n in N_VALUES:
            t = run_sim(sim_dir, bench_dir, n, r, f"seq/r{r}/N{n}")
            seq_times_nr[(n, r)] = t
    seq_wall = time.perf_counter() - t_seq_start

    # Per-N average across realizations
    seq_avg_n = {n: np.mean([seq_times_nr[(n, r)] for r in range(REALIZATIONS)])
                 for n in N_VALUES}
    for n in N_VALUES:
        print(f"  N={n:4d}  avg={seq_avg_n[n]:.3f} s")
    print(f"  → sequential wall: {seq_wall:.1f} s\n")

    # ── Parallel: one thread per realization, each runs all N sequentially ────
    print(f"=== Parallel by realization  ({REALIZATIONS} threads) ===")
    par_real_times = {}   # r -> {n: t}
    t_par_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=REALIZATIONS) as pool:
        futures = {pool.submit(run_realization, sim_dir, bench_dir, r): r
                   for r in range(REALIZATIONS)}
        for fut in concurrent.futures.as_completed(futures):
            r = futures[fut]
            par_real_times[r] = fut.result()
            thread_total = sum(par_real_times[r].values())
            print(f"  r={r}  thread total={thread_total:.2f} s  (finished)")
    par_wall = time.perf_counter() - t_par_start

    thread_totals = {r: sum(par_real_times[r].values()) for r in range(REALIZATIONS)}
    slowest_r = max(thread_totals, key=thread_totals.get)
    print(f"  → parallel wall: {par_wall:.2f} s"
          f"  (slowest thread: r={slowest_r} at {thread_totals[slowest_r]:.2f} s)\n")

    speedup = seq_wall / par_wall

    # ── Extrapolation ─────────────────────────────────────────────────────────
    step_scale = FULL_TF / TF        # more steps: 5000/50 = 100×
    seq_full_h = seq_wall * step_scale / 3600
    par_full_h = par_wall * step_scale / 3600

    print(f"=== Extrapolation to full simulation (tf={FULL_TF} s, dt={FULL_DT}, "
          f"{FULL_REAL} realizations) ===")
    print(f"  Step-count scale: {step_scale:.0f}×")
    print(f"  Sequential total: {seq_full_h:.2f} h  ({seq_full_h*60:.0f} min)")
    print(f"  Parallel total:   {par_full_h:.2f} h  ({par_full_h*60:.0f} min)")
    print(f"  Speedup:          {speedup:.1f}×")

    # ── Save results ──────────────────────────────────────────────────────────
    with open(bench_dir / "results.txt", "w") as f:
        f.write(f"sequential_wall {seq_wall:.4f}\n")
        f.write(f"parallel_wall   {par_wall:.4f}\n")
        f.write(f"speedup         {speedup:.4f}\n")
        for r in range(REALIZATIONS):
            f.write(f"thread_r{r} {thread_totals[r]:.4f}\n")

    # ── Plot ──────────────────────────────────────────────────────────────────
    ns = np.array(N_VALUES)
    seq_avg_arr = np.array([seq_avg_n[n] for n in N_VALUES])

    # Per-realization thread totals
    r_vals  = list(range(REALIZATIONS))
    r_totals = np.array([thread_totals[r] for r in r_vals])

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # Left: average time per N
    ax = axes[0]
    ax.bar(ns, seq_avg_arr, width=60, color="#e74c3c", alpha=0.85,
           label=f"t(N) promedio ({REALIZATIONS} realizaciones)")
    ax.set_xlabel("N", fontsize=12)
    ax.set_ylabel("Tiempo promedio [s]", fontsize=12)
    ax.set_title(f"Tiempo por N  (tf={TF} s, dt={DT}, CIM)", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, ls="--", alpha=0.4)

    # Centre: thread times in parallel run (should all be ~equal)
    ax2 = axes[1]
    ax2.bar(r_vals, r_totals, color="#3498db", alpha=0.85)
    ax2.axhline(np.mean(r_totals), color="#1a5276", ls="--", lw=1.5,
                label=f"Media = {np.mean(r_totals):.2f} s")
    ax2.set_xlabel("Realization r", fontsize=12)
    ax2.set_ylabel("Tiempo total del thread [s]", fontsize=12)
    ax2.set_title("Carga por thread (paralelo por realización)", fontsize=12)
    ax2.legend(fontsize=10)
    ax2.grid(True, ls="--", alpha=0.4)

    # Right: sequential cumulative vs parallel wall
    ax3 = axes[2]
    cum_seq = np.cumsum([seq_avg_n[n] * REALIZATIONS for n in N_VALUES])
    ax3.step(ns, cum_seq, where="post", color="#e74c3c", lw=2,
             label=f"Secuencial (acumulado) = {seq_wall:.0f} s")
    ax3.axhline(par_wall, color="#2980b9", ls="-", lw=2,
                label=f"Paralelo pared = {par_wall:.1f} s  ({speedup:.1f}×)")
    ax3.set_xlabel("N completado hasta", fontsize=12)
    ax3.set_ylabel("Tiempo de pared [s]", fontsize=12)
    ax3.set_title("Secuencial acumulado vs Paralelo", fontsize=12)
    ax3.legend(fontsize=10)
    ax3.grid(True, ls="--", alpha=0.4)

    fig.suptitle(
        f"TP4 – Paralelo (por realización) vs Secuencial  "
        f"(tf={TF} s, dt={DT}, {REALIZATIONS} realizaciones, CIM)\n"
        f"Speedup = {speedup:.1f}×  |  "
        f"Extrapolación full: seq={seq_full_h:.1f} h, par={par_full_h:.2f} h",
        fontsize=11)
    plt.tight_layout()
    out = img_dir / "tp4_parallel_vs_sequential.png"
    plt.savefig(out, dpi=150)
    print(f"\nSaved → {out}")
