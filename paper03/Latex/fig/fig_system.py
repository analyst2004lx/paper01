# -*- coding: utf-8 -*-
"""System model and message loop (paper03 fig:system)."""
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

C_SCH = "#dce6f4"
C_DEV = "#f8e6d4"
C_EDGE = "#333333"
C_NOTE = "#4a4a4a"
C_ORANGE = "#c45c26"


def box(ax, x, y, w, h, title, sub, fc):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
        facecolor=fc, edgecolor=C_EDGE, linewidth=1.15, zorder=3))
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center",
            fontsize=10.5, color="#111", zorder=4)
    ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
            fontsize=8.2, color="#444", zorder=4)


def arrow(ax, p, q, color=C_EDGE, lw=1.35, ls="-", rad=0.0, ms=11):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=ms, linewidth=lw,
        linestyle=ls, color=color, connectionstyle="arc3,rad=%.3f" % rad,
        shrinkA=1.2, shrinkB=1.2, zorder=2))


def routed_arrow(ax, pts, color=C_EDGE, lw=1.25, ls="--"):
    xs, ys = zip(*pts)
    ax.plot(xs[:-1], ys[:-1], color=color, lw=lw, ls=ls, zorder=2,
            solid_capstyle="butt")
    ax.add_patch(FancyArrowPatch(
        pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=11,
        linewidth=lw, linestyle=ls, color=color, zorder=2,
        shrinkA=0, shrinkB=0.4))


def main() -> None:
    fig, ax = plt.subplots(figsize=(8.6, 4.75))
    ax.set_xlim(0.0, 13.2)
    ax.set_ylim(-0.15, 8.35)
    ax.axis("off")

    sx, sy, sw, sh = 0.45, 4.55, 3.55, 1.55
    dx, dy, dw, dh = 8.55, 4.55, 3.75, 1.55
    bx, by, bw, bh = 8.55, 1.35, 3.75, 1.55
    box(ax, sx, sy, sw, sh, r"Scheduler $S$", r"ledger $c$, detect", C_SCH)
    box(ax, dx, dy, dw, dh, r"Device $d$", "(possibly hijacked)", C_DEV)
    box(ax, bx, by, bw, bh, r"Counterpart $d'$", "local sensing", C_DEV)

    s_r = (sx + sw, sy + sh / 2)
    d_l = (dx, dy + dh / 2)
    s_top = (sx + sw / 2, sy + sh)
    d_top = (dx + dw / 2, dy + dh)
    s_bot = (sx + sw / 2, sy)
    d_bot = (dx + dw / 2, dy)
    b_top = (bx + bw / 2, by + bh)
    b_l = (bx, by + bh / 2)

    arrow(ax, s_r, d_l)
    ax.text((s_r[0] + d_l[0]) / 2, s_r[1] + 0.38,
            r"cmd $u$ (opens pending)",
            ha="center", va="bottom", fontsize=8.4, color=C_NOTE)

    y_rep = 7.50
    routed_arrow(ax, [
        (d_top[0], d_top[1]),
        (d_top[0], y_rep),
        (s_top[0], y_rep),
        (s_top[0], s_top[1] + 0.04),
    ], ls=(0, (3.2, 1.8)))
    ax.text((s_top[0] + d_top[0]) / 2, y_rep + 0.20,
            r"report $r$ (completion)",
            ha="center", va="bottom", fontsize=8.4, color=C_NOTE)

    y_hb = s_r[1] - 0.42
    arrow(ax, (d_l[0], y_hb), (s_r[0], y_hb), ls=(0, (0.7, 1.15)))
    ax.text((s_r[0] + d_l[0]) / 2, y_hb - 0.22,
            r"preimage $h_k$",
            ha="center", va="top", fontsize=8.4, color=C_NOTE)

    arrow(ax, b_top, d_bot, color=C_ORANGE)
    ax.text(d_bot[0] + 0.22, (b_top[1] + d_bot[1]) / 2,
            "confirm / refute", ha="left", va="center",
            fontsize=8.4, color=C_ORANGE)

    arrow(ax, b_l, s_bot, color=C_ORANGE, rad=0.28, lw=1.35)
    ax.text(4.55, 1.85, r"evidence to $S$",
            ha="center", va="top", fontsize=8.4, color=C_ORANGE)

    ax.text(0.45, 0.55,
            r"Completion claims $\rightarrow$ coupled corroboration",
            ha="left", va="center", fontsize=8.3, color=C_NOTE)
    ax.text(0.45, 0.12,
            r"Heartbeat preimages $\rightarrow$ accountable silence",
            ha="left", va="center", fontsize=8.3, color=C_NOTE)

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
