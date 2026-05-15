#!/usr/bin/env python3
"""
TP4 – Validación del dt: <ΔE/E₀>(N) promediado sobre el tiempo y realizaciones.

Para cada corrida (N, r):
  1. Carga energy.txt  →  E(t)
  2. δ(t) = |E(t) - E₀| / |E₀|   con E₀ = E(t=0)
  3. drift = mean_t( δ(t) )        →  un escalar por corrida

Para cada N:
  mean ± std de drift sobre todas las realizaciones.

Lee desde: <bin-dir>/runs/N<n>/r<r>/energy.txt

Usage:
    python3 analysis_energy_drift_vs_N.py [--bin-dir PATH]
"""
import argparse, os, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin"))


def load_etot(path):
    """Return E_total array from energy.txt (columns: t Ekin Epot Etot)."""
    et = []
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 4:
                try:
                    et.append(float(p[3]))
                except ValueError:
                    pass
    return np.array(et)


def drift_of_run(etot):
    """Mean |E(t) - E₀| / |E₀| over all recorded time steps."""
    if len(etot) < 2:
        return float('nan')
    e0 = etot[0]
    if e0 == 0:
        return float('nan')
    return float(np.mean(np.abs(etot - e0) / abs(e0)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    a = ap.parse_args()

    bin_dir  = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    runs_root = os.path.join(bin_dir, "runs")
    img_dir  = os.path.join(bin_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    if not os.path.isdir(runs_root):
        print(f"ERROR: {runs_root} not found.")
        raise SystemExit(1)

    n_dirs = sorted(
        d for d in Path(runs_root).iterdir()
        if d.is_dir() and re.match(r"N\d+$", d.name)
    )

    ns_out, means, stds = [], [], []

    for n_dir in n_dirs:
        n = int(n_dir.name[1:])
        r_dirs = sorted(
            d for d in n_dir.iterdir()
            if d.is_dir() and re.match(r"r\d+$", d.name)
        )

        drifts = []
        for r_dir in r_dirs:
            efile = r_dir / "energy.txt"
            if not efile.exists():
                continue
            etot = load_etot(str(efile))
            d = drift_of_run(etot)
            if not np.isnan(d):
                drifts.append(d)

        if not drifts:
            print(f"  N={n}: no energy data, skipping")
            continue

        m = float(np.mean(drifts))
        s = float(np.std(drifts, ddof=1)) if len(drifts) > 1 else 0.0
        ns_out.append(n)
        means.append(m)
        stds.append(s)
        print(f"  N={n:4d}  <ΔE/E₀> = {m:.2e} ± {s:.2e}  ({len(drifts)} realizaciones)")

    if not ns_out:
        print("No data found.")
        raise SystemExit(1)

    ns_arr  = np.array(ns_out)
    m_arr   = np.array(means)
    s_arr   = np.array(stds)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.errorbar(ns_arr, m_arr, yerr=s_arr, fmt="o-", lw=2, color="#3498db",
                capsize=5, elinewidth=1.5, ms=7, label=r"$\langle\Delta E/E_0\rangle \pm \sigma$")
    ax.set_xlabel("N", fontsize=13)
    ax.set_ylabel(r"$\langle|\Delta E(t)|/|E_0|\rangle$", fontsize=13)
    ax.set_title(r"TP4 – Validación del dt: deriva de energía vs N  (dt = $10^{-3}$ s, tf = 5000 s)",
                 fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, ls="--", alpha=0.4)
    ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter(useMathText=True))
    ax.ticklabel_format(style="sci", axis="y", scilimits=(0, 0))
    plt.tight_layout()
    out = os.path.join(img_dir, "tp4_energy_drift_vs_N.png")
    plt.savefig(out, dpi=150)
    print(f"\nSaved → {out}")
