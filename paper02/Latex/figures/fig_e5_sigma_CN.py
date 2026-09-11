# -*- coding: utf-8 -*-
"""E5: 检出率与 rho* 随时序变异增大而塌掉。"""
from __future__ import print_function, division

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fig_e5_sigma import ARCHIVE, draw  # noqa: E402


def main():
    with open(ARCHIVE, encoding="utf-8") as f:
        blob = json.load(f)
    draw(blob, {
        "single": "单消息", "cusum": "CUSUM",
        "ylabel_dr": r"$\rho=0.30$ 检出率",
        "title_a": r"(a) 可检测性随 $\sigma$",
        "title_b": r"(b) 上界 $\rho^*(\sigma)$",
    }, "fig_e5_sigma_CN")


if __name__ == "__main__":
    main()
