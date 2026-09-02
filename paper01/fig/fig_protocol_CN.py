# -*- coding: utf-8 -*-
"""评价开销–次数中文版。数据与 fig_protocol.py 相同，输出 fig_protocol_CN。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import (COL, FS_ANNOT, FS_FOOT, FS_LEG, LADDER,  # noqa: E402
                    LADDER_COLOR, LADDER_SHORT, load_output, plt, save,
                    use_cjk)
import fig_protocol as src  # noqa: E402

use_cjk()


def main() -> None:
    rows = load_output("ladder_cost.csv", src.HINT)
    fig, ax = plt.subplots(figsize=(COL, 2.5))

    xs = [10 ** (i / 40.0) for i in range(-40, 121)]
    ax.plot(xs, [1000.0 * src.BUDGET / x for x in xs], color="#bbbbbb",
            linewidth=0.9, zorder=1,
            label="预算上限（%.0f 秒）" % src.BUDGET)

    stall_at = float("nan")
    for arm in LADDER:
        rs = [r for r in rows if r["arm"] == arm]
        if not rs:
            continue
        ax.plot([r["ms_per_eval"] for r in rs], [r["decodes"] for r in rs],
                "o", color=LADDER_COLOR[arm], markersize=2.6, alpha=0.35,
                markeredgewidth=0.0, zorder=3)
        x, y = src.gmean([r["ms_per_eval"] for r in rs]), src.gmean(
            [r["decodes"] for r in rs])
        ax.plot([x], [y], "o", color=LADDER_COLOR[arm], markersize=6.5,
                markeredgecolor="white", markeredgewidth=0.7, zorder=5)
        ax.annotate(LADDER_SHORT[arm], (x, y), textcoords="offset points",
                    xytext=(7, 4), fontsize=7.2, color=LADDER_COLOR[arm],
                    fontweight="bold")
        if arm == "B0":
            stall_at = src.gmean([r["runtime_sec"] for r in rs])

    ax.text(0.03, 0.06,
            "B0 与 B0$^+$ 共用一次开环搜索，故共用一个点；\n"
            "开环在 %.0f 秒自行停止——已收敛，并非被预算打断" % stall_at,
            transform=ax.transAxes, fontsize=FS_FOOT, color="#777777",
            va="bottom")

    try:
        pr = load_output("prune_ablation.csv",
                         "py -u -m tools.prune_ablation --budget 90")
    except SystemExit:
        pr = None
    if pr:
        pts = {}
        for label in ("开", "关"):
            rs = [r for r in pr if r["arm"] == label]
            if rs:
                pts[label] = (src.gmean([r["ms_per_eval"] for r in rs]),
                              src.gmean([r["decodes"] for r in rs]))
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts["关"], pts["开"]
            ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                        arrowprops=dict(arrowstyle="-|>", color="#d95f02",
                                        linewidth=1.3))
            ax.text(x1, y1, "  剪枝 + 胜者复用\n  （输出相同）",
                    fontsize=FS_ANNOT, color="#d95f02", va="top",
                    fontweight="bold")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("单次评价开销（ms）")
    ax.set_ylabel("完成的评价次数")
    ax.legend(loc="upper right", fontsize=FS_LEG)
    fig.tight_layout()
    save(fig, "fig_protocol_CN")


if __name__ == "__main__":
    main()
