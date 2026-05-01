#!/usr/bin/env python3
"""
TP4 Análisis – Perfiles radiales de partículas frescas (Time-Driven MD).

Same logic as TP3 analysis_radial.py but reads TP4 frame files.

Directory layout:
  <bin-dir>/radial/N<n>/r<r>/frames/frame_*.txt
  <bin-dir>/radial/N<n>/r<r>/metadata.txt

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
import matplotlib.ticker


N_VALUES        = [100, 200, 300, 400]
N_VALUES_TARGET = list(range(50, 501, 50))

DS        = 0.2
R_OBS_EFF = 2.0
R_WALL_EFF= 39.0
S_TARGET  = 2.0


def _default_bin_dir():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin"))


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


def shell_edges():
    return np.arange(R_OBS_EFF, R_WALL_EFF, DS)


def accumulate_radial(frames_dir, n, s_edges, target_idx=None):
    ns = len(s_edges)
    rho_sum = np.zeros(ns)
    vel_sum = np.zeros(ns)
    frame_count = 0
    target_frames = []

    for t, x, y, pvx, pvy, st in load_frames_raw(frames_dir, n):
        frame_count += 1
        r_mag = np.sqrt(x**2 + y**2)
        dot   = x * pvx + y * pvy
        v_n   = dot / np.where(r_mag > 0, r_mag, 1.0)
        mask  = (st == 0) & (dot < 0)

        for k, s in enumerate(s_edges):
            shell_mask = mask & (r_mag >= s) & (r_mag < s + DS)
            count = np.sum(shell_mask)
            if count == 0:
                continue
            area = np.pi * ((s + DS)**2 - s**2)
            rho_sum[k] += count / area
            vel_sum[k] += np.sum(np.abs(v_n[shell_mask]))

        if target_idx is not None:
            s_t = s_edges[target_idx]
            shell_mask_t = mask & (r_mag >= s_t) & (r_mag < s_t + DS)
            count_t = np.sum(shell_mask_t)
            area_t  = np.pi * ((s_t + DS)**2 - s_t**2)
            rho_f   = count_t / area_t
            v_f     = float(np.mean(np.abs(v_n[shell_mask_t]))) if count_t > 0 else 0.0
            target_frames.append((rho_f, v_f, rho_f * v_f))

    return rho_sum, vel_sum, frame_count, target_frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir",  default=None)
    ap.add_argument("--n-values", nargs="+", type=int, default=None)
    a = ap.parse_args()

    bin_root  = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir   = os.path.join(bin_root, "images")
    os.makedirs(img_dir, exist_ok=True)
    n_vals        = a.n_values or N_VALUES
    n_vals_target = a.n_values or N_VALUES_TARGET
    n_vals_all    = sorted(set(n_vals) | set(n_vals_target))
    rad_root  = os.path.join(bin_root, "radial")

    s_edges   = shell_edges()
    s_centres = s_edges + DS / 2
    idx_target = int(np.argmin(np.abs(s_centres - S_TARGET)))

    rho_profiles = {}; vel_profiles = {}; jin_profiles = {}
    jin_at_target = {}; jin_std_target = {}
    rho_at_target = {}; rho_std_target = {}
    vel_at_target = {}; vel_std_target = {}

    for n in n_vals_all:
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

        areas = np.pi * ((s_edges + DS)**2 - s_edges**2)
        rho_per_r = []; vel_per_r = []; jin_per_r = []
        rho_tgt_per_r = []; vel_tgt_per_r = []; jin_tgt_per_r = []

        for r_dir in r_dirs:
            print(f"  loading {r_dir.name} … ", end="", flush=True)
            rs, vs, fc, tgt = accumulate_radial(str(r_dir / "frames"), n, s_edges, idx_target)
            print(f"{fc} frames")
            if fc == 0:
                continue
            rho_r = rs / fc
            cnt_r = rs * areas
            vel_r = np.where(cnt_r > 0, vs / cnt_r, 0.0)
            jin_r = rho_r * vel_r
            rho_per_r.append(rho_r); vel_per_r.append(vel_r); jin_per_r.append(jin_r)

            tgt_arr = np.array(tgt)
            rho_tgt_per_r.append(float(np.mean(tgt_arr[:, 0])))
            vel_tgt_per_r.append(float(np.mean(tgt_arr[:, 1])))
            jin_tgt_per_r.append(float(np.mean(tgt_arr[:, 2])))

        if not rho_per_r:
            continue

        rho_mat = np.array(rho_per_r)
        vel_mat = np.array(vel_per_r)
        jin_mat = np.array(jin_per_r)

        rho_profiles[n] = rho_mat.mean(axis=0)
        vel_profiles[n] = vel_mat.mean(axis=0)
        jin_profiles[n] = jin_mat.mean(axis=0)

        def _ms(vals):
            a_ = np.array(vals)
            return float(np.mean(a_)), (float(np.std(a_, ddof=1)) if len(a_) > 1 else 0.0)

        rho_at_target[n], rho_std_target[n] = _ms(rho_tgt_per_r)
        vel_at_target[n], vel_std_target[n] = _ms(vel_tgt_per_r)
        jin_at_target[n], jin_std_target[n] = _ms(jin_tgt_per_r)

    if not rho_profiles:
        print("No profiles computed."); return

    colors = cm.plasma(np.linspace(0.1, 0.9, len(n_vals)))

    curve_defs = [
        ("tp4_rho_vs_S", r"$\langle\rho_f^{in}\rangle(S)$", rho_profiles),
        ("tp4_v_vs_S",   r"$|\langle v_f^{in}\rangle(S)|$",  vel_profiles),
        ("tp4_Jin_vs_S", r"$J_{in}(S)$",                     jin_profiles),
    ]
    for fname, ylabel, profiles in curve_defs:
        fig, ax = plt.subplots(figsize=(8, 5))
        for i, n in enumerate(n_vals):
            if n not in profiles:
                continue
            ax.plot(s_centres, profiles[n], lw=2, color=colors[i], label=f"N={n}")
        ax.set_xlabel("S [m]", fontsize=13)
        ax.set_ylabel(ylabel, fontsize=13)
        ax.set_title(f"TP4 – {ylabel}", fontsize=13)
        ax.legend(fontsize=11)
        ax.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        out_path = os.path.join(img_dir, f"{fname}.png")
        plt.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Saved → {out_path}")

    # vs-N plots at S~S_TARGET
    n_plot = [n for n in n_vals_target if n in jin_at_target]
    if n_plot:
        n_arr = np.array(n_plot)
        target_defs = [
            (r"$J_{in}(S \approx 2\,\mathrm{m})$",   "#e74c3c", jin_at_target, jin_std_target, "tp4_Jin_vs_N.png"),
            (r"$\langle\rho_f^{in}\rangle(S \approx 2\,\mathrm{m})$", "#3498db", rho_at_target, rho_std_target, "tp4_rho_vs_N.png"),
            (r"$|\langle v_f^{in}\rangle|(S \approx 2\,\mathrm{m})$", "#2ecc71", vel_at_target, vel_std_target, "tp4_v_vs_N.png"),
        ]
        for ylabel, color, data, std_data, fname in target_defs:
            fig_t, ax_t = plt.subplots(figsize=(7, 5))
            ax_t.errorbar(n_arr, [data[n] for n in n_plot],
                          yerr=[std_data[n] for n in n_plot],
                          fmt="o-", lw=2, color=color, capsize=5, elinewidth=1.5)
            ax_t.set_xlabel("N", fontsize=13)
            ax_t.set_ylabel(ylabel, fontsize=13)
            ax_t.set_title(f"TP4 – {ylabel}", fontsize=13)
            ax_t.grid(True, ls="--", alpha=0.4)
            plt.tight_layout()
            out_t = os.path.join(img_dir, fname)
            plt.savefig(out_t, dpi=150)
            plt.close(fig_t)
            print(f"Saved → {out_t}")


if __name__ == "__main__":
    main()
