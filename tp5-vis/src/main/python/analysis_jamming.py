#!/usr/bin/env python3
"""
TP5 Sistema 3 – Jamming fraction analysis.

For each (mode, N), reads stats.txt files and:
  - Identifies periods where v_mean < threshold (jammed state)
  - Computes time-jammed / time-total, averaged across realizations
  - Plots jam fraction vs N for both modes

The jamming threshold defaults to 0.1 * v0 (10% of free-swimming speed).
Override with --threshold.

Usage:
    python3 analysis_jamming.py [--bin-dir PATH] [--threshold FRAC_OF_V0]
                                [--stat-frac 0.5] [--n-runs 5]
"""
import argparse, os, glob, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODES  = ["quiral", "random"]
COLORS = ["#e74c3c", "#3498db"]
DEFAULT_V0 = 0.825


def _default_bin():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp5-bin"))


def discover_n_values(bin_root, modes):
    ns = set()
    for mode in modes:
        for d in glob.glob(os.path.join(bin_root, "runs", mode, "N*")):
            m = re.match(r"N(\d+)$", os.path.basename(d))
            if m:
                ns.add(int(m.group(1)))
    return sorted(ns)


def read_v0(bin_root, modes, default=DEFAULT_V0):
    for mode in modes:
        for meta in glob.glob(os.path.join(bin_root, "runs", mode, "N*", "r*", "metadata.txt")):
            try:
                with open(meta) as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) == 2 and parts[0] == "v0":
                            return float(parts[1])
            except Exception:
                continue
    return default


def load_stats(stats_path):
    data = np.loadtxt(stats_path, skiprows=1)
    if data.ndim == 1:
        data = data[np.newaxis, :]
    return data[:, 0], data[:, 1], data[:, 2]


def jam_fraction(v_series, threshold):
    return float(np.mean(v_series < threshold))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir",   default=None)
    ap.add_argument("--threshold", type=float, default=0.1,
                    help="Jamming threshold as fraction of v0 (default 0.1 → 0.0825 cm/s)")
    ap.add_argument("--stat-frac", type=float, default=0.0,
                    help="Discard first fraction of timeseries before computing jam fraction")
    ap.add_argument("--n-runs",    type=int, default=5)
    a = ap.parse_args()

    bin_root   = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin()
    img_dir    = os.path.join(bin_root, "images")
    os.makedirs(img_dir, exist_ok=True)
    N_ALL = discover_n_values(bin_root, MODES)
    if not N_ALL:
        print(f"No runs found under {bin_root}/runs/"); return
    V0 = read_v0(bin_root, MODES)
    threshold  = a.threshold * V0
    print(f"N values: {N_ALL}  |  v0 = {V0}")
    print(f"Jamming threshold: {threshold:.4f} cm/s  ({a.threshold*100:.0f}% of v0={V0})")

    # ── Plot jam fraction vs N for each mode (shared axes) ────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_xlabel("N", fontsize=12)
    ax.set_ylabel("Fracción tiempo atascado", fontsize=12)
    ax.set_title(f"TP5 – Fracción de tiempo atascado vs N\n(umbral = {a.threshold*100:.0f}% v₀)", fontsize=13)
    ax.set_ylim(-0.05, 1.05)

    for mode, col, marker in zip(MODES, COLORS, ["o", "s"]):
        ns, fj_mean, fj_std = [], [], []
        for n_val in N_ALL:
            fracs = []
            for r in range(a.n_runs):
                stats_path = os.path.join(bin_root, "runs", mode, f"N{n_val}", f"r{r}", "stats.txt")
                if not os.path.exists(stats_path):
                    continue
                try:
                    t, v, _ = load_stats(stats_path)
                    cutoff = int(len(v) * a.stat_frac)
                    fracs.append(jam_fraction(v[cutoff:], threshold))
                except Exception as e:
                    print(f"  Warning {stats_path}: {e}")
            if not fracs:
                continue
            ns.append(n_val)
            fj_mean.append(float(np.mean(fracs)))
            fj_std.append(float(np.std(fracs, ddof=1)) if len(fracs) > 1 else 0.0)
        if not ns:
            continue
        ax.errorbar(np.array(ns), fj_mean, yerr=fj_std,
                    fmt=f"{marker}-", color=col, lw=2,
                    capsize=5, elinewidth=1.5, label=mode)

    ax.legend(fontsize=11); ax.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out = os.path.join(img_dir, "tp5_jam_fraction_vs_N.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved → {out}")

    # ── Per-mode: v_mean(t) for all N colored by N (shows jammed dips) ────────
    for mode, col in zip(MODES, COLORS):
        cmap   = plt.cm.plasma
        colors = cmap(np.linspace(0.1, 0.9, len(N_ALL)))
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        ax2.set_xlabel("t [s]", fontsize=12)
        ax2.set_ylabel("v̄ [cm/s]", fontsize=12)
        ax2.set_yscale("log")
        ax2.set_title(f"TP5 – {mode}: v̄(t) para todos los N", fontsize=13)
        ax2.axhline(threshold, ls=":", color="#7f8c8d", lw=1.5,
                    label=f"umbral = {threshold:.3f} cm/s")
        sm = plt.cm.ScalarMappable(cmap="plasma",
                                   norm=plt.Normalize(vmin=min(N_ALL), vmax=max(N_ALL)))
        sm.set_array([])
        for n_val, c in zip(N_ALL, colors):
            stats_path = os.path.join(bin_root, "runs", mode, f"N{n_val}", "r0", "stats.txt")
            if not os.path.exists(stats_path):
                continue
            try:
                t, v, _ = load_stats(stats_path)
                ax2.plot(t, v, color=c, lw=0.8, alpha=0.85)
            except Exception:
                pass
        fig2.colorbar(sm, ax=ax2, label="N")
        ax2.legend(fontsize=10); ax2.grid(True, ls="--", alpha=0.3)
        plt.tight_layout()
        out2 = os.path.join(img_dir, f"tp5_{mode}_v_all_N.png")
        fig2.savefig(out2, dpi=150)
        plt.close(fig2)
        print(f"Saved → {out2}")


if __name__ == "__main__":
    main()
