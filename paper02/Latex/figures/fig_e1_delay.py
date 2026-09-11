# -*- coding: utf-8 -*-
"""E1 detection-delay boxplots, A1-A6, delay budget 10."""
from __future__ import print_function, division

import json
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "slid")))

from _style import (  # noqa: E402
    C_OURS, C_B3, C_B4, C_B5, C_LAB, C_LINE, FP_TINY,
    apply_style, save, set_cjk, legend,
)

ATTACKS = ["A1", "A2", "A3", "A4", "A5", "A6"]
ATTACK_EN = ["replay", "infeas.", "race", "mimic", "drift", "suppress"]
METHODS = [
    ("butla", "BUTLA", C_B3),
    ("tabor", "TABOR-like", C_B4),
    ("hsmm", "HSMM", C_B5),
    ("markov", "Label-only", C_LAB),
    ("ours", "Ours", C_OURS),
]
ARCHIVE = os.path.abspath(os.path.join(
    HERE, "..", "..", "slid", "output", "e1_archive.json"))


def _load(rate=None):
    with open(ARCHIVE, encoding="utf-8") as f:
        blob = json.load(f)
    primary = blob["meta"].get("primary_rate", 0.2)
    use = primary if rate is None else rate
    buckets = {(fam, m): [] for fam in ATTACKS for m, _, _ in METHODS}
    for rec in blob["runs"]:
        if abs(rec["rate"] - use) > 1e-9:
            continue
        key = (rec["family"], rec["method"])
        if key in buckets:
            buckets[key].extend(rec.get("detected_delays") or [])
    return buckets, blob["meta"]


def _draw(ax, buckets, labels, methods=None):
    methods = methods or METHODS
    n_m = len(methods)
    width = 0.14
    for k, (mid, name, color) in enumerate(methods):
        data, pos = [], []
        for i, fam in enumerate(ATTACKS):
            xs = buckets[(fam, mid)]
            if xs:
                data.append(xs)
                pos.append(i + (k - (n_m - 1) / 2.0) * width)
        if not data:
            continue
        bp = ax.boxplot(
            data, positions=pos, widths=width * 0.85, patch_artist=True,
            showfliers=True, flierprops={"marker": ".", "markersize": 3,
                                         "markerfacecolor": color,
                                         "markeredgecolor": color,
                                         "alpha": 0.5})
        for box in bp["boxes"]:
            box.set(facecolor=color, edgecolor="white", linewidth=0.6, alpha=0.85)
        for med in bp["medians"]:
            med.set(color=C_LINE, linewidth=1.0)
        for w in list(bp["whiskers"]) + list(bp["caps"]):
            w.set(color=color, linewidth=0.8)
        ax.plot([], [], color=color, linewidth=6, label=name, solid_capstyle="butt")
    ax.set_xticks(range(6))
    ax.set_xticklabels(["%s\n%s" % (a, z) for a, z in zip(ATTACKS, labels)])
    ax.set_ylim(-0.4, 10.6)
    ax.set_yticks([0, 2, 4, 6, 8, 10])
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    ax.axhline(10.0, color=C_LINE, linewidth=0.5, linestyle="--", alpha=0.4)


def main():
    apply_style()
    buckets, meta = _load()
    fig, ax = plt.subplots(figsize=(7.2, 3.85))
    _draw(ax, buckets, ATTACK_EN)
    set_cjk(ax, ylabel="Detection delay (messages)")
    legend(ax, ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.02),
           columnspacing=0.55, handlelength=1.15, handletextpad=0.3)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.86))
    save(fig, "fig_e1_delay")
    n = sum(len(v) for v in buckets.values())
    print("primary_rate", meta.get("primary_rate"), "n_detected", n)


if __name__ == "__main__":
    main()
