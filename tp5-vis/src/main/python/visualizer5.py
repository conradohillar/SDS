#!/usr/bin/env python3
"""
TP5 Sistema 3 – Interactive animation for active matter simulation.

Reads frames from <bin>/runs/<mode>/N<n>/r<r>/frames/frame_*.txt and metadata.txt.
Particles are coloured by chirality sign (σ = +1 → red, σ = -1 → blue).

Usage:
    python3 visualizer5.py [--bin PATH] [--mode quiral|random]
                           [--n N] [--r REALIZATION] [--fps N]
                           [--skip-time T]
"""
import argparse, os, re
import numpy as np
import matplotlib
try:
    matplotlib.use("TkAgg")
except Exception:
    pass
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation


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
    x = np.empty(n); y = np.empty(n)
    vx= np.empty(n); vy= np.empty(n)
    alpha = np.empty(n); sigma = np.empty(n, dtype=int)
    for i in range(n):
        p = lines[1+i].split()
        x[i]=float(p[0]); y[i]=float(p[1])
        vx[i]=float(p[2]); vy[i]=float(p[3])
        alpha[i]=float(p[4]); sigma[i]=int(p[5])
    return t, x, y, vx, vy, alpha, sigma


def load_frames(frames_dir, n, skip_time=0.0):
    files = sorted(f for f in os.listdir(frames_dir) if re.match(r"frame_\d+\.txt$", f))
    frames = []
    for fname in files:
        fr = parse_frame(os.path.join(frames_dir, fname), n)
        if fr[0] >= skip_time:
            frames.append(fr)
    return frames


def animate(run_dir, fps, arrow_len, skip_time=0.0):
    meta_path = os.path.join(run_dir, "metadata.txt")
    if not os.path.exists(meta_path):
        print(f"ERROR: {meta_path} not found"); return
    meta  = parse_metadata(meta_path)
    N     = int(meta["N"])
    R     = float(meta.get("R",   10.0))
    R_P   = float(meta.get("r_p", 1.6))
    mode  = meta.get("mode", "?")

    frames_dir = os.path.join(run_dir, "frames")
    frames = load_frames(frames_dir, N, skip_time)
    if not frames:
        print(f"No frames found in {frames_dir}"); return
    print(f"Loaded {len(frames)} frames  (N={N}, mode={mode}, R={R})")

    C_POS  = "#e74c3c"   # σ = +1 (quiral / CW)
    C_NEG  = "#3498db"   # σ = -1 (CCW)
    C_WALL = "#ecf0f1"
    C_BG   = "#1a1a2e"
    C_ARR  = "#bdc3c7"

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_aspect("equal"); pad = 1.5
    ax.set_xlim(-R-pad, R+pad); ax.set_ylim(-R-pad, R+pad)
    ax.set_facecolor(C_BG); fig.patch.set_facecolor(C_BG); ax.axis("off")
    ax.add_patch(plt.Circle((0,0), R, color=C_WALL, fill=False, lw=2, zorder=1))

    circles = [plt.Circle((0,0), R_P, color=C_POS, zorder=3) for _ in range(N)]
    for c in circles: ax.add_patch(c)

    quiv = ax.quiver(
        np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N),
        color=C_ARR, alpha=0.6, scale=1/arrow_len, scale_units="xy",
        angles="xy", width=0.004, zorder=4)

    time_txt = ax.text(0.02, 0.96, "", transform=ax.transAxes, color="white",
                       fontsize=14, va="top", family="monospace", fontweight="bold")
    ax.legend(handles=[
        mpatches.Patch(color=C_POS, label="σ = +1"),
        mpatches.Patch(color=C_NEG, label="σ = −1"),
    ], loc="upper right", facecolor="#2c2c2c", labelcolor="white",
       fontsize=12, handlelength=2)
    ax.set_title(f"TP5 Sistema 3 – {mode}  N={N}", color="white", pad=6, fontsize=13)

    def update(idx):
        t, x, y, vx_f, vy_f, alp, sig = frames[idx]
        for i, c in enumerate(circles):
            c.center = (x[i], y[i])
            c.set_color(C_POS if sig[i] > 0 else C_NEG)
        quiv.set_offsets(np.c_[x, y])
        quiv.set_UVC(vx_f*arrow_len, vy_f*arrow_len)
        time_txt.set_text(f"t = {t:.1f} s")
        return circles + [quiv, time_txt]

    ani = FuncAnimation(fig, update, frames=len(frames), interval=1000/fps, blit=True)
    plt.tight_layout()
    plt.show()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin",       default=None)
    ap.add_argument("--mode",      default="quiral", choices=["quiral","random"])
    ap.add_argument("--n",         type=int, default=20)
    ap.add_argument("--r",         type=int, default=0)
    ap.add_argument("--fps",       type=int, default=30)
    ap.add_argument("--arrow-len", type=float, default=0.5)
    ap.add_argument("--skip-time", type=float, default=0.0)
    a = ap.parse_args()

    bin_root = os.path.abspath(a.bin) if a.bin else _default_bin()
    run_dir  = os.path.join(bin_root, "runs", a.mode, f"N{a.n}", f"r{a.r}")
    if not os.path.isdir(run_dir):
        print(f"Run dir not found: {run_dir}"); return

    animate(run_dir, a.fps, a.arrow_len, a.skip_time)


if __name__ == "__main__":
    main()
