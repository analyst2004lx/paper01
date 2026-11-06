# -*- coding: utf-8 -*-
"""Coverage vs sensor-oracle ceiling (paper03 fig:coverage)."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import C_MUTED, C_OK, apply_style, load, save  # noqa: E402


def main():
    apply_style()
    c = load()["coverage"]
    covered = c["frac_corroborated"]
    gap = c["oracle_gap"]
    other = max(0.0, 1.0 - covered)
    fig, ax = plt.subplots(figsize=(4.6, 2.70))
    ax.barh([0], [covered], color=C_OK, height=0.45, label="Corroborated")
    ax.barh([0], [other], left=[covered], color=C_MUTED, height=0.45,
            label=f"Oracle gap {gap * 100:.1f}%")
    ax.set_xlim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel("Fraction of activities")
    ax.set_title("Coverage vs sensor-oracle ceiling (U1)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.28),
              ncol=2)
    fig.tight_layout()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    save(fig, "fig_coverage.pdf")


if __name__ == "__main__":
    main()
