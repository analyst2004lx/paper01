# -*- coding: utf-8 -*-
"""两张图对照：G_T 顶点是工序，G_R 顶点是预约；右侧标出四类依赖边。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_graphs_CN")

from _cjk_mpl import setup_cjk

setup_cjk()
plt.rcParams.update({"figure.dpi": 200})


def _box(ax, xy, w, h, text, fc, ec="#333333", fs=7.5):
    x, y = xy
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=ec, linewidth=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color="#1a1a1a")


def _node(ax, xy, lab, fc, radius=0.42):
    ax.add_patch(Circle(xy, radius, facecolor=fc, edgecolor="#222222", lw=0.9, zorder=3))
    ax.text(xy[0], xy[1], lab, ha="center", va="center", fontsize=7,
            color="white", fontweight="bold", zorder=4)


def _arrow(ax, p, q, color, style="-", lw=1.3):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=10,
        linestyle=style, linewidth=lw, color=color,
        shrinkA=8, shrinkB=8, zorder=2))


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.7))

    # ---- (a) G_T ----
    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title(r"(a) 工序依赖图 $G_T$（顶点 = 工序）", fontsize=9.5, pad=8)

    ops = [
        (0.7, 5.9, r"$O_{11}$"), (3.9, 5.9, r"$O_{12}$"), (7.1, 5.9, r"$O_{13}$"),
        (0.7, 2.9, r"$O_{21}$"), (3.9, 2.9, r"$O_{22}$"),
    ]
    for x, y, lab in ops:
        _box(ax, (x, y), 2.0, 1.15, lab, "#e8eef5")
    for (x1, y1, _), (x2, y2, _) in (
        (ops[0], ops[1]), (ops[1], ops[2]), (ops[3], ops[4]),
    ):
        ax.annotate("", xy=(x2, y2 + 0.58), xytext=(x1 + 2.0, y1 + 0.58),
                    arrowprops=dict(arrowstyle="->", color="#2e7d4f", lw=1.15))
    ax.text(3.35, 7.25, "工件先后", fontsize=7, color="#2e7d4f", ha="center")
    ax.annotate("", xy=(4.9, 4.05), xytext=(4.9, 5.9),
                arrowprops=dict(arrowstyle="->", color="#6b4c7a",
                                lw=1.15, linestyle="--"))
    ax.text(5.05, 4.95, r"机器先后（$O_{12}$、$O_{22}$ 在同一台机器上）",
            fontsize=7, color="#6b4c7a", va="center")

    ax.add_patch(Rectangle((2.3, 8.45), 5.4, 1.0, facecolor="#f7e6e6",
                            edgecolor="#8b1e1e", lw=1.0, linestyle="--"))
    ax.text(5.0, 8.95, r"走廊 $e^\star$ 阻断", ha="center", va="center",
            fontsize=8, color="#8b1e1e")
    ax.text(5.0, 7.85, "不作用于任何工序", ha="center", va="center",
            fontsize=7.5, color="#8b1e1e")
    ax.text(5.0, 1.55, "没有起点工序，划出的范围为空",
            ha="center", fontsize=9, fontweight="bold", color="#8b1e1e")
    ax.text(5.0, 0.65, "顶点只有工序，图中没有走廊占用",
            ha="center", fontsize=8, color="#555555")

    # ---- (b) G_R ----
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title(r"(b) 预约依赖图 $G_R$（顶点 = 走廊占用）", fontsize=9.5, pad=8)

    pos = {
        "p1": (1.4, 7.2),
        "p2": (5.0, 7.2),
        "p3": (8.6, 7.2),
        "p4": (5.0, 3.9),
    }
    _node(ax, pos["p1"], r"$\rho_1$", "#c45c26")
    _node(ax, pos["p2"], r"$\rho_2$", "#1f4e79")
    _node(ax, pos["p3"], r"$\rho_3$", "#1f4e79")
    _node(ax, pos["p4"], r"$\rho_4$", "#1f4e79")
    sub = {
        "p1": "$k_1$ 在 $e^\\star$ 上\n送往 $O_{12}$（起点）",
        "p2": "$k_1$ 在 $e_2$ 上\n送往 $O_{12}$",
        "p3": "$k_3$ 在 $e_3$ 上\n送往 $O_{13}$",
        "p4": "$k_2$ 在 $e^\\star$ 上\n送往 $O_{22}$",
    }
    for k, (x, y) in pos.items():
        yy = y + 0.75 if k != "p4" else y - 0.75
        va = "bottom" if k != "p4" else "top"
        ax.text(x, yy, sub[k], ha="center", va=va, fontsize=6.6,
                color=("#8b1e1e" if k == "p1" else "#333333"), linespacing=1.15)

    c_yield, c_agv, c_job, c_mach = "#c45c26", "#1f4e79", "#2e7d4f", "#6b4c7a"
    _arrow(ax, pos["p1"], pos["p2"], c_agv)               # 车辆接续
    _arrow(ax, pos["p2"], pos["p3"], c_job)               # 工件接续:O12 -> O13
    _arrow(ax, pos["p1"], pos["p4"], c_yield)             # 让行:同在 e*
    _arrow(ax, pos["p2"], pos["p4"], c_mach, style="--")  # 机器接续:O12 -> O22

    ax.text(3.2, 6.95, "车辆接续", fontsize=7, color=c_agv, fontweight="bold", ha="center", va="top")
    ax.text(6.8, 6.95, "工件接续", fontsize=7, color=c_job, fontweight="bold", ha="center", va="top")
    ax.text(2.75, 5.2, "让行", fontsize=7, color=c_yield, fontweight="bold", ha="center")
    ax.text(5.3, 5.55, "机器接续", fontsize=7, color=c_mach, fontweight="bold", ha="left")

    ax.text(5.0, 1.55, r"从起点 $\rho_1$ 沿边可达 $\rho_2$、$\rho_3$、$\rho_4$",
            ha="center", fontsize=9, fontweight="bold", color="#1f4e79")
    ax.text(5.0, 0.65, "工件接续边、机器接续边分别对应 (a) 中的工件先后、机器先后",
            ha="center", fontsize=7.5, color="#555555")

    handles = [
        Line2D([0], [0], color=c_yield, lw=1.6, label="让行边"),
        Line2D([0], [0], color=c_agv, lw=1.6, label="车辆接续边"),
        Line2D([0], [0], color=c_job, lw=1.6, label="工件接续边"),
        Line2D([0], [0], color=c_mach, lw=1.6, linestyle="--", label="机器接续边"),
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.06),
              fontsize=6.8, frameon=False, ncol=4, handlelength=1.6,
              columnspacing=0.8)

    fig.tight_layout()
    fig.savefig(OUT + ".pdf", bbox_inches="tight")
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
