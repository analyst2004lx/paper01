# -*- coding: utf-8 -*-
"""One generation of the memetic algorithm in this paper (EN, Section 4.2).

Complements the framework figure: that one shows the two layers and Paths 1/2;
this one shows one upper-layer generation---encoding without AGVs, evaluation
via the decoder and lower layer (C_max and yield records), contention-guided
local search, then selection / crossover / mutation for the next generation.
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

plt.rcParams["figure.dpi"] = 200
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]

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
            "One generation of the memetic algorithm: fitness from conflict-free "
            "planning; local search driven by yield records; AGVs not encoded",
            ha="center", va="center", fontsize=8.2, color=C_EDGE)

    # A
    rbox(ax, 2, 28, 28, 24, fc=C_BOX, ec=C_EDGE, lw=1.05)
    ax.text(16, 49.5, "A  Chromosome (two segments)", ha="center", va="center",
            fontsize=8.8, fontweight="bold", color=C_EDGE)

    ax.text(4.2, 45.2, "Machines", ha="left", va="center",
            fontsize=7.2, color=C_MS, fontweight="bold")
    genes(ax, 4.0, 41.6, ["M1", "M2", "M2", "M1"], C_MS)
    ax.text(16, 40.4, r"Fixed order $O_{11},O_{12},O_{21},O_{22}$",
            ha="center", va="top", fontsize=6.2, color=C_MS)

    ax.text(4.2, 37.0, "Sequence", ha="left", va="center",
            fontsize=7.2, color=C_OS, fontweight="bold")
    genes(ax, 4.0, 33.2, ["1", "2", "1", "2"], C_OS)
    ax.text(16, 32.0, "Execution order (repeated job IDs)",
            ha="center", va="top", fontsize=6.2, color=C_OS)

    ax.add_patch(Rectangle(
        (4.0, 29.0), 24, 2.4, facecolor="#fff7f0", edgecolor=C_DEC,
        linewidth=1.0, linestyle=(0, (2.5, 1.8)), zorder=4))
    ax.text(16, 30.2, "AGVs not in the chromosome", ha="center", va="center",
            fontsize=7.0, color=C_DEC, fontweight="bold", zorder=5)

    # B
    rbox(ax, 34, 28, 42, 24, fc=C_BOX, ec=C_OUT, lw=1.15)
    ax.text(55, 49.5, "B  Evaluation (decoder + lower layer)",
            ha="center", va="center", fontsize=8.8, fontweight="bold", color=C_OUT)

    boxes_b = [
        (36.0, 40.5, 11.5, 6.5, "Next op in\nsequence;\nlook up machine", C_OS),
        (49.5, 40.5, 12.0, 6.5, "If location\nchanges: create\ntask, call lower", C_DEC),
        (63.5, 40.5, 10.5, 6.5, "AGV &\ndelivery time;\nwrite table", C_DEC),
    ]
    for x, y, w, h, t, c in boxes_b:
        rbox(ax, x, y, w, h, fc=C_INNER, ec=c, lw=1.05)
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center",
                fontsize=6.6, color=c, linespacing=1.15)
    arrow(ax, (47.6, 43.7), (49.3, 43.7), color=C_EDGE, lw=0.95, ms=7)
    arrow(ax, (61.6, 43.7), (63.3, 43.7), color=C_EDGE, lw=0.95, ms=7)

    ax.text(55, 38.4, "After all operations", ha="center", va="center",
            fontsize=7.0, color=C_MUTE)

    rbox(ax, 36.5, 29.8, 16.5, 6.5, fc="#eef5fb", ec=C_OUT, lw=1.15)
    ax.text(44.75, 34.0, "Fitness", ha="center", va="center",
            fontsize=7.0, color=C_OUT)
    ax.text(44.75, 31.5, r"$C_{\max}$ (conflict-free)", ha="center", va="center",
            fontsize=7.0, color=C_OUT, fontweight="bold")

    rbox(ax, 56.5, 29.8, 17.0, 6.5, fc="#f6f0fb", ec=C_LS, lw=1.15)
    ax.text(65.0, 34.0, "For local search", ha="center", va="center",
            fontsize=7.0, color=C_LS)
    ax.text(65.0, 31.5, "Yield records", ha="center", va="center",
            fontsize=7.2, color=C_LS, fontweight="bold")

    # C
    rbox(ax, 80, 28, 30, 24, fc=C_BOX, ec=C_LS, lw=1.15)
    ax.text(95, 49.5, "C  Local search (memetic)", ha="center", va="center",
            fontsize=8.8, fontweight="bold", color=C_LS)

    ax.text(95, 45.6, "Neighbours from yield records", ha="center", va="center",
            fontsize=7.2, color=C_LS)

    rbox(ax, 82.5, 39.2, 11.5, 4.6, fc=C_INNER, ec=C_MS, lw=1.0)
    ax.text(88.25, 41.5, "Reassign", ha="center", va="center",
            fontsize=7.4, color=C_MS, fontweight="bold")
    rbox(ax, 95.5, 39.2, 12.0, 4.6, fc=C_INNER, ec=C_OS, lw=1.0)
    ax.text(101.5, 41.5, "Stagger", ha="center", va="center",
            fontsize=7.4, color=C_OS, fontweight="bold")

    ax.text(95, 36.6, r"Re-decode; accept better $C_{\max}$",
            ha="center", va="center", fontsize=6.6, color=C_EDGE)
    ax.text(95, 34.0, "A few rounds; stop if no gain",
            ha="center", va="center", fontsize=6.6, color=C_MUTE)

    rbox(ax, 83.5, 29.4, 23, 3.0, fc="#f6f0fb", ec=C_LS, lw=1.0)
    ax.text(95, 30.9, "Improved individual (still two segments)",
            ha="center", va="center", fontsize=6.6, color=C_LS, fontweight="bold")

    arrow(ax, (30.2, 40.0), (33.6, 40.0), color=C_EDGE, lw=1.2, ms=9)
    arrow(ax, (73.8, 33.0), (79.6, 33.0), color=C_LS, lw=1.2, ms=9)
    ax.text(76.6, 35.2, "yield", ha="center", va="bottom",
            fontsize=6.2, color=C_LS)

    # D
    rbox(ax, 2, 5.0, 76, 19.5, fc=C_BOX, ec=C_EDGE, lw=1.05)
    ax.text(40, 22.0, "D  Genetic operators and stopping", ha="center", va="center",
            fontsize=8.8, fontweight="bold", color=C_EDGE)

    ops = [
        (5.5, 12.2, 14, 7.0, "Select", "Tournament\n+ elites", C_EDGE),
        (22.5, 12.2, 16, 7.0, "Crossover", "Seq.: order XO\nMach.: uniform", C_MS),
        (41.5, 12.2, 16, 7.0, "Mutate", "Swap in sequence\nor reassign machine", C_OS),
        (60.5, 12.2, 14.5, 7.0, "Stop?", "Budget spent or\nno recent gain", C_OUT),
    ]
    for x, y, w, h, title, body, c in ops:
        rbox(ax, x, y, w, h, fc=C_INNER, ec=c, lw=1.05)
        ax.text(x + w / 2, y + h - 1.5, title, ha="center", va="center",
                fontsize=7.8, fontweight="bold", color=c)
        ax.text(x + w / 2, y + 2.5, body, ha="center", va="center",
                fontsize=6.4, color=C_EDGE, linespacing=1.15)
    for x in (19.7, 38.7, 57.7):
        arrow(ax, (x, 15.7), (x + 2.5, 15.7), color=C_EDGE, lw=0.95, ms=7)

    ax.text(67.7, 10.5, "No", ha="center", va="center", fontsize=7.0, color=C_EDGE)
    ax.text(75.5, 15.7, "Yes", ha="left", va="center", fontsize=7.0, color=C_OUT)

    # E
    rbox(ax, 82, 5.0, 28, 19.5, fc="#eef5fb", ec=C_OUT, lw=1.2)
    ax.text(96, 22.0, "E  Output", ha="center", va="center",
            fontsize=8.8, fontweight="bold", color=C_OUT)
    ax.text(96, 16.8, "Best chromosome found", ha="center", va="center",
            fontsize=7.4, color=C_OUT)
    ax.text(96, 13.5, "Conflict-free timetable", ha="center", va="center",
            fontsize=7.4, color=C_OUT)
    ax.text(96, 9.8, r"and its $C_{\max}$", ha="center", va="center",
            fontsize=8.0, color=C_OUT, fontweight="bold")
    ax.text(96, 6.6, "Feasibility from decode + lower layer",
            ha="center", va="center", fontsize=6.4, color=C_MUTE)

    arrow(ax, (84.0, 30.9), (70.0, 24.6), color=C_EDGE, lw=1.05, ms=8, rad=0.12)
    ax.text(74.5, 28.6, "to pool", ha="center", va="center",
            fontsize=6.2, color=C_EDGE)

    arrow(ax, (75.2, 15.7), (81.6, 15.7), color=C_OUT, lw=1.15, ms=9)

    ax.annotate(
        "", xy=(16, 28.0), xytext=(67.7, 11.2),
        arrowprops=dict(
            arrowstyle="-|>", color=C_EDGE, lw=1.15,
            connectionstyle="arc3,rad=0.32", mutation_scale=9),
        zorder=6)
    ax.text(42, 1.2, "Next generation (back to evaluation)", ha="center",
            va="center", fontsize=7.0, color=C_EDGE)

    stem = os.path.join(HERE, "fig_encoding")
    fig.savefig(stem + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(stem + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", stem + ".pdf/.png")


if __name__ == "__main__":
    main()
