# -*- coding: utf-8 -*-
"""
Generate experimental / theory figures for the Chinese draft.
Numbers are taken from the Trier evaluation reported in the paper
(E1 table, E2 ablation, E4 rho scan, CUSUM delay, coverage matrix).
Do not invent anomalous-traffic scan curves.

Usage (from this folder):
    python plot_figures.py
"""
from __future__ import print_function, division

import os
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _style import (  # noqa: E402
    FP, FP_SM, FP_TINY, C_OURS, C_B3, C_B4, C_B5, C_LAB,
    C_TIME, C_HARD, C_STR, C_LINE, apply_style, save, set_cjk, legend,
)

ATTACKS = [u"A1", u"A2", u"A3", u"A4", u"A5", u"A6"]
ATTACK_ZH = [u"\u91cd\u653e", u"\u4e0d\u53ef\u884c", u"\u62a2\u8dd1",
             u"\u6a21\u4eff", u"\u6f02\u79fb", u"\u6291\u5236"]


def fig_coverage():
    """Channel lift = DR - FPR, production three paths only."""
    apply_style()
    # rows: hard F, structure, timing; cols A1-A6
    dr = np.array([
        [0.22, 0.98, 0.00, 0.03, 0.00, 0.00],
        [0.19, 0.29, 0.02, 0.02, 0.01, 0.17],
        [0.03, 0.00, 0.43, 0.00, 0.48, 0.04],
    ], dtype=float)
    fpr = np.array([
        [0.00, 0.06, 0.00, 0.00, 0.00, 0.00],
        [0.02, 0.03, 0.01, 0.03, 0.01, 0.02],
        [0.03, 0.02, 0.02, 0.02, 0.03, 0.02],
    ], dtype=float)
    lift = dr - fpr

    cmap = LinearSegmentedColormap.from_list(
        "lift", ["#F7F7F7", "#FEE0D2", "#FC9272", "#DE2D26", "#A50F15"])
    fig, ax = plt.subplots(figsize=(6.4, 2.55))
    im = ax.imshow(lift, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(np.arange(6))
    ax.set_yticks(np.arange(3))
    ax.set_xticklabels([u"%s %s" % (a, z) for a, z in zip(ATTACKS, ATTACK_ZH)],
                       fontproperties=FP_SM)
    ax.set_yticklabels(
        [u"\u786c\u5c42 F", u"\u7ed3\u6784", u"\u65f6\u5e8f"],
        fontproperties=FP)
    ax.spines["top"].set_visible(True)
    ax.spines["right"].set_visible(True)
    for i in range(3):
        for j in range(6):
            val = lift[i, j]
            txt = u"%.2f" % val
            color = "white" if val >= 0.45 else C_LINE
            ax.text(j, i, txt, ha="center", va="center", color=color,
                    fontproperties=FP_SM)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(u"\u51c0\u63d0\u5347 DR$-$FPR", fontproperties=FP_SM)
    for t in cbar.ax.get_yticklabels():
        t.set_fontproperties(FP_TINY)
    fig.tight_layout()
    save(fig, "fig_coverage")


def fig_e1_dr():
    """E1 sequential net DR, floor subtracted, alpha=0.01."""
    apply_style()
    # B3 BUTLA, B4 TABOR, B5 HSMM, label-only Markov, ours
    data = {
        u"BUTLA":     np.array([0.04, 0.37, 0.10, -0.04, 0.59, -0.05]),
        u"TABOR\u5f0f": np.array([0.04, 0.67, 0.10, -0.01, 0.48, -0.01]),
        u"HSMM":      np.array([-0.01, 0.31, 0.06, 0.02, 0.25, 0.05]),
        u"\u4ec5\u6807\u7b7e": np.array([0.48, 0.76, -0.01, 0.23, 0.00, 0.28]),
        u"\u672c\u6587":     np.array([0.55, 0.95, 0.18, 0.17, 0.87, 0.14]),
    }
    colors = [C_B3, C_B4, C_B5, C_LAB, C_OURS]
    names = list(data.keys())
    x = np.arange(6)
    n = len(names)
    width = 0.15
    fig, ax = plt.subplots(figsize=(6.8, 3.35))
    for k, name in enumerate(names):
        offset = (k - (n - 1) / 2.0) * width
        ax.bar(x + offset, data[name], width=width * 0.92, color=colors[k],
               edgecolor="white", linewidth=0.4, label=name, zorder=3)
    ax.axhline(0.0, color=C_LINE, linewidth=0.6, zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels([u"%s\n%s" % (a, z) for a, z in zip(ATTACKS, ATTACK_ZH)])
    ax.set_ylim(-0.12, 1.05)
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    set_cjk(ax, ylabel=u"\u51c0\u68c0\u51fa\u7387\uff08\u5df2\u51cf\u5730\u677f\uff09")
    legend(ax, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.14),
           columnspacing=0.8, handlelength=1.2, handletextpad=0.35)
    fig.tight_layout()
    save(fig, "fig_e1_dr")


def fig_e2_ablation():
    """E2: production-relevant arms, per-channel alpha fixed, alpha=0.05."""
    apply_style()
    full = np.array([0.45, 0.74, 0.27, 0.15, 0.70, 0.15])
    no_t = np.array([0.54, 0.84, 0.01, 0.22, -0.02, 0.21])
    no_f = np.array([0.29, 0.51, 0.27, 0.09, 0.70, 0.15])
    no_s = np.array([0.37, 0.81, 0.26, 0.04, 0.78, -0.03])
    series = [
        (u"\u5b8c\u6574", full, C_OURS),
        (u"\u53bb\u65f6\u5e8f", no_t, C_TIME),
        (u"\u53bb\u786c\u5c42", no_f, C_HARD),
        (u"\u53bb\u7ed3\u6784", no_s, C_STR),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.2),
                             gridspec_kw={"width_ratios": [2.35, 1.0]})
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
    ax.set_ylim(-0.08, 1.0)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    set_cjk(ax, ylabel=u"\u51c0\u68c0\u51fa\u7387")
    ax.set_title(u"(a) \u6309\u653b\u51fb\u65cf", fontproperties=FP_SM, loc="left")
    legend(ax, ncol=2, loc="upper right", columnspacing=0.7,
           handlelength=1.1, handletextpad=0.3)

    ax2 = axes[1]
    deltas = np.array([-0.11, -0.07, -0.04])
    labels = [u"\u53bb\u65f6\u5e8f", u"\u53bb\u786c\u5c42", u"\u53bb\u7ed3\u6784"]
    cols = [C_TIME, C_HARD, C_STR]
    y = np.arange(3)
    ax2.barh(y, deltas, color=cols, edgecolor="white", height=0.55, zorder=3)
    ax2.axvline(0.0, color=C_LINE, linewidth=0.6)
    ax2.set_yticks(y)
    ax2.set_yticklabels(labels, fontproperties=FP_SM)
    ax2.set_xlim(-0.14, 0.02)
    ax2.xaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax2.set_axisbelow(True)
    set_cjk(ax2, xlabel=u"\u5747\u503c\u53d8\u5316 $\\Delta$")
    ax2.set_title(u"(b) \u516d\u65cf\u5747\u503c", fontproperties=FP_SM, loc="left")
    for yi, d in zip(y, deltas):
        ax2.text(d - 0.004, yi, u"%.2f" % d, va="center", ha="right",
                 fontproperties=FP_TINY, color=C_LINE)
    fig.tight_layout()
    save(fig, "fig_e2_ablation")


