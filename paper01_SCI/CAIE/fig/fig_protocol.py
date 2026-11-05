# -*- coding: utf-8 -*-
"""Cost per evaluation against evaluations completed (Section 5.7).

This is the figure behind the paper's cost argument.  Under a fixed wall clock
the two quantities are two readings of one thing, so plotting them against each
other on log axes puts every arm on a hyperbola and makes the budget line
visible: an arm can only move along it, and a mechanism has to buy more per
evaluation than it costs in evaluations forgone.  Stating it that way is what
turns "our method is slower" from an apology into a quantity.

The line is drawn at the *nominal* cap, not at the mean of observed runtimes.
Averaging the two regimes present here (B0 stalls at ~18 s, the closed-loop arms
exhaust the 90 s) would put the line at 54 s, a budget no run ever received.
B0 therefore sits visibly below the line, which is the honest picture: it
converged and stopped rather than being cut off.  Arm markers use the geometric
mean, the only average on log axes for which cost x evaluations still equals the
arm's wall clock -- the arithmetic mean of three instances whose cost scales
differ threefold puts B2 on a 121 s hyperbola that no run occupies.

The pruning ablation is drawn on the same axes when its CSV is present, because
it is the one intervention that moves an arm *along* the line without changing
what the arm computes -- the two points are bit-identical in output, so the
segment between them is pure cost reduction.

Output stem fig_protocol, which is what paper.tex includes.
Data: clbs/output/ladder_cost.csv (tools/ladder_diag.py),
      clbs/output/prune_ablation.csv (tools/prune_ablation.py, optional).

Run: py paper01/fig/fig_protocol.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import (COL, FS_ANNOT, FS_FOOT, FS_LEG, LADDER,  # noqa: E402
                    LADDER_COLOR, LADDER_SHORT, load_output, plt, save)

HINT = "py -u -m tools.ladder_diag --budget 90 --seeds 42,7,2024"

BUDGET = 90.0   # the cap offered to every arm, declared in Section 5.1.2


def gmean(vals):
    p = 1.0
    for v in vals:
        p *= v
    return p ** (1.0 / len(vals))


def main() -> None:
    rows = load_output("ladder_cost.csv", HINT)
    fig, ax = plt.subplots(figsize=(COL, 2.5))

    xs = [10 ** (i / 40.0) for i in range(-40, 121)]
    ax.plot(xs, [1000.0 * BUDGET / x for x in xs], color="#bbbbbb",
            linewidth=0.9, zorder=1,
            label="budget cap (%.0f s)" % BUDGET)

    stall_at = float("nan")
    for arm in LADDER:
        rs = [r for r in rows if r["arm"] == arm]
        if not rs:
            continue
        # Per-instance points behind the marker: the spread is real and the
        # marker is a summary of it, not a measurement in its own right.
        ax.plot([r["ms_per_eval"] for r in rs], [r["decodes"] for r in rs],
                "o", color=LADDER_COLOR[arm], markersize=2.6, alpha=0.35,
                markeredgewidth=0.0, zorder=3)
        x, y = gmean([r["ms_per_eval"] for r in rs]), gmean([r["decodes"]
                                                             for r in rs])
        ax.plot([x], [y], "o", color=LADDER_COLOR[arm], markersize=6.5,
                markeredgecolor="white", markeredgewidth=0.7, zorder=5)
        ax.annotate(LADDER_SHORT[arm], (x, y), textcoords="offset points",
                    xytext=(7, 4), fontsize=7.2, color=LADDER_COLOR[arm],
                    fontweight="bold")
        if arm == "B0":
            stall_at = gmean([r["runtime_sec"] for r in rs])

    # Two things a reader would otherwise misread: the overlapping B0/B0+ marker
    # looks like a plotting bug, and B0 sitting off the line looks like a
    # shortchanged baseline rather than one that finished searching.
    ax.text(0.03, 0.06, "B0 and B0$^+$ share one open-loop search, so they "
                        "share one point;\nit stalls at %.0f s — converged, "
                        "not cut off by the budget" % stall_at,
            transform=ax.transAxes, fontsize=FS_FOOT, color="#777777",
            va="bottom")

    try:
        pr = load_output("prune_ablation.csv",
                         "py -u -m tools.prune_ablation --budget 90")
    except SystemExit:
        pr = None
    if pr:
        pts = {}
        # prune_ablation.csv tags the two settings as 开/关; look up by those
        # keys and never print them -- the arrow label below is English.
        prune_on, prune_off = "开", "关"
        for label in (prune_on, prune_off):
            rs = [r for r in pr if r["arm"] == label]
            if rs:
                pts[label] = (gmean([r["ms_per_eval"] for r in rs]),
                              gmean([r["decodes"] for r in rs]))
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts[prune_off], pts[prune_on]
            # Markers stay on the hyperbola; the shaft must not — it sat on
            # the budget line and hid both the line and the label.
            ax.plot([x0, x1], [y0, y1], "o", color="#d95f02",
                    markersize=5.0, markeredgecolor="white",
                    markeredgewidth=0.6, zorder=6)
            ax.annotate(
                "pruning +\nwinner reuse\n(identical output)",
                xy=(x1, y1),
                xytext=(58, 8200),
                textcoords="data",
                ha="left", va="center",
                fontsize=FS_ANNOT, color="#d95f02", fontweight="bold",
                arrowprops=dict(
                    arrowstyle="-|>", color="#d95f02", lw=1.2,
                    connectionstyle="arc3,rad=-0.45",
                    shrinkA=4, shrinkB=5,
                ),
                annotation_clip=False, zorder=7,
            )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("cost per evaluation (ms)")
    ax.set_ylabel("evaluations completed")
    ax.legend(loc="upper right", fontsize=FS_LEG)
    fig.tight_layout()
    save(fig, "fig_protocol")


if __name__ == "__main__":
    main()
