import csv
import math
import os
from collections import defaultdict

import matplotlib.pyplot as plt

from sds_env import get_tp1_bin_path

BIN_PATH = get_tp1_bin_path()
CSV_PATH = os.path.join(BIN_PATH, "benchmark_results.csv")

# Debe coincidir con BenchmarkRunner
REFERENCE_L = 20.0
REFERENCE_N = 250
RHO = REFERENCE_N / (REFERENCE_L ** 2)


def load_results(path):
    results = defaultdict(list)
    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
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


def main():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"No se encontró {CSV_PATH}")

    results = load_results(CSV_PATH)
    stats = compute_stats(results)

    Ns = sorted({N for (N, _) in stats.keys()})

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
                x, y, yerr=yerr, marker="o", capsize=4,
                label=label, color=color,
            )

    title = f"Tiempo vs N (densidad constante ρ = {RHO:.4f} part./L²)"
    ax.set_title(title)
    ax.set_xlabel("N")
    ax.set_ylabel("Tiempo [ns]")
    ax.grid(True, which="both", linestyle="--", alpha=0.3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.legend()
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()

