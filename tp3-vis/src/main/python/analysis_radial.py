#!/usr/bin/env python3
"""
Análisis 1.4 – Perfiles radiales de partículas frescas.

Reads pre-generated simulation data (with frames) from:
  <bin-dir>/radial/N<n>/r<r>/frames/frame_*.txt
  <bin-dir>/radial/N<n>/r<r>/metadata.txt

Run simulations first with run_tp3_sims.sh.

Usage:
    python3 analysis_radial.py [--bin-dir PATH] [--n-values N1 N2 ...]
"""
import argparse, os, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm


# ── Configuration ──────────────────────────────────────────────────────────────
N_VALUES = [25, 50, 100, 200]

DS        = 0.2   # shell width [m]
R_OBS_EFF = 2.0   # SIGMA_OBS = R_OBSTACLE + R_PARTICLE
R_WALL_EFF= 39.0  # R_DOMAIN  - R_PARTICLE
S_TARGET  = 2.0   # shell near the obstacle for the final plot


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp3-bin"))


def parse_metadata(path):
    meta = {}
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 2:
                try: meta[p[0]] = float(p[1])
                except: meta[p[0]] = p[1]
    return meta


def load_frames_raw(frames_dir, n):
    """Yield (t, x, y, vx, vy, state) for each frame file."""
    files = sorted(f for f in os.listdir(frames_dir) if re.match(r"frame_\d+\.txt$", f))
    for fname in files:
        with open(os.path.join(frames_dir, fname)) as f:
            lines = [l.strip() for l in f if l.strip()]
        if len(lines) < n + 1:
            continue
        t = float(lines[0])
        x  = np.empty(n); y  = np.empty(n)
        pvx = np.empty(n); pvy = np.empty(n)
        st  = np.empty(n, dtype=int)
        for i in range(n):
            p = lines[1+i].split()
            x[i]=float(p[0]); y[i]=float(p[1])
            pvx[i]=float(p[2]); pvy[i]=float(p[3])
            st[i]=int(p[4])
        yield t, x, y, pvx, pvy, st


def shell_edges():
    return np.arange(R_OBS_EFF, R_WALL_EFF, DS)


