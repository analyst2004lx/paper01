# -*- coding: utf-8 -*-
"""走廊时段加价中文版。数据与 fig_theta.py 相同，输出 fig_theta_CN。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _style as S  # noqa: E402
from fig_theta import series  # noqa: E402

S.use_cjk()

TAG_CN = {"low": "低争用", "mid": "中争用", "high": "高争用", "funnel": "漏斗"}


def main():
    wall = S.load("theta_sweep.csv")
    gen = S.load("theta_sweep_gen.csv")

    fig, axes = S.plt.subplots(1, 2, figsize=(S.FULL * 0.86, 2.25),
                               sharey=True)
    panels = [
        (axes[0], wall, "同挂钟预算", True),
        (axes[1], gen, "同评价次数", False),
    ]

    for ax, df, title, show_cost in panels:
        insts = list(dict.fromkeys(df["instance"]))
        ax2 = ax.twinx() if show_cost else None
        if ax2 is not None:
            ax2.grid(False)
        for inst in insts:
            sub = df[df["instance"] == inst]
            thetas = sorted(sub["theta"].unique())
            tag = sub["tag"].iloc[0]
            mus, errs = series(sub, thetas)
            ax.errorbar(thetas, mus, yerr=errs,
                        marker="o" if tag == "high" else "s", ms=4,
                        elinewidth=0.8, capsize=2,
                        color=S.TAG_COLOR.get(tag, "0.3"),
                        label=TAG_CN.get(tag, tag))
            if ax2 is not None:
                cost = [sub[sub["theta"] == t]["ms_per_eval"].mean()
                        for t in thetas]
                ax2.plot(thetas, cost, ls=":", lw=0.9,
                         color=S.TAG_COLOR.get(tag, "0.3"), alpha=0.55)
        ax.axhline(0, color="0.4", lw=0.8)
        ax.set_xlabel(r"加价强度 $\theta$")
        ax.set_title(title, fontsize=7.6, pad=4)
        if ax2 is not None:
            ax2.set_ylabel("单次评价耗时（虚线，ms）", fontsize=7,
                           color="0.45")
            ax2.tick_params(axis="y", colors="0.45", labelsize=6.5)

    axes[0].set_ylabel(r"相对 $\theta=0$ 的 $C_{\max}$ 变化（%）")
    axes[0].legend(loc="lower right", handletextpad=0.5)

    n_wall = wall.groupby("theta").size().min()
    n_gen = gen.groupby("theta").size().min()
    fig.text(0.0, -0.03,
             "正值表示更差。左图每点 %d 次运行，右图 %d 次；两个算例，均值 $\\pm$ 标准误"
             % (n_wall, n_gen),
             fontsize=S.FS_FOOT, color="0.35")
    fig.subplots_adjust(bottom=0.28, wspace=0.32)
    S.save(fig, "fig_theta_CN")


if __name__ == "__main__":
    main()
