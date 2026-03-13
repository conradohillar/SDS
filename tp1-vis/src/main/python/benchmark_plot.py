import csv
import math
import os
from collections import defaultdict

import matplotlib.pyplot as plt

BIN_PATH = "/home/conradohillar/Documents/ITBA/4to_2C/SDS/tp1-bin/"
CSV_PATH = os.path.join(BIN_PATH, "benchmark_results.csv")


def load_results(path):
    results = defaultdict(list)
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 5:
                continue
            N = int(row[0])
            M = int(row[1])
            method = row[2]
            run_index = int(row[3])
            time_ns = int(row[4])
            key = (N, M, method)
            results[key].append(time_ns)
    return results


def compute_stats(results):
    stats = {}
    for key, times in results.items():
        n = len(times)
        if n == 0:
            continue
        mean = sum(times) / n
        if n > 1:
            var = sum((t - mean) ** 2 for t in times) / (n - 1)
            std = math.sqrt(var)
        else:
            std = 0.0
        stats[key] = (mean, std)
    return stats


def setup_ax(ax, title, xlabel, ylabel):
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", linestyle="--", alpha=0.3)


def plot_vs_N(stats):
    """
    Único gráfico t vs N con:
    - Una sola curva de fuerza bruta (brute_force) en naranja
    - Varias curvas de Cell Index (cell_index), una por cada M, en colores distintos
    """
    Ns = sorted({key[0] for key in stats.keys()})
    Ms = sorted({key[1] for key in stats.keys()})

    fig, ax = plt.subplots()
    max_time = 0.0
    min_time = float("inf")

    # Fuerza bruta: una única curva (usamos un M de referencia, por ejemplo el menor)
    if Ms:
        ref_M = Ms[0]
        x_bf = []
        y_bf = []
        yerr_bf = []
        for N in Ns:
            key = (N, ref_M, "brute_force")
            if key not in stats:
                continue
            mean, std = stats[key]
            x_bf.append(N)
            y_bf.append(mean)
            yerr_bf.append(std)
            max_time = max(max_time, mean + std)
            min_time = min(min_time, max(1.0, mean - std))

        if x_bf:
            ax.errorbar(
                x_bf,
                y_bf,
                yerr=yerr_bf,
                marker="o",
                capsize=4,
                label=f"Brute force",
                color="tab:orange",
            )

    # Cell Index Method: una curva por cada M, en colores distintos
    cmap = plt.get_cmap("tab10")
    for idx, M in enumerate(Ms):
        x_ci = []
        y_ci = []
        yerr_ci = []
        for N in Ns:
            key = (N, M, "cell_index")
            if key not in stats:
                continue
            mean, std = stats[key]
            x_ci.append(N)
            y_ci.append(mean)
            yerr_ci.append(std)
            max_time = max(max_time, mean + std)
            min_time = min(min_time, max(1.0, mean - std))

        if x_ci:
            color = cmap(idx % 10)
            ax.errorbar(
                x_ci,
                y_ci,
                yerr=yerr_ci,
                marker="o",
                capsize=4,
                label=f"Cell Index (M={M})",
                color=color,
            )

    setup_ax(ax, "Tiempo vs N (curvas por M)", "N", "Tiempo [ns]")
    # Escalas logarítmicas en ambos ejes
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.legend()
    fig.tight_layout()


def plot_vs_M(stats):
    methods = {"cell_index": "Cell Index", "brute_force": "Brute force"}
    Ns = sorted({key[0] for key in stats.keys()})
    Ms = sorted({key[1] for key in stats.keys()})

    for N in Ns:
        fig, ax = plt.subplots()
        max_time = 0.0
        min_time = float("inf")

        for method_key, method_label in methods.items():
            x = []
            y = []
            yerr = []
            for M in Ms:
                key = (N, M, method_key)
                if key not in stats:
                    continue
                mean, std = stats[key]
                x.append(M)
                y.append(mean)
                yerr.append(std)
                max_time = max(max_time, mean + std)
                min_time = min(min_time, max(1.0, mean - std))

            if x:
                ax.errorbar(x, y, yerr=yerr, marker="o", capsize=4, label=method_label)

        setup_ax(ax, f"Tiempo vs M (N={N})", "M", "Tiempo [ns]")
        if max_time > 0 and min_time < float("inf") and max_time / min_time > 100:
            ax.set_yscale("log")
        ax.legend()
        fig.tight_layout()


def main():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"No se encontró el archivo de resultados: {CSV_PATH}")

    results = load_results(CSV_PATH)
    stats = compute_stats(results)

    plot_vs_N(stats)
    plot_vs_M(stats)

    plt.show()


if __name__ == "__main__":
    main()

