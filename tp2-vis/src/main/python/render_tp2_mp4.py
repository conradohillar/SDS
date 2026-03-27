import argparse
import os
import math
import time
from dataclasses import dataclass


def _default_bin_dir() -> str:
    cwd = os.path.abspath(os.getcwd())
    cand = os.path.join(cwd, "tp2-bin")
    if os.path.isdir(cand):
        return cand
    return os.path.abspath(os.path.join(cwd, "..", "tp2-bin"))


@dataclass
class StaticData:
    n: int
    l: float
    radii: "list[float]"
    props: "list[float]"


@dataclass
class DynamicFrame:
    t: float
    x: "list[float]"
    y: "list[float]"
    vx: "list[float]"
    vy: "list[float]"


def parse_static(path: str) -> StaticData:
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    n = int(lines[0])
    l = float(lines[1])
    radii = [0.0] * n
    props = [0.0] * n
    for i in range(n):
        parts = lines[2 + i].split()
        radii[i] = float(parts[0])
        if len(parts) > 1:
            props[i] = float(parts[1])
    return StaticData(n=n, l=l, radii=radii, props=props)


def parse_dynamic_single_frame(path: str, n: int) -> DynamicFrame:
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    if not lines:
        raise ValueError("dynamic frame file is empty")
    t = float(lines[0].split()[0])
    if len(lines) < 1 + n:
        raise ValueError(f"frame has {len(lines) - 1} particles, expected {n}")

    x = [0.0] * n
    y = [0.0] * n
    vx = [0.0] * n
    vy = [0.0] * n
    for i in range(n):
        px, py, pvx, pvy = map(float, lines[1 + i].split())
        x[i] = px
        y[i] = py
        vx[i] = pvx
        vy[i] = pvy
    return DynamicFrame(t=t, x=x, y=y, vx=vx, vy=vy)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render TP2 tp2-bin frames into an MP4 video.")
    parser.add_argument("--bin", default=_default_bin_dir(), help="Directory containing static.txt and frames/")
    parser.add_argument("--output", default=None, help="Output mp4 path (default: tp2.mp4 in --bin)")
    parser.add_argument("--fps", type=float, default=30.0, help="Video frames per second")
    parser.add_argument("--macro-block-size", type=int, default=16,
                        help="H.264 macro block size used by the encoder (default: 16). "
                             "Use 1 to avoid resizing but compatibility may be worse.")
    parser.add_argument("--arrow-len", type=float, default=0.35, help="Arrow length (direction only)")
    parser.add_argument("--eta", type=float, default=None, help="Noise amplitude to show in the title (optional)")
    parser.add_argument("--leader-id", type=int, default=None,
                        help="Highlight leader particle (1-based id). Use 1 when sim was run with a leader.")
    args = parser.parse_args()

    bin_dir = os.path.abspath(args.bin)
    static_path = os.path.join(bin_dir, "static.txt")
    frames_dir = os.path.join(bin_dir, "frames")

    if not os.path.isdir(frames_dir):
        raise SystemExit(f"No frames directory found: {frames_dir}")
    if not os.path.exists(static_path):
        raise SystemExit(f"No static file found: {static_path}")

    out_path = args.output or os.path.join(bin_dir, "tp2.mp4")

    # Local imports (keeps the script nicer in environments where deps are absent).
    try:
        import numpy as np
    except ModuleNotFoundError as e:
        raise SystemExit("numpy is required. Install it with: pip install numpy") from e

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.colors import to_rgba
    except ModuleNotFoundError as e:
        raise SystemExit("matplotlib is required. Install it with: pip install matplotlib") from e

    try:
        import imageio.v2 as imageio
    except ModuleNotFoundError:
        try:
            import imageio
        except ModuleNotFoundError as e:
            raise SystemExit("imageio is required. Install it with: pip install imageio") from e
        imageio = imageio

    # Import-quality relies on ffmpeg; message if missing.
    try:
        writer = imageio.get_writer(
            out_path,
            fps=float(args.fps),
            codec="libx264",
            quality=8,
            macro_block_size=int(args.macro_block_size),
        )
    except Exception as e:
        raise SystemExit(
            "Failed to create MP4 writer. Install ffmpeg support, e.g. `pip install imageio-ffmpeg` "
            "and ensure ffmpeg is available on PATH."
        ) from e

    try:
        sd = parse_static(static_path)

        frame_files = sorted(
            [
                os.path.join(frames_dir, f)
                for f in os.listdir(frames_dir)
                if f.startswith("frame_") and f.endswith(".txt")
            ]
        )
        if not frame_files:
            raise SystemExit(f"No frame_*.txt files found in {frames_dir}")

        leader_idx = (args.leader_id - 1) if args.leader_id is not None and 1 <= args.leader_id <= sd.n else None
        # Leader should stand out on a white background without being pure black.
        leader_rgba = to_rgba("#444444")  # dark gray
        leader_scale = 1.5  # 50% larger arrow + leader dot
        scatter_alphas = np.full(sd.n, 0.15, dtype=float)
        if leader_idx is not None:
            scatter_alphas[leader_idx] = 0.9

        def angles_to_colors(vx_arr: np.ndarray, vy_arr: np.ndarray) -> np.ndarray:
            ang = np.arctan2(vy_arr, vx_arr)
            norm = (ang + math.pi) / (2.0 * math.pi)
            return plt.cm.hsv(norm)

        def direction_vectors(vx_arr: np.ndarray, vy_arr: np.ndarray, arrow_len: float):
            speed = np.sqrt(vx_arr * vx_arr + vy_arr * vy_arr)
            with np.errstate(divide="ignore", invalid="ignore"):
                ux = np.where(speed > 0, vx_arr / speed, 0.0)
                uy = np.where(speed > 0, vy_arr / speed, 0.0)
            return ux * arrow_len, uy * arrow_len

        def compute_polarization(vx_arr: np.ndarray, vy_arr: np.ndarray) -> float:
            """
            Polarization P(t) = | (1/N) * sum_i v_i / |v_i| |.
            Returns a value in [0, 1].
            """
            speed = np.sqrt(vx_arr * vx_arr + vy_arr * vy_arr)
            with np.errstate(divide="ignore", invalid="ignore"):
                ux = np.where(speed > 0, vx_arr / speed, 0.0)
                uy = np.where(speed > 0, vy_arr / speed, 0.0)
            sx = float(np.sum(ux) / len(vx_arr))
            sy = float(np.sum(uy) / len(vy_arr))
            return float(np.sqrt(sx * sx + sy * sy))

        # Preload frames (so we can compute polarization and render consistently).
        frames = [parse_dynamic_single_frame(p, sd.n) for p in frame_files]
        frame_count = len(frames)
        steps = np.arange(frame_count, dtype=int)
        pol_series = np.array([compute_polarization(np.array(df.vx, dtype=float),
                                                     np.array(df.vy, dtype=float))
                                for df in frames], dtype=float)

        # Setup figure (two panels: arrows left, polarization right).
        fig, (ax, ax_pol) = plt.subplots(
            1, 2,
            figsize=(12, 6.8),
            gridspec_kw={"width_ratios": [3.2, 1.6]},
        )
        # White background theme + dark text for video export.
        bg = "#ffffff"
        fg = "#111111"
        muted = "#444444"
        grid = "#d0d7de"
        spine_color = "#6e7781"

        fig.patch.set_facecolor(bg)
        ax.set_facecolor(bg)
        ax_pol.set_facecolor(bg)
        ax.set_xlim(0, sd.l)
        ax.set_ylim(0, sd.l)
        ax.set_aspect("equal")
        ax.tick_params(colors=muted)
        for sp in ax.spines.values():
            sp.set_edgecolor(spine_color)
        ax_pol.tick_params(colors=muted)
        for sp in ax_pol.spines.values():
            sp.set_edgecolor(spine_color)

        boundary = patches.Rectangle(
            (0, 0), sd.l, sd.l,
            linewidth=1.5, edgecolor=spine_color, facecolor="none", zorder=1
        )
        ax.add_patch(boundary)

        # Init from first frame.
        f0 = frames[0]
        x = np.array(f0.x, dtype=float)
        y = np.array(f0.y, dtype=float)
        vx = np.array(f0.vx, dtype=float)
        vy = np.array(f0.vy, dtype=float)

        u_vis, v_vis = direction_vectors(vx, vy, args.arrow_len)
        if leader_idx is not None:
            u_vis[leader_idx] *= leader_scale
            v_vis[leader_idx] *= leader_scale
        qcols = angles_to_colors(vx, vy)
        if leader_idx is not None:
            qcols[leader_idx] = leader_rgba
        scols = qcols.copy()
        scols[:, 3] = scatter_alphas

        quiv = ax.quiver(
            x, y, u_vis, v_vis,
            angles="xy", scale_units="xy", scale=1.0,
            color=qcols,
            width=0.004,
            headlength=4.5,
            headaxislength=4.0,
            zorder=2,
        )
        base_dot_size = 6.0
        scatter_sizes = np.full(sd.n, base_dot_size, dtype=float)
        if leader_idx is not None:
            scatter_sizes[leader_idx] = base_dot_size * leader_scale
        pts = ax.scatter(x, y, s=scatter_sizes, c=scols, zorder=1.5)

        eta_suffix = f" eta={args.eta:.3f}" if args.eta is not None else ""
        title = ax.set_title(
            f"TP2 Off-Lattice — frame=1/{frame_count} t={f0.t:.2f} N={sd.n} L={sd.l}{eta_suffix}",
            color=fg, fontsize=12, pad=12
        )

        # Polarization plot (va vs step).
        ax_pol.set_title("Polarización vs tiempo", color=fg, fontsize=11, pad=10)
        ax_pol.set_xlabel("tiempo (step)", color=muted)
        ax_pol.set_ylabel(r"polarización ($\mathrm{v}_a$)", color=muted)
        ax_pol.set_xlim(0, max(0, frame_count - 1))
        ax_pol.set_ylim(0.0, 1.0)
        ax_pol.grid(True, color=grid, alpha=0.9, linewidth=0.8)

        pol_line, = ax_pol.plot(
            steps, pol_series,
            color="#0969da",
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

        render_start = time.perf_counter()

        for idx in range(frame_count):
            df = frames[idx]
            x = np.array(df.x, dtype=float)
            y = np.array(df.y, dtype=float)
            vx = np.array(df.vx, dtype=float)
            vy = np.array(df.vy, dtype=float)

            quiv.set_offsets(np.c_[x, y])
            u_vis, v_vis = direction_vectors(vx, vy, args.arrow_len)
            if leader_idx is not None:
                u_vis[leader_idx] *= leader_scale
                v_vis[leader_idx] *= leader_scale
            quiv.set_UVC(u_vis, v_vis)

            qcols = angles_to_colors(vx, vy)
            if leader_idx is not None:
                qcols[leader_idx] = leader_rgba
            quiv.set_color(qcols)

            scols = qcols.copy()
            scols[:, 3] = scatter_alphas

            pts.set_offsets(np.c_[x, y])
            pts.set_facecolors(scols)

            title.set_text(
                f"step={idx + 1}/{frame_count} N={sd.n} L={sd.l}{eta_suffix}"
            )

            pol_marker.set_data([steps[idx]], [pol_series[idx]])
            pol_vline.set_xdata([steps[idx], steps[idx]])

            fig.canvas.draw()
            # Convert canvas buffer -> ndarray for imageio.
            # Matplotlib commonly stores RGBA (4 bytes/pixel); we drop alpha.
            buf = np.asarray(fig.canvas.buffer_rgba())  # shape: (h, w, 4)
            frame_img = buf[..., :3]  # RGB
            writer.append_data(frame_img)

        render_end = time.perf_counter()
    finally:
        try:
            writer.close()
        except Exception:
            pass

    try:
        plt.close("all")
    except Exception:
        pass

    print(f"MP4 written to: {out_path}")
    print(f"Total MP4 rendering time: {(render_end - render_start):.3f} s")


if __name__ == "__main__":
    main()

