#!/usr/bin/env python3
"""
TP4 – Benchmark: Brute vs CIM para tf=0.001 s y tf=5 s en un mismo gráfico.

Usage:
    python3 analysis_benchmark_comparison.py [--bin-dir PATH]
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

    # (results_file, label, color, linestyle)
    curve_defs = [
        ("benchmark_tf0.001/results_nocim.txt", "Bruta  tf=0.001 s", "#e74c3c", "--", "o"),
        ("benchmark_tf0.001/results_cim.txt",   "CIM    tf=0.001 s", "#3498db", "--", "s"),
        ("benchmark_tf5/results_nocim.txt",      "Bruta  tf=5 s",     "#c0392b", "-",  "o"),
        ("benchmark_tf5/results_cim.txt",        "CIM    tf=5 s",     "#2980b9", "-",  "s"),
    ]

    fig, ax = plt.subplots(figsize=(10, 6))

    for rel_path, label, color, ls, marker in curve_defs:
        path = os.path.join(bin_dir, rel_path)
        if not os.path.exists(path):
            print(f"SKIP: {path} not found")
            continue
        data = load(path)
        if not data:
            continue
        ns = np.array([d[0] for d in data])
        ts = np.array([d[1] for d in data])
        ax.plot(ns, ts, color=color, ls=ls, marker=marker, ms=6, lw=2, label=label)

    ax.set_xlabel("N", fontsize=13)
    ax.set_ylabel("t [s]", fontsize=13)
    ax.set_title("TP4 – Tiempo de cómputo vs N  (Bruta O(N²) vs CIM O(N))", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out = os.path.join(img_dir, "tp4_benchmark_comparison.png")
    plt.savefig(out, dpi=150)
    print(f"Saved → {out}")
