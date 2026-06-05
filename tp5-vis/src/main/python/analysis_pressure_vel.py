#!/usr/bin/env python3
"""
TP5 Sistema 3 – Velocity and pressure analysis.

Reads stats.txt from <bin>/runs/<mode>/N<n>/r<r>/stats.txt and produces:
  1. v_mean(t) and P_wall(t) for two selected N values (per mode)
  2. v_mean vs P_wall phase plot for two selected N values
  3. Stationary v_mean vs N  (mean ± std across realizations)
  4. Stationary P_wall vs N  (mean ± std across realizations)

Uses the second half of each simulation as the stationary regime.

Usage:
    python3 analysis_pressure_vel.py [--bin-dir PATH] [--stat-frac 0.5]
                                     [--representative-n N1 N2]
"""
import argparse, os, glob, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

MODES   = ["quiral", "random"]
COLORS  = ["#e74c3c", "#3498db"]   # quiral=red, random=blue
DEFAULT_V0 = 0.825  # fallback when no metadata.txt is found


def _default_bin():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp5-bin"))


def discover_n_values(bin_root, modes):
    """Scan runs/<mode>/N<n>/ directories and return sorted unique N values."""
    ns = set()
    for mode in modes:
        for d in glob.glob(os.path.join(bin_root, "runs", mode, "N*")):
            m = re.match(r"N(\d+)$", os.path.basename(d))
            if m:
                ns.add(int(m.group(1)))
    return sorted(ns)


def read_v0(bin_root, modes, default=DEFAULT_V0):
    """Read v0 from the first metadata.txt found under runs/."""
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
    t       = data[:, 0]
    v_mean  = data[:, 1]
    p_wall  = data[:, 2]
    return t, v_mean, p_wall


def load_mode_n(bin_root, mode, n, n_runs=5):
    """Load all realizations for a given mode and N. Returns list of (t, v, p)."""
    results = []
    for r in range(n_runs):
        stats_path = os.path.join(bin_root, "runs", mode, f"N{n}", f"r{r}", "stats.txt")
        if not os.path.exists(stats_path):
            continue
        try:
            t, v, p = load_stats(stats_path)
            results.append((t, v, p))
        except Exception as e:
            print(f"  Warning: could not load {stats_path}: {e}")
    return results


