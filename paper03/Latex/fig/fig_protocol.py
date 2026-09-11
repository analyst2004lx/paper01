# -*- coding: utf-8 -*-
"""Dual-deadline corroboration and heartbeat timeline (paper03 fig:protocol)."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_protocol")

plt.rcParams.update({
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "dejavusans",
    "figure.dpi": 200,
})

C_EDGE = "#333333"
C_NOTE = "#555555"
C_ORANGE = "#c45c26"
C_BLUE = "#2e6aa6"
C_GREEN = "#2e7d4f"
C_RED = "#b03a2e"
C_HB = "#888888"


def main() -> None:
    fig, ax = plt.subplots(figsize=(9.0, 3.75))
    ax.set_xlim(-0.6, 12.6)
    ax.set_ylim(-2.95, 2.75)
    ax.axis("off")

    ax.add_patch(FancyArrowPatch(
        (0.0, 0.0), (11.7, 0.0), arrowstyle="-|>", mutation_scale=10,
        linewidth=1.2, color=C_EDGE, zorder=2))
    ax.text(11.85, 0.0, r"$t$", ha="left", va="center", fontsize=9)

    ticks = [
        (0.8, r"$t_u$", "cmd $u$\nopens pending", "#111"),
        (2.2, r"$t_r$", "claim $r$\n(optional)", "#111"),
        (4.0, r"$t_{\mathrm{wd}}$", "", "#111"),
        (6.2, r"$t_{\mathrm{corr}}$", "confirm /\nrefute / expire", C_BLUE),
        (8.7, r"$t_{k}$", "", "#111"),
        (10.45, r"$t_{k}+T_{\mathrm{hb}}$", "", "#111"),
    ]
    for x, lab, ev, col in ticks:
        ax.plot([x, x], [-0.1, 0.1], color=C_EDGE, lw=1.0)
        ax.text(x, -0.22, lab, ha="center", va="top", fontsize=8)
        if ev:
            ax.text(x, 1.48, ev, ha="center", va="bottom", fontsize=7.6, color=col)

    ax.plot([0.8, 4.0], [0.55, 0.55], color=C_ORANGE, lw=1.6)
    ax.text(2.4, 0.62, "watchdog window", ha="center", va="bottom",
            fontsize=7.2, color=C_ORANGE)
    ax.plot([0.8, 6.2], [0.95, 0.95], color=C_BLUE, lw=1.6)
    ax.text(3.5, 1.02, r"corroboration window $\Delta$", ha="center",
            va="bottom", fontsize=7.2, color=C_BLUE)

    ax.plot([0.0, 11.7], [-1.55, -1.55], color=C_HB, lw=1.05, ls=(0, (3.0, 1.6)))
    ax.text(-0.12, -1.55, "HB", ha="right", va="center", fontsize=8, color=C_HB)
    beats = [1.4, 3.0, 4.6, 6.2, 7.8, 9.4]
    for x in beats:
        ax.add_patch(Circle((x, -1.55), 0.07, facecolor=C_GREEN,
                            edgecolor=C_GREEN, zorder=3))
    ax.text(4.6, -1.28, r"disclose $h_k$", ha="center", va="bottom",
            fontsize=7.2, color=C_GREEN)
    ax.plot([9.4, 10.45], [-1.28, -1.28], color=C_RED, lw=1.5)
    ax.text(10.55, -0.82, r"miss $\times r$" + "\n" + r"$\Rightarrow$ accountable",
            ha="center", va="bottom", fontsize=7.0, color=C_RED)

    ax.text(0.05, -2.25,
            r"Completion path (solid): conditional latency after counterpart dispatch.",
            ha="left", va="center", fontsize=7.4, color=C_NOTE)
    ax.text(0.05, -2.58,
            r"Heartbeat path (dashed): unconditional $T_{\mathrm{detect}}\leq r\,T_{\mathrm{hb}}$.",
            ha="left", va="center", fontsize=7.4, color=C_NOTE)

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
