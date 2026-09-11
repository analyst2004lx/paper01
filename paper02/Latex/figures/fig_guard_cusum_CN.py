# -*- coding: utf-8 -*-
"""Schematic: every sample inside the clock guard, CUSUM still crosses."""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP_SM, FP_TINY, C_OURS, C_B4, C_LAB, C_TIME, apply_style, save, set_cjk,
)


def main():
    apply_style()
    rng = np.random.RandomState(4)
    n = 24
    mu = 8.0
    rho = 0.22
    log_tau = np.log(mu) + np.log(1.0 - rho) + rng.normal(0.0, 0.07, size=n)
    tau = np.exp(log_tau)
    lo, hi = 0.50 * mu, 1.70 * mu
    inside = (tau >= lo) & (tau <= hi)
    if not inside.all():
        raise RuntimeError("schematic points escaped the clock guard")
    z = (log_tau - np.log(mu)) / 0.236
    h, c = 5.5, 0.35
    S = np.zeros(n)
    for i in range(n):
        prev = 0.0 if i == 0 else S[i - 1]
        S[i] = max(0.0, prev + (-z[i]) - c)

    t = np.arange(1, n + 1)
    fig, axes = plt.subplots(3, 1, figsize=(6.6, 4.75), sharex=True)
    ax = axes[0]
    ax.axhspan(lo, hi, color="#EEEEEE", zorder=0)
    ax.plot(t, tau, "o-", color=C_OURS, markersize=4, linewidth=1.1, zorder=2)
    ax.axhline(mu, color=C_LAB, linestyle="--", linewidth=0.8, zorder=1)
    set_cjk(ax, ylabel=u"停留 $\\tau$")
    ax.set_title(
        u"示意：$\\rho{=}0.22$ 的同向抢跑全部落在守卫内",
        fontproperties=FP_SM, loc="left")
    ax.set_ylim(lo * 0.85, hi * 1.08)

    ax = axes[1]
    ax.scatter(t, np.zeros(n), s=28, c=C_B4, zorder=3)
    ax.set_yticks([0.0, 1.0])
    ax.set_yticklabels([u"接受", u"拒绝"], fontproperties=FP_SM)
    set_cjk(ax, ylabel=u"时钟守卫")
    ax.set_ylim(-0.55, 1.35)
    ax.text(n - 0.4, 0.58, u"全部接受", ha="right",
            fontproperties=FP_TINY, color=C_LAB)

    ax = axes[2]
    ax.plot(t, S, "o-", color=C_OURS, markersize=4, linewidth=1.2)
    ax.axhline(h, color=C_TIME, linestyle="--", linewidth=1.0)
    ax.text(2.4, h + 0.45, u"$h$", color=C_TIME, fontproperties=FP_SM)
    hit = np.where(S >= h)[0]
    if len(hit) == 0:
        raise RuntimeError("schematic CUSUM never crossed h")
    ax.axvline(hit[0] + 1, color=C_TIME, linestyle=":", linewidth=0.9)
    ax.plot(hit[0] + 1, S[hit[0]], "o", color=C_TIME, markersize=7)
    set_cjk(ax, xlabel=u"消息序号", ylabel=u"CUSUM $S_t$")
    fig.tight_layout()
    save(fig, "fig_guard_cusum_CN")


if __name__ == "__main__":
    main()
