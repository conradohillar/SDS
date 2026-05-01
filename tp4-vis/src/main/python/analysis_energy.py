#!/usr/bin/env python3
"""
TP4 Análisis – Conservación de energía (Time-Driven MD).

Reads:
  <bin-dir>/<run-id>/energy.txt  columns: t Ekin Epot Etot

Usage:
    python3 analysis_energy.py [--bin-dir PATH] [--run-id ID]
"""
import argparse, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin"))


def load_energy(path):
    t, ek, ep, et = [], [], [], []
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 4:
                try:
                    t.append(float(p[0])); ek.append(float(p[1]))
                    ep.append(float(p[2])); et.append(float(p[3]))
                except ValueError:
                    pass
    return (np.array(t), np.array(ek), np.array(ep), np.array(et))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    ap.add_argument("--run-id",  default="default")
    a = ap.parse_args()

    bin_dir = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir = os.path.join(bin_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    energy_file = os.path.join(bin_dir, a.run_id, "energy.txt")
    if not os.path.exists(energy_file):
        print(f"ERROR: {energy_file} not found. Run run_tp4.sh first.")
        raise SystemExit(1)

    t, ek, ep, et = load_energy(energy_file)
    if len(t) == 0:
        print("No energy data found.")
        raise SystemExit(1)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(t, ek, lw=1.5, color="#e74c3c", label="$E_{kin}$")
    ax.plot(t, ep, lw=1.5, color="#3498db", label="$E_{pot}$")
    ax.plot(t, et, lw=2.0, color="black",   label="$E_{tot}$")
    ax.set_xlabel("t [s]", fontsize=13)
    ax.set_ylabel("Energía [J]", fontsize=13)
    ax.set_title("TP4 – Energía vs tiempo  (Time-Driven MD)", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out = os.path.join(img_dir, f"tp4_energy_{a.run_id}.png")
    plt.savefig(out, dpi=150)
    print(f"Saved → {out}")

    e0 = et[0] if et[0] != 0 else 1.0
    drift = (et.max() - et.min()) / abs(e0) * 100
    print(f"Energy drift: {drift:.4f}%  (max={et.max():.4e}, min={et.min():.4e})")