def fig_e4_rho():
    """Single-message DR vs theory; vertical line at rho*."""
    apply_style()
    rho = np.array([0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50])
    meas = np.array([0.060, 0.105, 0.199, 0.288, 0.452, 0.712, 0.874])
    theo = np.array([0.051, 0.127, 0.226, 0.317, 0.497, 0.701, 0.851])
    sigma = 0.236
    z = 2.326347874  # Phi^{-1}(0.99)
    rho_star = 1.0 - np.exp(-sigma * z)

    fig, ax = plt.subplots(figsize=(5.6, 3.35))
    # Table theory averages heterogeneous groups; do not overlay a
    # single-Gaussian CDF at the global sigma.
    ax.plot(rho, theo, "s--", color=C_LAB, linewidth=1.5, markersize=5,
            label=u"\u7406\u8bba\u9884\u6d4b", zorder=2)
    ax.plot(rho, meas, "o-", color=C_OURS, linewidth=1.8, markersize=6,
            label=u"\u5b9e\u6d4b\u5355\u6d88\u606f DR", zorder=3)
    ax.axvline(rho_star, color=C_TIME, linestyle=":", linewidth=1.2, zorder=1)
    ax.text(rho_star + 0.012, 0.18,
            u"$\\rho^*=42.2\\%%$", color=C_TIME, fontproperties=FP_SM)
    ax.set_xlim(0.0, 0.55)
    ax.set_ylim(0.0, 1.0)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    set_cjk(ax, xlabel=u"\u62a2\u8dd1\u91cf $\\rho$", ylabel=u"\u5355\u6d88\u606f\u68c0\u51fa\u7387")
    legend(ax, loc="upper left")
    fig.tight_layout()
    save(fig, "fig_e4_rho")


