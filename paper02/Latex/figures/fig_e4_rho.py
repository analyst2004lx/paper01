# -*- coding: utf-8 -*-
"""Single-message DR vs theory; vertical line at rho*."""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_SM, C_OURS, C_LAB, C_TIME, apply_style, save, set_cjk, legend,
)


def main():
    apply_style()
    rho = np.array([0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50])
    meas = np.array([0.060, 0.105, 0.199, 0.288, 0.452, 0.712, 0.874])
    theo = np.array([0.051, 0.127, 0.226, 0.317, 0.497, 0.701, 0.851])
    sigma = 0.236
    z = 2.326347874
    rho_star = 1.0 - np.exp(-sigma * z)

    fig, ax = plt.subplots(figsize=(5.6, 3.35))
    ax.plot(rho, theo, "s--", color=C_LAB, linewidth=1.5, markersize=5,
            label=u"Theory", zorder=2)
    ax.plot(rho, meas, "o-", color=C_OURS, linewidth=1.8, markersize=6,
            label=u"Measured single-msg DR", zorder=3)
    ax.axvline(rho_star, color=C_TIME, linestyle=":", linewidth=1.2, zorder=1)
    ax.text(rho_star + 0.012, 0.18,
            u"$\\rho^*=42.2$%", color=C_TIME, fontproperties=FP_SM)
    ax.set_xlim(0.0, 0.55)
    ax.set_ylim(0.0, 1.0)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    set_cjk(ax, xlabel=r"Race amount $\rho$", ylabel=u"Single-message DR")
    legend(ax, loc="upper left")
    fig.tight_layout()
    save(fig, "fig_e4_rho")


if __name__ == "__main__":
    main()
