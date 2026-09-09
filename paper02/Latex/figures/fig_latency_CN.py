# -*- coding: utf-8 -*-
"""Per-message processing time percentiles."""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import FP_TINY, C_OURS, apply_style, save, set_cjk  # noqa: E402


def main():
    apply_style()
    labels = [u"中位", u"$p_{95}$", u"$p_{99}$"]
    vals = np.array([81.0, 116.0, 159.0])
    fig, ax = plt.subplots(figsize=(3.6, 3.1))
    ax.bar([0, 1, 2], vals, color=C_OURS, width=0.55, edgecolor="white")
    for i, v in enumerate(vals):
        ax.text(i, v + 4, u"%d $\\mu$s" % int(v), ha="center",
                fontproperties=FP_TINY)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 200)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, ylabel=u"逐消息时延")
    fig.tight_layout()
    save(fig, "fig_latency_CN")


if __name__ == "__main__":
    main()
