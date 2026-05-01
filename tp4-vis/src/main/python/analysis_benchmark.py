#!/usr/bin/env python3
"""
TP4 Análisis – Tiempo de cómputo vs N (Time-Driven MD).

Reads:
  <bin-dir>/benchmark/results.txt

Usage:
    python3 analysis_benchmark.py [--bin-dir PATH]
"""
import argparse, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin"))


def load(path):
    data = []
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 2:
                try:
                    data.append((int(p[0]), float(p[1])))
                except ValueError:
                    pass
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    a = ap.parse_args()

    bin_dir = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir = os.path.join(bin_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    results_file = os.path.join(bin_dir, "benchmark", "results.txt")
    if not os.path.exists(results_file):
        print(f"ERROR: {results_file} not found. Run run_tp4_benchmark.sh first.")
        raise SystemExit(1)

    data = load(results_file)
    if not data:
        print(f"No data in {results_file}")
        raise SystemExit(1)

    for n, t in data:
        print(f"  N={n:4d}  t={t:.4f} s")

    ns = np.array([d[0] for d in data])
    ts = np.array([d[1] for d in data])

    # quadratic fit O(N^2) expected for pairwise forces
    coeffs2 = np.polyfit(ns, ts, 2)
    p2 = np.poly1d(coeffs2)
    ns_fit = np.linspace(ns.min(), ns.max(), 300)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(ns, ts, "o", color="#3498db", ms=7, lw=2, label="Datos simulación")
    ax.plot(ns_fit, p2(ns_fit), "--", color="#e74c3c", lw=2,
            label=f"Ajuste $O(N^2)$: {coeffs2[0]:.3g}$N^2$+{coeffs2[1]:.3g}$N$+{coeffs2[2]:.3g}")
    ax.set_xlabel("N", fontsize=13)
    ax.set_ylabel("t [s]", fontsize=13)
    ax.set_title("TP4 – Tiempo de cómputo vs N  (Time-Driven MD)", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.5)
    plt.tight_layout()
    out = os.path.join(img_dir, "tp4_benchmark.png")
    plt.savefig(out, dpi=150)
    print(f"Saved → {out}")
