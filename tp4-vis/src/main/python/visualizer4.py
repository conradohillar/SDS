#!/usr/bin/env python3
"""
Interactive animation for TP4 Sistema 2 – Time-Driven MD in a circular enclosure.

Reads frames from <bin>/<run-id>/frames/frame_*.txt and metadata.txt.
Particles are coloured green (fresh) or purple (used).

Usage:
    python3 visualizer4.py [--bin PATH] [--run-id ID] [--fps N] [--arrow-len F] [--skip-time T]
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

C_FRESH = "#2ecc71"
C_USED  = "#9b59b6"
C_WALL  = "#ecf0f1"
C_OBS   = "#e74c3c"
C_BG    = "#1a1a2e"
C_ARROW = "#bdc3c7"


def parse_metadata(path):
    meta = {}
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                try:    meta[parts[0]] = float(parts[1])
                except: meta[parts[0]] = parts[1]
    return meta


def parse_frame(path, n):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    t   = float(lines[0])
    x   = np.empty(n); y   = np.empty(n)
    pvx = np.empty(n); pvy = np.empty(n)
    st  = np.empty(n, dtype=int)
    for i in range(n):
        p = lines[1 + i].split()
        x[i]=float(p[0]); y[i]=float(p[1])
        pvx[i]=float(p[2]); pvy[i]=float(p[3])
        st[i]=int(p[4])
    return t, x, y, pvx, pvy, st


def load_frames(frames_dir, n, skip_time=0.0):
    files = sorted(f for f in os.listdir(frames_dir) if re.match(r"frame_\d+\.txt$", f))
    frames = [parse_frame(os.path.join(frames_dir, f), n) for f in files]
    return [fr for fr in frames if fr[0] >= skip_time]


def animate(run_dir, fps, arrow_len, skip_time=0.0):
    meta_path = os.path.join(run_dir, "metadata.txt")
    if not os.path.exists(meta_path):
        print(f"ERROR: {meta_path} not found")
        return
    meta     = parse_metadata(meta_path)
    N        = int(meta["N"])
    R_domain = float(meta.get("R_DOMAIN",   40.0))
    R_obs    = float(meta.get("R_OBSTACLE",  1.0))
    R_part   = float(meta.get("R_PARTICLE",  1.0))

    frames_dir = os.path.join(run_dir, "frames")
    frames = load_frames(frames_dir, N, skip_time)
    if not frames:
        print(f"No frame files found in {frames_dir}")
        return

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_aspect("equal")
    pad = 2
    ax.set_xlim(-R_domain - pad, R_domain + pad)
    ax.set_ylim(-R_domain - pad, R_domain + pad)
    ax.set_facecolor(C_BG); fig.patch.set_facecolor(C_BG); ax.axis("off")

    ax.add_patch(plt.Circle((0, 0), R_domain, color=C_WALL, fill=False, lw=2, zorder=1))
    ax.add_patch(plt.Circle((0, 0), R_obs,    color=C_OBS,  fill=True,  zorder=5))

    circles = [plt.Circle((0, 0), R_part, color=C_FRESH, zorder=3) for _ in range(N)]
    for c in circles:
        ax.add_patch(c)

    quiv = ax.quiver(
        np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N),
        color=C_ARROW, alpha=0.6, scale=1 / arrow_len, scale_units="xy",
        angles="xy", width=0.004, zorder=4
    )

    time_txt    = ax.text(0.02, 0.97, "", transform=ax.transAxes, color="white",
                          fontsize=11, va="top", family="monospace")
    counter_txt = ax.text(0.02, 0.92, "", transform=ax.transAxes, color="white",
                          fontsize=10, va="top")

    ax.legend(handles=[
        mpatches.Patch(color=C_FRESH, label="Fresh"),
        mpatches.Patch(color=C_USED,  label="Used"),
        mpatches.Patch(color=C_OBS,   label="Obstacle"),
    ], loc="upper right", facecolor="#2c2c2c", labelcolor="white", fontsize=9)

    def update(idx):
        t, x, y, pvx, pvy, st = frames[idx]
        n_used = int(np.sum(st))
        for i, c in enumerate(circles):
            c.center = (x[i], y[i])
            c.set_color(C_FRESH if st[i] == 0 else C_USED)
        quiv.set_offsets(np.c_[x, y])
        quiv.set_UVC(pvx * arrow_len, pvy * arrow_len)
        time_txt.set_text(f"t = {t:.3f} s")
        counter_txt.set_text(f"Used: {n_used}/{N}  ({100*n_used/N:.1f}%)")
        return circles + [quiv, time_txt, counter_txt]

    anim = FuncAnimation(fig, update, frames=len(frames), interval=1000 / fps, blit=False)
    plt.tight_layout()
    plt.show()


def _default_bin():
    s = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.normpath(os.path.join(s, "..", "..", "..", "..", "tp4-bin"))
    return cand if os.path.isdir(cand) else os.path.join(os.getcwd(), "tp4-bin")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TP4 visualizer – circular Time-Driven MD")
    ap.add_argument("--bin",       default=None,  help="Path to tp4-bin directory")
    ap.add_argument("--run-id",    default="default")
    ap.add_argument("--fps",       type=float, default=30)
    ap.add_argument("--arrow-len", type=float, default=1.5)
    ap.add_argument("--skip-time", type=float, default=0.0)
    a = ap.parse_args()

    bin_dir = os.path.abspath(a.bin) if a.bin else _default_bin()
    run_dir = os.path.join(bin_dir, a.run_id)
    animate(run_dir, a.fps, a.arrow_len, a.skip_time)
