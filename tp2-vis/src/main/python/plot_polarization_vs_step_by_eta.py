import argparse
import csv
import os
from collections import defaultdict


def _default_bin_dir() -> str:
    cwd = os.path.abspath(os.getcwd())
    cand = os.path.join(cwd, "tp2-bin")
    if os.path.isdir(cand):
        return cand
    return os.path.abspath(os.path.join(cwd, "..", "tp2-bin"))


LEADER_LABELS = {
    "none": "Sin líder",
    "fixed": "Líder fijo",
    "circular": "Líder circular",
}


def load_per_step_csv(path: str) -> dict[str, dict[float, tuple[list[int], list[float]]]]:
    """
    Reads benchmark_polarization_per_step.csv (long format):
        eta,leader_type,step,polarization

    Returns {leader_type: {eta: (steps[], polarizations[])}}.
    """
    data: dict[str, dict[float, tuple[list[int], list[float]]]] = defaultdict(lambda: defaultdict(lambda: ([], [])))

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            leader = row["leader_type"].strip()
            eta = float(row["eta"])
            step = int(row["step"])
            pol = float(row["polarization"])
            steps_list, pol_list = data[leader][eta]
            steps_list.append(step)
            pol_list.append(pol)

    return dict(data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot polarización vs step por eta (desde benchmark_polarization_per_step.csv)."
    )
    parser.add_argument("--bin", default=_default_bin_dir(), help="Directory containing CSV.")
    parser.add_argument("--csv", default="benchmark_polarization_per_step.csv", help="Input CSV filename.")
    parser.add_argument("--output-dir", default=None, help="Save PNGs to this directory.")
    parser.add_argument("--prefix", default="polarization_vs_step", help="Filename prefix for PNGs.")
    parser.add_argument("--show", action="store_true", help="Show plots interactively.")
    parser.add_argument(
        "--leader",
        default=None,
        help="Comma-separated leader types to plot (e.g. none,circular). Default: all in data.",
    )
    parser.add_argument(
        "--stationary-point",
        type=float,
        default=None,
        help="Draw a vertical line at this step to mark the stationary regime.",
    )
    args = parser.parse_args()

    bin_dir = os.path.abspath(args.bin)
    csv_path = os.path.join(bin_dir, args.csv)

    if not os.path.exists(csv_path):
        raise SystemExit(f"File not found: {csv_path}")

    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as e:
        raise SystemExit("matplotlib is required. Install it with: pip install matplotlib") from e

    data = load_per_step_csv(csv_path)

    if not data:
        raise SystemExit("No data found in CSV.")

    if args.leader:
        requested = [t.strip() for t in args.leader.split(",")]
        data = {k: v for k, v in data.items() if k in requested}
        if not data:
            raise SystemExit(f"No data for leader types: {args.leader}")

    out_dir = os.path.abspath(args.output_dir) if args.output_dir else None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    for leader_type, eta_series in sorted(data.items()):
        fig, ax = plt.subplots(figsize=(7.0, 3.5))

        sorted_etas = sorted(eta_series.keys())
        cmap = plt.get_cmap("tab10")
        colors = {eta: cmap(i % 10) for i, eta in enumerate(sorted_etas)}

        for eta in sorted_etas:
            steps, pols = eta_series[eta]
            ax.plot(
                steps,
                pols,
                linewidth=1.4,
                color=colors[eta],
                alpha=0.85,
                label=rf"$\eta={eta:g}$",
            )

        if args.stationary_point is not None:
            sp = float(args.stationary_point)
            all_steps = [s for ss, _ in eta_series.values() for s in ss]
            ax.axvspan(sp, max(all_steps), facecolor="#b9f6ca", alpha=0.35)
            ax.axvline(
                x=sp,
                color="#39ff14",
                linewidth=1.6,
                linestyle="--",
                alpha=0.9,
                label=f"límite estacionario = {sp:g}",
            )

        label = LEADER_LABELS.get(leader_type, leader_type)
        ax.set_title(f"Polarización vs tiempo — {label}")
        ax.set_xlabel("tiempo (step)")
        ax.set_ylabel(r"polarización ($v_{a}$)")
        all_steps = [s for ss, _ in eta_series.values() for s in ss]
        ax.set_xlim(min(all_steps), max(all_steps))
        ax.set_ylim(0.0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        fig.tight_layout()

        if out_dir:
            out_path = os.path.join(out_dir, f"{args.prefix}_{leader_type}.png")
            fig.savefig(out_path, dpi=200)
            print(f"Saved: {out_path}")

    if args.show or not out_dir:
        plt.show()


if __name__ == "__main__":
    main()
