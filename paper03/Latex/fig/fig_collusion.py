# -*- coding: utf-8 -*-
"""Collusion bound histogram (paper03 fig:collusion)."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import C_OURS, apply_style, load, save  # noqa: E402


def main():
    apply_style()
    c = load()["collusion"]
    hist = c.get("k_hist")
    fig, ax = plt.subplots(figsize=(5.2, 2.7))
    if hist:
        ks = sorted(int(k) for k in hist)
        ns = [hist[str(k)] for k in ks]
        ax.bar(ks, ns, color=C_OURS, edgecolor="black", lw=0.3, width=0.85)
        ax.set_xlabel(r"Collusion bound $k$ (forward closure size)")
        ax.set_ylabel("Number of chains")
        ax.set_title(
            f"Collusion bound histogram "
            f"(k_min={c['k_min']}, median={c['k_median']}, "
            f"k>=3: {c['frac_k_ge_3'] * 100:.0f}%)"
        )
    else:
        ax.text(0.5, 0.5,
                f"k_min={c['k_min']}, median={c['k_median']}, "
                f"k_max={c['k_max']}\n(run export_data without --anchored)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "fig_collusion.pdf")


if __name__ == "__main__":
    main()
