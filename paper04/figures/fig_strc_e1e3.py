"""E1/E3 汇总条形图:读 experiments/expanded CSV,无需新实验。"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(
    HERE, "..", "..", "STRC", "experiments", "expanded"))
OUT = os.path.join(HERE, "fig_strc_e1e3")

LABEL = {
    "example_3x3x2": "3x3x2",
    "congested_8x4x4": "congested",
    "S8x4x4_high": "S8 high",
}


def main() -> None:
    e1 = list(csv.DictReader(open(os.path.join(EXP, "e1_miss.csv"), encoding="utf-8")))
    e3 = list(csv.DictReader(open(os.path.join(EXP, "e3_boundary.csv"), encoding="utf-8")))

    by1 = defaultdict(list)
    for r in e1:
        by1[r["instance"]].append(r)
    names = [n for n in ("example_3x3x2", "congested_8x4x4", "S8x4x4_high") if n in by1]
    x = np.arange(len(names))
    w = 0.28

    t_imp = [sum(float(r["n_T_impact"]) for r in by1[n]) / len(by1[n]) for n in names]
    seeds = [sum(float(r["n_seeds"]) for r in by1[n]) / len(by1[n]) for n in names]
    cl = [sum(float(r["n_closure"]) for r in by1[n]) / len(by1[n]) for n in names]

    by3 = defaultdict(list)
    for r in e3:
        by3[r["instance"]].append(r)
    r1_feas = [sum(1 for r in by3[n] if r["R1_feasible"] == "True") / len(by3[n])
               for n in names]
    r2_feas = [sum(1 for r in by3[n] if r["R2_feasible"] == "True") / len(by3[n])
               for n in names]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))

    ax = axes[0]
    ax.bar(x - w, t_imp, w, label=r"$|T_{\mathrm{impact}}|$", color="#b0b8c0")
    ax.bar(x, seeds, w, label=r"$|\mathrm{Seeds}|$", color="#c45c26")
    ax.bar(x + w, cl, w, label=r"$|\mathrm{Cl}|$", color="#1f4e79")
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL[n] for n in names])
    ax.set_ylabel("mean count (5 seeds)")
    ax.set_title("E1: task-graph miss vs closure")
    ax.legend(loc="upper left", fontsize=7)
    ax.set_ylim(0, max(cl) * 1.25)

    ax = axes[1]
    ax.bar(x - w / 2, r1_feas, w, label="R1 feasible", color="#b0b8c0")
    ax.bar(x + w / 2, r2_feas, w, label="R2 / STRC feasible", color="#1f4e79")
    ax.set_xticks(x)
    ax.set_xticklabels([LABEL[n] for n in names])
    ax.set_ylabel("feasibility rate")
    ax.set_ylim(0, 1.15)
    ax.set_title("E3: same engine, swap boundary")
    ax.legend(loc="upper right", fontsize=7)
    for i, (a, b) in enumerate(zip(r1_feas, r2_feas)):
        ax.text(i - w / 2, a + 0.03, f"{a:.0%}", ha="center", fontsize=7, color="#555")
        ax.text(i + w / 2, b + 0.03, f"{b:.0%}", ha="center", fontsize=7, color="#1f4e79")

    fig.tight_layout()
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png")
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
