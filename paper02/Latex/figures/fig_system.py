# -*- coding: utf-8 -*-
"""Scheduling-layer command/status loop (paper02 fig:system)."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_system")

plt.rcParams.update({
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "dejavusans",
    "figure.dpi": 200,
})

C_EDGE = "#333333"
C_NOTE = "#555555"
C_SCHED = "#e6e6e6"
C_DEV = "#f0f0f0"
C_DET = "#d6e4f0"


def box(ax, x, y, w, h, title, sub, fc):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor=fc, edgecolor=C_EDGE, linewidth=1.15, zorder=3))
    ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center",
            fontsize=11, color="#111", zorder=4)
    ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
            fontsize=9, color="#333", zorder=4)


def arrow(ax, p, q, color=C_EDGE, lw=1.35, ls="-", ms=12):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=ms, linewidth=lw,
        linestyle=ls, color=color, shrinkA=1.0, shrinkB=1.0, zorder=2))


def main() -> None:
    fig, ax = plt.subplots(figsize=(7.4, 3.95))
    ax.set_xlim(0.0, 11.4)
    ax.set_ylim(-0.45, 5.45)
    ax.axis("off")

    sx, sy, sw, sh = 0.55, 3.25, 3.35, 1.45
    dx, dy, dw, dh = 0.55, 0.95, 3.35, 1.45
    tx, ty, tw, th = 6.85, 3.25, 3.85, 1.45

    box(ax, sx, sy, sw, sh, r"Scheduler $\mathcal{C}$",
        r"Command ledger $\mathcal{L}$", C_SCHED)
    box(ax, dx, dy, dw, dh, r"Field device $\mathcal{D}$",
        "Physical process", C_DEV)
    box(ax, tx, ty, tw, th, "Detector", "Hard / timing / structure", C_DET)

    s_bot_l = (sx + sw * 0.38, sy)
    s_bot_r = (sx + sw * 0.62, sy)
    d_top_l = (dx + dw * 0.38, dy + dh)
    d_top_r = (dx + dw * 0.62, dy + dh)
    s_r = (sx + sw, sy + sh / 2)
    t_l = (tx, ty + th / 2)
    d_r = (dx + dw, dy + dh * 0.55)
    t_bot = (tx + tw * 0.28, ty)

    arrow(ax, s_bot_l, d_top_l)
    ax.text(s_bot_l[0] - 0.18, (s_bot_l[1] + d_top_l[1]) / 2,
            r"Command $u_t$", ha="right", va="center", fontsize=9, color=C_NOTE)

    arrow(ax, d_top_r, s_bot_r)
    ax.text(s_bot_r[0] + 0.18, (s_bot_r[1] + d_top_r[1]) / 2,
            r"Status $s_t$", ha="left", va="center", fontsize=9, color=C_NOTE)

    arrow(ax, s_r, t_l, ls=(0, (3.2, 1.8)))
    ax.text((s_r[0] + t_l[0]) / 2, s_r[1] + 0.50,
            "Read-only ledger", ha="center", va="bottom", fontsize=9, color=C_NOTE)

    mid = (d_r[0] + 1.70, d_r[1])
    ax.plot([d_r[0], mid[0], mid[0], t_bot[0]],
            [d_r[1], mid[1], t_bot[1], t_bot[1]],
            color=C_EDGE, lw=1.2, ls=(0, (3.2, 1.8)), zorder=2)
    arrow(ax, (t_bot[0] + 0.28, t_bot[1]), t_bot, ls=(0, (3.2, 1.8)), lw=1.2)

    ax.text(0.55, 0.28,
            r"Attacker controls the content and timing of $s_t$,",
            ha="left", va="center", fontsize=8.0, color=C_NOTE)
    ax.text(0.55, -0.08,
            r"not the physical pace, $\mathcal{L}$, or $\mathbf{F}$",
            ha="left", va="center", fontsize=8.0, color=C_NOTE)

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
