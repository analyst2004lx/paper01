# -*- coding: utf-8 -*-
"""动机图中文版：同一排程、同一走廊阻断下，AOR 只看机器层得空范围，STRC 看走廊层得预约影响集。"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from _cjk_mpl import setup_cjk  # noqa: E402
from _motivate_draw import HEIGHT_RATIOS, draw_aor, draw_notes, draw_strc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_motivate_CN")

setup_cjk()
plt.rcParams.update({"figure.dpi": 200})

LABELS = {
    "title_aor": "(a) AOR：按工序依赖图划界",
    "title_strc": "(b) STRC：按预约影响集划界",
    "machine_layer": "机器层",
    "corridor_layer": "走廊层",
    "machine": "机器",
    "corridor": "走廊",
    "block": "阻断",
    "check": "√",
    "conflict": "车辆 $k_1$ 在走廊 $e^\\star$ 上的占用与阻断时段重叠，\n实际已冲突（AOR 不检查走廊层）",
    "aor_seed": "各工序均可执行 → 起点工序集为空",
    "aor_verdict": "重调度范围为空，判定无需重调度；但原排程实际已不可行",
    "seed": "起点",
    "impact_set": "预约影响集",
    "keep": "保持原计划",
    "done": "已完成，不可改写",
    "tag_yield": "让行",
    "tag_vehicle": "同车",
    "tag_machine": "同机",
    "lg_yield": "让行边：同一走廊上，前车的占用 → 紧随其后的他车占用\n（前车延误，后车须等前车驶离）",
    "lg_vehicle": "同车边：同一车辆的上一条占用 → 下一条占用",
    "lg_job_machine": "同工件 / 同机边：一道工序的运输占用 →\n同一工件或同一机器上下一道工序的运输占用",
    "lg_block": "走廊 $e^\\star$ 的阻断时段（禁止通行）",
    "lg_seed": "起点占用（与阻断时段重叠）",
    "lg_in": "影响集内的占用（允许改路）",
    "lg_out": "影响集外的占用（保持原计划）",
    "lg_done": "决策时刻前已完成的占用（不可改写）",
    "notes": "符号：$O_{ji}$ 为工件 $j$ 的第 $i$ 道工序；M1、M2 为机器；$k_1$、$k_2$、$k_3$ 为车辆"
             "（$k_1$ 运送工件 1，$k_2$ 运送工件 2，$k_3$ 运送其他工件）；\n"
             "$e^\\star$、$e_2$、$e_3$ 为走廊；走廊层每个色块是一辆车对一条走廊的一次占用，"
             "细点线连到该次运输送达的工序。",
}


def main() -> None:
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 7.7),
                             gridspec_kw={"height_ratios": HEIGHT_RATIOS})
    draw_aor(axes[0], LABELS)
    draw_strc(axes[1], LABELS)
    fig.tight_layout(h_pad=1.0, rect=(0, 0.05, 1, 1))
    draw_notes(fig, LABELS)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT + ".pdf", bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