def fig_delay():
    """CUSUM vs single-message DR, and detection delay in messages."""
    apply_style()
    rho = np.array([0.05, 0.10, 0.15, 0.20, 0.30, 0.50])
    single = np.array([0.060, 0.105, 0.199, 0.288, 0.452, 0.874])
    cusum = np.array([0.245, 0.604, 0.868, 0.925, 0.962, 0.962])
    med = np.array([15, 12, 10, 8, 4, 2], dtype=float)
    p90 = np.array([24, 26, 19, 11, 7, 3], dtype=float)

    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.15))
    ax = axes[0]
    ax.plot(rho, single, "s--", color=C_LAB, linewidth=1.5, markersize=5,
            label=u"\u5355\u6d88\u606f")
    ax.plot(rho, cusum, "o-", color=C_OURS, linewidth=1.8, markersize=6,
            label=u"CUSUM")
    ax.set_xlim(0.0, 0.55)
    ax.set_ylim(0.0, 1.05)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, xlabel=u"\u62a2\u8dd1\u91cf $\\rho$", ylabel=u"\u68c0\u51fa\u7387")
    ax.set_title(u"(a) \u5f31\u4fe1\u53f7\u7d2f\u79ef", fontproperties=FP_SM, loc="left")
    legend(ax, loc="lower right")

    ax2 = axes[1]
    yerr = np.vstack([np.zeros_like(med), p90 - med])
    ax2.errorbar(rho, med, yerr=yerr, fmt="o-", color=C_OURS,
                 linewidth=1.8, markersize=6, capsize=3, ecolor=C_STR,
                 label=u"\u4e2d\u4f4d / $p_{90}$")
    ax2.set_xlim(0.0, 0.55)
    ax2.set_ylim(0, 30)
    ax2.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax2.set_axisbelow(True)
    set_cjk(ax2, xlabel=u"\u62a2\u8dd1\u91cf $\\rho$",
            ylabel=u"\u68c0\u6d4b\u5ef6\u8fdf\uff08\u6d88\u606f\u6570\uff09")
    ax2.set_title(u"(b) \u4ee5\u6d88\u606f\u6570\u8ba1", fontproperties=FP_SM, loc="left")
    legend(ax2, loc="upper right")
    fig.tight_layout()
    save(fig, "fig_delay")


def fig_sigma():
    """rho*(sigma) curve; global sigma and extreme groups marked."""
    apply_style()
    z = 2.326347874
    sig = np.linspace(0.0, 2.0, 400)
    rho = 1.0 - np.exp(-sig * z)

    fig, ax = plt.subplots(figsize=(5.6, 3.25))
    ax.plot(sig, rho, color=C_OURS, linewidth=1.9, zorder=2,
            label=u"$\\rho^*(\\alpha,\\sigma)=1-e^{-\\sigma z_{1-\\alpha}}$")
    marks = [
        (0.007, 1.0 - np.exp(-0.007 * z), u"$\\sigma{=}0.007$\n(dm/lower)"),
        (0.236, 1.0 - np.exp(-0.236 * z), u"\u5168\u5c40 $\\sigma{=}0.236$"),
        (1.843, 1.0 - np.exp(-1.843 * z), u"$\\sigma{=}1.843$\n(\u4eba\u5de5\u5de5\u4f4d)"),
    ]
    ax.axvline(0.236, color=C_TIME, linestyle=":", linewidth=1.0, zorder=1)
    ax.axhline(1.0 - np.exp(-0.236 * z), color=C_TIME, linestyle=":",
               linewidth=1.0, zorder=1)
    for s, r, lab in marks:
        ax.plot(s, r, "o", color=C_TIME, markersize=6, zorder=3)
    ax.annotate(marks[0][2], xy=(marks[0][0], marks[0][1]),
                xytext=(0.18, 0.12), fontproperties=FP_TINY, color=C_LINE,
                arrowprops=dict(arrowstyle="-", color=C_LAB, lw=0.7))
    ax.annotate(marks[1][2], xy=(marks[1][0], marks[1][1]),
                xytext=(0.45, 0.28), fontproperties=FP_TINY, color=C_LINE,
                arrowprops=dict(arrowstyle="-", color=C_LAB, lw=0.7))
    ax.annotate(marks[2][2], xy=(marks[2][0], marks[2][1]),
                xytext=(1.15, 0.72), fontproperties=FP_TINY, color=C_LINE,
                arrowprops=dict(arrowstyle="-", color=C_LAB, lw=0.7))
    ax.set_xlim(0.0, 2.05)
    ax.set_ylim(0.0, 1.05)
    ax.yaxis.grid(True, linestyle=":", color="#DDDDDD")
    ax.set_axisbelow(True)
    set_cjk(ax, xlabel=u"\u65f6\u5e8f\u53d8\u5f02 $\\sigma$",
            ylabel=u"\u62a2\u8dd1\u91cf\u4e0a\u754c $\\rho^*$")
    legend(ax, loc="lower right")
    fig.tight_layout()
    save(fig, "fig_sigma")


