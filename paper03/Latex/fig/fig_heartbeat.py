# -*- coding: utf-8 -*-
"""H1 equal-bandwidth periodic vs silence (paper03 fig:heartbeat)."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import C_BASE, C_OURS, C_WARN, apply_style, load, save  # noqa: E402


def main():
    apply_style()
    h = load()["heartbeat"]
    x = np.arange(len(h["regimes"]))
    w = 0.35
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    ax.bar(x - w / 2, h["silence_tdet"], w, label="Accountable silence", color=C_OURS)
    ax.bar(x + w / 2, h["period_tdet"], w, label="Equal-bandwidth periodic (H1)", color=C_BASE)
    for i, b in enumerate(h["detect_budget_s"]):
        ax.hlines(b, i - 0.4, i + 0.4, colors=C_WARN, linestyles="--", lw=1.0)
    ax.plot([], [], color=C_WARN, ls="--", label="Detect budget")
    ax.set_xticks(x)
    ax.set_xticklabels(h["regime_labels"])
    ax.set_ylabel(r"Detection delay $T_{\mathrm{detect}}$ (s)")
    ax.set_title(r"H1: equal-bandwidth periodic vs silence ($\sim$8$\times$)")
    ax.legend(frameon=False, fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "fig_heartbeat.pdf")


if __name__ == "__main__":
    main()
