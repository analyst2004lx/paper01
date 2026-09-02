# -*- coding: utf-8 -*-
"""图 1 动机算例中文版。图内文字与 fig_motivating.py 相同，输出 fig_motivating_CN。"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fig_motivating as src  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    if not os.path.exists(src.DATA):
        raise SystemExit(f"缺 {src.DATA};先在 clbs/ 下跑 py -m tools.motivating --sweep")
    with open(src.DATA, encoding="utf-8") as f:
        d = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.15),
                             gridspec_kw={"width_ratios": [1.32, 1.0]})
    src.panel_layout(axes[0], d["params"])
    src.panel_reversal(axes[1], d)

    fig.tight_layout(w_pad=2.0)
    stem = os.path.join(HERE, "fig_motivating_CN")
    fig.savefig(stem + ".pdf", bbox_inches="tight", pad_inches=0.08)
    if os.environ.get("CLBS_FIG_PNG", "1") != "0":
        fig.savefig(stem + ".png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote", stem + ".pdf/.png")


if __name__ == "__main__":
    main()
