# -*- coding: utf-8 -*-
"""Offline fitting and online three parallel paths (English, paper02 fig:arch)."""
from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "fig_arch")

from _style import subset_pdf  # noqa: E402

_TIMES = r"C:\Windows\Fonts\times.ttf"


def _fp(size):
    p = FontProperties(fname=_TIMES)
    p.set_size(size)
    return p

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "stix",
    "figure.dpi": 200,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

C_EDGE = "#333333"
C_NOTE = "#555555"
C_OFF = "#f4f4f4"
C_MSG = "#e8e8e8"
C_HARD = "#f6d6d6"
C_STAT = "#d6e4f0"
C_SEQ = "#d9ecd9"
C_OUT = "#f4f4f4"


def box(ax, x, y, w, h, text, fc, fs=8.2):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor=fc, edgecolor=C_EDGE, linewidth=1.05, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontproperties=_fp(fs), color="#111111", zorder=4, linespacing=1.35,
            multialignment="center")


def arrow(ax, p, q):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle="-|>", mutation_scale=10, linewidth=1.15,
        color=C_EDGE, shrinkA=1.2, shrinkB=1.2, zorder=2))


def main() -> None:
    fig, ax = plt.subplots(figsize=(10.95, 3.85))
    ax.set_xlim(0.0, 16.7)
    ax.set_ylim(0.0, 5.05)
    ax.axis("off")

    ws = [2.85, 2.35, 3.85, 4.15]
    h, gap = 1.38, 0.50
    xs = []
    xcur = 0.40
    for wi in ws:
        xs.append(xcur)
        xcur += wi + gap
    y_off = 3.25
    labels_off = [
        "Normal logs",
        "BPMN",
        r"Estimate $\tilde{P}$" + "\nand duration kernels",
        "Conformal thresholds,\nCUSUM limits",
    ]
    for x, wi, lab in zip(xs, ws, labels_off):
        box(ax, x, y_off, wi, h, lab, C_OFF, fs=9.4)
    for i in range(3):
        arrow(ax, (xs[i] + ws[i], y_off + h / 2), (xs[i + 1], y_off + h / 2))
    ax.text(xs[1] + ws[1] + gap / 2, y_off + h + 0.16, "Offline",
            ha="center", va="bottom", fontproperties=_fp(11), color="#222222")

    y_on = 0.80
    h2 = 1.42
    ws2 = [2.55, 2.75, 3.70, 2.20, 3.10]
    gap2 = 0.42
    xs2 = []
    xcur = 0.40
    for wi in ws2:
        xs2.append(xcur)
        xcur += wi + gap2
    labels_on = [
        (C_MSG, r"Message $m_t$"),
        (C_HARD, "Hard-constraint layer\n" + r"$\mathbf{F}$ + assignment record"),
        (C_STAT, r"Timing $z$" + "\n" + r"Structural $\tilde{P}$"),
        (C_SEQ, "CUSUM"),
        (C_OUT, "Alarm or\ngated update"),
    ]
    for x, wi, (fc, lab) in zip(xs2, ws2, labels_on):
        box(ax, x, y_on, wi, h2, lab, fc, fs=9.2)
    for i in range(4):
        arrow(ax, (xs2[i] + ws2[i], y_on + h2 / 2), (xs2[i + 1], y_on + h2 / 2))
    ax.text(xs2[1] + ws2[1] + gap2 / 2, y_on + h2 + 0.16, "Online",
            ha="center", va="bottom", fontproperties=_fp(11), color="#222222")
    ax.text(xs2[2] + ws2[2] / 2, y_on - 0.18,
            r"$O(1)$ per message; parallel alarms split the budget as $\alpha/3$",
            ha="center", va="top", fontproperties=_fp(9.0), color=C_NOTE)

    fig.savefig(OUT + ".pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    subset_pdf(OUT + ".pdf")
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
