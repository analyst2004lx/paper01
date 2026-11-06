# -*- coding: utf-8 -*-
"""Tier-2 witness selection (paper03 fig:witness)."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import C_BASE, C_OURS, C_WARN, apply_style_cn, load, save  # noqa: E402


def main():
    apply_style_cn()
    t = load()["tier2"]
    labels = t["labels"]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.7), gridspec_kw={"wspace": 0.32})

    colors = [C_OURS if L == "OURS" else C_BASE for L in labels]
    axes[0].bar(x, t["p1_dr"], color=colors, edgecolor="black", lw=0.4)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylabel("P1 检出率")
    axes[0].set_ylim(0, 1.15)
    axes[0].set_title("同一协议，仅见证策略不同")
    axes[0].spines["top"].set_visible(False)
    axes[0].spines["right"].set_visible(False)

    axes[1].bar(x, t["witness_mean"], color=colors, edgecolor="black", lw=0.4)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel("平均见证集大小")
    axes[1].set_title(r"带宽代理 ($|W|$)")
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)

    ours_dr = t["p1_dr"][labels.index("OURS")]
    w4_dr = t["p1_dr"][labels.index("W4")]
    axes[0].annotate(
        f"W4 恢复 OURS 的 {w4_dr / ours_dr:.0%}",
        xy=(labels.index("W4"), w4_dr),
        xytext=(2.2, 0.85),
        fontsize=7,
        arrowprops=dict(arrowstyle="->", color=C_WARN, lw=0.8),
        color=C_WARN,
    )
    save(fig, "fig_witness_CN.pdf")


if __name__ == "__main__":
    main()
