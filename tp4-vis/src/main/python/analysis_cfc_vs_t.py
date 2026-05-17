#!/usr/bin/env python3
"""
TP4 – Cfc(t) promediado sobre realizaciones para N seleccionados.

Usage:
    python3 analysis_cfc_vs_t.py [--bin-dir PATH]
"""
import argparse, os, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

N_PLOT  = [100, 200, 500, 1000]
COLORS  = ["#3498db", "#e74c3c", "#2ecc71", "#9b59b6"]
T_GRID  = 500   # resolution of the common time axis


def _default_bin_dir():
    s = Path(__file__).resolve().parents[4]
    return str(s / "tp4-bin")


def load_cfc_times(path):
    times = []
    with open(path) as f:
        for line in f:
            v = line.strip()
            if v:
                try:
                    times.append(float(v))
                except ValueError:
                    pass
    return np.array(times)


def mean_cfc_trajectory(r_dirs):
    """Return (t_grid, mean_Cfc, std_Cfc) averaged over realizations."""
    series = []
    for r_dir in r_dirs:
        cfc_path = r_dir / "cfc.txt"
        if not cfc_path.exists():
            continue
        times = load_cfc_times(str(cfc_path))
        if len(times):
            series.append(times)

    if not series:
        return None, None, None

    tf = max(t[-1] for t in series)
    t_grid = np.linspace(0, tf, T_GRID)
    mat = np.array([[np.sum(times <= t) for t in t_grid] for times in series],
                   dtype=float)
    std = mat.std(axis=0, ddof=1) if len(series) > 1 else np.zeros(T_GRID)
    return t_grid, mat.mean(axis=0), std


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    a = ap.parse_args()

    bin_dir   = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    runs_root = Path(bin_dir) / "runs"
    img_dir   = Path(bin_dir) / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    print(f"\n{'N':>6}  {'pendiente [1/s]':>18}  {'R²':>6}")
    print("-" * 36)
    for n, color in zip(N_PLOT, COLORS):
        n_dir = runs_root / f"N{n}"
        if not n_dir.exists():
            print(f"SKIP N={n}: directory not found")
            continue
        r_dirs = sorted(
            (d for d in n_dir.iterdir() if d.is_dir() and re.match(r"r\d+$", d.name)),
            key=lambda d: int(d.name[1:])
        )
        t_grid, cfc_mean, cfc_std = mean_cfc_trajectory(r_dirs)
        if t_grid is None:
            print(f"SKIP N={n}: no cfc data")
            continue
        ax.fill_between(t_grid, cfc_mean - cfc_std, cfc_mean + cfc_std,
                        color=color, alpha=0.2)
        ax.plot(t_grid, cfc_mean, lw=1.8, color=color, label=f"N = {n}")

        slope, intercept = np.polyfit(t_grid, cfc_mean, 1)
        fit_line = slope * t_grid + intercept
        ss_res = np.sum((cfc_mean - fit_line) ** 2)
        ss_tot = np.sum((cfc_mean - cfc_mean.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        ax.plot(t_grid, fit_line, lw=1.2, color="black", ls="--", alpha=0.5)

        print(f"{n:>6}  {slope:>18.4f}  {r2:>6.4f}")
        print(f"  N={n}: {len(r_dirs)} realizaciones, tf≈{t_grid[-1]:.0f} s")

    ax.set_xlabel("t [s]", fontsize=13)
    ax.set_ylabel("$C_{fc}(t)$", fontsize=13)
    ax.set_title(r"TP4 – $C_{fc}(t)$ promediado sobre realizaciones", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out = str(img_dir / "tp4_cfc_vs_t.png")
    plt.savefig(out, dpi=150)
    print(f"\nSaved → {out}")