def fig_guard_cusum():
    """Schematic: every sample inside the clock guard, CUSUM still crosses."""
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
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 4.55), sharex=True)
    ax = axes[0]
    ax.axhspan(lo, hi, color="#EEEEEE", zorder=0)
    ax.plot(t, tau, "o-", color=C_OURS, markersize=4, linewidth=1.1, zorder=2)
    ax.axhline(mu, color=C_LAB, linestyle="--", linewidth=0.8, zorder=1)
    set_cjk(ax, ylabel=u"\u505c\u7559 $\\tau$")
    ax.set_title(
        u"\u793a\u610f\uff1a$\\rho{=}0.22$ \u7684\u540c\u5411\u62a2\u8dd1\u5168\u90e8\u843d\u5728\u5b88\u536b\u5185",
        fontproperties=FP_SM, loc="left")
    ax.set_ylim(lo * 0.85, hi * 1.08)

    ax = axes[1]
    ax.scatter(t, np.zeros(n), s=28, c=C_B4, zorder=3)
    ax.set_yticks([0.0, 1.0])
    ax.set_yticklabels([u"\u63a5\u53d7", u"\u62d2\u7edd"], fontproperties=FP_SM)
    set_cjk(ax, ylabel=u"\u65f6\u949f\u5b88\u536b")
    ax.set_ylim(-0.55, 1.35)
    ax.text(n, 0.35, u"\u5168\u90e8\u63a5\u53d7", ha="right",
            fontproperties=FP_TINY, color=C_LAB)

    ax = axes[2]
    ax.plot(t, S, "o-", color=C_OURS, markersize=4, linewidth=1.2)
    ax.axhline(h, color=C_TIME, linestyle="--", linewidth=1.0)
    ax.text(1.2, h + 0.25, u"$h$", color=C_TIME, fontproperties=FP_SM)
    hit = np.where(S >= h)[0]
    if len(hit) == 0:
        raise RuntimeError("schematic CUSUM never crossed h")
    ax.axvline(hit[0] + 1, color=C_TIME, linestyle=":", linewidth=0.9)
    ax.plot(hit[0] + 1, S[hit[0]], "o", color=C_TIME, markersize=7)
    set_cjk(ax, xlabel=u"\u6d88\u606f\u5e8f\u53f7", ylabel=u"CUSUM $S_t$")
    fig.tight_layout()
    save(fig, "fig_guard_cusum")


def fig_latency():
    """Per-message processing time percentiles."""
    apply_style()
    labels = [u"\u4e2d\u4f4d", u"$p_{95}$", u"$p_{99}$"]
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
    set_cjk(ax, ylabel=u"\u9010\u6d88\u606f\u65f6\u5ef6")
    fig.tight_layout()
    save(fig, "fig_latency")


def main():
    fig_coverage()
    fig_e1_dr()
    fig_e2_ablation()
    fig_e4_rho()
    fig_delay()
    fig_sigma()
    fig_guard_cusum()
    fig_latency()
    print("done")


if __name__ == "__main__":
    main()
