# -*- coding: utf-8 -*-
"""rho*(sigma) curve; global sigma and extreme groups marked."""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_TINY, C_OURS, C_LAB, C_TIME, C_LINE, apply_style, save, set_cjk, legend,
)


def main():
    apply_style()
    z = 2.326347874
    sig = np.linspace(0.0, 2.0, 400)
    rho = 1.0 - np.exp(-sig * z)

    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    ax.plot(sig, rho, color=C_OURS, linewidth=1.9, zorder=2,
            label=u"$\\rho^*(\\alpha,\\sigma)=1-e^{-\\sigma z_{1-\\alpha}}$")
    marks = [
        (0.007, 1.0 - np.exp(-0.007 * z), u"$\\sigma{=}0.007$\n(dm/lower)"),
        (0.236, 1.0 - np.exp(-0.236 * z), u"global $\\sigma{=}0.236$"),
        (1.843, 1.0 - np.exp(-1.843 * z), u"$\\sigma{=}1.843$\n(manual station)"),
    ]
    ax.axvline(0.236, color=C_TIME, linestyle=":", linewidth=1.0, zorder=1)
    ax.axhline(1.0 - np.exp(-0.236 * z), color=C_TIME, linestyle=":",
               linewidth=1.0, zorder=1)
    for s, r, lab in marks:
        ax.plot(s, r, "o", color=C_TIME, markersize=6, zorder=3)
    ax.annotate(marks[0][2], xy=(marks[0][0], marks[0][1]),
                xytext=(0.48, 0.28), fontproperties=FP_TINY, color=C_LINE,
                arrowprops=dict(arrowstyle="-", color=C_LAB, lw=0.7))
    ax.annotate(marks[1][2], xy=(marks[1][0], marks[1][1]),
                xytext=(0.92, 0.08), fontproperties=FP_TINY, color=C_LINE,
                arrowprops=dict(arrowstyle="-", color=C_LAB, lw=0.7))
    ax.annotate(marks[2][2], xy=(marks[2][0], marks[2][1]),
                xytext=(0.95, 0.58), fontproperties=FP_TINY, color=C_LINE,
                arrowprops=dict(arrowstyle="-", color=C_LAB, lw=0.7))
    ax.set_xlim(0.0, 2.05)
    ax.set_ylim(0.0, 1.05)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, xlabel=r"Timing variation $\sigma$",
            ylabel=r"Race-amount bound $\rho^*$")
    legend(ax, loc="lower right")
    fig.tight_layout()
    save(fig, "fig_sigma")


if __name__ == "__main__":
    main()
