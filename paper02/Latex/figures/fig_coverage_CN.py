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
ATTACK_ZH = [u"重放", u"不可行", u"提前", u"模仿", u"漂移", u"抑制"]


ARCHIVE = os.path.join(HERE, os.pardir, os.pardir, "slid", "output",
                       "coverage_archive.json")
ROWS = ("hard", "struct", "time")


def _load():
    import io
    import json
    with io.open(ARCHIVE, encoding="utf-8") as f:
        fam = json.load(f)["families"]
    dr = np.array([[round(fam[a]["mean"][r]["dr"], 2) for a in ATTACKS]
                   for r in ROWS])
    fpr = np.array([[round(fam[a]["mean"][r]["fpr"], 2) for a in ATTACKS]
                    for r in ROWS])
    return dr, fpr


def main():
    apply_style()
    dr, fpr = _load()
    lift = dr - fpr

    cmap = LinearSegmentedColormap.from_list(
        "lift", ["#F7F7F7", "#FEE0D2", "#FC9272", "#DE2D26", "#A50F15"])
    fig, ax = plt.subplots(figsize=(6.4, 2.55))
    im = ax.imshow(lift, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(np.arange(6))
    ax.set_yticks(np.arange(3))
    ax.set_xticklabels([u"%s %s" % (a, z) for a, z in zip(ATTACKS, ATTACK_ZH)],
                       fontproperties=FP_SM)
    ax.set_yticklabels([u"硬约束层 F", u"结构", u"时序"], fontproperties=FP)
    ax.spines["top"].set_visible(True)
    ax.spines["right"].set_visible(True)
    for i in range(3):
        for j in range(6):
            val = lift[i, j]
            color = "white" if val >= 0.45 else C_LINE
            ax.text(j, i, u"%.2f" % val, ha="center", va="center", color=color,
                    fontproperties=FP_SM)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(u"净提升 DR$-$FPR", fontproperties=FP_SM)
    for t in cbar.ax.get_yticklabels():
        t.set_fontproperties(FP_TINY)
    fig.tight_layout()
    save(fig, "fig_coverage_CN")


if __name__ == "__main__":
    main()
