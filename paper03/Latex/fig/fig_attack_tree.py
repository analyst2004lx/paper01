# -*- coding: utf-8 -*-
"""Attacker decision tree P1--P4 (paper03 fig:attack-tree)."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_attack_tree")

plt.rcParams.update({
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "dejavusans",
    "figure.dpi": 200,
})

C_EDGE = "#333333"
C_NOTE = "#555555"
C_FAIL = "#e6e6e6"
C_DEC = "#e4e4e4"
C_ATK = "#f6d6d6"
C_DET = "#d9ecd9"


def rbox(ax, cx, cy, w, h, text, fc, fs=7.6):
    x, y = cx - w / 2, cy - h / 2
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=C_EDGE, linewidth=1.0, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=fs, color="#111", zorder=4, linespacing=1.2)
    return (cx, cy + h / 2), (cx, cy - h / 2), (cx - w / 2, cy), (cx + w / 2, cy)


def diamond(ax, cx, cy, w, h, text, fs=7.2):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=C_DEC,
                         edgecolor=C_EDGE, linewidth=1.0, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
            color="#111", zorder=4, linespacing=1.15)
    return (cx, cy + h / 2), (cx, cy - h / 2), (cx - w / 2, cy), (cx + w / 2, cy)


def arrow(ax, p, q):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=9, linewidth=1.1,
        color=C_EDGE, shrinkA=0.4, shrinkB=0.4, zorder=2))


def main() -> None:
    fig, ax = plt.subplots(figsize=(9.6, 7.6))
    ax.set_xlim(-0.15, 14.7)
    ax.set_ylim(-0.70, 11.0)
    ax.axis("off")

    root = rbox(ax, 7.2, 10.15, 4.3, 1.05,
                "Hijacked device\nwants false ``done / idle''", C_FAIL, 8.0)
    q1 = diamond(ax, 7.2, 8.35, 2.7, 1.35, "Send\ncompletion?")
    d2 = rbox(ax, 1.15, 6.35, 2.15, 1.15,
              r"Silence:" + "\n" + r"missing $h_k$" + "\n" + r"($\sim$1.8 s)",
              C_DET, 6.8)
    p2 = rbox(ax, 3.65, 6.35, 2.15, 0.85, r"$\mathbf{P2}$ silence", C_ATK)
    q2 = diamond(ax, 9.55, 6.45, 2.6, 1.3, "Keep\nheartbeat?")

    d1 = rbox(ax, 3.45, 4.25, 2.2, 0.95, "Both:\nsilence faster", C_DET, 7.2)
    p1 = rbox(ax, 6.05, 4.25, 2.25, 0.95, r"$\mathbf{P1}$ lie," + "\nno heartbeat", C_ATK)
    p3 = rbox(ax, 10.75, 4.25, 2.25, 0.95, r"$\mathbf{P3}$ lie +" + "\n" + r"reveal $h_k$", C_ATK)
    d3 = rbox(ax, 13.40, 4.25, 2.30, 0.95, "Corr. only\n(silence DR${=}0$)", C_DET, 6.6)

    q3 = diamond(ax, 9.55, 2.15, 2.85, 1.35, "Collude with\ncounterpart?")
    p4 = rbox(ax, 9.35, 0.45, 3.15, 0.85, r"$\mathbf{P4}$ one-hop collusion", C_ATK)
    d4 = rbox(ax, 12.45, 0.45, 2.25, 0.95, "Next-hop\nhonest refute", C_DET, 7.2)

    arrow(ax, root[1], q1[0])
    arrow(ax, q1[2], p2[0])
    arrow(ax, q1[3], q2[2])
    arrow(ax, p2[2], d2[3])
    arrow(ax, q2[2], p1[0])
    arrow(ax, q2[3], p3[0])
    arrow(ax, p1[2], d1[3])
    arrow(ax, p3[3], d3[2])
    ax.plot([9.55, 9.55], [q2[1][1], q3[0][1]], color=C_EDGE, lw=1.1, zorder=2)
    arrow(ax, (9.55, q3[0][1] + 0.12), q3[0])
    arrow(ax, q3[1], p4[0])
    arrow(ax, p4[3], d4[2])

    ax.text(5.05, 7.45, "no", fontsize=7.2, color=C_NOTE, ha="center")
    ax.text(8.55, 7.55, "yes", fontsize=7.2, color=C_NOTE, ha="left")
    ax.text(7.45, 5.35, "no", fontsize=7.2, color=C_NOTE, ha="right")
    ax.text(10.55, 5.35, "yes", fontsize=7.2, color=C_NOTE, ha="left")
    ax.text(9.75, 1.20, "yes", fontsize=7.2, color=C_NOTE, ha="left")

    ax.text(7.2, -0.08,
            "P1--P3: no winning branch iff a counterpart exists;\n"
            "gap: P3 still escapes; P4 only defers",
            ha="center", va="top", fontsize=7.4, color="#777")

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
