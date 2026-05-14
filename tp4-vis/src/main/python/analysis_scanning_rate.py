#!/usr/bin/env python3
"""
TP4 Análisis – Tasa de escaneo J(N) (Time-Driven MD).

For each N reads cfc.txt files (one timestamp per Cfc event) from all
realizations and computes J = dCfc/dt via linear regression over the
stationary regime.

Directory layout expected:
  <bin-dir>/scanning_rate/N<n>/r<r>/cfc.txt
  <bin-dir>/scanning_rate/N<n>/r<r>/metadata.txt

Usage:
    python3 analysis_scanning_rate.py [--bin-dir PATH]
"""
import argparse, os, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


N_VALUES_TARGET = list(range(100, 801, 100))
TRANSIENT_FRAC  = 0.2   # skip first 20% of time as transient


def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin"))


def load_cfc_times(cfc_path):
    times = []
    with open(cfc_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    times.append(float(line))
                except ValueError:
                    pass
    return np.array(times)


def parse_metadata(path):
    meta = {}
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 2:
                try:
                    meta[p[0]] = float(p[1])
                except ValueError:
                    meta[p[0]] = p[1]
    return meta


def compute_j(times, tf, transient_frac=TRANSIENT_FRAC):
    """Compute scanning rate J = dCfc/dt via linear regression."""
    if len(times) < 2:
        return 0.0, 0.0

    t_start = transient_frac * tf
    mask = times >= t_start
    times_stat = times[mask]
    if len(times_stat) < 2:
        return 0.0, 0.0

    # build Cfc(t): each event increments by 1
    t_vals  = np.concatenate([[t_start], times_stat])
    c_vals  = np.arange(len(t_vals))

    coeffs = np.polyfit(t_vals, c_vals, 1)
    j = coeffs[0]
    return j, 0.0  # slope


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    a = ap.parse_args()

    bin_dir  = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir  = os.path.join(bin_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    sr_root  = os.path.join(bin_dir, "scanning_rate")

    if not os.path.isdir(sr_root):
        print(f"ERROR: {sr_root} not found. Run run_tp4_scanning_rate.sh first.")
        raise SystemExit(1)

    n_dirs = sorted(
        d for d in Path(sr_root).iterdir()
        if d.is_dir() and re.match(r"N\d+$", d.name)
    )

    j_mean = {}; j_std = {}

    for n_dir in n_dirs:
        n = int(n_dir.name[1:])
        r_dirs = sorted(
            d for d in n_dir.iterdir()
            if d.is_dir() and re.match(r"r\d+$", d.name)
        )
        if not r_dirs:
            print(f"N={n}: no realization dirs")
            continue

        js = []
        for r_dir in r_dirs:
            cfc_path  = r_dir / "cfc.txt"
            meta_path = r_dir / "metadata.txt"
            if not cfc_path.exists():
                continue
            tf = 1000.0
            if meta_path.exists():
                meta = parse_metadata(str(meta_path))
                tf   = float(meta.get("tf", tf))

            times = load_cfc_times(str(cfc_path))
            j, _ = compute_j(times, tf)
            js.append(j)
            print(f"  N={n}  {r_dir.name}  J={j:.4f}")

        if js:
            j_mean[n] = float(np.mean(js))
            j_std[n]  = float(np.std(js, ddof=1)) if len(js) > 1 else 0.0

    if not j_mean:
        print("No data found.")
        return

    ns   = np.array(sorted(j_mean.keys()))
    jm   = np.array([j_mean[n] for n in ns])
    jerr = np.array([j_std[n]  for n in ns])

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(ns, jm, yerr=jerr, fmt="o-", lw=2, color="#e74c3c",
                capsize=5, elinewidth=1.5, label="$\\langle J \\rangle$")
    ax.set_xlabel("N", fontsize=13)
    ax.set_ylabel("J [colisiones/s]", fontsize=13)
    ax.set_title("TP4 – Tasa de escaneo $J$ vs $N$  (Time-Driven MD)", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out = os.path.join(img_dir, "tp4_scanning_rate.png")
    plt.savefig(out, dpi=150)
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
