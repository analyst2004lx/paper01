# -*- coding: utf-8 -*-
"""闭环双层框架中文版（开题图5-2）。原图 fig_framework.* 保留不动。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 200,
})

C_EVAL = "#08519c"
C_DEC = "#d95f02"
C_BOX = "#f7f7f7"
C_EDGE = "#5a5a5a"
C_INNER = "#ffffff"


def box(ax, x, y, w, h, text, fc=C_INNER, ec=C_EDGE, lw=0.8, fs=8.5,
        weight="normal", style="round,pad=0.35", color="black", zorder=3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, linewidth=lw,
                                facecolor=fc, edgecolor=ec, zorder=zorder))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight=weight, color=color, zorder=zorder + 1, linespacing=1.35)


def arrow(ax, p, q, color=C_EDGE, lw=0.9, ls="-", rad=0.0, style="-|>",
          ms=7, zorder=5):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=ms,
                                 linewidth=lw, linestyle=ls, color=color,
                                 connectionstyle="arc3,rad=%.2f" % rad,
                                 shrinkA=1.5, shrinkB=1.5, zorder=zorder))


def badge(ax, x, y, n, color):
    ax.add_patch(mpatches.Circle((x, y), 2.0, facecolor=color,
                                 edgecolor="white", linewidth=0.8, zorder=8))
    ax.text(x, y, str(n), ha="center", va="center", fontsize=7.2,
            color="white", fontweight="bold", zorder=9)


def main() -> None:
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.2, 57)
    ax.axis("off")

    box(ax, 2, 5, 25, 45, "", fc=C_BOX, ec=C_EDGE, lw=1.0,
        style="round,pad=0.2", zorder=1)
    ax.text(14.5, 52.6, "上层：模因搜索", ha="center",
            va="center", fontsize=9.5, fontweight="bold")
    box(ax, 4.5, 37, 20, 7.5, "染色体种群\n（机器指派、工序排序）", fs=8.2)
    box(ax, 4.5, 27, 20, 7, "交叉、变异\n与局部搜索", fs=8.2)
    box(ax, 4.5, 16.5, 20, 7, "适应度 $=$ 真实 $C_{\\max}$",
        ec=C_EVAL, lw=1.4, weight="bold", color=C_EVAL, fs=8.5)
    box(ax, 4.5, 8, 20, 5, "选择", fs=8.2)
    arrow(ax, (14.5, 37), (14.5, 34.0))
    arrow(ax, (14.5, 16.5), (14.5, 13.0))
    arrow(ax, (3.4, 10.5), (3.4, 40.5))

    box(ax, 32, 5, 30, 45, "", fc=C_BOX, ec=C_EDGE, lw=1.0,
        style="round,pad=0.2", zorder=1)
    ax.text(47, 52.6, "事件驱动解码器", ha="center", va="center",
            fontsize=9.5, fontweight="bold")
    box(ax, 34.5, 40, 25, 5.5, "弹出下一道就绪工序", fs=8.2)
    box(ax, 34.5, 30, 25, 7.5, "生成运输任务\n（取货、送货、就绪时刻）", fs=8.2)
    box(ax, 34.5, 18, 25, 9, "选择车辆：\n对候选车试算预约表",
        ec=C_DEC, lw=1.4, weight="bold", color=C_DEC, fs=8.2)
    box(ax, 34.5, 8, 25, 7.5, "提交走廊预约\n推进仿真时钟", fs=8.2)
    arrow(ax, (47, 40), (47, 37.5))
    arrow(ax, (47, 30), (47, 27.0))
    arrow(ax, (47, 18), (47, 15.5))
    arrow(ax, (33.4, 11.5), (33.4, 42.0))

    box(ax, 70, 5, 27, 45, "", fc=C_BOX, ec=C_EDGE, lw=1.0,
        style="round,pad=0.2", zorder=1)
    ax.text(83.5, 52.6, "下层：无冲突路由", ha="center",
            va="center", fontsize=9.5, fontweight="bold")
    box(ax, 72, 35.5, 23, 9.5, "时间窗 Dijkstra\n走廊网络上\n最早到达搜索", fs=8.0)
    box(ax, 72, 21, 23, 9.5, "预约表\n走廊占用与车头时距", fs=8.0)
    box(ax, 72, 8, 23, 8, "试算路由后回滚\n（不留占用痕迹）",
        ec=C_DEC, lw=1.0, color=C_DEC, fs=8.0)
    arrow(ax, (80, 35.5), (80, 30.5))
    arrow(ax, (88, 30.5), (88, 35.5))
    arrow(ax, (83.5, 21), (83.5, 16.0), ls=(0, (2, 1.6)), color=C_DEC)

    arrow(ax, (59.5, 24.0), (72.0, 40.0), color=C_EDGE, lw=1.1, rad=-0.15)
    ax.text(68.2, 29.5, "路由\n请求", ha="center", va="center",
            fontsize=7.2, color=C_EDGE)

    arrow(ax, (72.0, 11.5), (59.5, 20.5), color=C_DEC, lw=1.7, rad=-0.16, ms=9)
    badge(ax, 65.8, 15.0, 2, C_DEC)

    arrow(ax, (34.5, 9.0), (24.5, 18.0), color=C_EVAL, lw=1.7, rad=-0.18, ms=9)
    badge(ax, 29.3, 12.8, 1, C_EVAL)

    arrow(ax, (24.5, 42.5), (34.5, 42.5), color=C_EDGE, lw=1.1)
    ax.text(29.5, 44.4, "候选解", ha="center", va="center", fontsize=7.2,
            color=C_EDGE)

    badge(ax, 3.5, 2.9, 1, C_EVAL)
    ax.text(6.5, 2.9, "通路一：回传无冲突时间表作为适应度  →  每个候选解一次",
            ha="left", va="center", fontsize=8.0, color=C_EVAL)
    badge(ax, 3.5, 0.6, 2, C_DEC)
    ax.text(6.5, 0.6, "通路二：回传可实现的送达时刻  →  每个运输任务一次",
            ha="left", va="center", fontsize=8.0, color=C_DEC)

    stem = os.path.join(HERE, "fig_framework_CN")
    fig.savefig(stem + ".pdf", bbox_inches="tight", pad_inches=0.05)
    fig.savefig(stem + ".png", dpi=200, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print("wrote", stem + ".pdf/.png")


if __name__ == "__main__":
    main()
