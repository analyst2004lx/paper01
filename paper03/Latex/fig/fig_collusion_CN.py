# -*- coding: utf-8 -*-
"""Collusion bound histogram (paper03 fig:collusion)."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import C_OURS, apply_style_cn, load, save  # noqa: E402


def main():
    apply_style_cn()
    c = load()["collusion"]
    hist = c.get("k_hist")
    fig, ax = plt.subplots(figsize=(5.2, 2.7))
    if hist:
        ks = sorted(int(k) for k in hist)
        ns = [hist[str(k)] for k in ks]
        ax.bar(ks, ns, color=C_OURS, edgecolor="black", lw=0.3, width=0.85)
        ax.set_xlabel(r"串谋界 $k$（前向闭包大小）")
        ax.set_ylabel("链数")
        ax.set_title(
            f"串谋界直方图 "
            f"(k_min={c['k_min']}, 中位={c['k_median']}, "
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
    save(fig, "fig_collusion_CN.pdf")


if __name__ == "__main__":
    main()
