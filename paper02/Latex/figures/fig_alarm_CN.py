# -*- coding: utf-8 -*-
"""告警走读: A2 硬层否决 vs A3 分级残差 + CUSUM。"""
from __future__ import print_function, division

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fig_alarm import ARCHIVE, draw  # noqa: E402


def main():
    with open(ARCHIVE, encoding="utf-8") as f:
        blob = json.load(f)
    draw(blob, {
        "A2": "(a) A2 物理不可行注入——硬层一票否决",
        "A3": "(b) A3 抢跑重放——分级残差经 CUSUM 累积",
    }, {
        "z": r"时序 $z$",
        "S": r"CUSUM $S$",
        "hard": "硬层否决",
        "ylabel": r"$z$ / $S$",
    }, "fig_alarm_CN")


if __name__ == "__main__":
    main()
