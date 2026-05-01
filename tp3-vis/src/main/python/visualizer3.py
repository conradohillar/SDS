#!/usr/bin/env python3
"""
Interactive animation for TP3 Sistema 1 – Event-Driven MD in a circular enclosure.

Reads frames from <bin>/frames/frame_NNNNN.txt and metadata from <bin>/metadata.txt.
Particles are coloured green (fresh) or purple (used).

Usage:
    python3 visualizer3.py [--bin PATH] [--fps N] [--arrow-len F]
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

# Colours
C_FRESH  = "#2ecc71"   # green
C_USED   = "#9b59b6"   # purple
C_WALL   = "#ecf0f1"   # light grey border
C_OBS    = "#e74c3c"   # red central obstacle
C_BG     = "#1a1a2e"   # dark background
C_ARROW  = "#bdc3c7"   # arrow colour


# ── I/O helpers ───────────────────────────────────────────────────────────────

def parse_metadata(path: str) -> dict:
    meta = {}
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                try:
                    meta[parts[0]] = float(parts[1])
                except ValueError:
                    meta[parts[0]] = parts[1]
    return meta


def parse_frame(path: str, n: int):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    t  = float(lines[0])
    x  = np.empty(n); y  = np.empty(n)
    pvx = np.empty(n); pvy = np.empty(n)
    st  = np.empty(n, dtype=int)
    for i in range(n):
        parts = lines[1 + i].split()
        x[i]   = float(parts[0]); y[i]   = float(parts[1])
        pvx[i] = float(parts[2]); pvy[i] = float(parts[3])
        st[i]  = int(parts[4])
    return t, x, y, pvx, pvy, st


def load_frames(frames_dir: str, n: int, skip_time: float = 0.0):
    files = sorted(f for f in os.listdir(frames_dir) if re.match(r"frame_\d+\.txt$", f))
    frames = [parse_frame(os.path.join(frames_dir, f), n) for f in files]
    return [fr for fr in frames if fr[0] >= skip_time]


# ── Animation ─────────────────────────────────────────────────────────────────

def animate(bin_dir: str, fps: float, arrow_len: float, skip_time: float = 0.0):
    meta = parse_metadata(os.path.join(bin_dir, "metadata.txt"))
    N        = int(meta["N"])
    R_domain = float(meta["R_domain"])
    R_obs    = float(meta["R_obstacle"])
    R_part   = float(meta["R_particle"])

    frames_dir = os.path.join(bin_dir, "frames")
    frames = load_frames(frames_dir, N, skip_time)
    if not frames:
        print(f"No frame files found in {frames_dir}")
        return

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_aspect("equal")
    pad = 2
    ax.set_xlim(-R_domain - pad, R_domain + pad)
    ax.set_ylim(-R_domain - pad, R_domain + pad)
    ax.set_facecolor(C_BG)
    fig.patch.set_facecolor(C_BG)
    ax.axis("off")

    # Static geometry
    wall = plt.Circle((0, 0), R_domain, color=C_WALL, fill=False, lw=2, zorder=1)
    obs  = plt.Circle((0, 0), R_obs,    color=C_OBS,  fill=True,  zorder=5)
    ax.add_patch(wall)
    ax.add_patch(obs)

    # Particle circles
    circles = [plt.Circle((0, 0), R_part, color=C_FRESH, zorder=3) for _ in range(N)]
    for c in circles:
        ax.add_patch(c)

    # Velocity arrows
    quiv = ax.quiver(
        np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N),
        color=C_ARROW, alpha=0.6, scale=1 / arrow_len, scale_units="xy",
        angles="xy", width=0.004, zorder=4
    )

    time_txt = ax.text(
        0.02, 0.97, "", transform=ax.transAxes,
        color="white", fontsize=11, va="top", family="monospace"
    )
    counter_txt = ax.text(
        0.02, 0.92, "", transform=ax.transAxes,
        color="white", fontsize=10, va="top"
    )

    # Legend
    legend_elems = [
        mpatches.Patch(color=C_FRESH, label="Fresh"),
        mpatches.Patch(color=C_USED,  label="Used"),
        mpatches.Patch(color=C_OBS,   label="Obstacle"),
    ]
    ax.legend(handles=legend_elems, loc="upper right",
              facecolor="#2c2c2c", labelcolor="white", fontsize=9)

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

    anim = FuncAnimation(
        fig, update, frames=len(frames),
        interval=1000 / fps, blit=False
    )
    plt.tight_layout()
    plt.show()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _default_bin() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.normpath(os.path.join(script_dir, "..", "..", "..", "..", "tp3-bin"))
    return cand if os.path.isdir(cand) else os.path.join(os.getcwd(), "tp3-bin")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TP3 visualizer – circular EDM")
    ap.add_argument("--bin",       default=None,  help="Path to tp3-bin directory")
    ap.add_argument("--fps",       type=float, default=30,  help="Animation FPS")
    ap.add_argument("--arrow-len",  type=float, default=1.5, help="Arrow scaling factor")
    ap.add_argument("--skip-time",  type=float, default=0.0, help="Skip frames with t < this value [s]")
    a = ap.parse_args()

    bin_dir = os.path.abspath(a.bin) if a.bin else _default_bin()
    animate(bin_dir, a.fps, a.arrow_len, a.skip_time)
