# -*- coding: utf-8 -*-
"""分层有界修复框架总图(中文)。原 fig_strc_framework_CN.* 保留。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_framework_CN_new")

from _cjk_mpl import setup_cjk

setup_cjk()
plt.rcParams.update({"figure.dpi": 200})

C_MEAS = "#1f4e79"
C_REP = "#2d6a4f"
C_CTRL = "#c45c26"
C_OFF = "#6b6b6b"
C_BOX = "#f7f7f7"
C_EDGE = "#444444"


def box(ax, x, y, w, h, text, fc=C_BOX, ec=C_EDGE, fs=8.5, bold=False, tc="#111111", ls="-"):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor=fc, edgecolor=ec, linewidth=1.15, linestyle=ls, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight=("bold" if bold else "normal"),
            color=tc, zorder=3, linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, color=C_EDGE, lw=1.2, ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw, linestyle=ls),
                zorder=1)


def main() -> None:
    fig, ax = plt.subplots(figsize=(8.9, 4.15))
    ax.set_xlim(0, 16.6)
    ax.set_ylim(2.3, 9.7)
    ax.axis("off")

    fs = 8.0
    # 输入与离线部分
    box(ax, 0.1, 6.35, 2.2, 1.6, "初始排程 $\\mathcal{S}^0$\n+ 扰动 $\\mathcal{D}$",
        fc="#eef2f6", fs=8.5)
    box(ax, 2.75, 8.6, 5.6, 0.9, "扰动到来前（离线）：由 $\\mathcal{S}^0$ 建好占用之间的依赖图 $G_R$",
        fc="#f2f2f2", ec=C_OFF, fs=fs, tc="#333333", ls="--")

    # 第一步:划界
    ax.add_patch(Rectangle((2.6, 5.75), 5.9, 2.6, facecolor="#e8eef5",
                           edgecolor=C_MEAS, lw=1.2, alpha=0.55, zorder=0))
    ax.text(5.55, 8.02, "第一步：划界", ha="center", fontsize=9,
            color=C_MEAS, fontweight="bold")
    box(ax, 2.75, 5.95, 2.55, 1.85,
        "起点占用 Src\n与扰动冲突的走廊占用，\n及受阻走廊两端的\n节点停留",
        fc="#dce6f1", ec=C_MEAS, fs=fs, tc=C_MEAS)
    box(ax, 5.6, 5.95, 2.75, 1.85,
        "预约影响集 Cl\n从起点沿依赖边\n可达的占用；所属运输\n构成改写集 $W$，\n其余运输冻结（$F$）",
        fc="#dce6f1", ec=C_MEAS, fs=fs, tc=C_MEAS)
    arrow(ax, 6.95, 8.6, 6.95, 7.8, C_OFF, ls="--")

    # 第二步:分层回放
    ax.add_patch(Rectangle((8.8, 5.75), 5.65, 2.6, facecolor="#e9f5ee",
                           edgecolor=C_REP, lw=1.2, alpha=0.55, zorder=0))
    ax.text(11.6, 8.02, "第二步：分层回放", ha="center", fontsize=9,
            color=C_REP, fontweight="bold")
    box(ax, 8.95, 5.95, 3.75, 1.85,
        "冻结的运输（$F$）：原样保留\n与扰动直接冲突的运输（$Q_0$）：\n在全图上重规划\n其余改写运输（$T$）：\n沿原路线只改时刻",
        fc="#d8efe3", ec=C_REP, fs=fs, tc=C_REP)
    box(ax, 12.95, 5.95, 1.35, 1.85, "无冲突\n校验",
        fc="#d8efe3", ec=C_REP, fs=8.5, tc=C_REP)
    box(ax, 14.85, 6.35, 1.65, 1.1, "修复后排程\n$\\mathcal{S}'$",
        fc="#eef2f6", fs=8.5)

    arrow(ax, 2.3, 7.15, 2.75, 7.15, C_MEAS)
    arrow(ax, 5.3, 6.88, 5.6, 6.88, C_MEAS)
    arrow(ax, 8.35, 6.88, 8.95, 6.88, C_REP)
    arrow(ax, 12.7, 6.88, 12.95, 6.88, C_REP)
    arrow(ax, 14.3, 6.9, 14.85, 6.9, C_REP)
    ax.text(14.57, 7.08, "通过", fontsize=7.5, color=C_REP, ha="center")

    # 第三步:失败后放宽
    ax.add_patch(Rectangle((2.6, 2.5), 11.85, 2.6, facecolor="#fff8f0",
                           edgecolor=C_CTRL, lw=1.1, alpha=0.6, zorder=0))
    ax.text(8.5, 4.78, "第三步：失败后放宽（每放宽一级，都重新执行第二步）", ha="center", fontsize=9,
            color="#7a3b10", fontweight="bold")
    box(ax, 2.75, 2.7, 3.3, 1.7, "(1) 调整次序重试\n规划失败的运输提前规划，\n至多 3 次",
        fc="#fff4e8", ec=C_CTRL, fs=fs, tc="#7a3b10")
    box(ax, 6.45, 2.7, 3.3, 1.7, "(2) 全图重规划\n$W$ 内全部运输\n都在全图上重规划",
        fc="#fff4e8", ec=C_CTRL, fs=fs, tc="#7a3b10")
    box(ax, 10.15, 2.7, 4.15, 1.7,
        "(3) 扩大改写集 $W$\n依次加入同一工件此后的运输、\n同一 AGV 此后的运输、\n全部尚未完成的运输",
        fc="#fff4e8", ec=C_CTRL, fs=fs, tc="#7a3b10")
    arrow(ax, 6.05, 3.55, 6.45, 3.55, C_CTRL)
    arrow(ax, 9.75, 3.55, 10.15, 3.55, C_CTRL)
    arrow(ax, 13.62, 5.95, 13.62, 5.1, C_CTRL)
    ax.text(13.75, 5.45, "失败", fontsize=7.5, color=C_CTRL, va="center")
    arrow(ax, 10.8, 5.1, 10.8, 5.95, C_CTRL)
    ax.text(10.95, 5.45, "重新执行第二步", fontsize=7.5, color=C_CTRL, va="center")

    fig.tight_layout()
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT + ".pdf", bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
