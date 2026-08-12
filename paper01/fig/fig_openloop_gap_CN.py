# -*- coding: utf-8 -*-
"""开环/常数矩阵缺口示意（开题图5-1）。对照 paper01 动机：拥堵难回馈指派。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 200,
})


def rbox(ax, x, y, w, h, text, fc="#f7f7f7", ec="#333", fs=9, weight="normal"):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.08",
        facecolor=fc, edgecolor=ec, linewidth=1.2, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight=weight, zorder=3, linespacing=1.3)


def arr(ax, p, q, color="#333", lw=1.4):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=12, linewidth=lw,
        color=color, shrinkA=2, shrinkB=2, zorder=4))


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.0))
    for ax in axes:
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)
        ax.axis("off")

    # ---- (a) 开环两阶段 ----
    ax = axes[0]
    ax.set_title("(a) 开环 / 两阶段结构（常见做法）", fontsize=11, fontweight="bold", pad=8)
    rbox(ax, 1.2, 6.2, 7.6, 1.2, "上层：在常数运输时间矩阵上\n做机器指派与工序排序", fc="#e8eef7")
    arr(ax, (5, 6.2), (5, 5.35))
    rbox(ax, 1.2, 4.0, 7.6, 1.2, "冻结排产方案", fc="#f0f0f0")
    arr(ax, (5, 4.0), (5, 3.15))
    rbox(ax, 1.2, 1.6, 7.6, 1.4, "下层：再消解 AGV 冲突 /\n对时间轴做一次修复", fc="#f7ebe3")
    ax.text(5, 0.55, "拥堵只改变到达时刻，\n难以回头改指派与排序",
            ha="center", va="center", fontsize=8.5, color="#a04000",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff8f0", edgecolor="#d95f02"))

    # ---- (b) 权衡写不出来 ----
    ax = axes[1]
    ax.set_title("(b) 为何需要闭环：指派权衡依赖真实拥堵", fontsize=11, fontweight="bold", pad=8)

    # simple layout sketch
    ax.add_patch(Rectangle((0.8, 1.2), 8.4, 5.6, fill=False, ec="#888", lw=1.0, ls="--"))
    ax.text(1.0, 6.5, "装卸站", fontsize=8, color="#444")
    ax.add_patch(FancyBboxPatch((1.2, 3.5), 1.4, 1.0, boxstyle="round,pad=0.15",
                                facecolor="#dceaf8", edgecolor="#08519c"))
    ax.text(1.9, 4.0, "LU", ha="center", va="center", fontsize=9, fontweight="bold")

    ax.add_patch(FancyBboxPatch((6.8, 5.2), 1.8, 1.0, boxstyle="round,pad=0.15",
                                facecolor="#e8f5e9", edgecolor="#2e7d32"))
    ax.text(7.7, 5.7, "快臂\n(远端)", ha="center", va="center", fontsize=8)

    ax.add_patch(FancyBboxPatch((6.8, 2.0), 1.8, 1.0, boxstyle="round,pad=0.15",
                                facecolor="#fff3e0", edgecolor="#ef6c00"))
    ax.text(7.7, 2.5, "慢臂\n(近端/通路好)", ha="center", va="center", fontsize=8)

    # corridors
    ax.annotate("", xy=(6.8, 5.6), xytext=(2.6, 4.2),
                arrowprops=dict(arrowstyle="->", color="#c62828", lw=2.0))
    ax.text(4.2, 5.35, "走廊拥堵\n(让行等待)", color="#c62828", fontsize=8, ha="center")

    ax.annotate("", xy=(6.8, 2.5), xytext=(2.6, 3.7),
                arrowprops=dict(arrowstyle="->", color="#2e7d32", lw=1.6))
    ax.text(4.0, 2.55, "通路更畅", color="#2e7d32", fontsize=8, ha="center")

    ax.text(5, 0.45,
            "常数矩阵看不见让行 → 总选快臂；\n闭环用真实路由评价 → 慢臂可能更优",
            ha="center", va="center", fontsize=8.5, color="#111",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f7f7f7", edgecolor="#666"))

    fig.tight_layout()
    stem = os.path.join(HERE, "fig_openloop_gap_CN")
    fig.savefig(stem + ".pdf", bbox_inches="tight", pad_inches=0.08)
    fig.savefig(stem + ".png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote", stem + ".pdf/.png")


if __name__ == "__main__":
    main()
