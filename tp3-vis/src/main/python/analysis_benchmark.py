#!/usr/bin/env python3
"""
Análisis 1.1 – Tiempo de ejecución en función de N.

Reads pre-generated benchmark results from:
  <bin-dir>/benchmark/results.txt

Run the benchmark first with run_tp3_sims.sh.

Usage:
    python3 analysis_benchmark.py [--bin-dir PATH] [--out benchmark.png]
"""
import argparse, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _default_bin_dir() -> str:
    script = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(script, "..", "..", "..", "..", "tp3-bin"))


def load_results(results_file: str) -> list[tuple[int, float]]:
    data = []
    with open(results_file) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                try:
                    data.append((int(parts[0]), float(parts[1])))
                except ValueError:
                    pass  # skip header
    return data


def plot(data: list[tuple[int, float]], out: str):
    ns = np.array([d[0] for d in data])
    ts = np.array([d[1] for d in data])

    # Exponential fit: t = a * exp(b * N)  →  log(t) = log(a) + b*N
    coeffs = np.polyfit(ns, np.log(ts), 1)
    b, log_a = coeffs
    a = np.exp(log_a)
    ns_fit = np.linspace(ns.min(), ns.max(), 300)
    ts_fit = a * np.exp(b * ns_fit)
    label_fit = rf"$a\,e^{{bN}}$,  $a={a:.3g}$,  $b={b:.3g}$"
    print(f"Exponential fit: a={a:.6g}, b={b:.6g}  →  t = {a:.3g} * exp({b:.3g} * N)")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(ns, ts, "o", color="#3498db", lw=2, ms=6, label="Datos simulación")
    ax.plot(ns_fit, ts_fit, "--", color="#e74c3c", lw=2, label=label_fit)
    ax.set_xlabel("N", fontsize=13)
    ax.set_ylabel("t [s]", fontsize=13)
    ax.set_title("1.1 – Tiempo de cómputo vs N  (tf = 5 s)", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    print(f"Saved → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    a = ap.parse_args()

    bin_dir = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir = os.path.join(bin_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    results_file = os.path.join(bin_dir, "benchmark", "results.txt")
    if not os.path.exists(results_file):
        print(f"ERROR: {results_file} not found. Run run_tp3_sims.sh first.")
        raise SystemExit(1)

    data = load_results(results_file)
    if data:
        for n, t in data:
            print(f"  N={n:4d}  t={t:.4f} s")
        plot(data, os.path.join(img_dir, "benchmark.png"))
    else:
        print(f"No data found in {results_file}.")
