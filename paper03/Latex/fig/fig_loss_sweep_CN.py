# -*- coding: utf-8 -*-
"""Loss sweep under motion hazard (paper03 fig:loss-sweep)."""
from __future__ import annotations

import csv
import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import C_BASE, C_OURS, C_WARN, DATA, apply_style_cn, save  # noqa: E402


def main():
    apply_style_cn()
    path = DATA / "loss_sweep.csv"
    if not path.exists():
        print("skip fig_loss_sweep_CN.pdf (no CSV)")
        return
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    ys = [0.0]
    for regime, color, marker in [
        ("motion_indep", C_BASE, "o"),
        ("motion_burst", C_OURS, "s"),
    ]:
        xs, ys = [], []
        for r in rows:
            if r["regime"] != regime:
                continue
            xs.append(float(r["p_loss"]))
            ys.append(float(r["bandwidth_bps"]))
        ax.plot(xs, ys, marker=marker, color=color, lw=1.2, ms=4, label=regime)
    ax.set_xscale("log")
    ax.set_xlabel(r"丢包概率 $p$")
    ax.set_ylabel("所需带宽 (B/s)")
    ax.set_title(r"丢包扫描（运动危害；PISTIS 标定点 $p{=}0.5$）")
    ax.axvline(0.5, color=C_WARN, ls=":", lw=0.9)
    ax.text(0.52, max(ys) * 0.55, r"$p{=}50\%$", color=C_WARN, fontsize=7)
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "fig_loss_sweep_CN.pdf")


if __name__ == "__main__":
    main()
