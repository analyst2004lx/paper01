# -*- coding: utf-8 -*-
"""E5: detection rate and rho* vs inflated timing sigma."""
from __future__ import print_function, division

import json
import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_SM, C_OURS, C_LAB, C_TIME, apply_style, save, set_cjk, legend,
)

ARCHIVE = os.path.abspath(os.path.join(
    HERE, "..", "..", "slid", "output", "e5_sigma_archive.json"))


def draw(blob, labels, out_name):
    apply_style()
    rows = blob["rows"]
    sig = [r["sigma"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.15))
    ax = axes[0]
    ax.plot(sig, [r["single_dr"] for r in rows], "s--", color=C_LAB,
            linewidth=1.5, markersize=5, label=labels["single"])
    ax.plot(sig, [r["cusum_dr"] for r in rows], "o-", color=C_OURS,
            linewidth=1.8, markersize=6, label=labels["cusum"])
    ax.axvline(blob["meta"]["sbar"], color=C_TIME, linestyle=":", linewidth=1.2)
    ax.set_ylim(0, 1.05)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, xlabel=r"$\sigma$", ylabel=labels["ylabel_dr"])
    ax.set_title(labels["title_a"], fontproperties=FP_SM, loc="left")
    legend(ax, loc="upper right")

    ax2 = axes[1]
    ax2.plot(sig, [r["rho_star"] * 100 for r in rows], "o-", color=C_OURS,
             linewidth=1.8, markersize=6)
    ax2.axvline(blob["meta"]["sbar"], color=C_TIME, linestyle=":", linewidth=1.2)
    ax2.set_ylim(0, 105)
    ax2.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax2.set_axisbelow(True)
    set_cjk(ax2, xlabel=r"$\sigma$", ylabel=r"$\rho^*$ (\%)")
    ax2.set_title(labels["title_b"], fontproperties=FP_SM, loc="left")
    fig.tight_layout()
    save(fig, out_name)


def main():
    with open(ARCHIVE, encoding="utf-8") as f:
        blob = json.load(f)
    draw(blob, {
        "single": "Single-msg", "cusum": "CUSUM",
        "ylabel_dr": r"DR at $\rho=0.30$",
        "title_a": r"(a) Detectability vs $\sigma$",
        "title_b": r"(b) Bound $\rho^*(\sigma)$",
    }, "fig_e5_sigma")


if __name__ == "__main__":
    main()
