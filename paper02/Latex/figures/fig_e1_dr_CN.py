# -*- coding: utf-8 -*-
"""E1 sequential net DR, floor subtracted, alpha=0.01."""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    C_OURS, C_B3, C_B4, C_B5, C_LAB, C_LINE,
    apply_style, save, set_cjk, legend,
)

ATTACKS = [u"A1", u"A2", u"A3", u"A4", u"A5", u"A6"]
ATTACK_ZH = [u"重放", u"不可行", u"抢跑", u"模仿", u"漂移", u"抑制"]


def main():
    apply_style()
    data = {
        u"BUTLA": np.array([0.04, 0.37, 0.10, -0.04, 0.59, -0.05]),
        u"TABOR式": np.array([0.04, 0.67, 0.10, -0.01, 0.48, -0.01]),
        u"HSMM": np.array([-0.01, 0.31, 0.06, 0.02, 0.25, 0.05]),
        u"仅标签": np.array([0.48, 0.76, -0.01, 0.23, 0.00, 0.28]),
        u"本文": np.array([0.55, 0.95, 0.18, 0.17, 0.87, 0.14]),
    }
    colors = [C_B3, C_B4, C_B5, C_LAB, C_OURS]
    names = list(data.keys())
    x = np.arange(6)
    n = len(names)
    width = 0.15
    fig, ax = plt.subplots(figsize=(7.2, 3.85))
    for k, name in enumerate(names):
        offset = (k - (n - 1) / 2.0) * width
        ax.bar(x + offset, data[name], width=width * 0.92, color=colors[k],
               edgecolor="white", linewidth=0.4, label=name, zorder=3)
    ax.axhline(0.0, color=C_LINE, linewidth=0.6, zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels([u"%s\n%s" % (a, z) for a, z in zip(ATTACKS, ATTACK_ZH)])
    ax.set_ylim(-0.12, 1.05)
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    set_cjk(ax, ylabel=u"净检出率（已减地板）")
    legend(ax, ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.02),
           columnspacing=0.55, handlelength=1.15, handletextpad=0.3)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.86))
    save(fig, "fig_e1_dr_CN")


if __name__ == "__main__":
    main()
