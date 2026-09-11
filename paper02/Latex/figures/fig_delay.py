# -*- coding: utf-8 -*-
"""CUSUM vs single-message DR, and detection-delay boxplots vs rho."""
from __future__ import print_function, division

import json
import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_SM, C_OURS, C_LAB, C_LINE,
    apply_style, save, set_cjk, legend,
)

ARCHIVE = os.path.abspath(os.path.join(
    HERE, "..", "..", "slid", "output", "e4_delay_archive.json"))


def load_e4():
    with open(ARCHIVE, encoding="utf-8") as f:
        return json.load(f)


def draw(blob, labels, out_name):
    apply_style()
    rows = blob["rows"]
    rho = [r["rho"] for r in rows]
    single = [r["single"] for r in rows]
    cusum = [r["cusum_dr"] for r in rows]

    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.15))
    ax = axes[0]
    ax.plot(rho, single, "s--", color=C_LAB, linewidth=1.5, markersize=5,
            label=labels["single"])
    ax.plot(rho, cusum, "o-", color=C_OURS, linewidth=1.8, markersize=6,
            label=labels["cusum"])
    ax.set_xlim(0.0, 0.55)
    ax.set_ylim(0.0, 1.05)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, xlabel=labels["xlabel_rho"], ylabel=labels["ylabel_dr"])
    ax.set_title(labels["title_a"], fontproperties=FP_SM, loc="left")
    legend(ax, loc="lower right")

    ax2 = axes[1]
    data, pos = [], []
    for i, r in enumerate(rows):
        xs = r.get("delays") or []
        if xs:
            data.append(xs)
            pos.append(r["rho"])
    if data:
        bp = ax2.boxplot(
            data, positions=pos, widths=0.035, patch_artist=True,
            showfliers=True,
            flierprops={"marker": ".", "markersize": 3,
                        "markerfacecolor": C_OURS, "markeredgecolor": C_OURS,
                        "alpha": 0.4})
        for box in bp["boxes"]:
            box.set(facecolor=C_OURS, edgecolor="white", linewidth=0.6, alpha=0.85)
        for med in bp["medians"]:
            med.set(color=C_LINE, linewidth=1.0)
        for w in list(bp["whiskers"]) + list(bp["caps"]):
            w.set(color=C_OURS, linewidth=0.8)
    ax2.set_xlim(0.0, 0.55)
    ax2.set_ylim(0, 42)
    ax2.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax2.set_axisbelow(True)
    set_cjk(ax2, xlabel=labels["xlabel_rho"], ylabel=labels["ylabel_delay"])
    ax2.set_title(labels["title_b"], fontproperties=FP_SM, loc="left")
    fig.tight_layout()
    save(fig, out_name)


def main():
    draw(load_e4(), {
        "single": "Single-msg",
        "cusum": "CUSUM",
        "xlabel_rho": r"Race amount $\rho$",
        "ylabel_dr": "Detection rate",
        "ylabel_delay": "Detection delay (messages)",
        "title_a": "(a) Weak-signal accumulation",
        "title_b": "(b) Delay boxplots",
    }, "fig_delay")


if __name__ == "__main__":
    main()
