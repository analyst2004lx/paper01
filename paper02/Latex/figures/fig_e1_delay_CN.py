# -*- coding: utf-8 -*-
"""E1 检测延迟箱线图, A1-A6, 延迟预算 10。"""
from __future__ import print_function, division

import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fig_e1_delay import METHODS, _load, _draw  # noqa: E402
from _style import apply_style, save, set_cjk, legend  # noqa: E402

ATTACK_ZH = ["重放", "不可行", "抢跑", "模仿", "漂移", "抑制"]
METHODS_CN = [
    ("butla", "BUTLA", METHODS[0][2]),
    ("tabor", "TABOR式", METHODS[1][2]),
    ("hsmm", "HSMM", METHODS[2][2]),
    ("markov", "仅标签", METHODS[3][2]),
    ("ours", "本文", METHODS[4][2]),
]


def main():
    apply_style()
    buckets, meta = _load()
    fig, ax = plt.subplots(figsize=(7.2, 3.85))
    _draw(ax, buckets, ATTACK_ZH, methods=METHODS_CN)
    set_cjk(ax, ylabel="检测延迟（消息数）")
    legend(ax, ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.02),
           columnspacing=0.55, handlelength=1.15, handletextpad=0.3)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.86))
    save(fig, "fig_e1_delay_CN")
    print("primary_rate", meta.get("primary_rate"))


if __name__ == "__main__":
    main()
