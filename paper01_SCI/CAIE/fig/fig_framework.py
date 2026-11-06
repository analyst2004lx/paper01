# -*- coding: utf-8 -*-
"""Schematic of the closed-loop bilevel framework (Section 4.1).

This is the paper's orienting figure, so it has one job: make visible that the
two feedback paths enter the upper layer at *different* places.  Path 1 returns
a realized objective and enters at fitness evaluation, once per candidate.
Path 2 returns a realizable arrival time and enters inside the decoder, once
per transport task, before the vehicle is chosen.  Everything else here is
subordinate to that contrast, which is why the two paths are the only elements
drawn in colour and the only ones carrying numbered badges.

The four ladder arms of Section 5.2 differ only in which of the two paths is
present, so the inset spells that out: the figure and the experiment then share
one vocabulary and the reader does not have to hold a mapping in their head.

No data is involved; this is a drawing.  Run: py paper01/fig/fig_framework.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib.patches as mpatches  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from _style import FULL, plt, save  # noqa: E402

# Colours: the two feedback paths are the only saturated elements.
C_EVAL = "#08519c"      # path 1, evaluation level
C_DEC = "#d95f02"       # path 2, decision level
C_BOX = "#f7f7f7"
C_EDGE = "#5a5a5a"
C_INNER = "#ffffff"


def box(ax, x, y, w, h, text, fc=C_INNER, ec=C_EDGE, lw=0.8, fs=7.5,
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
    """Numbered marker tying an arrow to the two-path story in the caption."""
    ax.add_patch(mpatches.Circle((x, y), 2.0, facecolor=color,
                                 edgecolor="white", linewidth=0.8, zorder=8))
    ax.text(x, y, str(n), ha="center", va="center", fontsize=6.8,
            color="white", fontweight="bold", zorder=9)


def main() -> None:
    fig, ax = plt.subplots(figsize=(FULL, 4.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(-8.6, 70.5)
    ax.axis("off")
    ax.grid(False)

    # Input and output sit above and below rather than beside the panels: the
    # full width is already shared by three panels, and side boxes would
    # squeeze their text past the box edges.
    box(ax, 2, 62.5, 60, 6.2,
        "Input: problem instance\n"
        "operation chains, eligible machines and processing times, "
        "fleet size, aisle network",
        fc=C_BOX, ec=C_EDGE, lw=1.0, fs=7.0, style="round,pad=0.3")
    arrow(ax, (5.5, 62.2), (5.5, 50.5), lw=1.1, ms=8)

    box(ax, 70, -7.6, 27, 7.4,
        "Output: conflict-free timetable\n"
        "(operation times, vehicle routes)\nand its $C_{\\max}$",
        fc=C_BOX, ec=C_EDGE, lw=1.0, fs=7.0, style="round,pad=0.3")
    arrow(ax, (76, 4.6), (76, 0.1), lw=1.1, ms=8)
    ax.text(77.5, 2.4, "best candidate at termination", ha="left",
            va="center", fontsize=6.2, color=C_EDGE)

    # The decoder is part of the upper layer's fitness evaluation, so both
    # panels share one dashed frame.
    ax.add_patch(FancyBboxPatch((0.3, 3.6), 63.4, 55.2,
                                boxstyle="round,pad=0.2", linewidth=1.1,
                                linestyle=(0, (4, 2.5)), facecolor="none",
                                edgecolor=C_EVAL, zorder=0.5))
    ax.text(32, 56.6, "Upper layer:  search and fitness evaluation "
                      "(the decoder belongs here)",
            ha="center", va="center", fontsize=7.8, fontweight="bold",
            color=C_EVAL)

    # The two feedback arrows carry a numbered badge and no text.  Two earlier
    # drafts labelled them in place and the labels collided with the boxes on
    # both sides; the gaps between the panels are simply not wide enough for a
    # phrase, and widening them would shrink the boxes the phrases describe.
    # The legend at the bottom says what each path returns and how often, which
    # is where a reader looks for exactly that anyway.

    # ---- upper layer: the memetic search -------------------------------
    box(ax, 2, 5, 25, 45, "", fc=C_BOX, ec=C_EDGE, lw=1.0,
        style="round,pad=0.2", zorder=1)
    ax.text(14.5, 52.6, "Memetic algorithm", ha="center",
            va="center", fontsize=7.8, fontweight="bold")
    box(ax, 4.5, 37, 20, 7.5, "Chromosome population\n"
                              "(assignment, sequence)")
    box(ax, 4.5, 27, 20, 7, "Crossover, mutation,\nguided local search")
    box(ax, 4.5, 16.5, 20, 7, "Fitness $=$ realized $C_{\\max}$",
        ec=C_EVAL, lw=1.4, weight="bold", color=C_EVAL)
    box(ax, 4.5, 8, 20, 5, "Selection")
    arrow(ax, (14.5, 37), (14.5, 34.0))
    arrow(ax, (14.5, 16.5), (14.5, 13.0))
    # Return paths are drawn straight rather than curved: a curve wide enough to
    # read as a loop bulges outside the panel it belongs to.
    arrow(ax, (3.4, 10.5), (3.4, 40.5))              # on to the next generation

    # ---- middle: the decoder ------------------------------------------
    box(ax, 32, 5, 30, 45, "", fc=C_BOX, ec=C_EDGE, lw=1.0,
        style="round,pad=0.2", zorder=1)
    ax.text(47, 52.6, "Event-driven decoder", ha="center", va="center",
            fontsize=7.8, fontweight="bold")
    box(ax, 34.5, 40, 25, 5.5, "Pop the next ready operation")
    box(ax, 34.5, 30, 25, 7.5, "Derive its transport task\n"
                               "(pickup, drop-off, ready)")
    box(ax, 34.5, 18, 25, 9, "Choose the vehicle:\ntrial query on the\n"
                             "table per candidate",
        ec=C_DEC, lw=1.4, weight="bold", color=C_DEC)
    box(ax, 34.5, 8, 25, 7.5, "Commit reservations,\nadvance the clock")
    arrow(ax, (47, 40), (47, 37.5))
    arrow(ax, (47, 30), (47, 27.0))
    arrow(ax, (47, 18), (47, 15.5))
    arrow(ax, (33.4, 11.5), (33.4, 42.0))            # on to the next operation

    # ---- lower layer: the router --------------------------------------
    box(ax, 70, 5, 27, 45, "", fc=C_BOX, ec=C_EDGE, lw=1.0,
        style="round,pad=0.2", zorder=1)
    ax.text(83.5, 52.6, "Lower layer:  conflict-free routing", ha="center",
            va="center", fontsize=7.8, fontweight="bold")
    box(ax, 72, 35.5, 23, 9.5, "Time-window Dijkstra\n"
                               "on the aisle network\n(earliest arrival)")
    box(ax, 72, 21, 23, 9.5, "Reservation table\ncorridor occupancy\n"
                             "intervals")
    box(ax, 72, 8, 23, 8, "Trial route, then roll back\n(no trace left)",
        ec=C_DEC, lw=1.0, color=C_DEC)
    arrow(ax, (80, 35.5), (80, 30.5))                 # ask for a feasible entry
    arrow(ax, (88, 30.5), (88, 35.5))                 # earliest one available
    arrow(ax, (83.5, 21), (83.5, 16.0), ls=(0, (2, 1.6)), color=C_DEC)

    # ---- the interface: one request down, two answers up ---------------
    arrow(ax, (59.5, 24.0), (72.0, 40.0), color=C_EDGE, lw=1.1, rad=-0.15)
    ax.text(68.2, 29.5, "route\nrequest", ha="center", va="center",
            fontsize=6.4, color=C_EDGE)

    arrow(ax, (72.0, 11.5), (59.5, 20.5), color=C_DEC, lw=1.7, rad=-0.16,
          ms=9)
    badge(ax, 65.8, 15.0, 2, C_DEC)

    arrow(ax, (34.5, 9.0), (24.5, 18.0), color=C_EVAL, lw=1.7, rad=-0.18,
          ms=9)
    badge(ax, 29.3, 12.8, 1, C_EVAL)

    # Candidate handed down to be decoded, along the top so it crosses nothing.
    arrow(ax, (24.5, 42.5), (34.5, 42.5), color=C_EDGE, lw=1.1)
    ax.text(29.5, 44.4, "candidate", ha="center", va="center", fontsize=6.4,
            color=C_EDGE)

    # ---- legend: what each path returns, and how often ------------------
    # Stacked rather than side by side: the two lines are what distinguishes the
    # paths, so they should be read against each other, not scanned across.
    badge(ax, 3.5, -0.4, 1, C_EVAL)
    ax.text(6.5, -0.4, "returns the conflict-free timetable's $C_{\\max}$ "
                       "as the fitness $\\rightarrow$  once per candidate",
            ha="left", va="center", fontsize=7.0, color=C_EVAL)
    badge(ax, 3.5, -3.4, 2, C_DEC)
    ax.text(6.5, -3.4, "returns the realizable arrival time "
                      "$\\rightarrow$  once per transport task",
            ha="left", va="center", fontsize=7.0, color=C_DEC)

    save(fig, "fig_framework")


if __name__ == "__main__":
    main()
