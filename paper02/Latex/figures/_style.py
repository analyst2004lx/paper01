# -*- coding: utf-8 -*-
"""Shared matplotlib style for paper02 figures (Python 3.7 / mpl 3.1)."""
from __future__ import print_function, division

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

HERE = os.path.dirname(os.path.abspath(__file__))

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttf",
]


def _find_cjk_font():
    for path in _FONT_CANDIDATES:
        if os.path.isfile(path):
            return FontProperties(fname=path)
    return FontProperties()


def _sized(base, size):
    path = base.get_file()
    fp = FontProperties(fname=path) if path else FontProperties()
    fp.set_size(size)
    return fp


FP = _find_cjk_font()
FP_SM = _sized(FP, 8)
FP_LG = _sized(FP, 10)
FP_TINY = _sized(FP, 7)

# Okabe-Ito, colour-blind friendly
C_OURS = "#0072B2"
C_B3 = "#E69F00"
C_B4 = "#009E73"
C_B5 = "#CC79A7"
C_LAB = "#7F7F7F"
C_TIME = "#D55E00"
C_HARD = "#E69F00"
C_STR = "#56B4E9"
C_GRID = "#D0D0D0"
C_LINE = "#333333"


def apply_style():
    plt.rcParams.update({
        "font.size": 9,
        "axes.linewidth": 0.8,
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "mathtext.fontset": "dejavusans",
        "legend.frameon": False,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.04,
    })


def save(fig, name):
    apply_style()
    pdf = os.path.join(HERE, name + ".pdf")
    png = os.path.join(HERE, name + ".png")
    fig.savefig(pdf)
    fig.savefig(png)
    plt.close(fig)
    print("wrote", pdf)
    return pdf


def set_cjk(ax, xlabel=None, ylabel=None, title=None):
    if xlabel:
        ax.set_xlabel(xlabel, fontproperties=FP)
    if ylabel:
        ax.set_ylabel(ylabel, fontproperties=FP)
    if title:
        ax.set_title(title, fontproperties=FP)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_fontproperties(FP_SM)


def legend(ax, **kwargs):
    kwargs.setdefault("prop", FP_SM)
    return ax.legend(**kwargs)
