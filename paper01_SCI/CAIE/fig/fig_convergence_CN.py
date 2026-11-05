# -*- coding: utf-8 -*-
"""收敛曲线中文版。数据与 fig_convergence.py 相同，输出 fig_convergence_closedloop_CN。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import (COL, FS_ANNOT, FS_LEG, by, load_output,  # noqa: E402
                    mean, plt, save, span, use_cjk)
import fig_convergence as src  # noqa: E402

use_cjk()

HINT = src.HINT
CURVES = [("B1", "#6baed6", "-", "B1  闭环，规则派车"),
          ("B2", "#08519c", "-", "B2  闭环，预约表感知派遣")]
LANDING = [("B0", "#525252", "X", "B0  执行后"),
           ("B0+", "#969696", "P", "B0$^+$  执行后")]
CASE_CN = {"A funnel": "漏斗算例"}


def main() -> None:
    want = sys.argv[1] if len(sys.argv) > 1 else None
    conv = load_output("ladder_convergence.csv", HINT)
    cost = load_output("ladder_cost.csv", HINT)
    cases = sorted({r["case"] for r in conv})
    case = want or ("A funnel" if "A funnel" in cases else cases[0])
    if case not in cases:
        raise SystemExit("算例 %r 不在收敛数据里,可选:%s" % (case, cases))
    conv = [r for r in conv if r["case"] == case]
    cost = [r for r in cost if r["case"] == case]
    seeds = sorted({r["seed"] for r in conv})

    fig, ax = plt.subplots(figsize=(COL, 2.5))

    sur = src.step_envelope([r for r in conv if r["arm"] == "B0"])
    if sur:
        src.band(ax, sur, "#525252")
        ax.plot([p[0] for p in sur], [p[1] for p in sur], ls=(0, (3, 1.6)),
                color="#525252", linewidth=1.2,
                label="B0  开环目标\n（代理量，不可实现）")

    for arm, colour, ls, label in CURVES:
        pts = src.step_envelope([r for r in conv if r["arm"] == arm])
        if pts:
            src.band(ax, pts, colour)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], ls,
                    color=colour, label=label)

    tmax = max(r["t_sec"] for r in conv)
    for arm, colour, marker, label in LANDING:
        vals = [r["makespan"] for r in cost if r["arm"] == arm]
        if not vals:
            continue
        y = mean(vals)
        ax.plot([tmax], [y], marker, color=colour, markersize=7,
                markeredgecolor="white", markeredgewidth=0.7, clip_on=False,
                zorder=6, label=label)

    b0 = mean([r["makespan"] for r in cost if r["arm"] == "B0"])
    if sur and b0 == b0:
        end = sur[-1][1]
        ax.annotate("", xy=(tmax, b0), xytext=(tmax, end),
                    arrowprops=dict(arrowstyle="<->", color="#d62728",
                                    linewidth=0.9, shrinkA=0, shrinkB=0))
        ax.text(tmax * 0.985, 0.5 * (b0 + end),
                "乐观幅度\n%+.1f%%" % (100.0 * (b0 - end) / end),
                ha="right", va="center", fontsize=FS_ANNOT, color="#d62728",
                fontweight="bold")

    ax.set_xlabel("挂钟时间（秒）")
    ax.set_ylabel("迄今最好 $C_{\\max}$")
    ax.set_title("%s，%d 个种子（色带：种子间最小–最大）"
                 % (CASE_CN.get(case, case), len(seeds)), fontsize=8.5)
    ax.legend(loc="upper right", bbox_to_anchor=(0.90, 1.02),
              fontsize=FS_LEG, handlelength=1.9, labelspacing=0.3)
    fig.tight_layout()
    save(fig, "fig_convergence_closedloop_CN")


if __name__ == "__main__":
    main()
