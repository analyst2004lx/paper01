# -*- coding: utf-8 -*-
"""CUSUM vs single-message DR, and detection delay in messages."""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_SM, C_OURS, C_LAB, C_STR, apply_style, save, set_cjk, legend,
)


def main():
    apply_style()
    rho = np.array([0.05, 0.10, 0.15, 0.20, 0.30, 0.50])
    single = np.array([0.060, 0.105, 0.199, 0.288, 0.452, 0.874])
    cusum = np.array([0.245, 0.604, 0.868, 0.925, 0.962, 0.962])
    med = np.array([15, 12, 10, 8, 4, 2], dtype=float)
    p90 = np.array([24, 26, 19, 11, 7, 3], dtype=float)

    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.15))
    ax = axes[0]
    ax.plot(rho, single, "s--", color=C_LAB, linewidth=1.5, markersize=5,
            label=u"单消息")
    ax.plot(rho, cusum, "o-", color=C_OURS, linewidth=1.8, markersize=6,
            label=u"CUSUM")
    ax.set_xlim(0.0, 0.55)
    ax.set_ylim(0.0, 1.05)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, xlabel=u"抢跑量 $\\rho$", ylabel=u"检出率")
    ax.set_title(u"(a) 弱信号累积", fontproperties=FP_SM, loc="left")
    legend(ax, loc="lower right")

    ax2 = axes[1]
    yerr = np.vstack([np.zeros_like(med), p90 - med])
    ax2.errorbar(rho, med, yerr=yerr, fmt="o-", color=C_OURS,
                 linewidth=1.8, markersize=6, capsize=3, ecolor=C_STR,
                 label=u"中位 / $p_{90}$")
    ax2.set_xlim(0.0, 0.55)
    ax2.set_ylim(0, 30)
    ax2.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax2.set_axisbelow(True)
    set_cjk(ax2, xlabel=u"抢跑量 $\\rho$", ylabel=u"检测延迟（消息数）")
    ax2.set_title(u"(b) 以消息数计", fontproperties=FP_SM, loc="left")
    legend(ax2, loc="upper right")
    fig.tight_layout()
    save(fig, "fig_delay_CN")


if __name__ == "__main__":
    main()
