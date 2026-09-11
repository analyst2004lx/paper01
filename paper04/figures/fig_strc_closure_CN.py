"""闭包构造示意中文版：种子→依赖边→传递闭包。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_closure_CN")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"],
    "axes.unicode_minus": False,
})


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.15),
                             gridspec_kw={"width_ratios": [1.15, 1.0]})

    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.5)
    ax.axis("off")
    ax.set_title("(a) 被阻断走廊上的种子", fontsize=9)

    for y, lab in ((5.0, r"$e^\star$"), (3.2, r"$e_2$"), (1.4, r"$e_3$")):
        ax.text(0.2, y + 0.35, lab, fontsize=8, va="center", color="#444")
        ax.plot([1.0, 9.5], [y, y], color="#ccc", lw=0.8)

    ax.add_patch(Rectangle((3.4, 4.75), 2.0, 0.9, facecolor="#e8a0a0",
                            edgecolor="#8b1e1e", hatch="////", alpha=0.9))
    ax.text(4.4, 5.2, "阻断", ha="center", va="center", fontsize=7,
            color="#5a1010", fontweight="bold")

    nodes = {
        "r1": (2.2, 5.2, "#c45c26", "种子"),
        "r2": (6.2, 5.2, "#1f4e79", ""),
        "r3": (3.5, 3.4, "#1f4e79", "等待"),
        "r4": (6.5, 3.4, "#5a7a9a", ""),
        "r5": (4.5, 1.6, "#5a7a9a", "工序"),
        "r6": (7.5, 1.6, "#9aa8b5", "外侧"),
    }
    for name, (x, y, c, tag) in nodes.items():
        ax.add_patch(Circle((x, y), 0.38, facecolor=c, edgecolor="#222",
                            lw=0.9, zorder=3))
        ax.text(x, y, name, ha="center", va="center", fontsize=7,
                color="white", fontweight="bold", zorder=4)
        if tag:
            ax.text(x, y - 0.65, tag, ha="center", fontsize=6.5, color="#555")

    ax.text(5, 0.35, r"种子 = 与 $e^\star$ 阻断重叠的预约",
            ha="center", fontsize=7.5, color="#8b1e1e")

    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.5)
    ax.axis("off")
    ax.set_title("(b) 依赖边与闭包", fontsize=9)

    pos = {
        "r1": (2.0, 5.0), "r2": (5.0, 5.0), "r3": (2.0, 3.0),
        "r4": (5.0, 3.0), "r5": (3.5, 1.2), "r6": (7.5, 2.2),
    }
    closed = {"r1", "r2", "r3", "r4", "r5"}
    colors = {n: ("#c45c26" if n == "r1" else "#1f4e79") for n in closed}
    colors["r6"] = "#b0b8c0"

    edges = [("r1", "r2"), ("r1", "r3"), ("r3", "r4"), ("r3", "r5"), ("r4", "r5")]
    for a, b in edges:
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#555", lw=1.1,
                                    connectionstyle="arc3,rad=0.08"),
                    zorder=1)
    ax.text(7.5, 3.1, "闭包无出边", ha="center", fontsize=6.5, color="#666")

    for name, (x, y) in pos.items():
        ax.add_patch(Circle((x, y), 0.42, facecolor=colors[name],
                            edgecolor="#222", lw=1.0, zorder=3))
        ax.text(x, y, name, ha="center", va="center", fontsize=7.5,
                color="white", fontweight="bold", zorder=4)

    ax.add_patch(FancyBboxPatch(
        (1.2, 0.55), 4.8, 5.2, boxstyle="round,pad=0.15,rounding_size=0.2",
        facecolor="none", edgecolor="#1f4e79", lw=1.4, linestyle="--", zorder=0))
    ax.text(3.6, 6.05, r"$\mathrm{Cl}(\mathrm{Seeds})$", ha="center",
            fontsize=8.5, color="#1f4e79", fontweight="bold")
    ax.text(7.5, 1.2, "外侧\n（冻结）", ha="center", fontsize=7, color="#666")

    fig.tight_layout()
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png")
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
