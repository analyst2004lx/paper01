# -*- coding: utf-8 -*-
"""Channel lift = DR - FPR, production three paths only."""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import FP, FP_SM, FP_TINY, C_LINE, apply_style, save  # noqa: E402

ATTACKS = [u"A1", u"A2", u"A3", u"A4", u"A5", u"A6"]
ATTACK_EN = [u"replay", u"infeas.", u"race", u"mimic", u"drift", u"suppress"]


def main():
    apply_style()
    dr = np.array([
        [0.22, 0.98, 0.00, 0.03, 0.00, 0.00],
        [0.19, 0.29, 0.02, 0.02, 0.01, 0.17],
        [0.03, 0.00, 0.43, 0.00, 0.48, 0.04],
    ], dtype=float)
    fpr = np.array([
        [0.00, 0.06, 0.00, 0.00, 0.00, 0.00],
        [0.02, 0.03, 0.01, 0.03, 0.01, 0.02],
        [0.03, 0.02, 0.02, 0.02, 0.03, 0.02],
    ], dtype=float)
    lift = dr - fpr

    cmap = LinearSegmentedColormap.from_list(
        "lift", ["#F7F7F7", "#FEE0D2", "#FC9272", "#DE2D26", "#A50F15"])
    fig, ax = plt.subplots(figsize=(6.4, 2.55))
    im = ax.imshow(lift, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(np.arange(6))
    ax.set_yticks(np.arange(3))
    ax.set_xticklabels([u"%s %s" % (a, z) for a, z in zip(ATTACKS, ATTACK_EN)],
                       fontproperties=FP_SM)
    ax.set_yticklabels([u"Hard F", u"Structure", u"Timing"], fontproperties=FP)
    ax.spines["top"].set_visible(True)
    ax.spines["right"].set_visible(True)
    for i in range(3):
        for j in range(6):
            val = lift[i, j]
            color = "white" if val >= 0.45 else C_LINE
            ax.text(j, i, u"%.2f" % val, ha="center", va="center", color=color,
                    fontproperties=FP_SM)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(u"Net lift DR$-$FPR", fontproperties=FP_SM)
    for t in cbar.ax.get_yticklabels():
        t.set_fontproperties(FP_TINY)
    fig.tight_layout()
    save(fig, "fig_coverage")


if __name__ == "__main__":
    main()
