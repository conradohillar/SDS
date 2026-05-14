#!/usr/bin/env python3
"""
TP4 Análisis – Tiempo de cómputo vs N: Brute-force O(N²) vs Cell Index Method O(N).

Reads:
  <bin-dir>/benchmark/results_nocim.txt
  <bin-dir>/benchmark/results_cim.txt

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

    bench_dir   = os.path.join(bin_dir, "benchmark")
    file_nocim  = os.path.join(bench_dir, "results_nocim.txt")
    file_cim    = os.path.join(bench_dir, "results_cim.txt")

    curves = []
    for path, label, color, marker in [
        (file_nocim, "Bruta O(N²)",       "#e74c3c", "o"),
        (file_cim,   "CIM O(N)",           "#3498db", "s"),
    ]:
        if not os.path.exists(path):
            print(f"SKIP: {path} not found")
            continue
        data = load(path)
        if data:
            curves.append((data, label, color, marker))
            for n, t in data:
                print(f"  [{label}]  N={n:4d}  t={t:.4f} s")

    if not curves:
        print("No data found. Run run_tp4_benchmark.sh first.")
        raise SystemExit(1)

    fig, ax = plt.subplots(figsize=(9, 5))
    for data, label, color, marker in curves:
        ns = np.array([d[0] for d in data])
        ts = np.array([d[1] for d in data])
        ax.plot(ns, ts, marker=marker, color=color, ms=7, lw=2, label=label)

    ax.set_xlabel("N", fontsize=13)
    ax.set_ylabel("t [s]", fontsize=13)
    ax.set_title("TP4 – Tiempo de cómputo vs N  (tf = 5 s, dt = 0.01)", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.5)
    plt.tight_layout()
    out = os.path.join(img_dir, "tp4_benchmark.png")
    plt.savefig(out, dpi=150)
    print(f"Saved → {out}")
