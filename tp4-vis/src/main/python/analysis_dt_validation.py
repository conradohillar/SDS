#!/usr/bin/env python3
"""
TP4 – Validación del paso de integración (dt).

Genera un gráfico por cada N mostrando la energía total del sistema
en función del tiempo para distintos valores de dt.

Lee archivos:
  <bin-dir>/dt_val_N<N>_dt<DT>/energy.txt   (columnas: t Ekin Epot Etot)

Usage:
    python3 analysis_dt_validation.py [--bin-dir PATH] \
        --n-values 100,200,400 --dt-values 0.1,0.01,0.001,0.0001 [--k-label k1e5]
"""
import argparse
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin", "dt_validation"))


def load_energy(path):
    """Return (t, Ekin, Epot, Etot) arrays from an energy.txt file."""
    t, ek, ep, et = [], [], [], []
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 4:
                try:
                    t.append(float(p[0]))
                    ek.append(float(p[1]))
                    ep.append(float(p[2]))
                    et.append(float(p[3]))
                except ValueError:
                    pass
    return np.array(t), np.array(ek), np.array(ep), np.array(et)


# Palette that cycles for any number of dt values
_COLOR_POOL = [
    "#e74c3c", "#3498db", "#2ecc71", "#9b59b6",
    "#e67e22", "#1abc9c", "#f1c40f", "#e84393",
]


def format_dt(dt):
    """Pretty-print a dt value using scientific notation."""
    exp = int(np.floor(np.log10(dt)))
    mantissa = dt / (10 ** exp)
    if mantissa == 1.0:
        return f"$10^{{{exp}}}$"
    return f"${mantissa:.0f}\\times10^{{{exp}}}$"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    ap.add_argument("--n-values", required=True,
                    help="Comma-separated list of N values, e.g. 100,200,400")
    ap.add_argument("--dt-values", required=True,
                    help="Comma-separated list of dt values, e.g. 0.1,0.01,0.001")
    ap.add_argument("--k-label", default=None,
                    help="Optional k identifier inserted into run-id, e.g. k1e5")
    a = ap.parse_args()

    bin_dir = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir = os.path.join(bin_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    n_values = [int(x) for x in a.n_values.split(",")]
    dt_strings = [x.strip() for x in a.dt_values.split(",")]
    dt_values = [float(x) for x in dt_strings]

    # Build color map for the given dt values
    dt_colors = {dt: _COLOR_POOL[i % len(_COLOR_POOL)]
                 for i, dt in enumerate(dt_values)}

    k_label = a.k_label  # e.g. "k1e5" or None

    for N in n_values:
        fig, ax = plt.subplots(figsize=(12, 6))

        found_any = False

        for dt, dt_str in zip(dt_values, dt_strings):
            if k_label:
                run_id = f"dt_val_N{N}_{k_label}_dt{dt_str}"
            else:
                run_id = f"dt_val_N{N}_dt{dt_str}"
            energy_file = os.path.join(bin_dir, run_id, "energy.txt")

            if not os.path.exists(energy_file):
                print(f"  SKIP  {energy_file} (not found)")
                continue

            t, ek, ep, et = load_energy(energy_file)
            if len(t) == 0:
                print(f"  SKIP  {run_id} (empty)")
                continue

            color = dt_colors.get(dt, "gray")
            label = f"dt = {format_dt(dt)} s"

            # Check for NaN/Inf (simulation diverged)
            if np.any(np.isnan(et)) or np.any(np.isinf(et)):
                print(f"  N={N}  dt={dt:.0e}  → DIVERGED (NaN/Inf detected), skipping curve")
                ax.plot([], [], lw=1.4, color=color,
                        label=f"{label} (diverge)", ls="--")
                continue

            found_any = True

            e0 = et[0] if et[0] != 0 else 1.0
            rel_dev = np.abs(et - e0) / abs(e0)
            rel_dev = np.where(rel_dev == 0, 1e-12, rel_dev)  # avoid log(0) at t=0
            ax.semilogy(t, rel_dev, lw=1.4, color=color, label=label, alpha=0.9)

            drift = (et.max() - et.min()) / abs(e0) * 100
            print(f"  N={N}  dt={dt:.0e}  E_drift={drift:.4f}%  "
                  f"(Etot range: [{et.min():.4e}, {et.max():.4e}])")

        if not found_any:
            print(f"WARNING: No data found for N={N}, skipping plot.")
            plt.close(fig)
            continue

        ax.set_ylabel(r"$|\Delta E| \/ / \/ |E_0|$", fontsize=13)
        ax.set_xlabel("Tiempo [s]", fontsize=13)
        k_title = f", k = {k_label}" if k_label else ""
        ax.set_title(f"Validación del dt – N = {N}{k_title}", fontsize=15, fontweight="bold")
        ax.legend(fontsize=11, loc="best")
        ax.grid(True, ls="--", alpha=0.4)

        plt.tight_layout()
        k_suffix = f"_{k_label}" if k_label else ""
        out = os.path.join(img_dir, f"tp4_dt_validation_N{N}{k_suffix}.png")
        plt.savefig(out, dpi=150)
        plt.close(fig)
        print(f"  Saved → {out}")

    print("\nDone.")

