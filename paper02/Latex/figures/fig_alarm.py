# -*- coding: utf-8 -*-
"""Walkthrough: A2 hard veto vs A3 graded timing + CUSUM."""
from __future__ import print_function, division

import json
import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP, FP_SM, FP_TINY, C_OURS, C_HARD, C_TIME, C_LAB, C_LINE,
    apply_style, save, set_cjk,
)

ARCHIVE = os.path.abspath(os.path.join(
    HERE, "..", "..", "slid", "output", "alarm_walkthrough.json"))


def _short(op):
    return op.rsplit("/", 1)[-1] if op else ""


def _panel(ax, rows, title, labels):
    n = len(rows)
    x = list(range(n))
    inj = [i for i, r in enumerate(rows) if r["injected"]]
    hard = [i for i, r in enumerate(rows) if r["hard"]]
    zs = [r["z"] if r["z"] is not None else 0.0 for r in rows]
    Ss = [r["S"] for r in rows]

    ax.axhline(0.0, color=C_LAB, linewidth=0.6)
    ax.plot(x, zs, "o--", color=C_TIME, linewidth=1.2, markersize=4,
            label=labels["z"])
    ax.plot(x, Ss, "s-", color=C_OURS, linewidth=1.4, markersize=4,
            label=labels["S"])
    for i in inj:
        ax.axvspan(i - 0.45, i + 0.45, color=C_TIME, alpha=0.12, zorder=0)
    for i in hard:
        ax.scatter([i], [max(zs[i], Ss[i]) + 0.35], marker="x", s=36,
                   color=C_HARD, zorder=5, label=labels["hard"] if i == hard[0] else None)
    ax.set_xticks(x)
    ax.set_xticklabels(
        ["%s\n%s" % (_short(r["op"]), r["device"].split("_")[0]) for r in rows],
        fontproperties=FP_TINY)
    ax.set_title(title, fontproperties=FP_SM, loc="left")
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, ylabel=labels["ylabel"])


def draw(blob, titles, labels, out_name):
    apply_style()
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.6), sharey=False)
    _panel(axes[0], blob["A2"], titles["A2"], labels)
    _panel(axes[1], blob["A3"], titles["A3"], labels)
    handles, labs = axes[1].get_legend_handles_labels()
    # unique labels
    seen, H, L = set(), [], []
    for h, lab in zip(handles, labs):
        if lab in seen:
            continue
        seen.add(lab)
        H.append(h)
        L.append(lab)
    axes[0].legend(H, L, prop=FP_TINY, loc="upper right", frameon=False)
    fig.tight_layout()
    save(fig, out_name)


def main():
    with open(ARCHIVE, encoding="utf-8") as f:
        blob = json.load(f)
    draw(blob, {
        "A2": "(a) A2 infeasible injection — hard-layer veto",
        "A3": "(b) A3 race replay — graded residual + CUSUM",
    }, {
        "z": r"timing $z$",
        "S": r"CUSUM $S$",
        "hard": "hard veto",
        "ylabel": r"$z$ / $S$",
    }, "fig_alarm")


if __name__ == "__main__":
    main()
