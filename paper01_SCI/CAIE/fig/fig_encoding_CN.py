# -*- coding: utf-8 -*-
"""文化基因算法在本文中的一代（中文示意，配合第 4.2 节）。

与框架图分工：框架图画双层与通路 1/2；本图画上层一轮——
编码（不含 AGV）→ 解码评价（下层给出 C_max 与让行记录）→
按让行记录局部搜索 → 选择/交叉/变异进入下一代。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

from _style import use_cjk  # noqa: E402

use_cjk()
plt.rcParams["figure.dpi"] = 200

C_EDGE = "#5a5a5a"
C_BOX = "#f7f7f7"
C_INNER = "#ffffff"
C_MS = "#2171b5"
C_OS = "#238b45"
C_DEC = "#d95f02"
C_OUT = "#08519c"
C_LS = "#6a3d9a"
C_MUTE = "#8a8a8a"


def rbox(ax, x, y, w, h, fc=C_INNER, ec=C_EDGE, lw=1.0, z=3):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.28", linewidth=lw,
        facecolor=fc, edgecolor=ec, zorder=z))


def arrow(ax, p, q, color=C_EDGE, lw=1.05, ms=8, rad=0.0, z=6):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=ms, linewidth=lw, color=color,
        connectionstyle="arc3,rad=%.2f" % rad, shrinkA=2, shrinkB=2, zorder=z))


def genes(ax, x0, y, vals, ec, cell_w=5.6, cell_h=3.4, fs=8.5):
    for i, v in enumerate(vals):
        x = x0 + i * cell_w
        ax.add_patch(Rectangle(
            (x, y), cell_w - 0.3, cell_h, facecolor=C_INNER, edgecolor=ec,
            linewidth=1.05, zorder=4))
        ax.text(x + (cell_w - 0.3) / 2, y + cell_h / 2, v, ha="center",
                va="center", fontsize=fs, fontweight="bold", color=ec, zorder=5)


def main() -> None:
    fig, ax = plt.subplots(figsize=(12.0, 5.6))
    ax.set_xlim(0, 112)
    ax.set_ylim(-0.5, 58)
    ax.axis("off")

    ax.text(56, 55.5,
            "文化基因算法在本文中的一代：评价依赖下层无冲突规划；"
            "局部搜索由让行记录驱动；AGV 不进入染色体",
            ha="center", va="center", fontsize=8.6, color=C_EDGE)

    # A chromosome
    rbox(ax, 2, 28, 28, 24, fc=C_BOX, ec=C_EDGE, lw=1.05)
    ax.text(16, 49.5, "A  染色体（两段）", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color=C_EDGE)

    ax.text(4.2, 45.2, "机器指派", ha="left", va="center",
            fontsize=7.4, color=C_MS, fontweight="bold")
    genes(ax, 4.0, 41.6, ["M1", "M2", "M2", "M1"], C_MS)
    ax.text(16, 40.4, r"固定枚举 $O_{11},O_{12},O_{21},O_{22}$",
            ha="center", va="top", fontsize=6.4, color=C_MS)

    ax.text(4.2, 37.0, "工序序列", ha="left", va="center",
            fontsize=7.4, color=C_OS, fontweight="bold")
    genes(ax, 4.0, 33.2, ["1", "2", "1", "2"], C_OS)
    ax.text(16, 32.0, "执行先后（工件号重复出现）",
            ha="center", va="top", fontsize=6.4, color=C_OS)

    ax.add_patch(Rectangle(
        (4.0, 29.0), 24, 2.4, facecolor="#fff7f0", edgecolor=C_DEC,
        linewidth=1.0, linestyle=(0, (2.5, 1.8)), zorder=4))
    ax.text(16, 30.2, "AGV 不在染色体中", ha="center", va="center",
            fontsize=7.2, color=C_DEC, fontweight="bold", zorder=5)

    # B evaluation
    rbox(ax, 34, 28, 42, 24, fc=C_BOX, ec=C_OUT, lw=1.15)
    ax.text(55, 49.5, "B  评价（解码器 + 下层）", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color=C_OUT)

    boxes_b = [
        (36.0, 40.5, 11.5, 6.5, "按序列\n逐道取工序\n查机器指派", C_OS),
        (49.5, 40.5, 12.0, 6.5, "换地点则\n生成运输任务\n调用下层", C_DEC),
        (63.5, 40.5, 10.5, 6.5, "承运 AGV\n送达时刻\n写入预约表", C_DEC),
    ]
    for x, y, w, h, t, c in boxes_b:
        rbox(ax, x, y, w, h, fc=C_INNER, ec=c, lw=1.05)
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center",
                fontsize=7.0, color=c, linespacing=1.2)
    arrow(ax, (47.6, 43.7), (49.3, 43.7), color=C_EDGE, lw=0.95, ms=7)
    arrow(ax, (61.6, 43.7), (63.3, 43.7), color=C_EDGE, lw=0.95, ms=7)

    ax.text(55, 38.4, "全部工序排完后得到", ha="center", va="center",
            fontsize=7.0, color=C_MUTE)

    rbox(ax, 36.5, 29.8, 16.5, 6.5, fc="#eef5fb", ec=C_OUT, lw=1.15)
    ax.text(44.75, 34.0, "适应度", ha="center", va="center",
            fontsize=7.0, color=C_OUT)
    ax.text(44.75, 31.5, r"$C_{\max}$（无冲突）", ha="center", va="center",
            fontsize=7.4, color=C_OUT, fontweight="bold")

    rbox(ax, 56.5, 29.8, 17.0, 6.5, fc="#f6f0fb", ec=C_LS, lw=1.15)
    ax.text(65.0, 34.0, "供局部搜索", ha="center", va="center",
            fontsize=7.0, color=C_LS)
    ax.text(65.0, 31.5, "让行记录", ha="center", va="center",
            fontsize=7.4, color=C_LS, fontweight="bold")

    # C local search
    rbox(ax, 80, 28, 30, 24, fc=C_BOX, ec=C_LS, lw=1.15)
    ax.text(95, 49.5, "C  局部搜索（memetic）", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color=C_LS)

    ax.text(95, 45.6, "由让行记录生成邻居", ha="center", va="center",
            fontsize=7.4, color=C_LS)

    rbox(ax, 82.5, 39.2, 11.5, 4.6, fc=C_INNER, ec=C_MS, lw=1.0)
    ax.text(88.25, 41.5, "改派机器", ha="center", va="center",
            fontsize=7.6, color=C_MS, fontweight="bold")
    rbox(ax, 95.5, 39.2, 12.0, 4.6, fc=C_INNER, ec=C_OS, lw=1.0)
    ax.text(101.5, 41.5, "错峰调序", ha="center", va="center",
            fontsize=7.6, color=C_OS, fontweight="bold")

    ax.text(95, 36.6, r"再解码；更好的 $C_{\max}$ 即接受",
            ha="center", va="center", fontsize=6.8, color=C_EDGE)
    ax.text(95, 34.0, "至多数轮；无改进则停止",
            ha="center", va="center", fontsize=6.8, color=C_MUTE)

    rbox(ax, 83.5, 29.4, 23, 3.0, fc="#f6f0fb", ec=C_LS, lw=1.0)
    ax.text(95, 30.9, "改进后的个体（仍为两段）",
            ha="center", va="center", fontsize=7.0, color=C_LS, fontweight="bold")

    arrow(ax, (30.2, 40.0), (33.6, 40.0), color=C_EDGE, lw=1.2, ms=9)
    arrow(ax, (73.8, 33.0), (79.6, 33.0), color=C_LS, lw=1.2, ms=9)
    ax.text(76.6, 35.2, "让行记录", ha="center", va="bottom",
            fontsize=6.4, color=C_LS)

    # D genetic ops
    rbox(ax, 2, 5.0, 76, 19.5, fc=C_BOX, ec=C_EDGE, lw=1.05)
    ax.text(40, 22.0, "D  遗传操作与终止", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color=C_EDGE)

    ops = [
        (5.5, 12.2, 14, 7.0, "选择", "锦标赛\n保留精英", C_EDGE),
        (22.5, 12.2, 16, 7.0, "交叉", "工序：顺序交叉\n机器：均匀交叉", C_MS),
        (41.5, 12.2, 16, 7.0, "变异", "交换序列位置\n或改派机器", C_OS),
        (60.5, 12.2, 14.5, 7.0, "终止？", "预算用尽或\n连续无改进", C_OUT),
    ]
    for x, y, w, h, title, body, c in ops:
        rbox(ax, x, y, w, h, fc=C_INNER, ec=c, lw=1.05)
        ax.text(x + w / 2, y + h - 1.5, title, ha="center", va="center",
                fontsize=8.0, fontweight="bold", color=c)
        ax.text(x + w / 2, y + 2.5, body, ha="center", va="center",
                fontsize=6.6, color=C_EDGE, linespacing=1.2)
    for x in (19.7, 38.7, 57.7):
        arrow(ax, (x, 15.7), (x + 2.5, 15.7), color=C_EDGE, lw=0.95, ms=7)

    ax.text(67.7, 10.5, "否", ha="center", va="center", fontsize=7.0, color=C_EDGE)
    ax.text(75.5, 15.7, "是", ha="left", va="center", fontsize=7.0, color=C_OUT)

    # E output
    rbox(ax, 82, 5.0, 28, 19.5, fc="#eef5fb", ec=C_OUT, lw=1.2)
    ax.text(96, 22.0, "E  输出", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color=C_OUT)
    ax.text(96, 16.8, "搜索所得最好染色体", ha="center", va="center",
            fontsize=7.6, color=C_OUT)
    ax.text(96, 13.5, "对应的无冲突时间表", ha="center", va="center",
            fontsize=7.6, color=C_OUT)
    ax.text(96, 9.8, r"及其 $C_{\max}$", ha="center", va="center",
            fontsize=8.2, color=C_OUT, fontweight="bold")
    ax.text(96, 6.6, "可行来自解码与下层规划", ha="center", va="center",
            fontsize=6.6, color=C_MUTE)

    # C -> D
    arrow(ax, (84.0, 30.9), (70.0, 24.6), color=C_EDGE, lw=1.05, ms=8, rad=0.12)
    ax.text(74.5, 28.6, "进入种群", ha="center", va="center",
            fontsize=6.4, color=C_EDGE)

    # terminate yes -> E
    arrow(ax, (75.2, 15.7), (81.6, 15.7), color=C_OUT, lw=1.15, ms=9)

    # next generation loop
    ax.annotate(
        "", xy=(16, 28.0), xytext=(67.7, 11.2),
        arrowprops=dict(
            arrowstyle="-|>", color=C_EDGE, lw=1.15,
            connectionstyle="arc3,rad=0.32", mutation_scale=9),
        zorder=6)
    ax.text(42, 1.2, "下一代（回到评价）", ha="center", va="center",
            fontsize=7.2, color=C_EDGE)

    stem = os.path.join(HERE, "fig_encoding_CN")
    fig.savefig(stem + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(stem + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", stem + ".pdf/.png")


if __name__ == "__main__":
    main()
