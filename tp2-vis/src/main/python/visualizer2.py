import argparse
import math
import os
from dataclasses import dataclass

import matplotlib

# Try to match TP1 visualizer defaults, but don't hard-fail if Tk isn't available.
try:
    matplotlib.use("TkAgg")
except Exception:
    pass

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation
from matplotlib.colors import to_rgba
import numpy as np


@dataclass
class StaticData:
    n: int
    l: float
    radii: np.ndarray  # shape (n,)
    props: np.ndarray  # shape (n,)


@dataclass
class DynamicFrame:
    t: float
    x: np.ndarray  # shape (n,)
    y: np.ndarray  # shape (n,)
    vx: np.ndarray  # shape (n,)
    vy: np.ndarray  # shape (n,)


def _default_bin_dir() -> str:
    # Resolve relative to repo layout; robust to running from IDE or CLI.
    cwd = os.path.abspath(os.getcwd())
    cand = os.path.join(cwd, "tp2-bin")
    if os.path.isdir(cand):
        return cand
    return os.path.abspath(os.path.join(cwd, "..", "tp2-bin"))


def parse_static(path: str) -> StaticData:
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    n = int(lines[0])
    l = float(lines[1])

    radii = np.zeros(n, dtype=float)
    props = np.zeros(n, dtype=float)
    for i in range(n):
        parts = lines[2 + i].split()
        radii[i] = float(parts[0])
        if len(parts) > 1:
            props[i] = float(parts[1])
    return StaticData(n=n, l=l, radii=radii, props=props)


