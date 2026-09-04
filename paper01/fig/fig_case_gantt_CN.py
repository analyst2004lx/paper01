# -*- coding: utf-8 -*-
"""案例甘特图中文版。数据与 fig_case_gantt.py 相同，输出 fig_case_gantt_CN。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import (FULL, FS_ANNOT, FS_FOOT, FS_LEG,  # noqa: E402
                    FS_TICK_SM, plt, save, use_cjk)
import fig_case_gantt as src  # noqa: E402

use_cjk()

C_OP, C_LOADED, C_EMPTY = src.C_OP, src.C_LOADED, src.C_EMPTY
C_YIELD, C_IDLE = src.C_YIELD, src.C_IDLE
C_LABEL = src.C_LABEL


def draw(ax, tt, title, xmax):
    ops = tt["operations"]
    segs = tt["agv_segments"]
    machines = sorted({o["machine"] for o in ops})
    agvs = sorted({s["agv"] for s in segs})

    ypos, labels = {}, []
    y = 0
    for m in machines:
        ypos[("M", m)] = y
        labels.append("机械臂 %s" % m)
        y += 1
    y += 0.6
    for a in agvs:
        ypos[("A", a)] = y
        labels.append("AGV %s" % a)
        y += 1

    for o in ops:
        ax.broken_barh([(o["start"], o["finish"] - o["start"])],
                       (ypos[("M", o["machine"])] - 0.33, 0.66),
                       facecolors=C_OP, edgecolor="white", linewidth=0.4,
                       zorder=3)
        if o["finish"] - o["start"] >= 0.04 * xmax:
            ax.text(0.5 * (o["start"] + o["finish"]),
                    ypos[("M", o["machine"])], "J%s-%s" % (o["job"], o["i"]),
                    ha="center", va="center", fontsize=5.2, color=C_LABEL,
                    zorder=4)

    for s in segs:
        loaded = s["task"].endswith("loaded")
        ax.broken_barh([(s["enter"], max(s["exit"] - s["enter"], 1e-9))],
                       (ypos[("A", s["agv"])] - 0.3, 0.6),
                       facecolors=C_LOADED if loaded else C_EMPTY,
                       edgecolor="none", zorder=3)

    n_yield = 0
    for agv, t, gap, kind in src.agv_gaps(segs):
        ax.broken_barh([(t, gap)], (ypos[("A", agv)] - 0.3, 0.6),
                       facecolors=C_YIELD if kind == "yield" else C_IDLE,
                       edgecolor="none", hatch="///" if kind == "yield" else None,
                       linewidth=0.0, zorder=2)
        if kind == "yield":
            n_yield += gap

    ax.axvline(tt["makespan"], color="#111111", linewidth=1.0, zorder=6)
    ax.text(tt["makespan"], 0.11, " $C_{\\max}=%.0f$" % tt["makespan"],
            fontsize=7, va="bottom", fontweight="bold",
            transform=ax.get_xaxis_transform(), clip_on=False, zorder=7)
    if tt.get("surrogate"):
        ax.axvline(tt["surrogate"], color="#d62728", linewidth=0.9,
                   linestyle=(0, (3, 1.6)), zorder=6)
        ax.text(tt["surrogate"], -0.9, "代理目标 %.0f " % tt["surrogate"],
                fontsize=FS_ANNOT, color="#d62728", ha="right", va="center")

    ax.set_yticks([ypos[k] for k in ypos])
    ax.set_yticklabels(labels, fontsize=FS_TICK_SM)
    ax.set_ylim(y - 0.2, -0.8)
    ax.set_xlim(0, xmax)
    ax.set_title("%s   （让行合计 %.0f 时间单位）" % (title, n_yield),
                 fontsize=8.5, loc="left")
    ax.grid(axis="x", alpha=0.25)
    ax.grid(axis="y", visible=False)
    return n_yield


def main() -> None:
    tt = src.load_case()
    xmax = 1.06 * max(tt[a]["makespan"] for a in ("B0", "B2"))
    fig, axes = plt.subplots(2, 1, figsize=(FULL, 5.0), sharex=True)
    draw(axes[0], tt["B0"], "B0  开环，规则派车", xmax)
    draw(axes[1], tt["B2"], "B2  闭环，预约表感知派遣（本文）", xmax)
    axes[1].set_xlabel("时间")

    handles = [
        plt.Rectangle((0, 0), 1, 1, fc=C_OP, label="加工"),
        plt.Rectangle((0, 0), 1, 1, fc=C_LOADED, label="满载行驶"),
        plt.Rectangle((0, 0), 1, 1, fc=C_EMPTY, label="空载行驶"),
        plt.Rectangle((0, 0), 1, 1, fc=C_YIELD, hatch="///",
                      label="等待：走廊占用"),
        plt.Rectangle((0, 0), 1, 1, fc=C_IDLE, label="等待：无任务"),
    ]
    axes[0].legend(handles=handles, loc="upper center", ncol=5,
                   fontsize=FS_LEG,
                   bbox_to_anchor=(0.5, 1.30), frameon=False)
    fig.text(0.005, 0.005, "算例 %s，种子 %s，争用 %.1f%%"
             % (tt["B2"]["case"], tt["B2"]["seed"],
                100.0 * tt["B2"]["contention"]),
             fontsize=FS_FOOT, color="#777777")
    fig.tight_layout(rect=(0, 0.015, 1, 0.955))
    save(fig, "fig_case_gantt_CN")


if __name__ == "__main__":
    main()
