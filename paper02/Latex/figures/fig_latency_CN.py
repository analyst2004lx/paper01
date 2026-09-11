# -*- coding: utf-8 -*-
"""E8: 逐消息时延箱线与设备数扩展。"""
from __future__ import print_function, division

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fig_latency import ARCHIVE, draw  # noqa: E402


def main():
    with open(ARCHIVE, encoding="utf-8") as f:
        blob = json.load(f)
    draw(blob, {
        "box": "逐消息", "ylabel": r"时延（$\mu$s）",
        "title_a": "(a) 时延分布",
        "title_b": r"(b) 随设备数 $M$",
    }, "fig_latency_CN")


if __name__ == "__main__":
    main()
