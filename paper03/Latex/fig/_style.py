# -*- coding: utf-8 -*-
"""Shared matplotlib style and data loaders for paper03 experiment figures."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

FIG = Path(__file__).resolve().parent
DATA = FIG / "data"

C_OURS = "#1B4F72"
C_BASE = "#5D6D7E"
C_ACCENT = "#B9770E"
C_WARN = "#922B21"
C_OK = "#196F3D"
C_MUTED = "#AEB6BF"


def apply_style() -> None:
    mpl.rcParams.update({
        "font.family": "serif",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
    })


def apply_style_cn() -> None:
    mpl.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"],
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
    })


def load() -> dict:
    return json.loads((DATA / "plot_data.json").read_text(encoding="utf-8"))


def save(fig, name: str) -> None:
    path = FIG / name
    fig.savefig(path, format="pdf")
    png = path.with_suffix(".png")
    fig.savefig(png, format="png", dpi=200)
    plt.close(fig)
    print("wrote", path.name)
