#!/usr/bin/env python3
"""
TP5 Sistema 3 – Render animation to MP4.

Usage:
    python3 render_tp5_mp4.py [--bin PATH] [--mode quiral|random]
                              [--n N] [--r R] [--fps N] [--skip-time T]
                              [--output PATH]
"""
import argparse, os, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation, FFMpegWriter


def _default_bin():
    s = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp5-bin"))


def parse_metadata(path):
    meta = {}
    with open(path) as f:
        for line in f:
            p = line.strip().split()
            if len(p) == 2:
                try:    meta[p[0]] = float(p[1])
                except: meta[p[0]] = p[1]
    return meta


def parse_frame(path, n):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    t = float(lines[0])
    x=np.empty(n); y=np.empty(n); vx=np.empty(n); vy=np.empty(n)
    alpha=np.empty(n); sigma=np.empty(n, dtype=int)
    for i in range(n):
        p = lines[1+i].split()
        x[i]=float(p[0]); y[i]=float(p[1]); vx[i]=float(p[2]); vy[i]=float(p[3])
        alpha[i]=float(p[4]); sigma[i]=int(p[5])
    return t, x, y, vx, vy, alpha, sigma


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin",        default=None)
    ap.add_argument("--mode",       default="quiral", choices=["quiral","random"])
    ap.add_argument("--n",          type=int,   default=20)
    ap.add_argument("--r",          type=int,   default=0)
    ap.add_argument("--speed",      type=float, default=1.0,
                    help="Simulation seconds per animation second (default 1.0 = real time)")
    ap.add_argument("--fps",        type=int,   default=None,
                    help="Override output fps (default: derived from --speed and dt2)")
    ap.add_argument("--skip-time",  type=float, default=0.0)
    ap.add_argument("--arrow-len",  type=float, default=0.75,
                    help="Arrow length as fraction of R_P (default 0.75)")
    ap.add_argument("--output",     default=None)
    a = ap.parse_args()

    bin_root = os.path.abspath(a.bin) if a.bin else _default_bin()
    run_dir  = os.path.join(bin_root, "runs", a.mode, f"N{a.n}", f"r{a.r}")
    meta     = parse_metadata(os.path.join(run_dir, "metadata.txt"))
    N   = int(meta["N"])
    R   = float(meta.get("R", 10.0))
    R_P = float(meta.get("r_p", 1.6))
    mode= meta.get("mode", a.mode)

    frames_dir = os.path.join(run_dir, "frames")
    files = sorted(f for f in os.listdir(frames_dir) if re.match(r"frame_\d+\.txt$", f))
    frames = []
    for fname in files:
        fr = parse_frame(os.path.join(frames_dir, fname), N)
        if fr[0] >= a.skip_time:
            frames.append(fr)
    dt2 = frames[1][0] - frames[0][0] if len(frames) > 1 else 0.1
    fps = a.fps if a.fps is not None else max(1, round(a.speed / dt2))
    print(f"Rendering {len(frames)} frames  N={N}  mode={mode}  dt2={dt2:.3f}s  fps={fps}")

    C_POS = "#e74c3c"; C_NEG = "#3498db"; C_WALL = "#ecf0f1"; C_BG = "#1a1a2e"
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_aspect("equal"); pad = 1.5
    ax.set_xlim(-R-pad, R+pad); ax.set_ylim(-R-pad, R+pad)
    ax.set_facecolor(C_BG); fig.patch.set_facecolor(C_BG); ax.axis("off")
    ax.add_patch(plt.Circle((0,0), R, color=C_WALL, fill=False, lw=2, zorder=1))
    circles = [plt.Circle((0,0), R_P, color=C_POS, zorder=3) for _ in range(N)]
    for c in circles: ax.add_patch(c)
    display_len = a.arrow_len * R_P

    quiv = ax.quiver(np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N),
                     color="#bdc3c7", alpha=0.6, scale=1.0,
                     scale_units="xy", angles="xy", width=0.004, zorder=4)
    time_txt = ax.text(0.02, 0.96, "", transform=ax.transAxes, color="white",
                       fontsize=14, va="top", family="monospace", fontweight="bold")
    ax.set_title(f"TP5 Sistema 3 – {mode}  N={N}", color="white", pad=6, fontsize=13)

    def update(idx):
        t, x, y, vx_f, vy_f, alp, sig = frames[idx]
        for i, c in enumerate(circles):
            c.center = (x[i], y[i])
            c.set_color(C_POS if sig[i] > 0 else C_NEG)
        speeds = np.hypot(vx_f, vy_f)
        speeds = np.where(speeds > 0, speeds, 1.0)
        quiv.set_offsets(np.c_[x, y])
        quiv.set_UVC(vx_f / speeds * display_len, vy_f / speeds * display_len)
        time_txt.set_text(f"t = {t:.1f} s")
        return circles + [quiv, time_txt]

    ani = FuncAnimation(fig, update, frames=len(frames), blit=True)
    out = a.output or os.path.join(bin_root, "animations", f"tp5_{mode}_N{N}_r{a.r}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    writer = FFMpegWriter(fps=fps, bitrate=2000)
    ani.save(out, writer=writer, dpi=120)
    plt.close(fig)
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
