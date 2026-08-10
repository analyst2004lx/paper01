# -*- coding: utf-8 -*-
"""Cost per evaluation against evaluations completed (Section 5.7).

This is the figure behind the paper's cost argument.  Under a fixed wall clock
the two quantities are two readings of one thing, so plotting them against each
other on log axes puts every arm on a hyperbola and makes the budget line
visible: an arm can only move along it, and a mechanism has to buy more per
evaluation than it costs in evaluations forgone.  Stating it that way is what
turns "our method is slower" from an apology into a quantity.

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

from _style import (COL, LADDER, LADDER_COLOR, LADDER_SHORT, by,  # noqa: E402
                    load_output, mean, plt, save)

HINT = "py -u -m tools.ladder_diag --budget 90 --seeds 42,7,2024"


def main() -> None:
    rows = load_output("ladder_cost.csv", HINT)
    fig, ax = plt.subplots(figsize=(COL, 2.5))

    # The budget hyperbola: cost x evaluations = wall clock.  Drawn from the
    # measured budget rather than assumed, so a mismatch would be visible.
    budget = mean([r["runtime_sec"] for r in rows])
    xs = [10 ** (i / 40.0) for i in range(-40, 121)]
    ax.plot(xs, [1000.0 * budget / x for x in xs], color="#bbbbbb",
            linewidth=0.9, zorder=1,
            label="equal wall clock (%.0f s)" % budget)

    for arm in LADDER:
        rs = [r for r in rows if r["arm"] == arm]
        if not rs:
            continue
        x, y = mean([r["ms_per_eval"] for r in rs]), mean([r["decodes"]
                                                           for r in rs])
        ax.plot([x], [y], "o", color=LADDER_COLOR[arm], markersize=6.5,
                markeredgecolor="white", markeredgewidth=0.7, zorder=5)
        ax.annotate(LADDER_SHORT[arm], (x, y), textcoords="offset points",
                    xytext=(7, 4), fontsize=7.2, color=LADDER_COLOR[arm],
                    fontweight="bold")

    # B0 and B0+ share one search, hence one point; say so on the figure rather
    # than letting the overlap look like a plotting bug.
    ax.text(0.03, 0.06, "B0 and B0$^+$ share one open-loop search,\n"
                        "so they share one point",
            transform=ax.transAxes, fontsize=6.2, color="#777777",
            va="bottom")

    try:
        pr = load_output("prune_ablation.csv",
                         "py -u -m tools.prune_ablation --budget 90")
    except SystemExit:
        pr = None
    if pr:
        pts = {}
        for label in ("开", "关"):
            rs = [r for r in pr if r["arm"] == label]
            if rs:
                pts[label] = (mean([r["ms_per_eval"] for r in rs]),
                              mean([r["decodes"] for r in rs]))
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts["关"], pts["开"]
            ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                        arrowprops=dict(arrowstyle="-|>", color="#d95f02",
                                        linewidth=1.3))
            ax.text(x1, y1, "  pruning +\n  winner reuse\n  (identical output)",
                    fontsize=6.4, color="#d95f02", va="top",
                    fontweight="bold")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("cost per evaluation (ms)")
    ax.set_ylabel("evaluations completed")
    ax.legend(loc="upper right", fontsize=6.5)
    fig.tight_layout()
    save(fig, "fig_protocol")


if __name__ == "__main__":
    main()
