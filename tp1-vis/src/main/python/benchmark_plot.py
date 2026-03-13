import csv
import math
import os
from collections import defaultdict

import matplotlib.pyplot as plt

BIN_PATH = "/home/conradohillar/Documents/ITBA/4to_2C/SDS/tp1-bin/"
CSV_PATH = os.path.join(BIN_PATH, "benchmark_results.csv")


def load_results(path):
    """
    Lee el CSV generado por BenchmarkRunner, sin columna de M:
    N,method,run_index,time_ns
    """
    results = defaultdict(list)
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 4:
                continue
            N = int(row[0])
            method = row[1]
            time_ns = int(row[3])
            key = (N, method)
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


def plot_vs_N(stats, rho):
    """
    Único gráfico t vs N comparando Cell Index vs Brute force
    con densidad constante.
    """
    Ns = sorted({key[0] for key in stats.keys()})

    fig, ax = plt.subplots()

    for method, label, color in [
        ("cell_index", "Cell Index", "tab:blue"),
        ("brute_force", "Brute force", "tab:orange"),
    ]:
        x = []
        y = []
        yerr = []
        for N in Ns:
            key = (N, method)
            if key not in stats:
                continue
            mean, std = stats[key]
            x.append(N)
            y.append(mean)
            yerr.append(std)

        if x:
            ax.errorbar(
                x,
                y,
                yerr=yerr,
                marker="o",
                capsize=4,
                label=label,
                color=color,
            )

    title = f"Tiempo vs N (densidad constante ρ = {rho:.4f} part./L²)"
    setup_ax(ax, title, "N", "Tiempo [ns]")
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

    # Debe coincidir con el BenchmarkRunner
    reference_L = 20.0
    reference_N = 100
    rho = reference_N / (reference_L ** 2)

    plot_vs_N(stats, rho)

    plt.show()


if __name__ == "__main__":
    main()

