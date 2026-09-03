# -*- coding: utf-8 -*-
"""合并案例图中文版。数据与 fig_case.py 相同，输出 fig_case_CN。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import use_cjk  # noqa: E402
import fig_case as src  # noqa: E402
import fig_case_chain as chain  # noqa: E402

use_cjk()

STRINGS = {
    "title_b0": "B0  开环，规则派车",
    "title_b2": "B2  闭环，预约表感知派遣（本文）",
    "xlabel": "时间",
    "ylabel": "关键链构成（时间单位）",
    "xtick_b0": "B0\n开环",
    "xtick_b2": "B2\n本文",
    "bar_title": "走廊等待消除 %.0f，收回完工时间 %.0f",
    "foot": "算例 %s，种子 %s，争用 %.1f%%",
    "leg_proc": "加工",
    "leg_loaded": "满载行驶",
    "leg_empty": "空载行驶",
    "leg_yield": "等待：走廊占用",
    "leg_idle": "等待：无任务",
    "arm_label": "机械臂 %s",
    "agv_label": "AGV %s",
    "yield_suffix": "   （让行合计 %.0f 时间单位）",
}

# Override chain.KINDS labels used by the composition bars.
chain.KINDS = [
    ("corridor", "等待：走廊占用", "#d62728"),
    ("vehicle", "等待：无车可用", "#fd8d3c"),
    ("machine", "等待：机械臂繁忙", "#9ecae1"),
    ("upstream", "等待：上游工序", "#4292c6"),
    ("operation", "加工", "#08519c"),
]
chain.OTHER = ("other", "其他", "#cccccc")


def main() -> None:
    src.render(STRINGS, "fig_case_CN")


if __name__ == "__main__":
    main()
