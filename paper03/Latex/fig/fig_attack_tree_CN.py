# -*- coding: utf-8 -*-
"""攻击者决策树 P1--P4（中文版）。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_attack_tree_CN")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "dejavusans",
    "figure.dpi": 200,
})

C_EDGE = "#333333"
C_NOTE = "#555555"
C_FAIL = "#e6e6e6"
C_DEC = "#e4e4e4"
C_ATK = "#f6d6d6"
C_DET = "#d9ecd9"


def rbox(ax, cx, cy, w, h, text, fc, fs=7.6):
    x, y = cx - w / 2, cy - h / 2
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=C_EDGE, linewidth=1.0, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=fs, color="#111", zorder=4, linespacing=1.2)
    return (cx, cy + h / 2), (cx, cy - h / 2), (cx - w / 2, cy), (cx + w / 2, cy)


def diamond(ax, cx, cy, w, h, text, fs=7.2):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=C_DEC,
                         edgecolor=C_EDGE, linewidth=1.0, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
            color="#111", zorder=4, linespacing=1.15)
    return (cx, cy + h / 2), (cx, cy - h / 2), (cx - w / 2, cy), (cx + w / 2, cy)


def arrow(ax, p, q):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=9, linewidth=1.1,
        color=C_EDGE, shrinkA=0.4, shrinkB=0.4, zorder=2))


def main() -> None:
    fig, ax = plt.subplots(figsize=(9.6, 7.6))
    ax.set_xlim(-0.15, 14.7)
    ax.set_ylim(-0.70, 11.0)
    ax.axis("off")

    root = rbox(ax, 7.2, 10.15, 4.3, 1.05,
                "被劫持设备要伪造\n「完成 / 空闲」", C_FAIL, 8.0)
    q1 = diamond(ax, 7.2, 8.35, 2.7, 1.35, "是否上报\n完成？")
    d2 = rbox(ax, 1.15, 6.35, 2.15, 1.15,
              r"沉默：" + "\n" + r"缺失 $h_k$" + "\n" + r"（约 1.8 s）",
              C_DET, 6.8)
    p2 = rbox(ax, 3.65, 6.35, 2.15, 0.85, r"$\mathbf{P2}$ 沉默", C_ATK)
    q2 = diamond(ax, 9.55, 6.45, 2.6, 1.3, "是否维持\n心跳？")

    d1 = rbox(ax, 3.45, 4.25, 2.2, 0.95, "合用：\n沉默更快", C_DET, 7.2)
    p1 = rbox(ax, 6.05, 4.25, 2.25, 0.95, r"$\mathbf{P1}$ 谎报、" + "\n无心跳", C_ATK)
    p3 = rbox(ax, 10.75, 4.25, 2.25, 0.95, r"$\mathbf{P3}$ 谎报并" + "\n" + r"披露 $h_k$", C_ATK)
    d3 = rbox(ax, 13.40, 4.25, 2.30, 0.95, "仅互证\n（沉默 DR${=}0$）", C_DET, 6.6)

    q3 = diamond(ax, 9.55, 2.15, 2.85, 1.35, "是否与对手方\n串谋？")
    p4 = rbox(ax, 9.35, 0.45, 3.15, 0.85, r"$\mathbf{P4}$ 一跳串谋", C_ATK)
    d4 = rbox(ax, 12.45, 0.45, 2.25, 0.95, "下一跳\n诚实否证", C_DET, 7.2)

    arrow(ax, root[1], q1[0])
    arrow(ax, q1[2], p2[0])
    arrow(ax, q1[3], q2[2])
    arrow(ax, p2[2], d2[3])
    arrow(ax, q2[2], p1[0])
    arrow(ax, q2[3], p3[0])
    arrow(ax, p1[2], d1[3])
    arrow(ax, p3[3], d3[2])
    ax.plot([9.55, 9.55], [q2[1][1], q3[0][1]], color=C_EDGE, lw=1.1, zorder=2)
    arrow(ax, (9.55, q3[0][1] + 0.12), q3[0])
    arrow(ax, q3[1], p4[0])
    arrow(ax, p4[3], d4[2])

    ax.text(5.05, 7.45, "否", fontsize=7.2, color=C_NOTE, ha="center")
    ax.text(8.55, 7.55, "是", fontsize=7.2, color=C_NOTE, ha="left")
    ax.text(7.45, 5.35, "否", fontsize=7.2, color=C_NOTE, ha="right")
    ax.text(10.55, 5.35, "是", fontsize=7.2, color=C_NOTE, ha="left")
    ax.text(9.75, 1.20, "是", fontsize=7.2, color=C_NOTE, ha="left")

    ax.text(7.2, -0.15,
            "有对手方时 P1–P3 无获胜支；缺口上 P3 可逃；P4 只推迟",
            ha="center", va="top", fontsize=7.4, color="#777")

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
