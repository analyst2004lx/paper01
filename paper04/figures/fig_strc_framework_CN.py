# -*- coding: utf-8 -*-
"""STRC 框架总图中文版（开题图5-5）。原 fig_strc_framework.* 保留。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_framework_CN")

from _cjk_mpl import setup_cjk

setup_cjk()
plt.rcParams.update({"figure.dpi": 200})

C_MEAS = "#1f4e79"
C_REP = "#2d6a4f"
C_CTRL = "#c45c26"
C_BOX = "#f7f7f7"
C_EDGE = "#444444"


def box(ax, x, y, w, h, text, fc=C_BOX, ec=C_EDGE, fs=8.5, bold=False, tc="#111111"):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor=fc, edgecolor=ec, linewidth=1.15, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight=("bold" if bold else "normal"),
            color=tc, zorder=3, linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, color=C_EDGE, lw=1.2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw),
                zorder=1)


def main() -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.1))
    ax.set_xlim(0, 14)
    ax.set_ylim(-0.15, 8)
    ax.axis("off")

    box(ax, 0.25, 5.5, 2.7, 1.8,
        "可行排程 $\\mathcal{S}^0$\n+ 扰动 $\\mathcal{D}$",
        fc="#eef2f6", fs=8.5)

    ax.add_patch(Rectangle((3.3, 5.2), 5.0, 2.4, facecolor="#e8eef5",
                            edgecolor=C_MEAS, lw=1.2, alpha=0.55, zorder=0))
    ax.text(5.8, 7.3, "划定范围（预约影响集）", ha="center", fontsize=9,
            color=C_MEAS, fontweight="bold")
    box(ax, 3.5, 5.5, 2.1, 1.5, "起点占用\n与阻断窗重叠", fc="#dce6f1",
        ec=C_MEAS, fs=8, tc=C_MEAS)
    box(ax, 6.0, 5.5, 2.1, 1.5, "影响集\n$U=\\mathrm{Cl}(S)$", fc="#dce6f1",
        ec=C_MEAS, fs=8.5, bold=True, tc=C_MEAS)

    ax.add_patch(Rectangle((8.7, 5.2), 5.0, 2.4, facecolor="#e9f5ee",
                            edgecolor=C_REP, lw=1.2, alpha=0.55, zorder=0))
    ax.text(11.2, 7.3, "有界修复（第 1 级改路）", ha="center", fontsize=9,
            color=C_REP, fontweight="bold")
    box(ax, 8.9, 5.5, 2.2, 1.5, "集外保持原计划\n集内 $U$ 改路",
        fc="#d8efe3", ec=C_REP, fs=7.5, tc=C_REP)
    box(ax, 11.4, 5.5, 2.1, 1.5, "校验\n$\\mathcal{S}'$",
        fc="#d8efe3", ec=C_REP, fs=8.5, tc=C_REP)

    arrow(ax, 2.95, 6.4, 3.5, 6.4, C_MEAS)
    arrow(ax, 5.6, 6.4, 6.0, 6.4, C_MEAS)
    arrow(ax, 8.1, 6.4, 8.9, 6.4, C_REP)
    arrow(ax, 11.1, 6.4, 11.4, 6.4, C_REP)

    box(ax, 8.9, 3.15, 4.6, 1.4,
        "失败则扩大 $U$\n（工件后缀→同车后缀→全部未来）",
        fc="#fff4e8", ec=C_CTRL, fs=8, tc="#7a3b10")
    arrow(ax, 10.0, 5.5, 10.0, 4.55, C_CTRL)
    ax.annotate("", xy=(12.4, 5.5), xytext=(12.4, 3.9),
                arrowprops=dict(arrowstyle="->", color=C_CTRL, lw=1.1))

    box(ax, 0.25, 0.85, 4.0, 1.7,
        "对照 R1\n同一套改路\n$U\\leftarrow$ 工序依赖图",
        fc="#fdeee6", ec=C_CTRL, fs=8, tc="#7a3b10")
    box(ax, 4.7, 0.85, 4.1, 1.7,
        "对照 R0+\n热启动全局重调度\n限定搜索时间",
        fc="#fdeee6", ec=C_CTRL, fs=8, tc="#7a3b10")
    box(ax, 9.2, 0.85, 4.5, 1.7,
        "输出\n可行性、耗时、\n$C_{\\max}$、预约改动量",
        fc="#eef2f6", fs=8.5)

    ax.text(7.0, 0.32,
            "同一套路网、时间窗路由与无冲突校验；",
            ha="center", fontsize=8, color="#555555", style="italic")
    ax.text(7.0, 0.02,
            "只差允许改写哪些占用，或是否打开搜索",
            ha="center", fontsize=8, color="#555555", style="italic")

    fig.tight_layout()
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT + ".pdf", bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
