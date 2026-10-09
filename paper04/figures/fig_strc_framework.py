"""STRC 框架总图:测量(闭包)→有界协调→对照臂。无需实验数据。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_framework")

C_MEAS = "#1f4e79"
C_REP = "#2d6a4f"
C_CTRL = "#c45c26"
C_BOX = "#f7f7f7"
C_EDGE = "#444444"


def box(ax, x, y, w, h, text, fc=C_BOX, ec=C_EDGE, fs=8, bold=False, tc="#111111"):
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
    fig, ax = plt.subplots(figsize=(7.6, 3.7))
    ax.set_xlim(0, 14)
    ax.set_ylim(-0.15, 8)
    ax.axis("off")

    # Input
    box(ax, 0.3, 5.6, 2.6, 1.6,
        "Feasible schedule\n$\\mathcal{S}^0=(x,\\pi,y,R)$\n+ disturbance $\\mathcal{D}$",
        fc="#eef2f6", fs=7.5)

    # Measure strip
    ax.add_patch(Rectangle((3.3, 5.3), 5.0, 2.2, facecolor="#e8eef5",
                            edgecolor=C_MEAS, lw=1.2, alpha=0.55, zorder=0))
    ax.text(5.8, 7.2, "Delineate scope (STRC)", ha="center", fontsize=8,
            color=C_MEAS, fontweight="bold")
    box(ax, 3.5, 5.6, 2.1, 1.4, "Seeds\noverlap blockage", fc="#dce6f1",
        ec=C_MEAS, fs=7.5, tc=C_MEAS)
    box(ax, 6.0, 5.6, 2.1, 1.4, "Impact set\n$U=\\mathrm{Cl}(S)$", fc="#dce6f1",
        ec=C_MEAS, fs=7.5, bold=True, tc=C_MEAS)

    # Repair strip
    ax.add_patch(Rectangle((8.7, 5.3), 5.0, 2.2, facecolor="#e9f5ee",
                            edgecolor=C_REP, lw=1.2, alpha=0.55, zorder=0))
    ax.text(11.2, 7.2, "Bounded repair (level-1 rerouting)", ha="center", fontsize=8,
            color=C_REP, fontweight="bold")
    box(ax, 8.9, 5.6, 2.2, 1.4, "Keep rest as planned\nReroute inside $U$",
        fc="#d8efe3", ec=C_REP, fs=7.2, tc=C_REP)
    box(ax, 11.4, 5.6, 2.1, 1.4, "Validate\n$\\mathcal{S}'$",
        fc="#d8efe3", ec=C_REP, fs=7.5, tc=C_REP)

    arrow(ax, 2.9, 6.4, 3.5, 6.4, C_MEAS)
    arrow(ax, 5.6, 6.4, 6.0, 6.4, C_MEAS)
    arrow(ax, 8.1, 6.4, 8.9, 6.4, C_REP)
    arrow(ax, 11.1, 6.4, 11.4, 6.4, C_REP)

    # Escalate branch
    box(ax, 8.9, 3.2, 4.6, 1.3,
        "If infeasible: escalate $U$\njob suffix $\\rightarrow$ same-vehicle suffix\n$\\rightarrow$ all unfinished occupancies",
        fc="#fff4e8", ec=C_CTRL, fs=7.2, tc="#7a3b10")
    arrow(ax, 10.0, 5.6, 10.0, 4.5, C_CTRL)
    ax.annotate("", xy=(12.4, 5.6), xytext=(12.4, 4.5),
                arrowprops=dict(arrowstyle="->", color=C_CTRL, lw=1.1))

    # Controls
    box(ax, 0.3, 1.0, 4.0, 1.6,
        "Baseline R1\nsame level-1 rerouting\n$U\\leftarrow$ affected set on $G_T$",
        fc="#fdeee6", ec=C_CTRL, fs=7.2, tc="#7a3b10")
    box(ax, 4.8, 1.0, 4.0, 1.6,
        "Baseline R0+\nwarm-started global rescheduling\nwall-clock budget",
        fc="#fdeee6", ec=C_CTRL, fs=7.2, tc="#7a3b10")
    box(ax, 9.3, 1.0, 4.4, 1.6,
        "Outputs\nfeasibility, runtime, $C_{\\max}$,\nrewrite fraction",
        fc="#eef2f6", fs=7.5)

    ax.text(7.0, 0.32,
            "Same network, time-window router, and conflict-free check;",
            ha="center", fontsize=7.5, color="#555555", style="italic")
    ax.text(7.0, 0.02,
            "only the rewritable set or the search differs.",
            ha="center", fontsize=7.5, color="#555555", style="italic")

    fig.tight_layout()
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png")
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
