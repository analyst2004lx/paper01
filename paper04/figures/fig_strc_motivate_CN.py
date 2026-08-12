# -*- coding: utf-8 -*-
"""动机图中文版：走廊阻断下任务图空洞 vs 预约级联。原 fig_strc_motivate.* 保留。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_motivate_CN")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 200,
})


def _box(ax, xy, w, h, text, fc, ec="#333", fs=8, bold=False):
    x, y = xy
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=ec, linewidth=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight=("bold" if bold else "normal"),
            color="#1a1a1a")


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.4))

    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("走廊阻断下的任务依赖图", fontsize=10, pad=6)

    ops = [
        (1.2, 7.2, "J1-1"), (4.2, 7.2, "J1-2"), (7.2, 7.2, "J1-3"),
        (1.2, 4.0, "J2-1"), (4.2, 4.0, "J2-2"), (7.2, 4.0, "J2-3"),
    ]
    for x, y, lab in ops:
        _box(ax, (x, y), 1.8, 1.1, lab, "#e8eef5")
    for (x1, y1, _), (x2, y2, _) in zip(ops, ops[1:]):
        if y1 == y2:
            ax.annotate("", xy=(x2, y2 + 0.55), xytext=(x1 + 1.8, y1 + 0.55),
                        arrowprops=dict(arrowstyle="->", color="#555", lw=1.0))
    ax.text(5, 2.3, r"$T_{\mathrm{direct}}=\varnothing$",
            ha="center", fontsize=11, fontweight="bold", color="#8b1e1e")
    ax.text(5, 1.2, "任务图规则：判定无需重调度",
            ha="center", fontsize=9, color="#8b1e1e")
    _box(ax, (2.2, 8.8), 5.6, 0.9, "走廊阻断（未命中任何工序/机器）",
         "#f7e6e6", ec="#8b1e1e", fs=8)

    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("预约表上级联（STRC）", fontsize=10, pad=6)

    ax.plot([1.0, 9.2], [2.0, 2.0], color="#444", lw=1.0)
    ax.text(9.3, 2.0, "t", va="center", fontsize=8)
    ax.add_patch(Rectangle((3.5, 6.2), 2.2, 1.1, facecolor="#e8a0a0",
                            edgecolor="#8b1e1e", hatch="////", alpha=0.85))
    ax.text(4.6, 6.75, "阻断", ha="center", va="center", fontsize=7.5,
            color="#5a1010", fontweight="bold")

    bars = [
        (1.2, 6.35, 2.0, 0.8, "r1 种子", "#c45c26"),
        (5.9, 6.35, 2.0, 0.8, "r2", "#1f4e79"),
        (2.5, 4.65, 2.4, 0.8, "r3 等待", "#1f4e79"),
        (5.2, 4.65, 2.2, 0.8, "r4", "#5a7a9a"),
        (3.0, 2.95, 2.6, 0.8, "r5 工件/车", "#5a7a9a"),
    ]
    for x, y, w, h, lab, c in bars:
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.03",
            facecolor=c, edgecolor="#222", alpha=0.9))
        ax.text(x + w / 2, y + h / 2, lab, ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold")

    ax.annotate("", xy=(3.6, 5.45), xytext=(2.8, 6.35),
                arrowprops=dict(arrowstyle="->", color="#c45c26", lw=1.3))
    ax.annotate("", xy=(4.2, 3.75), xytext=(3.6, 4.65),
                arrowprops=dict(arrowstyle="->", color="#c45c26", lw=1.3))
    ax.text(8.2, 5.2, "闭包\nCl(Seeds)", ha="center", fontsize=8.5,
            color="#1f4e79", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="#e8eef5", ec="#1f4e79"))

    ax.text(5, 0.7, "须在预约影响闭包上修复",
            ha="center", fontsize=9, color="#1f4e79", fontweight="bold")

    for y, lab in ((6.75, r"走廊 $e^\star$"), (5.05, r"走廊 $e_2$"),
                   (3.35, r"走廊 $e_3$")):
        ax.text(0.2, y, lab, fontsize=7.5, va="center", color="#444")

    fig.tight_layout()
    fig.savefig(OUT + ".pdf", bbox_inches="tight")
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
