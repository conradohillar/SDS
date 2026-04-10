#!/usr/bin/env python3
"""
Renders TP3 animation to MP4 (headless, no display required).

Usage:
    python3 render_tp3_mp4.py [--bin PATH] [--output out.mp4] [--fps N] [--arrow-len F]
                              [--macro-block-size N]
"""
import argparse, os, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation, FFMpegWriter

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
        p = lines[1+i].split()
        x[i]=float(p[0]); y[i]=float(p[1])
        pvx[i]=float(p[2]); pvy[i]=float(p[3])
        st[i]=int(p[4])
    return t, x, y, pvx, pvy, st


def load_frames(frames_dir, n):
    files = sorted(f for f in os.listdir(frames_dir) if re.match(r"frame_\d+\.txt$", f))
    return [parse_frame(os.path.join(frames_dir, f), n) for f in files]


def render(bin_dir, output, fps, arrow_len, macro_block_size):
    meta     = parse_metadata(os.path.join(bin_dir, "metadata.txt"))
    N        = int(meta["N"])
    R_domain = float(meta["R_domain"])
    R_obs    = float(meta["R_obstacle"])
    R_part   = float(meta["R_particle"])

    frames_dir = os.path.join(bin_dir, "frames")
    frames = load_frames(frames_dir, N)
    if not frames:
        print("No frames found"); return

    fig, ax = plt.subplots(figsize=(7, 7), dpi=120)
    ax.set_aspect("equal")
    pad = 2
    ax.set_xlim(-R_domain-pad, R_domain+pad)
    ax.set_ylim(-R_domain-pad, R_domain+pad)
    ax.set_facecolor(C_BG); fig.patch.set_facecolor(C_BG); ax.axis("off")

    ax.add_patch(plt.Circle((0,0), R_domain, color=C_WALL, fill=False, lw=2, zorder=1))
    ax.add_patch(plt.Circle((0,0), R_obs,    color=C_OBS,  fill=True,  zorder=5))

    circles = [plt.Circle((0,0), R_part, color=C_FRESH, zorder=3) for _ in range(N)]
    for c in circles: ax.add_patch(c)

    quiv = ax.quiver(np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N),
                     color=C_ARROW, alpha=0.6, scale=1/arrow_len, scale_units="xy",
                     angles="xy", width=0.004, zorder=4)

    time_txt    = ax.text(0.02, 0.97, "", transform=ax.transAxes, color="white", fontsize=11, va="top", family="monospace")
    counter_txt = ax.text(0.02, 0.92, "", transform=ax.transAxes, color="white", fontsize=10, va="top")
    ax.legend(handles=[mpatches.Patch(color=C_FRESH, label="Fresh"),
                        mpatches.Patch(color=C_USED,  label="Used")],
              loc="upper right", facecolor="#2c2c2c", labelcolor="white", fontsize=9)

    def update(idx):
        t, x, y, pvx, pvy, st = frames[idx]
        n_used = int(np.sum(st))
        for i, c in enumerate(circles):
            c.center = (x[i], y[i]); c.set_color(C_FRESH if st[i]==0 else C_USED)
        quiv.set_offsets(np.c_[x,y]); quiv.set_UVC(pvx*arrow_len, pvy*arrow_len)
        time_txt.set_text(f"t = {t:.3f} s")
        counter_txt.set_text(f"Used: {n_used}/{N}")
        return circles + [quiv, time_txt, counter_txt]

    anim = FuncAnimation(fig, update, frames=len(frames), interval=1000/fps, blit=False)
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    writer = FFMpegWriter(fps=fps, metadata={"title": "TP3 EDM"}, bitrate=2000,
                          extra_args=["-vf", f"scale=trunc(iw/{macro_block_size})*{macro_block_size}:trunc(ih/{macro_block_size})*{macro_block_size}",
                                      "-pix_fmt", "yuv420p"])
    print(f"Rendering {len(frames)} frames to {output} ...")
    anim.save(output, writer=writer)
    print("Done.")


def _default_bin():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.normpath(os.path.join(script_dir, "..", "..", "..", "..", "tp3-bin"))
    return cand if os.path.isdir(cand) else os.path.join(os.getcwd(), "tp3-bin")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin",              default=None)
    ap.add_argument("--output",           default="tp3-bin/animations/tp3.mp4")
    ap.add_argument("--fps",              type=float, default=30)
    ap.add_argument("--arrow-len",        type=float, default=1.5)
    ap.add_argument("--macro-block-size", type=int,   default=1)
    a = ap.parse_args()
    bin_dir = os.path.abspath(a.bin) if a.bin else _default_bin()
    render(bin_dir, a.output, a.fps, a.arrow_len, a.macro_block_size)
