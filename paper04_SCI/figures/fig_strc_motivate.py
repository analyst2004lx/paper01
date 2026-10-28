"""动机图:走廊阻断下任务图空洞 vs 预约表级联。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_motivate")


def _box(ax, xy, w, h, text, fc, ec="#333", fs=8, bold=False):
    x, y = xy
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=ec, linewidth=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight=("bold" if bold else "normal"),
            color="#1a1a1a", wrap=True)


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2))

    # ----- Left: task graph -----
    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Task graph under corridor block", fontsize=9, pad=6)

    # ops
    ops = [
        (1.2, 7.2, "J1-1"), (4.2, 7.2, "J1-2"), (7.2, 7.2, "J1-3"),
        (1.2, 4.0, "J2-1"), (4.2, 4.0, "J2-2"), (7.2, 4.0, "J2-3"),
    ]
    for x, y, lab in ops:
        _box(ax, (x, y), 1.8, 1.1, lab, "#e8eef5")
    # precedence arrows
    for (x1, y1, _), (x2, y2, _) in zip(ops, ops[1:]):
        if y1 == y2:
            ax.annotate("", xy=(x2, y2 + 0.55), xytext=(x1 + 1.8, y1 + 0.55),
                        arrowprops=dict(arrowstyle="->", color="#555", lw=1.0))
    ax.text(5, 2.3, r"$T_{\mathrm{direct}}=\varnothing$",
            ha="center", fontsize=10, fontweight="bold", color="#8b1e1e")
    ax.text(5, 1.2, "Task-graph rule: no reschedule",
            ha="center", fontsize=8, color="#8b1e1e")
    _box(ax, (2.5, 8.8), 5, 0.9, "Corridor block (no op / no machine hit)",
         "#f7e6e6", ec="#8b1e1e", fs=7.5)

    # ----- Right: reservation cascade -----
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Reservation table cascade (STRC)", fontsize=9, pad=6)

    # time axis
    ax.plot([1.0, 9.2], [2.0, 2.0], color="#444", lw=1.0)
    ax.text(9.3, 2.0, "t", va="center", fontsize=8)
    # corridor lanes
    lanes = [
        (6.5, "e*", "#f7e6e6", True),
        (4.8, "e2", "#e8eef5", False),
        (3.1, "e3", "#e8eef5", False),
    ]
    # blocked window on e*
    ax.add_patch(Rectangle((3.5, 6.2), 2.2, 1.1, facecolor="#e8a0a0",
                            edgecolor="#8b1e1e", hatch="////", alpha=0.85))
    ax.text(4.6, 6.75, "block", ha="center", va="center", fontsize=7,
            color="#5a1010", fontweight="bold")

    # reservations
    bars = [
        (1.2, 6.35, 2.0, 0.8, "r1 seed", "#c45c26"),
        (5.9, 6.35, 2.0, 0.8, "r2", "#1f4e79"),
        (2.5, 4.65, 2.4, 0.8, "r3 wait", "#1f4e79"),
        (5.2, 4.65, 2.2, 0.8, "r4", "#5a7a9a"),
        (3.0, 2.95, 2.6, 0.8, "r5 job/AGV", "#5a7a9a"),
    ]
    for x, y, w, h, lab, c in bars:
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.03",
            facecolor=c, edgecolor="#222", alpha=0.9))
        ax.text(x + w / 2, y + h / 2, lab, ha="center", va="center",
                fontsize=7, color="white", fontweight="bold")

    # cascade arrows
    ax.annotate("", xy=(3.6, 5.45), xytext=(2.8, 6.35),
                arrowprops=dict(arrowstyle="->", color="#c45c26", lw=1.3))
    ax.annotate("", xy=(4.2, 3.75), xytext=(3.6, 4.65),
                arrowprops=dict(arrowstyle="->", color="#c45c26", lw=1.3))
    ax.text(8.2, 5.2, "closure\nCl(Seeds)", ha="center", fontsize=8,
            color="#1f4e79", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="#e8eef5", ec="#1f4e79"))

    ax.text(5, 0.7, "Must repair on reservation closure",
            ha="center", fontsize=8, color="#1f4e79", fontweight="bold")

    for ax, y, lab in ((axes[1], 6.75, r"corridor $e^\star$"),
                       (axes[1], 5.05, r"corridor $e_2$"),
                       (axes[1], 3.35, r"corridor $e_3$")):
        ax.text(0.35, y, lab, fontsize=7, va="center", color="#444")

    fig.tight_layout()
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png")
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
