# -*- coding: utf-8 -*-
"""Hazard to bandwidth four-stage chain (paper03 fig:budget-chain)."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_budget_chain")

plt.rcParams.update({
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "dejavusans",
    "figure.dpi": 200,
})

C_EDGE = "#333333"
C_NOTE = "#555555"
C_BOX = "#dce6f4"


def box(ax, x, y, w, h, title, sub):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor=C_BOX, edgecolor=C_EDGE, linewidth=1.1, zorder=3))
    ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center",
            fontsize=10, color="#111", zorder=4)
    ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
            fontsize=8.2, color="#444", zorder=4)


def arrow(ax, p, q):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=12, linewidth=1.6,
        color=C_EDGE, shrinkA=0.6, shrinkB=0.6, zorder=2))


def main() -> None:
    fig, ax = plt.subplots(figsize=(8.4, 2.55))
    ax.set_xlim(-0.1, 13.2)
    ax.set_ylim(-0.55, 2.35)
    ax.axis("off")

    w, h, gap = 2.65, 1.25, 0.55
    xs = [0.25 + i * (w + gap) for i in range(4)]
    y = 0.85
    items = [
        ("Hazard model", r"field$/v$, ISO dist."),
        ("Time budget", r"FHI $\to$ detect"),
        ("Feasible", r"$(r,T_{\mathrm{hb}})$"),
        ("Bandwidth", r"$nL/T_{\mathrm{hb}}$"),
    ]
    for x, (title, sub) in zip(xs, items):
        box(ax, x, y, w, h, title, sub)
    for i in range(3):
        arrow(ax, (xs[i] + w, y + h / 2), (xs[i + 1], y + h / 2))

    ax.text(xs[1] + w / 2, 0.22,
            r"Theorem binds only silence: $T_{\mathrm{detect}}\leq r\,T_{\mathrm{hb}}$",
            ha="center", va="center", fontsize=8.2, color=C_NOTE)
    ax.text(xs[1] + w / 2, -0.12,
            "(corroboration delay is queue-conditioned)",
            ha="center", va="center", fontsize=8.2, color=C_NOTE)

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
