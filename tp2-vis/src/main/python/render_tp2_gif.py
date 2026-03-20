import argparse
import os
import math
import shutil
import tempfile
import csv
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
    radii: "list[float]"  # kept for compatibility, but not used
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
    parser = argparse.ArgumentParser(description="Render TP2 tp2-bin frames into an animated GIF.")
    parser.add_argument("--bin", default=_default_bin_dir(), help="Directory containing static.txt and frames/")
    parser.add_argument("--output", default=None, help="Output GIF path (default: tp2.gif in --bin)")
    parser.add_argument("--fps", type=float, default=30.0, help="GIF playback frames per second")
    parser.add_argument("--arrow-len", type=float, default=0.35, help="Arrow length (direction only)")
    parser.add_argument("--eta", type=float, default=None,
                        help="Vicsek noise amplitude (only used for the title; not required)")
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

    out_path = args.output or os.path.join(bin_dir, "tp2.gif")

    # Local imports to keep the script import-friendly even if deps are missing.
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
        raise SystemExit(
            "matplotlib is required to render GIF. Install it with: pip install matplotlib"
        ) from e

    try:
        import imageio.v2 as imageio
    except ModuleNotFoundError:
        try:
            import imageio
        except ModuleNotFoundError as e:
            raise SystemExit("imageio is required. Install it with: pip install imageio") from e
        imageio = imageio

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
    leader_rgba = to_rgba("#ffffff")
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

    # Figure setup (close to visualizer2.py style).
    fig, ax = plt.subplots(figsize=(7.0, 7.0))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax.set_xlim(0, sd.l)
    ax.set_ylim(0, sd.l)
    ax.set_aspect("equal")
    ax.tick_params(colors="#8b949e")
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")

    boundary = patches.Rectangle((0, 0), sd.l, sd.l, linewidth=1.5, edgecolor="#30363d", facecolor="none", zorder=1)
    ax.add_patch(boundary)

    # Init from first frame.
    f0 = parse_dynamic_single_frame(frame_files[0], sd.n)
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
        f"TP2 Off-Lattice — frame=1/{len(frame_files)} t={f0.t:.2f} N={sd.n} L={sd.l}{eta_suffix}",
        color="#e6edf3", fontsize=12, pad=12
    )

    tmp_dir = tempfile.mkdtemp(prefix="tp2_frames_")
    png_paths: list[str] = []
    render_start = time.perf_counter()
    try:
        for idx, frame_path in enumerate(frame_files):
            df = parse_dynamic_single_frame(frame_path, sd.n)
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
                f"TP2 Off-Lattice — frame={idx + 1}/{len(frame_files)} t={df.t:.2f} N={sd.n} L={sd.l}{eta_suffix}"
            )

            fig.savefig(
                os.path.join(tmp_dir, f"frame_{idx:05d}.png"),
                facecolor=fig.get_facecolor(),
                dpi=120,
            )
            png_paths.append(os.path.join(tmp_dir, f"frame_{idx:05d}.png"))

        # Assemble GIF.
        # GIF delay is commonly quantized to 1/100s steps (centiseconds),
        # so we quantize explicitly to match the requested --fps as closely as possible.
        fps = float(args.fps)
        requested_duration_s = 1.0 / max(1e-9, fps)
        duration_cs = int(round(requested_duration_s * 100.0))  # centiseconds
        duration_cs = max(1, duration_cs)  # avoid 0 delay
        duration_s = duration_cs / 100.0
        effective_fps = 1.0 / duration_s

        images = [imageio.imread(p) for p in png_paths]
        writer = imageio.get_writer(out_path, mode="I", duration=duration_s)
        try:
            for im in images:
                writer.append_data(im)
        finally:
            writer.close()

        print(f"GIF frame delay: {duration_s:.4f} s (effective fps ~ {effective_fps:.3f})")
    finally:
        render_end = time.perf_counter()
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"GIF written to: {out_path}")
    print(f"Total GIF rendering time: {(render_end - render_start):.3f} s")

    # Probe actual stored frame delay (in ms) when possible.
    # This helps determine if the slowdown comes from encoding vs the player.
    try:
        from PIL import Image  # type: ignore

        im = Image.open(out_path)
        delays_ms = []
        i = 0
        while True:
            info = im.info
            d = info.get("duration", None)
            if d is not None:
                delays_ms.append(int(d))
            i += 1
            try:
                im.seek(i)
            except EOFError:
                break

        if delays_ms:
            avg_delay_ms = sum(delays_ms) / len(delays_ms)
            eff_fps = 1000.0 / avg_delay_ms if avg_delay_ms > 0 else float("inf")
            print(f"GIF stored avg delay: {avg_delay_ms:.1f} ms (effective fps ~ {eff_fps:.3f})")
    except ModuleNotFoundError:
        pass


if __name__ == "__main__":
    main()

