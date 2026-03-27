import argparse
import os
import csv

import math
try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError as e:
    raise SystemExit(
        "matplotlib is required to plot. Install it with `pip install matplotlib` "
        "or in your environment where tp2-vis normally runs."
    ) from e


def _default_bin_dir() -> str:
    cwd = os.path.abspath(os.getcwd())
    cand = os.path.join(cwd, "tp2-bin")
    if os.path.isdir(cand):
        return cand
    return os.path.abspath(os.path.join(cwd, "..", "tp2-bin"))


def load_summary(path: str) -> dict[tuple[float, str], tuple[float, float]]:
    """
    CSV:
      eta,leader_type,mean_polarization,std_polarization
    """
    out: dict[tuple[float, str], tuple[float, float]] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 4:
                continue
            eta = float(row[0])
            leader_type = row[1].strip()
            mean_pol = float(row[2])
            std_pol = float(row[3])
            out[(eta, leader_type)] = (mean_pol, std_pol)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot TP2 polarization vs eta (from BenchmarkRunner).")
    parser.add_argument("--bin", default=_default_bin_dir(), help="Directory containing benchmark CSVs.")
    parser.add_argument("--summary", default="benchmark_polarization_summary.csv", help="Summary CSV filename.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="If provided, save PNGs into this directory (and don't open GUI unless --show).",
    )
    parser.add_argument(
        "--prefix",
        default="benchmark_polarization_vs_eta",
        help="Output filename prefix when saving PNGs (default: benchmark_polarization_vs_eta).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show plots interactively (useful even when --output-dir is provided).",
    )
    args = parser.parse_args()

    bin_dir = os.path.abspath(args.bin)
    summary_path = os.path.join(bin_dir, args.summary)

    if not os.path.exists(summary_path):
        raise SystemExit(f"File not found: {summary_path}")

    data = load_summary(summary_path)

    leader_order = [
        ("none", "Sin líder", "tab:blue"),
        ("fixed", "Líder fijo", "tab:orange"),
        ("circular", "Líder circular", "tab:green"),
    ]

    etas = sorted({eta for (eta, _) in data.keys()})
    if not etas:
        raise SystemExit("No data found in summary CSV.")

    out_dir = os.path.abspath(args.output_dir) if args.output_dir else None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    def plot_figure(
        leaders: list[tuple[str, str, str]],
        title: str,
        out_name: str | None,
        with_legend: bool,
    ) -> None:
        # Cuadrado: mismo alto que ancho (pedido del benchmark).
        fig, ax = plt.subplots(figsize=(7.0, 7.0))

        for leader_type, label, color in leaders:
            ys: list[float] = []
            yerrs: list[float] = []
            for eta in etas:
                mean_pol, std_pol = data.get((eta, leader_type), (math.nan, math.nan))
                ys.append(mean_pol)
                yerrs.append(std_pol)

            ax.errorbar(
                etas,
                ys,
                yerr=yerrs,
                fmt="o-",
                capsize=4,
                linewidth=2,
                label=label,
                color=color,
            )

        ax.set_title(title)
        ax.set_xlabel("η (rad)")
        ax.set_ylabel("polarización ($v_{a}$)")
        ax.set_xlim(min(etas), max(etas))
        ax.set_ylim(0.0, 1.05)
        ax.grid(True, alpha=0.3)
        if with_legend:
            ax.legend()
        fig.tight_layout()

        if out_dir and out_name:
            out_path = os.path.join(out_dir, out_name)
            fig.savefig(out_path, dpi=200)
            print(f"Saved: {out_path}")

    # 3 gráficos separados (uno por escenario de líder)
    for leader_type, label, _color in leader_order:
        plot_figure(
            leaders=[next(lo for lo in leader_order if lo[0] == leader_type)],
            title=f"Polarización promedio vs η — {label}",
            out_name=f"{args.prefix}_{leader_type}.png" if out_dir else None,
            with_legend=False,
        )

    # gráfico compuesto (los 3 escenarios)
    plot_figure(
        leaders=leader_order,
        title="Polarización promedio vs η",
        out_name=f"{args.prefix}_all.png" if out_dir else None,
        with_legend=True,
    )

    if args.show or not out_dir:
        plt.show()


if __name__ == "__main__":
    main()

