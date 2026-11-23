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
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    ax.set_xlim(0, 16)
    ax.set_ylim(-0.2, 9.6)
    ax.axis("off")

    # 输入与离线部分
    box(ax, 0.2, 6.3, 2.3, 1.7, "可行排程 $\\mathcal{S}^0$\n+ 扰动 $\\mathcal{D}$",
        fc="#eef2f6", fs=8.5)
    box(ax, 0.2, 8.45, 6.9, 0.95, "离线（扰动到来前）：由 $\\mathcal{S}^0$ 预建依赖图 $G_R$ 与节点停留表",
        fc="#f2f2f2", ec=C_OFF, fs=7.8, tc="#333333", ls="--")

    # 第一步:划界
    ax.add_patch(Rectangle((2.85, 5.9), 5.3, 2.35, facecolor="#e8eef5",
                           edgecolor=C_MEAS, lw=1.2, alpha=0.55, zorder=0))
    ax.text(5.5, 7.95, "第一步：划界", ha="center", fontsize=9,
            color=C_MEAS, fontweight="bold")
    box(ax, 3.0, 6.1, 2.35, 1.55,
        "起点集 $\\mathrm{Src}$\n走廊占用 $\\mathrm{Src}_E$\n端点停留 $\\mathrm{Src}_V$",
        fc="#dce6f1", ec=C_MEAS, fs=7.6, tc=C_MEAS)
    box(ax, 5.65, 6.1, 2.35, 1.55,
        "预约影响集 $\\mathrm{Cl}(\\mathrm{Src})$\n改写集 $W=\\tau(\\mathrm{Cl})$\n其余运输冻结 $F$",
        fc="#dce6f1", ec=C_MEAS, fs=7.6, tc=C_MEAS, bold=False)
    arrow(ax, 7.4, 8.45, 7.4, 7.65, C_OFF, ls="--")

    # 第二步:分层回放
    ax.add_patch(Rectangle((8.5, 5.9), 7.3, 2.35, facecolor="#e9f5ee",
                           edgecolor=C_REP, lw=1.2, alpha=0.55, zorder=0))
    ax.text(12.15, 7.95, "第二步：分层回放", ha="center", fontsize=9,
            color=C_REP, fontweight="bold")
    box(ax, 8.65, 6.1, 4.6, 1.55,
        "$F$：原样预提交\n$Q_0=\\tau(\\mathrm{Src}_E)$：全图重规划\n"
        "$T=W\\setminus Q_0$：沿原路线平移，失败则升级",
        fc="#d8efe3", ec=C_REP, fs=7.6, tc=C_REP)
    box(ax, 13.55, 6.1, 2.1, 1.55, "校验\n$\\mathcal{S}'$",
        fc="#d8efe3", ec=C_REP, fs=8.5, tc=C_REP)

    arrow(ax, 2.5, 7.15, 3.0, 7.15, C_MEAS)
    arrow(ax, 5.35, 6.88, 5.65, 6.88, C_MEAS)
    arrow(ax, 8.0, 6.88, 8.65, 6.88, C_REP)
    arrow(ax, 13.25, 6.88, 13.55, 6.88, C_REP)

    # 第三步:失败后放宽
    ax.add_patch(Rectangle((2.85, 3.05), 12.95, 2.25, facecolor="#fff8f0",
                           edgecolor=C_CTRL, lw=1.1, alpha=0.6, zorder=0))
    ax.text(9.3, 5.0, "第三步：失败后放宽（每一级仍为确定性回放）", ha="center", fontsize=9,
            color="#7a3b10", fontweight="bold")
    box(ax, 3.0, 3.25, 3.6, 1.4, "(1) 调整次序重试\n卡住的运输提前，至多 3 次",
        fc="#fff4e8", ec=C_CTRL, fs=7.6, tc="#7a3b10")
    box(ax, 7.0, 3.25, 3.6, 1.4, "(2) 全图重规划\n取 $Q=W$，再试一遍",
        fc="#fff4e8", ec=C_CTRL, fs=7.6, tc="#7a3b10")
    box(ax, 11.0, 3.25, 4.65, 1.4,
        "(3) 扩大 $W$\n工件后缀 → 同车后缀 → 全部未完成运输",
        fc="#fff4e8", ec=C_CTRL, fs=7.6, tc="#7a3b10")
    arrow(ax, 6.6, 3.95, 7.0, 3.95, C_CTRL)
    arrow(ax, 10.6, 3.95, 11.0, 3.95, C_CTRL)
    arrow(ax, 14.6, 6.1, 14.6, 5.3, C_CTRL)
    ax.text(14.75, 5.65, "失败", fontsize=7.5, color=C_CTRL, va="center")
    arrow(ax, 10.9, 5.3, 10.9, 6.1, C_CTRL)
    ax.text(11.05, 5.65, "重做第二步", fontsize=7.5, color=C_CTRL, va="center")

    # 对照与输出
    box(ax, 0.2, 0.75, 4.6, 1.75,
        "对照 AOR\n同一套分层回放\n$W\\leftarrow$ 工序依赖图上的影响域",
        fc="#fdeee6", ec=C_CTRL, fs=7.8, tc="#7a3b10")
    box(ax, 5.2, 0.75, 5.0, 1.75,
        "对照 ALL / RS / RD / GR\n不划界改写、全局右移、\n原染色体重解码、热启动全局重调度",
        fc="#fdeee6", ec=C_CTRL, fs=7.8, tc="#7a3b10")
    box(ax, 10.6, 0.75, 5.2, 1.75,
        "输出\n可行性、耗时、$C_{\\max}$、\n改动比例（路线改变 / 只改时刻）",
        fc="#eef2f6", fs=8.0)

    ax.text(8.0, 0.25,
            "同一套路网、节点模型、安全区间路径规划与无冲突校验；ALL 与本文只差改写集取 $W$ 还是全部未完成运输",
            ha="center", fontsize=7.6, color="#555555", style="italic")

    fig.tight_layout()
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT + ".pdf", bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
