#!/usr/bin/env python3
"""
TP4 Análisis 1.4 – Variación de la constante elástica k.

Computes for each k:
  1) <J>(N)   – scanning rate from cfc.txt  (same as analysis_scanning_rate.py)
  2) <J_in|S≈2>(N) – inward fresh-particle flux at S≈2 m from frame files

Then:
  - Plots both curves for all k values on the same figure.
  - Identifies scalars that characterise each curve:
      · N*(k)   = argmax_N <J>(N)          (for <J>)
      · max(<J>)(k)                         (for <J>)
      · N*(k)   = argmax_N <J_in|S≈2>(N)  (for <J_in>)
      · max(<J_in|S≈2>)(k)                 (for <J_in>)
  - Plots those scalars vs k.

Directory layout expected:
  <bin-dir>/k_variation/k<k>/N<n>/r<r>/cfc.txt
  <bin-dir>/k_variation/k<k>/N<n>/r<r>/metadata.txt
  <bin-dir>/k_variation/k<k>/N<n>/r<r>/frames/frame_*.txt

Usage:
    python3 analysis_k_variation.py [--bin-dir PATH]
"""
import argparse, os, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm


TRANSIENT_FRAC = 0.2   # skip first 20 % of time as transient
DS             = 0.2    # radial shell width
R_OBS_EFF      = 2.0
R_WALL_EFF     = 39.0
S_TARGET       = 2.0    # target shell centre for J_in|S-2


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin"))


def _default_tp3_bin():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp3-bin"))


def load_tp3_j(tp3_bin, transient_frac=TRANSIENT_FRAC):
    """Return {N: (mean_J, std_J)} from TP3 scanning_rate/N*/r*/stats.txt."""
    sr_root = Path(tp3_bin) / "scanning_rate"
    if not sr_root.exists():
        return {}
    result = {}
    for n_dir in sorted(
        (d for d in sr_root.iterdir() if d.is_dir() and re.match(r"N\d+$", d.name)),
        key=lambda d: int(d.name[1:])
    ):
        n = int(n_dir.name[1:])
        js = []
        for r_dir in sorted(
            d for d in n_dir.iterdir() if d.is_dir() and re.match(r"r\d+$", d.name)
        ):
            stats = r_dir / "stats.txt"
            if not stats.exists():
                continue
            t_vals, c_vals = [], []
            with open(stats) as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) >= 2:
                        try:
                            t_vals.append(float(p[0])); c_vals.append(float(p[1]))
                        except ValueError:
                            pass
            if len(t_vals) < 2:
                continue
            t_arr = np.array(t_vals); c_arr = np.array(c_vals)
            t_start = transient_frac * t_arr[-1]
            mask = t_arr >= t_start
            if mask.sum() < 2:
                continue
            js.append(np.polyfit(t_arr[mask], c_arr[mask], 1)[0])
        if js:
            result[n] = (float(np.mean(js)),
                         float(np.std(js, ddof=1)) if len(js) > 1 else 0.0)
    return result


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


# ── <J> from cfc.txt ──────────────────────────────────────────────────────────

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


def compute_j(times, tf, transient_frac=TRANSIENT_FRAC):
    """Compute scanning rate J = dCfc/dt via linear regression."""
    if len(times) < 2:
        return 0.0

    t_start = transient_frac * tf
    mask = times >= t_start
    times_stat = times[mask]
    if len(times_stat) < 2:
        return 0.0

    t_vals = np.concatenate([[t_start], times_stat])
    c_vals = np.arange(len(t_vals))
    coeffs = np.polyfit(t_vals, c_vals, 1)
    return coeffs[0]  # slope


# ── <J_in|S≈2> from frame files ──────────────────────────────────────────────

