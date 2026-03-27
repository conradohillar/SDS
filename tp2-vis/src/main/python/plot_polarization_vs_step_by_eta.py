import argparse
import csv
import os
import re


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

    fig, ax = plt.subplots(figsize=(7.0, 3.5))

    def parse_eta_and_run_from_col(col: str) -> tuple[float, int]:
        # Accepted formats:
        # - eta_<value>
        # - eta_<value>_run_<idx>
        m = re.fullmatch(r"eta_([0-9eE+\-.]+)(?:_run_(\d+))?", col)
        if not m:
            raise ValueError(f"Invalid eta column name: {col}")
        eta_val = float(m.group(1))
        run_idx = int(m.group(2)) if m.group(2) is not None else 1
        return eta_val, run_idx

    ordered_series = sorted(
        series.items(),
        key=lambda kv: parse_eta_and_run_from_col(kv[0]),
    )
    unique_etas = sorted({parse_eta_and_run_from_col(col)[0] for col in series.keys()})
    cmap = plt.get_cmap("tab10")
    color_by_eta = {eta: cmap(i % 10) for i, eta in enumerate(unique_etas)}
    label_drawn: set[float] = set()

    # One line per run; runs with same eta share color.
    for eta_col, ys in ordered_series:
        eta_val, run_idx = parse_eta_and_run_from_col(eta_col)
        color = color_by_eta[eta_val]
        label = rf"$\eta={eta_val:g}$" if eta_val not in label_drawn else None
        label_drawn.add(eta_val)
        ax.plot(
            steps,
            ys,
            linewidth=1.8,
            color=color,
            alpha=0.9 if run_idx == 1 else 0.55,
            label=label,
        )

    if args.stationary_point is not None:
        stationary_point = float(args.stationary_point)
        # Highlight the stationary regime to the right of the threshold.
        ax.axvspan(
            stationary_point,
            max(steps),
            facecolor="#b9f6ca",
            alpha=0.35,
            label="estado estacionario",
        )
        ax.axvline(
            x=stationary_point,
            color="#39ff14",  # neon green
            linewidth=1.6,
            linestyle="--",
            alpha=0.9,
            label=f"límite estacionario = {args.stationary_point:g}",
        )

    ax.set_title("Polarización vs tiempo")
    ax.set_xlabel("tiempo (step)")
    ax.set_ylabel(r"polarización ($v_{a}$)")
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