def accumulate_radial(frames_dir, n, s_edges):
    ns = len(s_edges)
    rho_sum = np.zeros(ns)
    vel_sum = np.zeros(ns)
    frame_count = 0

    for t, x, y, pvx, pvy, st in load_frames_raw(frames_dir, n):
        frame_count += 1
        r_mag = np.sqrt(x**2 + y**2)
        dot   = x * pvx + y * pvy
        v_n   = dot / np.where(r_mag > 0, r_mag, 1.0)

        mask = (st == 0) & (dot < 0)

        for k, s in enumerate(s_edges):
            shell_mask = mask & (r_mag >= s) & (r_mag < s + DS)
            count = np.sum(shell_mask)
            if count == 0:
                continue
            area = np.pi * ((s + DS)**2 - s**2)
            rho_sum[k] += count / area
            vel_sum[k] += np.sum(np.abs(v_n[shell_mask]))

    return rho_sum, vel_sum, frame_count


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir",  default=None)
    ap.add_argument("--n-values", nargs="+", type=int, default=None)
    a = ap.parse_args()

    bin_root  = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir   = os.path.join(bin_root, "images")
    os.makedirs(img_dir, exist_ok=True)
    n_vals    = a.n_values or N_VALUES
    rad_root  = os.path.join(bin_root, "radial")

    s_edges   = shell_edges()
    s_centres = s_edges + DS / 2
    idx_target = int(np.argmin(np.abs(s_centres - S_TARGET)))

    rho_profiles  = {}
    vel_profiles  = {}
    jin_profiles  = {}
    jin_at_target = {}
    rho_at_target = {}
    vel_at_target = {}

    for n in n_vals:
        print(f"\nN = {n}")
        n_dir = os.path.join(rad_root, f"N{n}")
        if not os.path.isdir(n_dir):
            print(f"  WARNING: {n_dir} not found, skipping")
            continue

        r_dirs = sorted(
            d for d in Path(n_dir).iterdir()
            if d.is_dir() and (d / "frames").is_dir()
        )
        if not r_dirs:
            print(f"  WARNING: no realization dirs in {n_dir}, skipping")
            continue

        rho_total    = np.zeros(len(s_edges))
        vel_total    = np.zeros(len(s_edges))
        total_frames = 0

        for r_dir in r_dirs:
            print(f"  loading {r_dir.name} frames … ", end="", flush=True)
            rs, vs, fc = accumulate_radial(str(r_dir / "frames"), n, s_edges)
            rho_total   += rs
            vel_total   += vs
            total_frames += fc
            print(f"{fc} frames")

        if total_frames == 0:
            print("  Warning: no frames accumulated")
            continue

        rho_mean = rho_total / total_frames
        areas    = np.pi * ((s_edges + DS)**2 - s_edges**2)
        count_total = rho_total * areas
        vel_mean = np.where(count_total > 0, vel_total / count_total, 0.0)
        jin_mean = rho_mean * vel_mean

        rho_profiles[n] = rho_mean
        vel_profiles[n] = vel_mean
        jin_profiles[n] = jin_mean

        jin_at_target[n] = jin_mean[idx_target]
        rho_at_target[n] = rho_mean[idx_target]
        vel_at_target[n] = vel_mean[idx_target]

    if not rho_profiles:
        print("No profiles computed."); return

    colors = cm.plasma(np.linspace(0.1, 0.9, len(n_vals)))

    # ── Plot radial profiles: one figure per quantity, all N overlaid ────────
    curve_defs = [
        ("rho", r"$\langle\rho_f^{in}\rangle(S)$", rho_profiles),
        ("v",   r"$|\langle v_f^{in}\rangle(S)|$",  vel_profiles),
        ("Jin", r"$J_{in}(S)$",                     jin_profiles),
    ]
    for fname, ylabel, profiles in curve_defs:
        fig, ax = plt.subplots(figsize=(8, 5))
        for i, n in enumerate(n_vals):
            if n not in profiles:
                continue
            ax.plot(s_centres, profiles[n], lw=2, color=colors[i], label=f"N={n}")
        ax.set_xlabel("S [m]", fontsize=13)
        ax.set_ylabel(ylabel, fontsize=13)
        ax.set_title(ylabel, fontsize=13)
        ax.legend(fontsize=11)
        ax.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        out_path = os.path.join(img_dir, f"{fname}_vs_S.png")
        plt.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Saved → {out_path}")

    # ── Plot 1.4: rho(S) for all N overlaid ──────────────────────────────────
    fig_rho, ax_rho = plt.subplots(figsize=(8, 5))
    for i, n in enumerate(n_vals):
        if n not in rho_profiles:
            continue
        ax_rho.plot(s_centres, rho_profiles[n], lw=2, color=colors[i], label=f"N={n}")
    ax_rho.set_xlabel("S [m]", fontsize=13)
    ax_rho.set_ylabel(r"$\rho(S)$", fontsize=13)
    ax_rho.set_title(r"Perfil radial de densidad $\rho(S)$", fontsize=13)
    ax_rho.legend(fontsize=11)
    ax_rho.grid(True, ls="--", alpha=0.4)
    plt.tight_layout()
    out_rho = os.path.join(img_dir, "rho_vs_S.png")
    plt.savefig(out_rho, dpi=150)
    print(f"Saved → {out_rho}")

    # ── Plot J_in, rho, v at S≈S_TARGET vs N ─────────────────────────────────
    n_plot = [n for n in n_vals if n in jin_at_target]
    if n_plot:
        fig2, ax2 = plt.subplots(figsize=(7, 5))
        n_arr = np.array(n_plot)
        ax2.plot(n_arr, [jin_at_target[n] for n in n_plot], "o-", lw=2,
                 color="#e74c3c", label=r"$J_{in}$")
        ax2.plot(n_arr, [rho_at_target[n] for n in n_plot], "s-", lw=2,
                 color="#3498db", label=r"$\langle\rho_f^{in}\rangle$")
        ax2.plot(n_arr, [vel_at_target[n] for n in n_plot], "^-", lw=2,
                 color="#2ecc71", label=r"$|\langle v_f^{in}\rangle|$")
        ax2.set_xlabel("N", fontsize=13)
        ax2.set_ylabel("Magnitud en S ≈ 2 m", fontsize=13)
        ax2.set_title(f"1.4 – Observables en capa S≈{S_TARGET:.1f} m vs N", fontsize=13)
        ax2.legend(fontsize=11)
        ax2.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        out2 = os.path.join(img_dir, "radial_target_vs_N.png")
        plt.savefig(out2, dpi=150)
        print(f"Saved → {out2}")

    plt.close("all")


if __name__ == "__main__":
    main()
