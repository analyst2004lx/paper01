# -*- coding: utf-8 -*-
"""离线拟合与在线三路并行（中文版，paper02 fig:arch）。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_arch_CN")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "dejavusans",
    "figure.dpi": 200,
})

C_EDGE = "#333333"
C_NOTE = "#555555"
C_OFF = "#f4f4f4"
C_MSG = "#e8e8e8"
C_HARD = "#f6d6d6"
C_STAT = "#d6e4f0"
C_SEQ = "#d9ecd9"
C_OUT = "#f4f4f4"


def box(ax, x, y, w, h, text, fc, fs=8.2):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=C_EDGE, linewidth=1.05, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color="#111", zorder=4, linespacing=1.35,
            multialignment="center")


def arrow(ax, p, q):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=10, linewidth=1.15,
        color=C_EDGE, shrinkA=1.2, shrinkB=1.2, zorder=2))


def main() -> None:
    fig, ax = plt.subplots(figsize=(12.2, 3.85))
    ax.set_xlim(0.0, 18.6)
    ax.set_ylim(0.0, 5.05)
    ax.axis("off")

    ws = [2.85, 2.35, 3.85, 4.15]
    h, gap = 1.38, 0.50
    xs = []
    xcur = 0.40
    for wi in ws:
        xs.append(xcur)
        xcur += wi + gap
    y_off = 3.25
    labels_off = [
        "正常日志",
        "BPMN",
        r"估计 $\tilde{P}$" + "\n时长核",
        "共形阈值、\nCUSUM 门限",
    ]
    for x, wi, lab in zip(xs, ws, labels_off):
        box(ax, x, y_off, wi, h, lab, C_OFF, fs=8.8)
    for i in range(3):
        arrow(ax, (xs[i] + ws[i], y_off + h / 2), (xs[i + 1], y_off + h / 2))
    ax.text(xs[1] + ws[1] + gap / 2, y_off + h + 0.16, "离线",
            ha="center", va="bottom", fontsize=10.5, color="#222")

    y_on = 0.80
    h2 = 1.42
    ws2 = [2.55, 2.75, 3.70, 2.20, 3.10]
    gap2 = 0.42
    xs2 = []
    xcur = 0.40
    for wi in ws2:
        xs2.append(xcur)
        xcur += wi + gap2
    labels_on = [
        (C_MSG, r"消息 $m_t$"),
        (C_HARD, r"硬层 $\mathbf{F}$" + "\n+ 账本"),
        (C_STAT, r"时序 $z$" + "\n" + r"结构 $\tilde{P}$"),
        (C_SEQ, "CUSUM"),
        (C_OUT, "告警或\n门控更新"),
    ]
    for x, wi, (fc, lab) in zip(xs2, ws2, labels_on):
        box(ax, x, y_on, wi, h2, lab, fc, fs=8.6)
    for i in range(4):
        arrow(ax, (xs2[i] + ws2[i], y_on + h2 / 2), (xs2[i + 1], y_on + h2 / 2))
    ax.text(xs2[1] + ws2[1] + gap2 / 2, y_on + h2 + 0.16, "在线",
            ha="center", va="bottom", fontsize=10.5, color="#222")
    ax.text(xs2[2] + ws2[2] / 2, y_on - 0.18,
            r"$O(1)$；合并报警按 $\alpha/3$ 划分",
            ha="center", va="top", fontsize=8.4, color=C_NOTE)

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
