# -*- coding: utf-8 -*-
"""图 1 动机算例中文版。几何与数据同 fig_motivating.py，图内文字为本文件的中文副本。"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fig_motivating as src  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

STRINGS_CN = {
    "title_a": "(a) 通往快臂的唯一通路是一条排他干道",
    "trunk_tau": "τ = {tau:.0f}（排他）",
    "avoids_trunk": "不经过干道",
    "fast_arm": "快臂  t$^P$={proc:.0f}",
    "slow_arm": "慢臂  t$^P$={proc:.0f}",
    "m3_jobs": "{n:.0f} 个只能上 M3 加工的工件",
    "m3_yield": "只能上 M3 的工件反复穿越干道 → 让行等待",
    "two_assign": (
        "同一道工序的两个指派：快臂 M1 往返行程 {t1:.0f} + 加工 {p1:.0f}　|　"
        "慢臂 M2 往返行程 {t2:.0f} + 加工 {p2:.0f}"
    ),
    "title_b": "(b) 同一对指派：常数矩阵与无冲突路由",
    "group_ideal": "常数运输时间\n矩阵",
    "group_routed": "无冲突路由",
    "chosen": "选中",
    "reversal": "优劣对调：常数矩阵选 M{a}（快臂），无冲突路由选 M{b}（慢臂）",
    "ylabel": "完工时间 $C_{\\max}$",
}


def main() -> None:
    if not os.path.exists(src.DATA):
        raise SystemExit(f"缺 {src.DATA};先在 clbs/ 下跑 py -m tools.motivating --sweep")
    with open(src.DATA, encoding="utf-8") as f:
        d = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.15),
                             gridspec_kw={"width_ratios": [1.32, 1.0]})
    src.panel_layout(axes[0], d["params"], STRINGS_CN)
    src.panel_reversal(axes[1], d, STRINGS_CN)

    fig.tight_layout(w_pad=2.0)
    stem = os.path.join(HERE, "fig_motivating_CN")
    fig.savefig(stem + ".pdf", bbox_inches="tight", pad_inches=0.08)
    if os.environ.get("CLBS_FIG_PNG", "1") != "0":
        fig.savefig(stem + ".png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote", stem + ".pdf/.png")


if __name__ == "__main__":
    main()
