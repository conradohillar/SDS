#!/usr/bin/env python3
"""
TP4 Sistema 1 – Oscilador amortiguado.

Reads pre-generated data from:
  <bin-dir>/oscillator/analytical.txt
  <bin-dir>/oscillator/euler.txt
  <bin-dir>/oscillator/verlet.txt
  <bin-dir>/oscillator/beeman.txt
  <bin-dir>/oscillator/gear.txt
  <bin-dir>/oscillator/ecm_vs_dt.txt

Produces:
  images/oscillator_trajectory.png   – r(t) for all integrators
  images/oscillator_ecm.png          – log-log ECM vs dt
"""
import argparse, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin"))


def load_traj(path):
    t, r = [], []
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 2:
                try:
                    t.append(float(p[0])); r.append(float(p[1]))
                except ValueError:
                    pass
    return np.array(t), np.array(r)


def load_ecm(path):
    rows = []
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 5:
                try:
                    rows.append([float(x) for x in p])
                except ValueError:
                    pass
    return np.array(rows)  # columns: dt, ecm_euler, ecm_verlet, ecm_beeman, ecm_gear


def plot_trajectory(osc_dir, img_dir):
    files = {
        "Analítica":  "analytical.txt",
        "Euler":      "euler.txt",
        "Verlet":     "verlet.txt",
        "Beeman":     "beeman.txt",
        "Gear 5":     "gear.txt",
    }
    colors = {
        "Analítica": "black",
        "Euler":     "#e74c3c",
        "Verlet":    "#3498db",
        "Beeman":    "#2ecc71",
        "Gear 5":    "#9b59b6",
    }
    styles = {
        "Analítica": "-",
        "Euler":     "--",
        "Verlet":    "--",
        "Beeman":    "--",
        "Gear 5":    "--",
    }

    fig, ax = plt.subplots(figsize=(10, 5))
    for label, fname in files.items():
        path = os.path.join(osc_dir, fname)
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found, skipping")
            continue
        t, r = load_traj(path)
        lw = 2.5 if label == "Analítica" else 1.5
        ax.plot(t, r, styles[label], color=colors[label], lw=lw, label=label)

    ax.set_xlabel("t [s]", fontsize=13)
    ax.set_ylabel("r(t) [m]", fontsize=13)
    ax.set_title("Oscilador amortiguado – Trayectoria", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out = os.path.join(img_dir, "oscillator_trajectory.png")
    plt.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved → {out}")


def plot_ecm(osc_dir, img_dir):
    path = os.path.join(osc_dir, "ecm_vs_dt.txt")
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found, skipping ECM plot")
        return

    data = load_ecm(path)
    if data.size == 0:
        print("  No ECM data found")
        return

    dt_arr = data[:, 0]
    labels = ["Euler", "Verlet", "Beeman", "Gear 5"]
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6"]
    markers = ["o", "s", "^", "D"]

    fig, ax = plt.subplots(figsize=(8, 6))
    for col, (label, color, marker) in enumerate(zip(labels, colors, markers), start=1):
        ecm = data[:, col]
        ax.loglog(dt_arr, ecm, marker=marker, lw=2, color=color, ms=6, label=label)

    # reference slopes
    x_ref = np.array([dt_arr.min(), dt_arr.max()])
    ax.loglog(x_ref, 1e-4 * (x_ref / x_ref[0]) ** 1, "k:", lw=1, label=r"$O(\Delta t)$")
    ax.loglog(x_ref, 1e-5 * (x_ref / x_ref[0]) ** 2, "k--", lw=1, label=r"$O(\Delta t^2)$")
    ax.loglog(x_ref, 1e-7 * (x_ref / x_ref[0]) ** 5, "k-.", lw=1, label=r"$O(\Delta t^5)$")

    ax.set_xlabel(r"$\Delta t$ [s]", fontsize=13)
    ax.set_ylabel("ECM [m²]", fontsize=13)
    ax.set_title("ECM vs $\\Delta t$ – Oscilador amortiguado", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, which="both", ls="--", alpha=0.4)
    plt.tight_layout()
    out = os.path.join(img_dir, "oscillator_ecm.png")
    plt.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    a = ap.parse_args()

    bin_dir = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    osc_dir = os.path.join(bin_dir, "oscillator")
    img_dir = os.path.join(bin_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    if not os.path.isdir(osc_dir):
        print(f"ERROR: {osc_dir} not found. Run run_tp4_oscillator.sh first.")
        raise SystemExit(1)

    plot_trajectory(osc_dir, img_dir)
    plot_ecm(osc_dir, img_dir)