def parse_dynamic_single_frame(path: str, n: int) -> DynamicFrame:
    """
    Parses a single-frame dynamic.txt or frame_XXXXX.txt:
      t0
      x y vx vy
      ...
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    if not lines:
        raise ValueError("dynamic file is empty")

    t = float(lines[0].split()[0])
    if len(lines) < 1 + n:
        raise ValueError(f"dynamic file has {len(lines) - 1} particles, expected {n}")

    x = np.zeros(n, dtype=float)
    y = np.zeros(n, dtype=float)
    vx = np.zeros(n, dtype=float)
    vy = np.zeros(n, dtype=float)
    for i in range(n):
        px, py, pvx, pvy = map(float, lines[1 + i].split())
        x[i] = px
        y[i] = py
        vx[i] = pvx
        vy[i] = pvy
    return DynamicFrame(t=t, x=x, y=y, vx=vx, vy=vy)


def angles_to_colors(vx: np.ndarray, vy: np.ndarray) -> np.ndarray:
    # Map angle [-pi, pi] -> [0, 1] and use HSV colormap.
    ang = np.arctan2(vy, vx)
    norm = (ang + math.pi) / (2.0 * math.pi)
    return plt.cm.hsv(norm)


def direction_vectors(vx: np.ndarray, vy: np.ndarray, arrow_len: float) -> tuple[np.ndarray, np.ndarray]:
    # Normalize to show direction clearly (visual length is fixed), even if |v| is small.
    speed = np.sqrt(vx * vx + vy * vy)
    with np.errstate(divide="ignore", invalid="ignore"):
        ux = np.where(speed > 0, vx / speed, 0.0)
        uy = np.where(speed > 0, vy / speed, 0.0)
    return ux * arrow_len, uy * arrow_len


def compute_polarization(vx: np.ndarray, vy: np.ndarray) -> float:
    """
    Polarization P(t) = | (1/N) * sum_i v_i / |v_i| |.
    Returns a value in [0, 1].
    """
    speed = np.sqrt(vx * vx + vy * vy)
    with np.errstate(divide="ignore", invalid="ignore"):
        ux = np.where(speed > 0, vx / speed, 0.0)
        uy = np.where(speed > 0, vy / speed, 0.0)
    sx = float(np.sum(ux) / len(vx))
    sy = float(np.sum(uy) / len(vy))
    return float(np.sqrt(sx * sx + sy * sy))


def main() -> None:
    parser = argparse.ArgumentParser(description="TP2 Off-lattice (Vicsek) visualizer (frame-by-frame).")
    parser.add_argument("--bin", default=_default_bin_dir(), help="Directory containing static.txt and frames/")
    parser.add_argument("--static", default=None, help="Static file path (overrides --bin)")
    parser.add_argument("--frames-dir", default=None, help="Directory containing frame_XXXXX.txt files (defaults to bin/frames)")
    parser.add_argument("--fps", type=float, default=30.0, help="Target frames per second")
    parser.add_argument("--arrow-len", type=float, default=0.35,
                        help="Visual arrow length (in box units). Uses direction only, not speed magnitude.")
    parser.add_argument("--rho", type=float, default=None,
                        help="Particle density rho to show in the animation title (default: computed as N/L^2).")
    parser.add_argument("--eta", type=float, default=None,
                        help="Vicsek noise amplitude eta to show in the animation title (not stored in exported files). "
                             "If omitted, tries env var TP2_ETA.")
    parser.add_argument("--periodic", action=argparse.BooleanOptionalAction, default=True,
                        help="Apply periodic boundary conditions")
    parser.add_argument("--leader-id", type=int, default=None,
                        help="Highlight leader particle in white and larger (1-based id; use 1 when sim was run with a leader)")
    args = parser.parse_args()

    bin_dir = os.path.abspath(args.bin)
    static_path = args.static or os.path.join(bin_dir, "static.txt")
    frames_dir = args.frames_dir or os.path.join(bin_dir, "frames")

    sd = parse_static(static_path)
    # Simulation parameters:
    # - rho is derivable from exported N and L.
    # - eta isn't stored in exported files, so it's optional via CLI (or env var TP2_ETA).
    rho_value = args.rho if args.rho is not None else float(sd.n) / float(sd.l * sd.l)
    eta_value = args.eta
    if eta_value is None:
        eta_env = os.environ.get("TP2_ETA")
        if eta_env is not None and eta_env.strip():
            eta_value = float(eta_env)
    eta_str = "?" if eta_value is None else f"{eta_value:.5g}"
    frame_files = []
    if os.path.isdir(frames_dir):
        frame_files = sorted(
            [
                os.path.join(frames_dir, f)
                for f in os.listdir(frames_dir)
                if f.startswith("frame_") and f.endswith(".txt")
            ]
        )
    if not frame_files:
        raise SystemExit(f"No frame_*.txt files found in {frames_dir}")

    frames: list[DynamicFrame] = [parse_dynamic_single_frame(p, sd.n) for p in frame_files]
    frame_count = len(frames)

    # State (mutable) - start from first frame
    current = frames[0]
    x = current.x.copy()
    y = current.y.copy()
    vx = current.vx.copy()
    vy = current.vy.copy()

    # ---- Figure setup (inspired by tp1-vis visualizer.py) ----
    fig, (ax, ax_pol) = plt.subplots(
        1, 2,
        figsize=(12, 6.8),
        gridspec_kw={"width_ratios": [3.2, 1.6]},
    )
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax_pol.set_facecolor("#0d1117")

    ax.set_xlim(0, sd.l)
    ax.set_ylim(0, sd.l)
    ax.set_aspect("equal")
    ax.tick_params(colors="#8b949e")
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")

    ax_pol.tick_params(colors="#8b949e")
    for spine in ax_pol.spines.values():
        spine.set_edgecolor("#30363d")

    title = ax.set_title(
        f"TP2 Off-Lattice  —  frame=1/{frame_count}  t={current.t:.2f}  "
        f"N={sd.n}  L={sd.l}  rho={rho_value:.3g}  eta={eta_str}",
        color="#e6edf3",
        fontsize=12,
        pad=12,
    )

    boundary = patches.Rectangle(
        (0, 0), sd.l, sd.l,
        linewidth=1.5, edgecolor="#30363d",
        facecolor="none", zorder=1
    )
    ax.add_patch(boundary)

    leader_idx = (args.leader_id - 1) if args.leader_id is not None and 1 <= args.leader_id <= sd.n else None
    leader_rgba = to_rgba("#ffffff")
    leader_scale = 1.5  # 50% larger (direction arrow length and leader dot)

    scatter_alphas = np.full(sd.n, 0.15, dtype=float)
    if leader_idx is not None:
        scatter_alphas[leader_idx] = 0.9

    # Precompute polarization and colors for each frame.
    pol_series = np.array([compute_polarization(df.vx, df.vy) for df in frames], dtype=float)
    steps = np.arange(frame_count, dtype=int)

    frame_quiver_colors: list[np.ndarray] = []
    frame_scatter_colors: list[np.ndarray] = []
    for df in frames:
        qcols = angles_to_colors(df.vx, df.vy)
        if leader_idx is not None:
            qcols[leader_idx] = leader_rgba
        scols = qcols.copy()
        scols[:, 3] = scatter_alphas
        frame_quiver_colors.append(qcols)
        frame_scatter_colors.append(scols)

    # Draw as velocity vectors (as requested by TP2 statement).
    # Use direction-only vectors so arrows are clearly visible.
    u_vis, v_vis = direction_vectors(vx, vy, args.arrow_len)
    if leader_idx is not None:
        u_vis[leader_idx] *= leader_scale
        v_vis[leader_idx] *= leader_scale
    quiv = ax.quiver(
        x, y, u_vis, v_vis,
        angles="xy", scale_units="xy", scale=1.0,
        color=frame_quiver_colors[0],
        width=0.004,
        headlength=4.5,
        headaxislength=4.0,
        zorder=2,
    )

    # Tiny dots under arrows (and leader highlighted in white when --leader-id set).
    base_dot_size = 6
    scatter_sizes = np.full(sd.n, base_dot_size, dtype=float)
    if leader_idx is not None:
        scatter_sizes[leader_idx] = base_dot_size * leader_scale
    pts = ax.scatter(x, y, s=scatter_sizes, c=frame_scatter_colors[0], zorder=1.5)

    # ---- Polarization plot (va vs step) ----
    ax_pol.set_title("Polarizacion vs step", color="#e6edf3", fontsize=11, pad=10)
    ax_pol.set_xlabel("step", color="#8b949e")
    ax_pol.set_ylabel("va", color="#8b949e")
    ax_pol.set_xlim(0, max(0, frame_count - 1))
    ax_pol.set_ylim(0.0, 1.0)
    ax_pol.grid(True, color="#30363d", alpha=0.35, linewidth=0.8)

    pol_line, = ax_pol.plot(
        steps, pol_series,
        color="#58a6ff",
        linewidth=2,
    )
    pol_marker, = ax_pol.plot(
        [steps[0]], [pol_series[0]],
        marker="o",
        color="#2ea043",
        markersize=7,
        zorder=3,
    )
    pol_vline = ax_pol.axvline(steps[0], color="#8b949e", linewidth=1.2, alpha=0.75, zorder=2)

    # ---- Update loop (frame playback) ----
    interval_ms = int(max(1.0, 1000.0 / max(1e-9, args.fps)))

    def step(frame_idx: int):
        nonlocal x, y, vx, vy

        idx = frame_idx % frame_count
        df = frames[idx]
        x = df.x
        y = df.y
        vx = df.vx
        vy = df.vy

        quiv.set_offsets(np.c_[x, y])
        u_vis, v_vis = direction_vectors(vx, vy, args.arrow_len)
        if leader_idx is not None:
            u_vis[leader_idx] *= leader_scale
            v_vis[leader_idx] *= leader_scale
        quiv.set_UVC(u_vis, v_vis)
        quiv.set_color(frame_quiver_colors[idx])
        pts.set_offsets(np.c_[x, y])
        pts.set_facecolors(frame_scatter_colors[idx])

        title.set_text(
            f"TP2 Off-Lattice  —  frame={idx+1}/{frame_count}  t={df.t:.2f}  "
            f"N={sd.n}  L={sd.l}  rho={rho_value:.3g}  eta={eta_str}"
        )
        pol_marker.set_data([steps[idx]], [pol_series[idx]])
        pol_vline.set_xdata([steps[idx], steps[idx]])
        return quiv, pts, title, pol_marker, pol_vline

    # Keep a reference to the animation object; otherwise it can get GC'd and stop updating.
    _anim = FuncAnimation(fig, step, frames=frame_count, interval=interval_ms, blit=False)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
