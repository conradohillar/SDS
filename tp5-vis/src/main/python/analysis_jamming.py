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
from scipy.stats import gaussian_kde
from scipy.signal import find_peaks

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


def compute_kde_threshold(all_v, n_points=2000):
    """
    Fit KDE to pooled velocity samples, find the valley between the two
    highest peaks (bimodal jamming threshold).
    Returns (threshold, x_grid, kde_values, peak_indices, valley_index).
    Returns (None, ...) if fewer than two peaks are found.
    """
    v = np.asarray(all_v)
    v = v[np.isfinite(v) & (v >= 0)]
    kde = gaussian_kde(v, bw_method="scott")
    x = np.linspace(v.min(), v.max(), n_points)
    y = kde(x)

    peaks, props = find_peaks(y, prominence=y.max() * 0.03)
    if len(peaks) < 2:
        return None, x, y, peaks, None

    # Two most prominent peaks
    top2 = peaks[np.argsort(props["prominences"])[-2:]]
    left, right = sorted(top2)

    valley_local = np.argmin(y[left : right + 1])
    valley_idx = left + valley_local
    return float(x[valley_idx]), x, y, peaks, valley_idx


def plot_kde_threshold(all_v_per_mode, thresholds, img_dir, v0):
    """
    One subplot per mode: KDE curve with peaks and valley/threshold annotated.
    """
    modes = list(all_v_per_mode.keys())
    fig, axes = plt.subplots(1, len(modes), figsize=(7 * len(modes), 5))
    if len(modes) == 1:
        axes = [axes]

    for ax, mode, col in zip(axes, modes, COLORS):
        v = np.asarray(all_v_per_mode[mode])
        v = v[np.isfinite(v) & (v >= 0)]
        thr, x, y, peaks, valley_idx = compute_kde_threshold(v)

        ax.fill_between(x, y, alpha=0.15, color=col)
        ax.plot(x, y, color=col, lw=2, label="KDE")
        ax.plot(x[peaks], y[peaks], "^", color="black", ms=8, label="picos")

        if valley_idx is not None:
            ax.axvline(x[valley_idx], color="#e67e22", lw=2, ls="--",
                       label=f"umbral KDE = {x[valley_idx]:.4f} cm/s\n"
                             f"({x[valley_idx]/v0*100:.1f}% v₀)")

        ax.set_xlabel("v̄ [cm/s]", fontsize=12)
        ax.set_ylabel("Densidad", fontsize=12)
        ax.set_title(f"TP5 – {mode}: distribución de v̄(t)\n(todas las N, todas las corridas, estado estacionario)",
                     fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, ls="--", alpha=0.35)

    plt.tight_layout()
    out = os.path.join(img_dir, "tp5_kde_threshold.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved → {out}")
    return out


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

    # ── KDE-based threshold detection ────────────────────────────────────────
    all_v_per_mode = {mode: [] for mode in MODES}
    for mode in MODES:
        for n_val in N_ALL:
            for r in range(a.n_runs):
                stats_path = os.path.join(bin_root, "runs", mode, f"N{n_val}", f"r{r}", "stats.txt")
                if not os.path.exists(stats_path):
                    continue
                try:
                    t, v, _ = load_stats(stats_path)
                    cutoff = int(len(v) * a.stat_frac)
                    all_v_per_mode[mode].extend(v[cutoff:].tolist())
                except Exception:
                    pass

    kde_thresholds = {}
    print("\n── KDE threshold detection ──")
    for mode in MODES:
        v_pool = all_v_per_mode[mode]
        if not v_pool:
            print(f"  {mode}: no data"); continue
        thr, x, y, peaks, valley_idx = compute_kde_threshold(v_pool)
        if thr is None:
            print(f"  {mode}: bimodal distribution not found (< 2 peaks)")
        else:
            print(f"  {mode}: umbral KDE = {thr:.4f} cm/s  ({thr/V0*100:.1f}% v₀)")
            kde_thresholds[mode] = thr

    plot_kde_threshold(all_v_per_mode, kde_thresholds, img_dir, V0)
    print()

    def plot_jam_fraction(thresh_frac, suffix=""):
        thr = thresh_frac * V0
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.set_xlabel("N", fontsize=12)
        ax.set_ylabel("Fracción tiempo atascado", fontsize=12)
        ax.set_title(f"TP5 – Fracción de tiempo atascado vs N\n(umbral = {thresh_frac*100:.0f}% v₀ = {thr:.4f} cm/s)", fontsize=13)
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
                        fracs.append(jam_fraction(v[cutoff:], thr))
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
        fname = f"tp5_jam_fraction_vs_N{suffix}.png"
        out = os.path.join(img_dir, fname)
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"Saved → {out}")

    # ── Plot jam fraction vs N: umbral configurado + 5/10/15/20% ─────────────
    for pct in [0.05, 0.10, 0.15, 0.20]:
        plot_jam_fraction(pct, suffix=f"_{int(pct*100)}pct")

    # ── Per-mode: v̄(t) para N=20 y N=27, realización r=0, t∈[2000,3000] ─────
    REP_N  = [min(N_ALL), max(N_ALL)]
    N_COLS = ["#e74c3c", "#2ecc71"]
    T_MIN, T_MAX = 2000.0, 3000.0
    for mode in MODES:
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        ax2.set_xlabel("t [s]", fontsize=12)
        ax2.set_ylabel("v̄ [cm/s]", fontsize=12)
        ax2.set_title(f"TP5 – {mode}: v̄(t)  N=20 y N=27 (r=0, t∈[{int(T_MIN)}, {int(T_MAX)}] s)", fontsize=13)
        ax2.axhline(threshold, ls=":", color="#7f8c8d", lw=1.5,
                    label=f"umbral = {threshold:.3f} cm/s")
        for n_val, c in zip(REP_N, N_COLS):
            stats_path = os.path.join(bin_root, "runs", mode, f"N{n_val}", "r0", "stats.txt")
            if not os.path.exists(stats_path):
                continue
            try:
                t, v, _ = load_stats(stats_path)
                mask = (t >= T_MIN) & (t <= T_MAX)
                ax2.plot(t[mask], v[mask], color=c, lw=0.9, alpha=0.9, label=f"N = {n_val}")
            except Exception:
                pass
        ax2.legend(fontsize=10); ax2.grid(True, ls="--", alpha=0.3)
        plt.tight_layout()
        out2 = os.path.join(img_dir, f"tp5_{mode}_v_all_N.png")
        fig2.savefig(out2, dpi=150)
        plt.close(fig2)
        print(f"Saved → {out2}")


if __name__ == "__main__":
    main()
