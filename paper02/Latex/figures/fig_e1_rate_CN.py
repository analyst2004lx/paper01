# -*- coding: utf-8 -*-
"""E1 净检出率随注入率, 分攻击族。"""
from __future__ import print_function, division

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fig_e1_rate import METHODS, load_curves, draw  # noqa: E402

ATTACK_ZH = ["重放", "不可行", "抢跑", "模仿", "漂移", "抑制"]
METHODS_CN = [
    ("butla", "BUTLA", METHODS[0][2]),
    ("tabor", "TABOR式", METHODS[1][2]),
    ("hsmm", "HSMM", METHODS[2][2]),
    ("markov", "仅标签", METHODS[3][2]),
    ("ours", "本文", METHODS[4][2]),
]


def main():
    rates, curves, _ = load_curves(ATTACK_ZH)
    if len(rates) < 2:
        raise SystemExit("e1_archive 只有一个注入率, 请用 --rates 重跑")
    # temporarily swap English method names used inside draw via monkeypatch
    import fig_e1_rate as m
    m.METHODS = METHODS_CN
    draw(rates, curves, ATTACK_ZH, "净检出率（已减地板）", "fig_e1_rate_CN")


if __name__ == "__main__":
    main()