def stationary_stats(results, stat_frac):
    """Compute mean stationary v and P from list of (t, v, p) tuples."""
    v_means, p_means = [], []
    for t, v, p in results:
        cutoff = int(len(t) * (1 - stat_frac))
        v_means.append(float(np.mean(v[cutoff:])))
        p_means.append(float(np.mean(p[cutoff:])))
    if not v_means:
        return None, None, None, None
    return (float(np.mean(v_means)), float(np.std(v_means, ddof=1) if len(v_means)>1 else 0),
            float(np.mean(p_means)), float(np.std(p_means, ddof=1) if len(p_means)>1 else 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir",         default=None)
    ap.add_argument("--stat-frac",       type=float, default=0.5,
                    help="Fraction of simulation tail used for stationary stats")
    ap.add_argument("--representative-n", nargs="+", type=int, default=None,
                    help="N values used for time-series and v-vs-P plots (default: min/max)")
    ap.add_argument("--n-runs",          type=int, default=5)
    a = ap.parse_args()

    bin_root = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin()
    img_dir  = os.path.join(bin_root, "images")
    os.makedirs(img_dir, exist_ok=True)

    N_ALL = discover_n_values(bin_root, MODES)
    if not N_ALL:
        print(f"No runs found under {bin_root}/runs/"); return
    V0 = read_v0(bin_root, MODES)
    rep_n = a.representative_n if a.representative_n else [N_ALL[0], N_ALL[-1]]
    print(f"N values: {N_ALL}  |  v0 = {V0}  |  representative N = {rep_n}")

    # ── 1 & 2: Time series and v-vs-P for representative N values ─────────────
    n_colors = plt.cm.tab10(np.linspace(0.0, 0.6, max(len(rep_n), 1)))

    for mode in MODES:
        fig_t, axes_t = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
        axes_t[0].set_ylabel("v̄ [cm/s]", fontsize=12)
        axes_t[1].set_ylabel("P [cm/s / cm]", fontsize=12)
        axes_t[1].set_xlabel("t [s]", fontsize=12)
        axes_t[0].set_title(f"TP5 – {mode}: v̄(t) y P(t)", fontsize=13)
        axes_t[0].set_yscale("log")
        axes_t[0].axhline(V0, ls=":", color="#7f8c8d", lw=1.5, label=f"v₀ = {V0}")

        fig_vp, ax_vp = plt.subplots(figsize=(7, 6))
        ax_vp.set_xlabel("P [cm/s / cm]", fontsize=12)
        ax_vp.set_ylabel("v̄ [cm/s]", fontsize=12)
        ax_vp.set_title(f"TP5 – {mode}: v̄ vs P", fontsize=13)

        for n_val, nc in zip(rep_n, n_colors):
            results = load_mode_n(bin_root, mode, n_val, a.n_runs)
            if not results:
                print(f"  No data: {mode} N={n_val}"); continue

            label  = f"N = {n_val}"
            n_real = len(results)
            t_ref  = results[0][0]
            v_stack = np.array([v for (_, v, _) in results])
            p_stack = np.array([p for (_, _, p) in results])
            v_mean_ts = v_stack.mean(axis=0)
            p_mean_ts = p_stack.mean(axis=0)
            v_std_ts  = v_stack.std(axis=0, ddof=1) if n_real > 1 else np.zeros_like(v_mean_ts)
            p_std_ts  = p_stack.std(axis=0, ddof=1) if n_real > 1 else np.zeros_like(p_mean_ts)

            # v̄(t): mean + shaded ±1σ (lower band clipped for log scale)
            axes_t[0].plot(t_ref, v_mean_ts, lw=1.5, color=nc, label=label)
            axes_t[0].fill_between(t_ref,
                                   np.maximum(v_mean_ts - v_std_ts, v_mean_ts * 1e-3),
                                   v_mean_ts + v_std_ts, alpha=0.2, color=nc)

            # P(t): mean + shaded ±1σ
            axes_t[1].plot(t_ref, p_mean_ts, lw=1.5, color=nc, label=label)
            axes_t[1].fill_between(t_ref,
                                   np.maximum(p_mean_ts - p_std_ts, 0),
                                   p_mean_ts + p_std_ts, alpha=0.2, color=nc)

            # v vs P: mean trajectory
            ax_vp.plot(p_mean_ts, v_mean_ts, lw=1.8, color=nc, label=label, alpha=0.85)

        for ax in axes_t:
            ax.legend(fontsize=11)
            ax.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        fig_t.savefig(os.path.join(img_dir, f"tp5_{mode}_vP_vs_t.png"), dpi=150)
        plt.close(fig_t)
        print(f"Saved → {img_dir}/tp5_{mode}_vP_vs_t.png")

        ax_vp.legend(fontsize=11)
        ax_vp.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        fig_vp.savefig(os.path.join(img_dir, f"tp5_{mode}_v_vs_P.png"), dpi=150)
        plt.close(fig_vp)
        print(f"Saved → {img_dir}/tp5_{mode}_v_vs_P.png")

    # ── 3 & 4: Stationary v and P vs N (both modes on same axes) ──────────────
    fig_sv, ax_sv = plt.subplots(figsize=(8, 5))
    fig_sp, ax_sp = plt.subplots(figsize=(8, 5))
    ax_sv.set_xlabel("N", fontsize=12); ax_sv.set_ylabel("v̄_stat [cm/s]", fontsize=12)
    ax_sp.set_xlabel("N", fontsize=12); ax_sp.set_ylabel("P_stat [cm/s / cm]", fontsize=12)
    ax_sv.set_title("TP5 – Velocidad promedio estacionaria vs N", fontsize=13)
    ax_sp.set_title("TP5 – Presión estacionaria sobre la pared vs N", fontsize=13)
    for mode, col, marker in zip(MODES, COLORS, ["o", "s"]):
        ns, vm_arr, vs_arr, pm_arr, ps_arr = [], [], [], [], []
        for n_val in N_ALL:
            results = load_mode_n(bin_root, mode, n_val, a.n_runs)
            if not results:
                continue
            vm, vs, pm, ps = stationary_stats(results, a.stat_frac)
            if vm is None:
                continue
            ns.append(n_val)
            vm_arr.append(vm); vs_arr.append(vs)
            pm_arr.append(pm); ps_arr.append(ps)

        if not ns:
            continue
        ns = np.array(ns)
        ax_sv.errorbar(ns, vm_arr, yerr=vs_arr, fmt=f"{marker}-",
                       color=col, lw=2, capsize=5, elinewidth=1.5, label=mode)
        ax_sp.errorbar(ns, pm_arr, yerr=ps_arr, fmt=f"{marker}-",
                       color=col, lw=2, capsize=5, elinewidth=1.5, label=mode)

    for ax, name in [(ax_sv, "v_stat_vs_N"), (ax_sp, "P_stat_vs_N")]:
        ax.legend(fontsize=11); ax.grid(True, ls="--", alpha=0.4)
        plt.figure(ax.figure.number)
        plt.tight_layout()
        out = os.path.join(img_dir, f"tp5_{name}.png")
        ax.figure.savefig(out, dpi=150)
        print(f"Saved → {out}")
    plt.close("all")

    # ── 5: v̄_stat vs P_stat para todos los N (ambos modos) ───────────────────
    for (ylabel, yfunc, fname) in [
        ("v̄_stat [cm/s]",    lambda v: v,    "tp5_v_stat_vs_P_stat_allN.png"),
        ("v̄²_stat [cm²/s²]", lambda v: v**2, "tp5_v2_stat_vs_P_stat_allN.png"),
    ]:
        fig_vp_all, ax_vp_all = plt.subplots(figsize=(8, 6))
        ax_vp_all.set_xlabel("P_stat [dina/cm]", fontsize=12)
        ax_vp_all.set_ylabel(ylabel, fontsize=12)
        ax_vp_all.set_title(f"TP5 – {ylabel} vs P estacionaria (todos los N)", fontsize=13)

        for mode, col, marker in zip(MODES, COLORS, ["o", "s"]):
            pts_p, pts_v, pts_n = [], [], []
            for n_val in N_ALL:
                results = load_mode_n(bin_root, mode, n_val, a.n_runs)
                if not results:
                    continue
                vm, vs, pm, ps = stationary_stats(results, a.stat_frac)
                if vm is None:
                    continue
                pts_p.append(pm); pts_v.append(yfunc(vm)); pts_n.append(n_val)
            if not pts_p:
                continue
            ax_vp_all.plot(pts_p, pts_v, color=col, lw=1.5, alpha=0.5)
            ax_vp_all.scatter(pts_p, pts_v, color=col, marker=marker, s=80, zorder=5)
            for p, v, n_val in zip(pts_p, pts_v, pts_n):
                ax_vp_all.annotate(str(n_val), (p, v), textcoords="offset points",
                                   xytext=(5, 4), fontsize=9, color=col)

        ax_vp_all.legend(handles=[
            mpatches.Patch(color=COLORS[0], label="quiral"),
            mpatches.Patch(color=COLORS[1], label="random"),
        ], fontsize=11)
        ax_vp_all.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        out = os.path.join(img_dir, fname)
        fig_vp_all.savefig(out, dpi=150)
        plt.close(fig_vp_all)
        print(f"Saved → {out}")


if __name__ == "__main__":
    main()
