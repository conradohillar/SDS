#!/usr/bin/env python3
"""
TP4 – Tiempo de cómputo vs N: comparación TP3 (event-driven) vs TP4 CIM (time-driven).

Reads:
  <tp4-bin>/benchmark_vs_tp3/results_cim.txt   (N  wall_time_s)
  <tp3-bin>/benchmark/results.txt              (N  wall_time_s)

Usage:
    python3 analysis_benchmark_vs_tp3.py [--tp4-bin PATH] [--tp3-bin PATH]
"""
import argparse, os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _default_tp4_bin():
    s = Path(__file__).resolve().parents[4]
    return str(s / "tp4-bin")


def _default_tp3_bin():
    s = Path(__file__).resolve().parents[4]
    return str(s / "tp3-bin")


def load(path):
    ns, ts = [], []
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 2:
                try:
                    ns.append(int(p[0]))
                    ts.append(float(p[1]))
                except ValueError:
                    pass
    return np.array(ns), np.array(ts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tp4-bin", default=None)
    ap.add_argument("--tp3-bin", default=None)
    a = ap.parse_args()

    tp4_bin = os.path.abspath(a.tp4_bin) if a.tp4_bin else _default_tp4_bin()
    tp3_bin = os.path.abspath(a.tp3_bin) if a.tp3_bin else _default_tp3_bin()
    img_dir = os.path.join(tp4_bin, "images")
    os.makedirs(img_dir, exist_ok=True)

    tp4_file = os.path.join(tp4_bin, "benchmark_vs_tp3", "results_cim.txt")
    tp3_file = os.path.join(tp3_bin, "benchmark", "results.txt")

    fig, ax = plt.subplots(figsize=(10, 6))

    if os.path.exists(tp4_file):
        ns4, ts4 = load(tp4_file)
        ax.plot(ns4, ts4, "o-", lw=2, color="#2980b9", ms=5,
                label="TP4 – Time-Driven MD (CIM, tf=5 s, dt=10⁻³ s)")
        print(f"TP4 CIM: N={ns4[0]}..{ns4[-1]}, {len(ns4)} puntos")
    else:
        print(f"SKIP TP4: {tp4_file} not found")

    if os.path.exists(tp3_file):
        ns3, ts3 = load(tp3_file)
        ax.plot(ns3, ts3, "s--", lw=2, color="#e74c3c", ms=5,
                label="TP3 – Event-Driven MD (tf=5 s)")
        print(f"TP3:     N={ns3[0]}..{ns3[-1]}, {len(ns3)} puntos")
    else:
        print(f"SKIP TP3: {tp3_file} not found")

    ax.set_xlabel("N", fontsize=13)
    ax.set_ylabel("Tiempo de cómputo [s]", fontsize=13)
    ax.set_title("Tiempo de cómputo vs N: TP3 (event-driven) vs TP4 CIM (time-driven)",
                 fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()

    out = os.path.join(img_dir, "tp4_benchmark_vs_tp3.png")
    plt.savefig(out, dpi=150)
    print(f"\nSaved → {out}")