def load_frames_raw(frames_dir, n):
    files = sorted(f for f in os.listdir(frames_dir) if re.match(r"frame_\d+\.txt$", f))
    for fname in files:
        with open(os.path.join(frames_dir, fname)) as f:
            lines = [l.strip() for l in f if l.strip()]
        if len(lines) < n + 1:
            continue
        t = float(lines[0])
        x   = np.empty(n); y   = np.empty(n)
        pvx = np.empty(n); pvy = np.empty(n)
        st  = np.empty(n, dtype=int)
        for i in range(n):
            p = lines[1 + i].split()
            x[i]=float(p[0]); y[i]=float(p[1])
            pvx[i]=float(p[2]); pvy[i]=float(p[3])
            st[i]=int(p[4])
        yield t, x, y, pvx, pvy, st


def compute_jin_at_target(frames_dir, n, s_target=S_TARGET, ds=DS):
    """Average inward fresh-particle flux at shell S≈s_target."""
    s_lo = s_target
    s_hi = s_target + ds
    area = np.pi * (s_hi**2 - s_lo**2)

    jin_vals = []
    for t, x, y, pvx, pvy, st in load_frames_raw(frames_dir, n):
        r_mag = np.sqrt(x**2 + y**2)
        dot   = x * pvx + y * pvy
        v_n   = dot / np.where(r_mag > 0, r_mag, 1.0)
        # fresh, inward, in target shell
        mask = (st == 0) & (dot < 0) & (r_mag >= s_lo) & (r_mag < s_hi)
        count = np.sum(mask)
        rho_f = count / area
        v_f   = float(np.mean(np.abs(v_n[mask]))) if count > 0 else 0.0
        jin_vals.append(rho_f * v_f)
    return float(np.mean(jin_vals)) if jin_vals else 0.0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", default=None)
    ap.add_argument("--tp3-bin", default=None)
    ap.add_argument("--k-subdir", default="k_variation",
                    help="Subdirectory under bin-dir that contains k* dirs (default: k_variation)")
    a = ap.parse_args()

    bin_dir = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    tp3_bin = os.path.abspath(a.tp3_bin) if a.tp3_bin else _default_tp3_bin()
    img_dir = os.path.join(bin_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    kv_root = os.path.join(bin_dir, a.k_subdir)

    if not os.path.isdir(kv_root):
        print(f"ERROR: {kv_root} not found. Run run_tp4_k_variation.sh first.")
        raise SystemExit(1)

    # Discover k directories
    k_dirs = sorted(
        d for d in Path(kv_root).iterdir()
        if d.is_dir() and re.match(r"k\d+(\.\d+)?$", d.name)
    )
    if not k_dirs:
        print("No k directories found.")
        raise SystemExit(1)

    # ── Collect data ──────────────────────────────────────────────────────────
    # k → {N: [j_per_realization, ...]}
    j_data   = {}    # <J> from cfc
    jin_data = {}    # <J_in|S≈2> from frames
    dt_used  = {}    # dt used per k (for reporting)

    for k_dir in k_dirs:
        k_val = float(k_dir.name[1:])
        print(f"\n{'='*50}")
        print(f"  k = {k_val}")
        print(f"{'='*50}")

        j_data[k_val]   = {}
        jin_data[k_val] = {}

        n_dirs = sorted(
            (d for d in k_dir.iterdir()
             if d.is_dir() and re.match(r"N\d+$", d.name)),
            key=lambda d: int(d.name[1:])
        )

        for n_dir in n_dirs:
            n = int(n_dir.name[1:])
            r_dirs = sorted(
                d for d in n_dir.iterdir()
                if d.is_dir() and re.match(r"r\d+$", d.name)
            )
            if not r_dirs:
                continue

            j_list   = []
            jin_list = []

            for r_dir in r_dirs:
                # Read metadata for tf and dt
                meta_path = r_dir / "metadata.txt"
                tf = 2000.0
                if meta_path.exists():
                    meta = parse_metadata(str(meta_path))
                    tf = float(meta.get("tf", tf))
                    dt_used[k_val] = meta.get("dt", "?")

                # <J> from cfc.txt
                cfc_path = r_dir / "cfc.txt"
                if cfc_path.exists():
                    times = load_cfc_times(str(cfc_path))
                    j = compute_j(times, tf)
                    j_list.append(j)

                # <J_in|S≈2> from frames
                frames_dir = r_dir / "frames"
                if frames_dir.is_dir():
                    jin = compute_jin_at_target(str(frames_dir), n)
                    jin_list.append(jin)

            if j_list:
                j_data[k_val][n] = j_list
            if jin_list:
                jin_data[k_val][n] = jin_list

            j_mean_n   = np.mean(j_list)   if j_list   else float('nan')
            jin_mean_n = np.mean(jin_list) if jin_list else float('nan')
            print(f"  N={n:4d}  <J>={j_mean_n:.4f}  <J_in|S≈2>={jin_mean_n:.6f}  ({len(r_dirs)} realiz.)")

    # ── Compute means and errors ──────────────────────────────────────────────
    k_vals = sorted(j_data.keys())
    colors_map = cm.viridis(np.linspace(0.15, 0.85, len(k_vals)))
    k_colors = {k: colors_map[i] for i, k in enumerate(k_vals)}

    tp3_j = load_tp3_j(tp3_bin)

    def mean_std(vals):
        m = float(np.mean(vals))
        s = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        return m, s

    # ── PLOT 1: <J>(N) for each k ────────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(9, 6))
    n_star_j = {}; max_j = {}

    for k_val in k_vals:
        if not j_data[k_val]:
            continue
        ns = np.array(sorted(j_data[k_val].keys()))
        jm = np.array([mean_std(j_data[k_val][n])[0] for n in ns])
        je = np.array([mean_std(j_data[k_val][n])[1] for n in ns])

        label = f"k={k_val:.0f}"
        ax1.errorbar(ns, jm, yerr=je, fmt="o-", lw=2, color=k_colors[k_val],
                     capsize=4, elinewidth=1.2, label=label)

        # Scalar: N* and max <J>
        idx_max = np.argmax(jm)
        n_star_j[k_val] = int(ns[idx_max])
        max_j[k_val]    = float(jm[idx_max])

    if tp3_j:
        ns3 = np.array(sorted(tp3_j.keys()))
        jm3 = np.array([tp3_j[n][0] for n in ns3])
        je3 = np.array([tp3_j[n][1] for n in ns3])
        ax1.errorbar(ns3, jm3, yerr=je3, fmt="s--", lw=2, color="black",
                     capsize=4, elinewidth=1.2, label="TP3 – Event-Driven")

    ax1.set_xlabel("N", fontsize=13)
    ax1.set_ylabel("J", fontsize=13)
    ax1.set_title("Tasa de escaneo $J(N)$ para distintos $k$", fontsize=14)
    ax1.legend(fontsize=10)
    ax1.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out1 = os.path.join(img_dir, "tp4_k_variation_J_vs_N.png")
    plt.savefig(out1, dpi=150)
    plt.close(fig1)
    print(f"\nSaved → {out1}")

    # ── PLOT 2: <J_in|S≈2>(N) for each k ─────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(9, 6))
    n_star_jin = {}; max_jin = {}

    for k_val in k_vals:
        if not jin_data[k_val]:
            continue
        ns = np.array(sorted(jin_data[k_val].keys()))
        jm = np.array([mean_std(jin_data[k_val][n])[0] for n in ns])
        je = np.array([mean_std(jin_data[k_val][n])[1] for n in ns])

        label = f"k={k_val:.0f}"
        ax2.errorbar(ns, jm, yerr=je, fmt="s-", lw=2, color=k_colors[k_val],
                     capsize=4, elinewidth=1.2, label=label)

        idx_max = np.argmax(jm)
        n_star_jin[k_val] = int(ns[idx_max])
        max_jin[k_val]    = float(jm[idx_max])

    ax2.set_xlabel("N", fontsize=13)
    ax2.set_ylabel("$\\langle J_{in}|_{S \\approx 2} \\rangle$", fontsize=13)
    ax2.set_title("TP4 1.4 – Flujo entrante $\\langle J_{in}|_{S \\approx 2} \\rangle (N)$ para distintos $k$",
                  fontsize=14)
    ax2.legend(fontsize=10)
    ax2.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out2 = os.path.join(img_dir, "tp4_k_variation_Jin_vs_N.png")
    plt.savefig(out2, dpi=150)
    plt.close(fig2)
    print(f"Saved → {out2}")

    # ── PLOT 3: Scalars vs k ──────────────────────────────────────────────────
    fig3, axes = plt.subplots(2, 2, figsize=(12, 9))

    # 3a: N*(k) from <J>
    ax = axes[0, 0]
    ks = sorted(n_star_j.keys())
    if ks:
        ax.plot(ks, [n_star_j[k] for k in ks], "o-", lw=2, color="#e74c3c", ms=8)
        ax.set_xscale("log")
        ax.set_xlabel("k [N/m]", fontsize=12)
        ax.set_ylabel("$N^*(k)$", fontsize=12)
        ax.set_title("$N^*$ que maximiza $\\langle J \\rangle$", fontsize=13)
        ax.grid(True, ls="--", alpha=0.4)

    # 3b: max <J>(k)
    ax = axes[0, 1]
    ks = sorted(max_j.keys())
    if ks:
        ax.plot(ks, [max_j[k] for k in ks], "o-", lw=2, color="#3498db", ms=8)
        ax.set_xscale("log")
        ax.set_xlabel("k [N/m]", fontsize=12)
        ax.set_ylabel("$\\max\\langle J \\rangle$", fontsize=12)
        ax.set_title("Máximo de $\\langle J \\rangle$ vs $k$", fontsize=13)
        ax.grid(True, ls="--", alpha=0.4)

    # 3c: N*(k) from <J_in>
    ax = axes[1, 0]
    ks = sorted(n_star_jin.keys())
    if ks:
        ax.plot(ks, [n_star_jin[k] for k in ks], "s-", lw=2, color="#e67e22", ms=8)
        ax.set_xscale("log")
        ax.set_xlabel("k [N/m]", fontsize=12)
        ax.set_ylabel("$N^*(k)$", fontsize=12)
        ax.set_title("$N^*$ que maximiza $\\langle J_{in}|_{S \\approx 2} \\rangle$", fontsize=13)
        ax.grid(True, ls="--", alpha=0.4)

    # 3d: max <J_in>(k)
    ax = axes[1, 1]
    ks = sorted(max_jin.keys())
    if ks:
        ax.plot(ks, [max_jin[k] for k in ks], "s-", lw=2, color="#2ecc71", ms=8)
        ax.set_xscale("log")
        ax.set_xlabel("k [N/m]", fontsize=12)
        ax.set_ylabel("$\\max\\langle J_{in}|_{S \\approx 2} \\rangle$", fontsize=12)
        ax.set_title("Máximo de $\\langle J_{in}|_{S \\approx 2} \\rangle$ vs $k$", fontsize=13)
        ax.grid(True, ls="--", alpha=0.4)

    plt.suptitle("TP4 1.4 – Escalares característicos en función de $k$",
                 fontsize=15, y=1.01)
    plt.tight_layout()
    out3 = os.path.join(img_dir, "tp4_k_variation_scalars.png")
    plt.savefig(out3, dpi=150, bbox_inches="tight")
    plt.close(fig3)
    print(f"Saved → {out3}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  RESUMEN – Escalares característicos")
    print("="*60)
    print(f"{'k':>10s}  {'dt':>10s}  {'N*(J)':>6s}  {'max<J>':>10s}  {'N*(Jin)':>8s}  {'max<Jin>':>10s}")
    print("-"*60)
    for k_val in sorted(set(list(n_star_j.keys()) + list(n_star_jin.keys()))):
        dt_str   = str(dt_used.get(k_val, "?"))
        ns_j     = n_star_j.get(k_val, "-")
        mj       = f"{max_j.get(k_val, 0):.4f}" if k_val in max_j else "-"
        ns_jin   = n_star_jin.get(k_val, "-")
        mjin     = f"{max_jin.get(k_val, 0):.6f}" if k_val in max_jin else "-"
        print(f"{k_val:>10.0f}  {dt_str:>10s}  {ns_j!s:>6s}  {mj:>10s}  {ns_jin!s:>8s}  {mjin:>10s}")


if __name__ == "__main__":
    main()
