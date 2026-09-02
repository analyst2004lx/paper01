# -*- coding: utf-8 -*-
"""关键链归因中文版。数据与 fig_case_chain.py 相同，输出 fig_case_chain_CN。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import COL, FS_FOOT, FS_LEG, plt, save, use_cjk  # noqa: E402
import fig_case_chain as src  # noqa: E402

use_cjk()

KINDS = [
    ("corridor", "等待：走廊占用", "#d62728"),
    ("vehicle", "等待：无车可用", "#fd8d3c"),
    ("machine", "等待：机械臂繁忙", "#9ecae1"),
    ("upstream", "等待：上游工序", "#4292c6"),
    ("operation", "加工", "#08519c"),
]
OTHER = ("other", "其他", "#cccccc")


def compose(chain):
    known = {k for k, _l, _c in KINDS}
    agg = {k: 0.0 for k, _l, _c in KINDS}
    agg[OTHER[0]] = 0.0
    for it in chain:
        k = it["kind"] if it["kind"] in known else OTHER[0]
        agg[k] += max(it["amount"], 0.0)
    return agg


def main() -> None:
    arms = src.load_arms()
    order = ["B0", "B2"]
    comps = {a: compose(arms[a]["chain"]) for a in order}
    kinds = KINDS + [OTHER] if any(c[OTHER[0]] > 1e-9 for c in comps.values()) \
        else KINDS

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(COL, 3.5),
                                  gridspec_kw={"height_ratios": [1.5, 1]})

    for x, arm in enumerate(order):
        bottom = 0.0
        for k, label, colour in kinds:
            v = comps[arm][k]
            if v <= 1e-9:
                continue
            ax.bar(x, v, bottom=bottom, width=0.55, color=colour,
                   edgecolor="white", linewidth=0.6,
                   label=label if x == 0 else None, zorder=3)
            if v >= 0.06 * sum(comps[arm].values()):
                ax.text(x, bottom + v / 2, "%.0f" % v, ha="center",
                        va="center", fontsize=6.2, color="white",
                        fontweight="bold", zorder=4)
            bottom += v
        ax.text(x, bottom, "  $C_{\\max}=%.0f$" % arms[arm]["makespan"],
                ha="center", va="bottom", fontsize=7, fontweight="bold")

    d_corr = comps["B0"]["corridor"] - comps["B2"]["corridor"]
    d_mk = arms["B0"]["makespan"] - arms["B2"]["makespan"]
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(["B0\n开环", "B2\n本文"], fontsize=7)
    ax.set_ylabel("关键链构成\n（时间单位）")
    ax.set_ylim(0, 1.62 * max(sum(comps[a].values()) for a in order))
    ax.legend(loc="upper right", fontsize=FS_LEG, labelspacing=0.3)
    ax.set_title("走廊等待消除 %.0f，收回完工时间 %.0f"
                 % (d_corr, d_mk), fontsize=7.6, loc="left")

    colour_of = {k: c for k, _l, c in kinds}
    for y, arm in enumerate(order):
        for it in arms[arm]["chain"]:
            k = it["kind"] if it["kind"] in colour_of else OTHER[0]
            w = max(it["t_end"] - it["t_start"], 0.0)
            if w <= 0:
                continue
            ax2.broken_barh([(it["t_start"], w)], (y - 0.3, 0.6),
                            facecolors=colour_of.get(k, OTHER[2]),
                            edgecolor="white", linewidth=0.3, zorder=3)
        ax2.axvline(arms[arm]["makespan"], color="#111111", linewidth=0.7,
                    zorder=2)
    ax2.set_yticks(range(len(order)))
    ax2.set_yticklabels(["B0", "B2"], fontsize=7)
    ax2.set_ylim(len(order) - 0.5, -0.5)
    ax2.set_xlabel("时间（关键链，按位置）")
    ax2.grid(axis="y", visible=False)

    fig.text(0.005, 0.005, "算例 %s，种子 %s"
             % (arms["B2"]["case"], arms["B2"]["seed"]),
             fontsize=FS_FOOT, color="#777777")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    save(fig, "fig_case_chain_CN")


if __name__ == "__main__":
    main()
