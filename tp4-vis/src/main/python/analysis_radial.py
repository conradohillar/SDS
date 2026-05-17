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


N_VALUES        = list(range(100, 1001, 100))
N_VALUES_TARGET = list(range(100, 1001, 100))

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


T_MIN_DEFAULT = 0.0  # default: use all frames; override via --t-min


def accumulate_radial(frames_dir, n, s_edges, target_idx=None, t_min=0.0, stride=1):
    ns = len(s_edges)
    rho_sum = np.zeros(ns)
    vel_sum = np.zeros(ns)
    frame_count = 0
    raw_count = 0
    target_frames = []

    for t, x, y, pvx, pvy, st in load_frames_raw(frames_dir, n):
        if t < t_min:
            continue
        raw_count += 1
        if (raw_count - 1) % stride != 0:
            continue
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
    ap.add_argument("--runs-dir", default=None, help="Override runs directory (default: <bin-dir>/runs)")
    ap.add_argument("--tp3-bin",  default=None, help="TP3 bin dir for Jin(N) comparison")
    ap.add_argument("--t-min",    type=float, default=0.0, help="Discard frames with t < T_MIN (default: 0)")
    ap.add_argument("--stride",   type=int,   default=10,  help="Use every Nth frame (default: 10)")
    ap.add_argument("--n-values", nargs="+", type=int, default=None)
    a = ap.parse_args()

    bin_root  = os.path.abspath(a.bin_dir) if a.bin_dir else _default_bin_dir()
    img_dir   = os.path.join(bin_root, "images")
    os.makedirs(img_dir, exist_ok=True)
    n_vals        = a.n_values or N_VALUES
    n_vals_target = a.n_values or N_VALUES_TARGET
    n_vals_all    = sorted(set(n_vals) | set(n_vals_target))
    rad_root  = os.path.abspath(a.runs_dir) if a.runs_dir else os.path.join(bin_root, "runs")

    s_edges   = shell_edges()
    s_centres = s_edges + DS / 2
    idx_target = int(np.argmin(np.abs(s_centres - S_TARGET)))

    def _ms(vals):
        a_ = np.array(vals)
        return float(np.mean(a_)), (float(np.std(a_, ddof=1)) if len(a_) > 1 else 0.0)

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
            rs, vs, fc, tgt = accumulate_radial(str(r_dir / "frames"), n, s_edges, idx_target, t_min=a.t_min, stride=a.stride)
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

        rho_at_target[n], rho_std_target[n] = _ms(rho_tgt_per_r)
        vel_at_target[n], vel_std_target[n] = _ms(vel_tgt_per_r)
        jin_at_target[n], jin_std_target[n] = _ms(jin_tgt_per_r)

    if not rho_profiles:
        print("No profiles computed."); return

    colors = cm.plasma(np.linspace(0.1, 0.9, max(len(n_vals), 1)))

    curve_defs = [
        ("tp4_rho_vs_S", r"$\langle\rho_f^{in}\rangle(S)$", rho_profiles),
        ("tp4_v_vs_S",   r"$|\langle v_f^{in}\rangle(S)|$",  vel_profiles),
        ("tp4_Jin_vs_S", r"$J_{in}(S)$",                     jin_profiles),
    ]
    sm = cm.ScalarMappable(cmap="plasma",
                           norm=plt.Normalize(vmin=min(n_vals), vmax=max(n_vals)))
    sm.set_array([])
    for fname, ylabel, profiles in curve_defs:
        fig, ax = plt.subplots(figsize=(8, 5))
        for i, n in enumerate(n_vals):
            if n not in profiles:
                continue
            ax.plot(s_centres, profiles[n], lw=2, color=colors[i], alpha=0.8)
        ax.set_xlabel("S [m]", fontsize=13)
        ax.set_ylabel(ylabel, fontsize=13)
        ax.set_title(f"TP4 – {ylabel}", fontsize=13)
        fig.colorbar(sm, ax=ax, label="N")
        ax.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        out_path = os.path.join(img_dir, f"{fname}.png")
        plt.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Saved → {out_path}")

    # Zoom detail of Jin(S) in S=[1.5, 5] m as required by rubric 1.3
    if jin_profiles:
        s_zoom_mask = (s_centres >= 1.5) & (s_centres <= 5.0)
        fig_z, ax_z = plt.subplots(figsize=(7, 5))
        for i, n in enumerate(n_vals):
            if n not in jin_profiles:
                continue
            ax_z.plot(s_centres[s_zoom_mask], jin_profiles[n][s_zoom_mask],
                      lw=2, color=colors[i], alpha=0.8)
        ax_z.set_xlabel("S [m]", fontsize=13)
        ax_z.set_ylabel(r"$J_{in}(S)$", fontsize=13)
        ax_z.set_title(r"TP4 – $J_{in}(S)$ detalle $S \in [1.5, 5]$ m", fontsize=13)
        ax_z.set_xlim(1.5, 5.0)
        fig_z.colorbar(sm, ax=ax_z, label="N")
        ax_z.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        out_z = os.path.join(img_dir, "tp4_Jin_vs_S_zoom.png")
        plt.savefig(out_z, dpi=150)
        plt.close(fig_z)
        print(f"Saved → {out_z}")

    # ── TP3 Jin at target ─────────────────────────────────────────────────────
    tp3_n_plot = []
    tp3_jin_at_target = {}
    tp3_jin_std_target = {}
    if a.tp3_bin:
        tp3_rad_root = os.path.join(os.path.abspath(a.tp3_bin), "radial")
        if os.path.isdir(tp3_rad_root):
            tp3_n_dirs = sorted(
                (d for d in Path(tp3_rad_root).iterdir()
                 if d.is_dir() and re.match(r"N\d+$", d.name)),
                key=lambda d: int(d.name[1:])
            )
            for n_dir in tp3_n_dirs:
                n3 = int(n_dir.name[1:])
                r_dirs3 = sorted(
                    d for d in n_dir.iterdir()
                    if d.is_dir() and (d / "frames").is_dir()
                )
                jin_tgt3 = []
                for r_dir in r_dirs3:
                    _, _, fc3, tgt3 = accumulate_radial(
                        str(r_dir / "frames"), n3, s_edges, idx_target, t_min=0.0, stride=a.stride)
                    if fc3 == 0 or not tgt3:
                        continue
                    tgt_arr3 = np.array(tgt3)
                    jin_tgt3.append(float(np.mean(tgt_arr3[:, 2])))
                if jin_tgt3:
                    tp3_jin_at_target[n3], tp3_jin_std_target[n3] = _ms(jin_tgt3)
                    tp3_n_plot.append(n3)
            print(f"TP3: Jin computed for N = {tp3_n_plot}")

    # vs-N plots at S~S_TARGET
    n_plot = [n for n in n_vals_target if n in jin_at_target]
    if n_plot:
        n_arr = np.array(n_plot)

        # Combined rho + v (dual y-axis)
        fig_rv, ax_rho = plt.subplots(figsize=(7, 5))
        ax_vel = ax_rho.twinx()
        ax_rho.errorbar(n_arr, [rho_at_target[n] for n in n_plot],
                        yerr=[rho_std_target[n] for n in n_plot],
                        fmt="o-", lw=2, color="#3498db", capsize=5, elinewidth=1.5,
                        label=r"$\langle\rho_f^{in}\rangle$")
        ax_vel.errorbar(n_arr, [vel_at_target[n] for n in n_plot],
                        yerr=[vel_std_target[n] for n in n_plot],
                        fmt="s--", lw=2, color="#2ecc71", capsize=5, elinewidth=1.5,
                        label=r"$|\langle v_f^{in}\rangle|$")
        ax_rho.set_xlabel("N", fontsize=13)
        ax_rho.set_ylabel(r"$\langle\rho_f^{in}\rangle\ (S \approx 2\,\mathrm{m})$",
                          fontsize=13, color="#3498db")
        ax_vel.set_ylabel(r"$|\langle v_f^{in}\rangle|\ (S \approx 2\,\mathrm{m})$",
                          fontsize=13, color="#2ecc71")
        ax_rho.tick_params(axis="y", labelcolor="#3498db")
        ax_vel.tick_params(axis="y", labelcolor="#2ecc71")
        lines1, labels1 = ax_rho.get_legend_handles_labels()
        lines2, labels2 = ax_vel.get_legend_handles_labels()
        ax_rho.legend(lines1 + lines2, labels1 + labels2, fontsize=11)
        ax_rho.set_title(r"TP4 – $\langle\rho_f^{in}\rangle$ y $|\langle v_f^{in}\rangle|$ vs $N$",
                         fontsize=13)
        ax_rho.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        out_rv = os.path.join(img_dir, "tp4_rho_v_vs_N.png")
        plt.savefig(out_rv, dpi=150)
        plt.close(fig_rv)
        print(f"Saved → {out_rv}")

        # Jin(N): TP4 vs TP3
        fig_j, ax_j = plt.subplots(figsize=(7, 5))
        ax_j.errorbar(n_arr, [jin_at_target[n] for n in n_plot],
                      yerr=[jin_std_target[n] for n in n_plot],
                      fmt="o-", lw=2, color="#e74c3c", capsize=5, elinewidth=1.5,
                      label="TP4 – Time-Driven")
        if tp3_n_plot:
            tp3_n_arr = np.array(tp3_n_plot)
            ax_j.errorbar(tp3_n_arr,
                          [tp3_jin_at_target[n] for n in tp3_n_plot],
                          yerr=[tp3_jin_std_target[n] for n in tp3_n_plot],
                          fmt="s--", lw=2, color="#2c3e50", capsize=5, elinewidth=1.5,
                          label="TP3 – Event-Driven")
        ax_j.set_xlabel("N", fontsize=13)
        ax_j.set_ylabel(r"$J_{in}(S \approx 2\,\mathrm{m})$", fontsize=13)
        ax_j.set_title(r"TP4 vs TP3 – $J_{in}$ vs $N$", fontsize=13)
        ax_j.legend(fontsize=11)
        ax_j.grid(True, ls="--", alpha=0.4)
        plt.tight_layout()
        out_j = os.path.join(img_dir, "tp4_Jin_vs_N.png")
        plt.savefig(out_j, dpi=150)
        plt.close(fig_j)
        print(f"Saved → {out_j}")


if __name__ == "__main__":
    main()
