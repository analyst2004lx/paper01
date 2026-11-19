# -*- coding: utf-8 -*-
"""机器节点容量敏感性中文版。数据与 fig_sens_capacity.py 相同。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import use_cjk  # noqa: E402
import fig_sens_capacity as src  # noqa: E402

use_cjk()


def main() -> None:
    src.draw(
        labels={"xlabel": "机器节点容量 $c$"},
        ylabel="$\\Delta C_{\\max}$（%）\n负值更好",
        foot=("每组 10 个种子，相同运行时间；误差棒为种子间均值标准误；"
              "实心 $=$ 未校正 Wilcoxon $p<%.2f$ 显著；"
              "点状竖线为表中对照点 $c=2$" % src.ALPHA),
        stem="fig_sens_capacity_CN",
        series=src.SERIES_CN,
    )


if __name__ == "__main__":
    main()
