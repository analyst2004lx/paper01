# -*- coding: utf-8 -*-
"""E2: production-relevant arms, per-channel alpha fixed, alpha=0.05."""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_SM, FP_TINY, C_OURS, C_TIME, C_HARD, C_STR, C_LINE,
    apply_style, save, set_cjk, legend,
)

ATTACKS = [u"A1", u"A2", u"A3", u"A4", u"A5", u"A6"]


def main():
    apply_style()
    full = np.array([0.45, 0.74, 0.27, 0.15, 0.70, 0.15])
    no_t = np.array([0.54, 0.84, 0.01, 0.22, -0.02, 0.21])
    no_f = np.array([0.29, 0.51, 0.27, 0.09, 0.70, 0.15])
    no_s = np.array([0.37, 0.81, 0.26, 0.04, 0.78, -0.03])
    series = [
        (u"Full", full, C_OURS),
        (u"w/o timing", no_t, C_TIME),
        (u"w/o hard", no_f, C_HARD),
        (u"w/o structure", no_s, C_STR),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.85),
                             gridspec_kw={"width_ratios": [2.35, 1.05]})
    ax = axes[0]
    x = np.arange(6)
    width = 0.18
    n = len(series)
    for k, (name, vals, col) in enumerate(series):
        offset = (k - (n - 1) / 2.0) * width
        ax.bar(x + offset, vals, width=width * 0.92, color=col,
               edgecolor="white", linewidth=0.4, label=name, zorder=3)
    ax.axhline(0.0, color=C_LINE, linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(ATTACKS, fontproperties=FP_SM)
    ax.set_ylim(-0.08, 1.05)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    set_cjk(ax, ylabel=u"Net DR")
    ax.set_title(u"(a) By attack family", fontproperties=FP_SM, loc="left")
    legend(ax, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.02),
           columnspacing=0.7, handlelength=1.1, handletextpad=0.3)

    ax2 = axes[1]
    deltas = np.array([-0.11, -0.07, -0.04])
    labels = [u"w/o timing", u"w/o hard", u"w/o structure"]
    cols = [C_TIME, C_HARD, C_STR]
    y = np.arange(3)
    ax2.barh(y, deltas, color=cols, edgecolor="white", height=0.55, zorder=3)
    ax2.axvline(0.0, color=C_LINE, linewidth=0.6)
    ax2.set_yticks(y)
    ax2.set_yticklabels(labels, fontproperties=FP_SM)
    ax2.set_xlim(-0.20, 0.03)
    ax2.xaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax2.set_axisbelow(True)
    set_cjk(ax2, xlabel=u"Mean change $\\Delta$")
    ax2.set_title(u"(b) Mean over six families", fontproperties=FP_SM, loc="left")
    for yi, d in zip(y, deltas):
        ax2.text(d - 0.008, yi, u"%.2f" % d, va="center", ha="right",
                 fontproperties=FP_TINY, color=C_LINE)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.86))
    save(fig, "fig_e2_ablation")


if __name__ == "__main__":
    main()
