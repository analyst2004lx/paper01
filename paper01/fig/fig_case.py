# -*- coding: utf-8 -*-
"""Merged case study: Gantt of B0 vs B2 plus critical-chain composition.

Replaces the pair fig_case_gantt + fig_case_chain in the compressed manuscript.
The Gantt shows what changed on one funnel instance (yielding wait cut,
reassignment visible).  The stacked bars show why the recovered makespan is
smaller than the corridor wait removed: another constraint is promoted to
binding.  That is the dilution argument of Section 5.6.

Data: clbs/output/case_study/*.json, written by tools/ladder_diag.py.
Run: py paper01/fig/fig_case.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import FULL, FS_FOOT, FS_LEG, plt, save  # noqa: E402
import fig_case_chain as chain  # noqa: E402
import fig_case_gantt as gantt  # noqa: E402

STRINGS = {
    "title_b0": "B0  open loop, rule dispatch",
    "title_b2": "B2  closed loop, reservation-aware dispatch (proposed)",
    "xlabel": "time",
    "ylabel": "critical-chain composition (time units)",
    "xtick_b0": "B0\nopen loop",
    "xtick_b2": "B2\nproposed",
    "bar_title": "corridor waiting removed %.0f,  makespan recovered %.0f",
    "foot": "instance %s,  seed %s,  contention %.1f%%",
    "leg_proc": "processing",
    "leg_loaded": "travel, loaded",
    "leg_empty": "travel, empty",
    "leg_yield": "waiting: corridor occupied",
    "leg_idle": "waiting: unassigned",
    "arm_label": "arm %s",
    "agv_label": "AGV %s",
    "yield_suffix": "   (yielding total %.0f time units)",
}


def _draw_bars(ax, arms, kinds, strings):
    order = ["B0", "B2"]
    comps = {a: chain.compose(arms[a]["chain"]) for a in order}
    stack_max = max(sum(comps[a].values()) for a in order)
    ax.set_ylim(0, 1.55 * stack_max)
    for x, arm in enumerate(order):
        bottom = 0.0
        slices = []
        stack = sum(comps[arm].values())
        for k, label, colour in kinds:
            v = comps[arm][k]
            if v <= 1e-9:
                continue
            ax.bar(x, v, bottom=bottom, width=0.55, color=colour,
                   edgecolor="white", linewidth=0.6,
                   label=label if x == 0 else None, zorder=3)
            slices.append((bottom, v, colour))
            bottom += v
        chain._label_slices(ax, x, slices, stack)
    d_corr = comps["B0"]["corridor"] - comps["B2"]["corridor"]
    d_mk = arms["B0"]["makespan"] - arms["B2"]["makespan"]
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(
        [strings["xtick_b0"] + "\n$C_{\\max}=%.0f$" % arms["B0"]["makespan"],
         strings["xtick_b2"] + "\n$C_{\\max}=%.0f$" % arms["B2"]["makespan"]],
        fontsize=7)
    ax.set_ylabel(strings["ylabel"])
    ax.set_xlim(-0.5, 1.5)
    ax.legend(loc="upper right", fontsize=FS_LEG, ncol=3, labelspacing=0.25)
    ax.set_title(strings["bar_title"] % (d_corr, d_mk), fontsize=8, loc="left")
    return d_corr, d_mk


def render(strings, stem):
    tt = gantt.load_case()
    arms = chain.load_arms()
    xmax = 1.06 * max(tt[a]["makespan"] for a in ("B0", "B2"))
    kinds = list(chain.KINDS)
    comps = {a: chain.compose(arms[a]["chain"]) for a in ("B0", "B2")}
    if any(c[chain.OTHER[0]] > 1e-9 for c in comps.values()):
        kinds = kinds + [chain.OTHER]

    fig, axes = plt.subplots(
        3, 1, figsize=(FULL, 6.6),
        gridspec_kw={"height_ratios": [2.15, 2.15, 1.45]})
    gantt_kw = dict(arm_label=strings["arm_label"],
                    agv_label=strings["agv_label"],
                    yield_suffix=strings["yield_suffix"])
    gantt.draw(axes[0], tt["B0"], strings["title_b0"], xmax, **gantt_kw)
    gantt.draw(axes[1], tt["B2"], strings["title_b2"], xmax, **gantt_kw)
    axes[1].set_xlabel(strings["xlabel"])
    _draw_bars(axes[2], arms, kinds, strings)

    handles = [
        plt.Rectangle((0, 0), 1, 1, fc=gantt.C_OP, label=strings["leg_proc"]),
        plt.Rectangle((0, 0), 1, 1, fc=gantt.C_LOADED, label=strings["leg_loaded"]),
        plt.Rectangle((0, 0), 1, 1, fc=gantt.C_EMPTY, label=strings["leg_empty"]),
        plt.Rectangle((0, 0), 1, 1, fc=gantt.C_YIELD, hatch="///",
                      label=strings["leg_yield"]),
        plt.Rectangle((0, 0), 1, 1, fc=gantt.C_IDLE, label=strings["leg_idle"]),
    ]
    axes[0].legend(handles=handles, loc="upper center", ncol=5,
                   fontsize=FS_LEG,
                   bbox_to_anchor=(0.5, 1.28), frameon=False)
    fig.text(0.005, 0.005, strings["foot"]
             % (tt["B2"]["case"], tt["B2"]["seed"],
                100.0 * tt["B2"]["contention"]),
             fontsize=FS_FOOT, color="#777777")
    fig.tight_layout(rect=(0, 0.018, 1, 0.96))
    save(fig, stem)


def main() -> None:
    render(STRINGS, "fig_case")


if __name__ == "__main__":
    main()
