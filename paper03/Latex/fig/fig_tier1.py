# -*- coding: utf-8 -*-
"""Tier-1 single-observer baselines (paper03 fig:tier1)."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    C_ACCENT, C_BASE, C_MUTED, C_OURS, apply_style, load, save,
)


def main():
    apply_style()
    t = load()["tier1"]
    labels = t["labels"]
    x = np.arange(len(labels))
    w = 0.25
    fig, ax = plt.subplots(figsize=(5.2, 3.05))
    ax.bar(x - w, t["p1_dr"], w, label="P1 DR", color=C_OURS)
    ax.bar(x, t["p3_dr"], w, label="P3 DR", color=C_ACCENT)
    ax.bar(x + w, t["p2_dr"], w, label="P2 DR", color=C_BASE)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Detection rate")
    ax.set_ylim(0, 1.15)
    ax.axhline(1.0, color=C_MUTED, lw=0.6, ls=":")
    ax.legend(frameon=False, ncol=3, loc="lower center",
              bbox_to_anchor=(0.5, 1.02))
    ax.set_title("Tier-1 single-observer baselines (structural zero on P1/P3)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "fig_tier1.pdf")


if __name__ == "__main__":
    main()
