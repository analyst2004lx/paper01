# -*- coding: utf-8 -*-
"""CUSUM 相对单消息的功效, 以及随 rho 的检测延迟箱线图。"""
from __future__ import print_function, division

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fig_delay import draw, load_e4  # noqa: E402


def main():
    draw(load_e4(), {
        "single": "单消息",
        "cusum": "CUSUM",
        "xlabel_rho": r"抢跑量 $\rho$",
        "ylabel_dr": "检出率",
        "ylabel_delay": "检测延迟（消息数）",
        "title_a": "(a) 弱信号累积",
        "title_b": "(b) 延迟箱线图",
    }, "fig_delay_CN")


if __name__ == "__main__":
    main()
