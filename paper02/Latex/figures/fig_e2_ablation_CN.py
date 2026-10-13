# -*- coding: utf-8 -*-
"""E2: production three-path ablation, per-channel alpha fixed, alpha=0.01.

Reads slid/output/e2_prod_archive.json (tools/ablate_prod.py).
"""
from __future__ import print_function, division

import io
import json
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_SM, FP_TINY, C_OURS, C_TIME, C_HARD, C_STR, C_LINE,
    apply_style, save, set_cjk, legend,
)

ATTACKS = [u"A1", u"A2", u"A3", u"A4", u"A5", u"A6"]
ARCHIVE = os.path.join(HERE, "..", "..", "slid", "output", "e2_prod_archive.json")
ALPHA = 0.01


def _arm(runs, arm):
    return np.array([np.mean([r["seq_net"] for r in runs
                              if r["arm"] == arm and r["family"] == f])
                     for f in ATTACKS])


def main():
    apply_style()
    with io.open(ARCHIVE, encoding="utf-8") as f:
        runs = [r for r in json.load(f)["runs"] if r["alpha"] == ALPHA]
    full = _arm(runs, "full")
    no_t = _arm(runs, "no_timing")
    no_f = _arm(runs, "no_hard")
    no_s = _arm(runs, "no_structural")
    series = [
        (u"完整", full, C_OURS),
        (u"去时序", no_t, C_TIME),
        (u"去硬约束层", no_f, C_HARD),
        (u"去结构", no_s, C_STR),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.85),
                             gridspec_kw={"width_ratios": [2.35, 1.05]})
    ax = axes[0]
    x = np.arange(6)
    width = 0.18
    n = len(series)
    for k, (name, vals, col) in enumerate(series):
        offset = (k - (n - 1) / 2.0) * width
        ax.bar(x + offset, vals, width=width * 0.92, color=col,
               edgecolor="white", linewidth=0.4, label=name, zorder=3)
    ax.axhline(0.0, color=C_LINE, linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(ATTACKS, fontproperties=FP_SM)
    ax.set_ylim(-0.08, 1.05)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    set_cjk(ax, ylabel=u"净检出率")
    ax.set_title(u"(a) 按攻击族", fontproperties=FP_SM, loc="left")
    legend(ax, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.02),
           columnspacing=0.7, handlelength=1.1, handletextpad=0.3)

    ax2 = axes[1]
    deltas = np.array([a.mean() - full.mean() for a in (no_t, no_f, no_s)])
    labels = [u"去时序", u"去硬约束层", u"去结构"]
    cols = [C_TIME, C_HARD, C_STR]
    y = np.arange(3)
    ax2.barh(y, deltas, color=cols, edgecolor="white", height=0.55, zorder=3)
    ax2.axvline(0.0, color=C_LINE, linewidth=0.6)
    ax2.set_yticks(y)
    ax2.set_yticklabels(labels, fontproperties=FP_SM)
    ax2.set_xlim(-0.25, 0.03)
    ax2.xaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax2.set_axisbelow(True)
    set_cjk(ax2, xlabel=u"均值变化 $\\Delta$")
    ax2.set_title(u"(b) 六族均值", fontproperties=FP_SM, loc="left")
    for yi, d in zip(y, deltas):
        ax2.text(d - 0.008, yi, u"%.2f" % d, va="center", ha="right",
                 fontproperties=FP_TINY, color=C_LINE)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.86))
    save(fig, "fig_e2_ablation_CN")


if __name__ == "__main__":
    main()
