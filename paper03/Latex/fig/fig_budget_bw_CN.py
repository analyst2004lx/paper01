# -*- coding: utf-8 -*-
"""Silence bandwidth vs 5 Hz PBFT (paper03 fig:budget-bw)."""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    C_ACCENT, C_BASE, C_OURS, C_WARN, apply_style_cn, load, save,
)


def main():
    apply_style_cn()
    d = load()
    h = d["heartbeat"]
    pbft = d["budget_pbft_5hz_bps"]
    bps = h["silence_bps"]
    labels = h["regime_labels"]
    ratios = [pbft / b for b in bps]
    fig, ax = plt.subplots(figsize=(5.0, 2.7))
    bars = ax.bar(labels, bps, color=[C_BASE, C_ACCENT, C_OURS],
                  edgecolor="black", lw=0.4)
    ax.set_ylabel("心跳带宽 (B/s)")
    ax.set_title("沉默带宽对比 5 Hz PBFT")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, r, b in zip(bars, ratios, bps):
        ax.text(bar.get_x() + bar.get_width() / 2, b + 120,
                f"PBFT/{r:.0f}", ha="center", va="bottom", fontsize=7)
    ax.annotate("报告此项\n（最严）",
                xy=(2, bps[2]), xytext=(1.15, 5500),
                fontsize=7, color=C_WARN,
                arrowprops=dict(arrowstyle="->", color=C_WARN, lw=0.8))
    save(fig, "fig_budget_bw_CN.pdf")


if __name__ == "__main__":
    main()
