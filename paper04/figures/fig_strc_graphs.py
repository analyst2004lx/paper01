# -*- coding: utf-8 -*-
"""Two graphs side by side: vertices of G_T are operations, vertices of G_R are
reservations; the right panel marks the four kinds of dependency edge."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_graphs")

plt.rcParams.update({"figure.dpi": 200})


def _box(ax, xy, w, h, text, fc, ec="#333333", fs=7.5):
    x, y = xy
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=ec, linewidth=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color="#1a1a1a")


def _node(ax, xy, lab, fc, radius=0.42):
    ax.add_patch(Circle(xy, radius, facecolor=fc, edgecolor="#222222", lw=0.9, zorder=3))
    ax.text(xy[0], xy[1], lab, ha="center", va="center", fontsize=7,
            color="white", fontweight="bold", zorder=4)


def _arrow(ax, p, q, color, style="-", lw=1.3):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=10,
        linestyle=style, linewidth=lw, color=color,
        shrinkA=8, shrinkB=8, zorder=2))


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.85))

    # ---- (a) G_T ----
    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title(r"(a) operation-precedence graph $G_T$ (vertex = operation)",
                 fontsize=9.5, pad=8)

    ops = [
        (0.7, 6.6, "J1-1"), (3.6, 6.6, "J1-2"), (6.5, 6.6, "J1-3"),
        (0.7, 3.4, "J2-1"), (3.6, 3.4, "J2-2"),
    ]
    for x, y, lab in ops:
        _box(ax, (x, y), 2.0, 1.15, lab, "#e8eef5")
    for (x1, y1, _), (x2, y2, _) in (
        (ops[0], ops[1]), (ops[1], ops[2]), (ops[3], ops[4]),
    ):
        ax.annotate("", xy=(x2, y2 + 0.58), xytext=(x1 + 2.0, y1 + 0.58),
                    arrowprops=dict(arrowstyle="->", color="#3d5a73", lw=1.15))
    ax.annotate("", xy=(1.7, 4.55), xytext=(1.7, 6.6),
                arrowprops=dict(arrowstyle="->", color="#6b4c7a",
                                lw=1.15, linestyle="--"))
    ax.text(2.55, 5.45, "same machine", fontsize=7, color="#6b4c7a")
    ax.text(4.5, 8.05, "job successor", fontsize=7, color="#3d5a73")

    ax.add_patch(Rectangle((0.7, 8.55), 8.6, 1.05, facecolor="#f7e6e6",
                            edgecolor="#8b1e1e", lw=1.0, linestyle="--"))
    ax.text(5.0, 9.07, "corridor blockage (no operation to start from)",
            ha="center", va="center", fontsize=7.6, color="#8b1e1e")
    ax.text(5.0, 1.55, r"$T_{\mathrm{direct}}=\varnothing$",
            ha="center", fontsize=10, fontweight="bold", color="#8b1e1e")
    ax.text(5.0, 0.65, "vertex set disjoint from the corridor occupancies",
            ha="center", fontsize=8, color="#555555")

    # ---- (b) G_R ----
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title(r"(b) reservation dependency graph $G_R$ (vertex = corridor occupancy)",
                 fontsize=9.5, pad=8)

    pos = {
        "r1": (1.7, 7.3),
        "r2": (4.6, 7.3),
        "r3": (4.6, 4.7),
        "r4": (7.5, 7.3),
        "r5": (7.5, 4.7),
    }
    _node(ax, pos["r1"], "r1", "#c45c26")
    _node(ax, pos["r2"], "r2", "#1f4e79")
    _node(ax, pos["r3"], "r3", "#1f4e79")
    _node(ax, pos["r4"], "r4", "#5a7a9a")
    _node(ax, pos["r5"], "r5", "#5a7a9a")
    ax.text(1.7, 6.55, "seed", ha="center", fontsize=6.5, color="#8b1e1e")

    c_yield, c_agv, c_job, c_mach = "#c45c26", "#1f4e79", "#2e7d4f", "#6b4c7a"
    _arrow(ax, pos["r1"], pos["r3"], c_yield)             # yielding
    _arrow(ax, pos["r1"], pos["r2"], c_agv)               # same vehicle
    _arrow(ax, pos["r2"], pos["r4"], c_job)               # same job
    _arrow(ax, pos["r3"], pos["r5"], c_mach, style="--")  # same machine

    ax.text(2.35, 5.85, "yielding", fontsize=7, color=c_yield, fontweight="bold")
    ax.text(2.45, 7.85, "same vehicle", fontsize=7, color=c_agv, fontweight="bold")
    ax.text(5.45, 7.85, "same job", fontsize=7, color=c_job, fontweight="bold")
    ax.text(6.25, 5.85, "same machine", fontsize=7, color=c_mach, fontweight="bold")

    ax.text(5.0, 2.15,
            "seed occupancies non-empty; successors collected along four edge kinds",
            ha="center", fontsize=8.6, fontweight="bold", color="#1f4e79")
    ax.text(5.0, 1.35,
            "the impact set is the transitive closure on this graph, not an operation neighbourhood",
            ha="center", fontsize=7.4, color="#555555")

    handles = [
        Line2D([0], [0], color=c_yield, lw=1.6,
               label="yielding (same corridor, different vehicles)"),
        Line2D([0], [0], color=c_agv, lw=1.6, label="same-vehicle successor"),
        Line2D([0], [0], color=c_job, lw=1.6, label="same-job successor"),
        Line2D([0], [0], color=c_mach, lw=1.6, linestyle="--",
               label="same-machine successor"),
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.02),
              fontsize=6.8, frameon=False, ncol=2, handlelength=1.6,
              columnspacing=0.8)

    fig.tight_layout()
    fig.savefig(OUT + ".pdf", bbox_inches="tight")
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
