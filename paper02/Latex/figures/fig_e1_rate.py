# -*- coding: utf-8 -*-
"""E1 net DR vs injection rate, one panel per attack family."""
from __future__ import print_function, division

import json
import os
import sys
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    C_OURS, C_B3, C_B4, C_B5, C_LAB, FP_TINY,
    apply_style, save, set_cjk, legend,
)

ATTACKS = ["A1", "A2", "A3", "A4", "A5", "A6"]
ATTACK_EN = ["replay", "infeas.", "race", "mimic", "drift", "suppress"]
METHODS = [
    ("butla", "BUTLA", C_B3),
    ("tabor", "TABOR-like", C_B4),
    ("hsmm", "HSMM", C_B5),
    ("markov", "Label-only", C_LAB),
    ("ours", "Ours", C_OURS),
]
ARCHIVE = os.path.abspath(os.path.join(
    HERE, "..", "..", "slid", "output", "e1_archive.json"))


def load_curves(labels):
    with open(ARCHIVE, encoding="utf-8") as f:
        blob = json.load(f)
    acc = defaultdict(list)
    for rec in blob["runs"]:
        acc[(rec["family"], rec["method"], rec["rate"])].append(rec["seq_net"])
    rates = sorted({r for _, _, r in acc})
    curves = {}
    for fam in ATTACKS:
        curves[fam] = {}
        for mid, _, _ in METHODS:
            curves[fam][mid] = [float(np.mean(acc[(fam, mid, r)])) for r in rates]
    return rates, curves, labels


def draw(rates, curves, labels, ylabel, out_name):
    apply_style()
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.4), sharex=True, sharey=True)
    for i, fam in enumerate(ATTACKS):
        ax = axes[i // 3][i % 3]
        for mid, name, color in METHODS:
            ax.plot(rates, curves[fam][mid], "o-", color=color, linewidth=1.4,
                    markersize=4, label=name if i == 0 else None)
        ax.axhline(0.0, color="#333333", linewidth=0.5)
        ax.set_ylim(-0.15, 1.05)
        ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
        ax.set_axisbelow(True)
        ax.set_title("%s  %s" % (fam, labels[i]), fontproperties=FP_TINY, loc="left")
        set_cjk(ax, xlabel="Injection rate" if i >= 3 else None,
                ylabel=ylabel if i % 3 == 0 else None)
    legend(axes[0][0], ncol=1, loc="lower right", handlelength=1.2)
    fig.tight_layout()
    save(fig, out_name)


def main():
    rates, curves, _ = load_curves(ATTACK_EN)
    if len(rates) < 2:
        raise SystemExit("e1_archive has only one injection rate; rerun with --rates")
    draw(rates, curves, ATTACK_EN, "Net DR (floor subtracted)", "fig_e1_rate")


if __name__ == "__main__":
    main()
