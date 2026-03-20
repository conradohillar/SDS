import argparse
import csv
import os


def _default_bin_dir() -> str:
    cwd = os.path.abspath(os.getcwd())
    cand = os.path.join(cwd, "tp2-bin")
    if os.path.isdir(cand):
        return cand
    return os.path.abspath(os.path.join(cwd, "..", "tp2-bin"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot va(step) for eta=0..5 as colored lines.")
    parser.add_argument("--bin", default=_default_bin_dir(), help="Directory containing polarization CSV.")
    parser.add_argument("--csv", default="polarization_vs_step_by_eta.csv", help="Input CSV filename.")
    parser.add_argument("--output", default=None, help="Optional PNG output path. If omitted, shows plot.")
    parser.add_argument(
        "--stationary-point",
        type=float,
        default=None,
        help="If provided, draw a vertical line at step=STATIONARY_POINT.",
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

    steps: list[int] = []
    series: dict[str, list[float]] = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        eta_fields = [fn for fn in fieldnames if fn.startswith("eta_")]

        for fn in eta_fields:
            series[fn] = []

        for row in reader:
            if not row:
                continue
            steps.append(int(row["step"]))
            for fn in eta_fields:
                series[fn].append(float(row[fn]))

    if not series:
        raise SystemExit("No eta_* columns found in CSV header.")

    fig, ax = plt.subplots(figsize=(7.0, 7.0))

    def parse_eta_from_col(col: str) -> float:
        # Column format: "eta_<value>".
        # We keep it robust to scientific notation.
        return float(col.replace("eta_", ""))

    # One line per eta column; label uses the actual eta value from the CSV header.
    for eta_col, ys in sorted(series.items(), key=lambda kv: parse_eta_from_col(kv[0])):
        eta_val = parse_eta_from_col(eta_col)
        # Use Greek eta symbol in the legend.
        ax.plot(steps, ys, linewidth=2, label=rf"$\eta={eta_val:g}$")

    if args.stationary_point is not None:
        ax.axvline(
            x=float(args.stationary_point),
            color="#39ff14",  # neon green
            linewidth=1.6,
            linestyle="--",
            alpha=0.9,
            label=f"límite estacionario = {args.stationary_point:g}",
        )

    ax.set_title("Polarización vs step (L=10, ρ=4)")
    ax.set_xlabel("step")
    ax.set_ylabel("polarización")
    ax.set_xlim(min(steps), max(steps))
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    if args.output:
        out_path = os.path.abspath(args.output)
        fig.savefig(out_path, dpi=200)
        print(f"Saved: {out_path}")
    else:
        plt.show()


if __name__ == "__main__":
    main()

