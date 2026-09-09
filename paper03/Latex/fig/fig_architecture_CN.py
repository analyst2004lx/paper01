# -*- coding: utf-8 -*-
"""方法架构 M1--M7（中文版）。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_architecture_CN")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "dejavusans",
    "figure.dpi": 200,
})

C_EDGE = "#333333"
C_NOTE = "#666666"
C_OFF = "#dce6f4"
C_ON = "#f8e6d4"


def box(ax, x, y, w, h, text, fc, fs=7.8):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=C_EDGE, linewidth=1.0, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color="#111", zorder=4, linespacing=1.2)
    return x, y, w, h


def arrow(ax, p, q, color=C_EDGE, ls="-"):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=9, linewidth=1.1,
        color=color, linestyle=ls, shrinkA=0.5, shrinkB=0.5, zorder=2))


def routed(ax, pts, color="#777777", ls=(0, (3.0, 1.6))):
    xs, ys = zip(*pts)
    ax.plot(xs[:-1], ys[:-1], color=color, lw=1.05, ls=ls, zorder=2)
    ax.add_patch(FancyArrowPatch(
        pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=9,
        linewidth=1.05, linestyle=ls, color=color, zorder=2,
        shrinkA=0, shrinkB=0.4))


def main() -> None:
    fig, ax = plt.subplots(figsize=(9.0, 3.85))
    ax.set_xlim(-0.25, 13.5)
    ax.set_ylim(-0.95, 4.40)
    ax.axis("off")

    w, h, gap = 2.15, 0.95, 0.28
    xs = [0.35 + i * (w + gap) for i in range(5)]
    y_off = 2.35
    labs_off = [
        "M1 接入",
        r"M2 任务图" + "\n" + r"$G\!\to\!H$",
        "M5 覆盖",
        "M6 串谋",
        r"M7 预算" + "\n" + r"$(r,T_{hb})$",
    ]
    for x, lab in zip(xs, labs_off):
        box(ax, x, y_off, w, h, lab, C_OFF)
    for i in range(4):
        arrow(ax, (xs[i] + w, y_off + h / 2), (xs[i + 1], y_off + h / 2))

    ax.add_patch(Rectangle(
        (0.15, 2.12), xs[-1] + w - 0.05, 1.48,
        fill=False, edgecolor="#999999", linestyle=(0, (3.0, 1.6)),
        linewidth=0.9, zorder=1))
    ax.text(0.35, 3.72, "离线 / 派发前", ha="left", va="bottom",
            fontsize=7.4, color=C_NOTE, fontweight="bold")

    y_on = 0.15
    w2 = 2.35
    xs2 = [0.35, 3.55, 6.75, 9.95]
    labs_on = [
        r"命令 $u$" + "\n打开 pending",
        r"M3 互证" + "\n" + r"$W(a)$",
        r"M4 沉默" + "\n" + r"原像 $h_k$",
        "冻结\n派发",
    ]
    for x, lab in zip(xs2, labs_on):
        box(ax, x, y_on, w2, 1.05, lab, C_ON)
    arrow(ax, (xs2[0] + w2, y_on + 0.52), (xs2[1], y_on + 0.52))
    arrow(ax, (xs2[1] + w2, y_on + 0.52), (xs2[2], y_on + 0.52))
    arrow(ax, (xs2[2] + w2, y_on + 0.52), (xs2[3], y_on + 0.52))
    ax.text((xs2[1] + w2 + xs2[2]) / 2, y_on + 0.72, r"$\parallel$",
            ha="center", va="bottom", fontsize=8, color=C_NOTE)

    routed(ax, [
        (xs2[1] + w2 / 2, y_on),
        (xs2[1] + w2 / 2, -0.35),
        (xs2[3] + w2 / 2, -0.35),
        (xs2[3] + w2 / 2, y_on),
    ], color=C_EDGE, ls="-")

    routed(ax, [
        (xs[1] + w / 2, y_off),
        (xs[1] + w / 2, 1.48),
        (xs2[1] + w2 / 2, 1.48),
        (xs2[1] + w2 / 2, y_on + 1.05),
    ])
    ax.text(xs[1] + w / 2 + 0.12, 1.58, r"$W(a)$",
            ha="left", va="bottom", fontsize=7, color="#777")

    routed(ax, [
        (xs[4] + w / 2, y_off),
        (xs[4] + w / 2, 1.48),
        (xs2[2] + w2 / 2, 1.48),
        (xs2[2] + w2 / 2, y_on + 1.05),
    ])
    ax.text((xs[4] + xs2[2] + w2) / 2, 1.58, r"$T_{hb}$",
            ha="center", va="bottom", fontsize=7, color="#777")

    ax.text(-0.08, y_on + 0.52, "在线", ha="center", va="center",
            fontsize=7.4, color=C_NOTE, fontweight="bold", rotation=90)

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
