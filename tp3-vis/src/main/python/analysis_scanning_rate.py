#!/usr/bin/env python3
"""
Análisis 1.2 + 1.3 – Scanning rate J vs N  AND  evolución de Fu(t).

Reads pre-generated simulation data from:
  <bin-dir>/scanning_rate/N<n>/r<r>/stats.txt

Run simulations first with run_tp3_sims.sh.

Usage:
    python3 analysis_scanning_rate.py [--bin-dir PATH] [--n-values N1 N2 ...]
"""
import argparse, os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm


# ── Configuration ──────────────────────────────────────────────────────────────
N_VALUES = list(range(100, 900, 100))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp3-bin"))


def load_stats(run_dir: str) -> np.ndarray:
    """Returns array with columns [time, Cfc, Nu]."""
    rows = []
    with open(os.path.join(run_dir, "stats.txt")) as f:
        next(f)  # skip header
        for line in f:
            p = line.strip().split()
            if p:
                rows.append([float(p[0]), int(p[1]), int(p[2])])
    return np.array(rows) if rows else np.zeros((0, 3))


def linear_slope(t: np.ndarray, cfc: np.ndarray) -> float:
    """Fit Cfc(t) = J*t + b, return J."""
    if len(t) < 2:
        return 0.0
    slope, _ = np.polyfit(t, cfc, 1)
    return float(slope)


def steady_state(t: np.ndarray, fu: np.ndarray, window_frac: float = 0.2):
    """
    Returns (t_ss, f_est):
      t_ss  – time at which Fu first enters the steady-state band
      f_est – mean of Fu over the last window_frac of simulation time
    """
    if len(t) < 10:
        return t[-1] if len(t) else 0.0, fu[-1] if len(fu) else 0.0
    win = max(1, int(len(t) * window_frac))
    f_est = float(np.mean(fu[-win:]))
    band = 0.05 * f_est if f_est > 0 else 0.01
    for i in range(len(fu)):
        if abs(fu[i] - f_est) < band:
            return float(t[i]), f_est
    return float(t[-1]), f_est


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir",  default=None)
    ap.add_argument("--n-values", nargs="+", type=int, default=None)
    a = ap.parse_args()

    bin_root = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir  = os.path.join(bin_root, "images")
    os.makedirs(img_dir, exist_ok=True)
    n_vals  = a.n_values or N_VALUES
    sr_root = os.path.join(bin_root, "scanning_rate")

    J_means   = []
    J_stds    = []
    tss_vals  = []
    fest_vals = []
    fu_curves = {}

    for n in n_vals:
        print(f"\nN = {n}")
        n_dir = os.path.join(sr_root, f"N{n}")
        if not os.path.isdir(n_dir):
            print(f"  WARNING: {n_dir} not found, skipping")
            J_means.append(0); J_stds.append(0)
            tss_vals.append(0); fest_vals.append(0)
            fu_curves[n] = None
            continue

        r_dirs = sorted(
            d for d in Path(n_dir).iterdir()
            if d.is_dir() and (d / "stats.txt").exists()
        )
        if not r_dirs:
            print(f"  WARNING: no realization dirs in {n_dir}, skipping")
            J_means.append(0); J_stds.append(0)
            tss_vals.append(0); fest_vals.append(0)
            fu_curves[n] = None
            continue

        J_list         = []
        tss_list       = []
        fest_list      = []
        fu_interp_list = []

        for r_dir in r_dirs:
            print(f"  loading {r_dir.name} … ", end="", flush=True)
            data = load_stats(str(r_dir))
            print("done")

            if data.shape[0] < 2:
                continue

            t   = data[:, 0]
            cfc = data[:, 1]
            nu  = data[:, 2]
            fu  = nu / n
            tf  = float(t[-1])

            J_list.append(linear_slope(t, cfc))
            tss, fest = steady_state(t, fu)
            tss_list.append(tss)
            fest_list.append(fest)

            t_common  = np.linspace(0, tf, 500)
            fu_interp = np.interp(t_common, t, fu)
            fu_interp_list.append((t_common, fu_interp))

        if J_list:
            J_means.append(np.mean(J_list))
            J_stds.append(np.std(J_list, ddof=1) if len(J_list) > 1 else 0)
        else:
            J_means.append(0); J_stds.append(0)

        tss_vals.append(np.mean(tss_list) if tss_list else 0)
        fest_vals.append(np.mean(fest_list) if fest_list else 0)

        if fu_interp_list:
            tf_min   = min(tc[-1] for tc, _ in fu_interp_list)
            t_common = np.linspace(0, tf_min, 500)
            fu_all   = [np.interp(t_common, tc, fui) for tc, fui in fu_interp_list]
            fu_curves[n] = (t_common, np.mean(fu_all, axis=0))
        else:
            fu_curves[n] = None

    n_arr = np.array(n_vals)

    # ── Plot 1.2: <J>(N) ──────────────────────────────────────────────────────
    fig12, ax12 = plt.subplots(figsize=(7, 5))
    ax12.errorbar(n_arr, J_means, yerr=J_stds, fmt="o-",
                  color="#3498db", capsize=5, lw=2, ms=7, elinewidth=1.5)
    ax12.set_xlabel("N (número de partículas)", fontsize=13)
    ax12.set_ylabel("Scanning rate  J  [eventos/s]", fontsize=13)
    ax12.set_title("1.2 – Scanning rate ⟨J⟩ vs N", fontsize=14)
    ax12.grid(True, ls="--", alpha=0.5)
    plt.tight_layout()
    out12 = os.path.join(img_dir, "scanning_rate.png")
    plt.savefig(out12, dpi=150)
    print(f"\nSaved → {out12}")

    # ── Plot 1.3: Fu(t) per N + steady-state markers ─────────────────────────
    fig13, ax13 = plt.subplots(figsize=(8, 5))
    colors = cm.plasma(np.linspace(0.1, 0.9, len(n_vals)))
    for i, n in enumerate(n_vals):
        curve = fu_curves.get(n)
        if curve is None:
            continue
        t_c, fu_c = curve
        ax13.plot(t_c, fu_c, lw=2, color=colors[i], label=f"N={n}")
        if fest_vals[i] > 0:
            ax13.axhline(fest_vals[i], color=colors[i], ls=":", lw=1, alpha=0.7)
            ax13.axvline(tss_vals[i],  color=colors[i], ls="--", lw=1, alpha=0.7)

    ax13.set_xlabel("Tiempo [s]", fontsize=13)
    ax13.set_ylabel("Fu(t) = Nu(t)/N", fontsize=13)
    ax13.set_title("1.3 – Evolución temporal de la fracción de partículas usadas", fontsize=13)
    ax13.legend(fontsize=10)
    ax13.set_ylim(0.0, 0.2)
    ax13.grid(True, ls="--", alpha=0.5)
    plt.tight_layout()
    out13 = os.path.join(img_dir, "fu_evolution.png")
    plt.savefig(out13, dpi=150)
    print(f"Saved → {out13}")
    plt.close("all")

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n{'N':>6} {'<J>':>10} {'std(J)':>10} {'t_ss':>8} {'F_est':>8}")
    print("-" * 50)
    for i, n in enumerate(n_vals):
        print(f"{n:6d} {J_means[i]:10.4f} {J_stds[i]:10.4f} {tss_vals[i]:8.1f} {fest_vals[i]:8.4f}")


if __name__ == "__main__":
    main()
