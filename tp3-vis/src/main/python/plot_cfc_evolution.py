#!/usr/bin/env python3
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm

N_VALUES = [100, 200, 400, 800]
BIN_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "..", "..", "..", "..", "tp3-bin"))

def load_stats(run_dir):
    rows = []
    with open(os.path.join(run_dir, "stats.txt")) as f:
        next(f)
        for line in f:
            p = line.strip().split()
            if p:
                rows.append([float(p[0]), int(p[1]), int(p[2])])
    return np.array(rows) if rows else np.zeros((0, 3))

fig, ax = plt.subplots(figsize=(8, 5))
colors = cm.plasma(np.linspace(0.1, 0.9, len(N_VALUES)))

for i, n in enumerate(N_VALUES):
    n_dir = os.path.join(BIN_ROOT, "scanning_rate", f"N{n}")
    r_dirs = sorted(d for d in Path(n_dir).iterdir()
                    if d.is_dir() and (d / "stats.txt").exists())
    runs = []
    for r_dir in r_dirs:
        data = load_stats(str(r_dir))
        if data.shape[0] < 2:
            continue
        runs.append((data[:, 0], data[:, 1]))

    if not runs:
        continue

    tf_min   = min(t[-1] for t, _ in runs)
    t_common = np.linspace(0, tf_min, 1000)
    cfc_mat  = np.array([np.interp(t_common, t, c) for t, c in runs])
    cfc_mean = cfc_mat.mean(axis=0)
    cfc_std  = cfc_mat.std(axis=0, ddof=1) if len(runs) > 1 else np.zeros_like(cfc_mean)

    J, b = np.polyfit(t_common, cfc_mean, 1)
    print(f"N={n:4d}  J = {J:.4f} eventos/s")

    ax.fill_between(t_common, cfc_mean - cfc_std, cfc_mean + cfc_std,
                    color=colors[i], alpha=0.2)
    ax.plot(t_common, cfc_mean, lw=2, color=colors[i], label=f"N={n}")
    fit_color = (1 - colors[i][0], 1 - colors[i][1], 1 - colors[i][2], 1.0)
    ax.plot([t_common[0], t_common[-1]],
            [J * t_common[0] + b, J * t_common[-1] + b],
            color=fit_color, lw=0.6, ls="--")

ax.set_xlabel("t [s]", fontsize=13)
ax.set_ylabel(r"$C_{fc}(t)$", fontsize=13)
ax.set_title(r"Colisiones acumuladas $C_{fc}(t)$", fontsize=13)
ax.legend(fontsize=11)
ax.grid(True, ls="--", alpha=0.5)
plt.tight_layout()

img_dir = os.path.join(BIN_ROOT, "images")
os.makedirs(img_dir, exist_ok=True)
out = os.path.join(img_dir, "cfc_evolution.png")
plt.savefig(out, dpi=150)
print(f"Saved → {out}")
