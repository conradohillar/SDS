#!/usr/bin/env python3
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm

N_VALUES       = [100, 200, 400, 800]
TRANSIENT_TIME = 2000
BIN_ROOT       = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
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

fu_curves = {}
for n in N_VALUES:
    n_dir = os.path.join(BIN_ROOT, "scanning_rate", f"N{n}")
    r_dirs = sorted(d for d in Path(n_dir).iterdir()
                    if d.is_dir() and (d / "stats.txt").exists())
    fu_interp_list = []
    for r_dir in r_dirs:
        data = load_stats(str(r_dir))
        if data.shape[0] < 2:
            continue
        t  = data[:, 0]
        fu = data[:, 2] / n
        t_common  = np.linspace(0, float(t[-1]), 500)
        fu_interp_list.append(np.interp(t_common, t, fu))
    if fu_interp_list:
        tf_min   = min(d[:, 0][-1] for d in [load_stats(str(r)) for r in r_dirs] if d.shape[0] > 1)
        t_common = np.linspace(0, tf_min, 500)
        fu_all   = []
        for r_dir in r_dirs:
            data = load_stats(str(r_dir))
            if data.shape[0] < 2:
                continue
            fu_all.append(np.interp(t_common, data[:, 0], data[:, 2] / n))
        fu_curves[n] = (t_common, np.mean(fu_all, axis=0))

img_dir = os.path.join(BIN_ROOT, "images")
os.makedirs(img_dir, exist_ok=True)

fig, ax = plt.subplots(figsize=(8, 5))
colors = cm.plasma(np.linspace(0.1, 0.9, len(N_VALUES)))

ax.axvspan(0, TRANSIENT_TIME, color="red", alpha=0.08, zorder=0)
ax.axvline(TRANSIENT_TIME, color="red", lw=1.2, ls="--", alpha=0.6, zorder=1)

for i, n in enumerate(N_VALUES):
    curve = fu_curves.get(n)
    if curve is None:
        continue
    t_c, fu_c = curve
    ax.plot(t_c, fu_c, lw=2, color=colors[i], label=f"N={n}", zorder=2)
    mask = t_c >= TRANSIENT_TIME
    fest = float(np.mean(fu_c[mask])) if mask.any() else float(np.mean(fu_c))
    if fest > 0:
        ax.axhline(fest, color=colors[i], lw=1.0, ls=":", alpha=0.8, zorder=1)

ax.set_xlabel("t [s]", fontsize=13)
ax.set_ylabel(r"$F_u(t)$", fontsize=13)
ax.set_title("Evolución temporal de la fracción de partículas usadas", fontsize=13)
ax.legend(fontsize=10)
ax.set_ylim(0.0, 0.2)
ax.grid(True, ls="--", alpha=0.5)
plt.tight_layout()
out = os.path.join(img_dir, "fu_evolution.png")
plt.savefig(out, dpi=150)
print(f"Saved → {out}")
