# -*- coding: utf-8 -*-
"""E8: per-message latency boxplot and M-scale."""
from __future__ import print_function, division

import json
import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_SM, C_OURS, C_LINE, apply_style, save, set_cjk,
)

ARCHIVE = os.path.abspath(os.path.join(
    HERE, "..", "..", "slid", "output", "e8_latency.json"))


def draw(blob, labels, out_name):
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.15))
    ax = axes[0]
    xs = blob["latency_us"]
    bp = ax.boxplot([xs], widths=0.45, patch_artist=True, showfliers=True,
                    flierprops={"marker": ".", "markersize": 3,
                                "markerfacecolor": C_OURS,
                                "markeredgecolor": C_OURS, "alpha": 0.35})
    for box in bp["boxes"]:
        box.set(facecolor=C_OURS, edgecolor="white", linewidth=0.6, alpha=0.85)
    for med in bp["medians"]:
        med.set(color=C_LINE, linewidth=1.0)
    ax.set_xticklabels([labels["box"]])
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, ylabel=labels["ylabel"])
    ax.set_title(labels["title_a"], fontproperties=FP_SM, loc="left")

    ax2 = axes[1]
    Ms = [r["M"] for r in blob["scale"]]
    ys = [r["median_us"] for r in blob["scale"]]
    ax2.plot(Ms, ys, "o-", color=C_OURS, linewidth=1.8, markersize=6)
    ax2.set_xticks(Ms)
    ax2.set_ylim(0, max(ys + [80]) * 1.25)
    ax2.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax2.set_axisbelow(True)
    set_cjk(ax2, xlabel=r"$M$", ylabel=labels["ylabel"])
    ax2.set_title(labels["title_b"], fontproperties=FP_SM, loc="left")
    fig.tight_layout()
    save(fig, out_name)


def main():
    with open(ARCHIVE, encoding="utf-8") as f:
        blob = json.load(f)
    draw(blob, {
        "box": "per-message", "ylabel": r"Latency ($\mu$s)",
        "title_a": "(a) Latency distribution",
        "title_b": r"(b) Scale with $M$ devices",
    }, "fig_latency")


if __name__ == "__main__":
    main()
