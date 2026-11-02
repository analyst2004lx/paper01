"""预约影响集构造示意（中文版）。"""
from __future__ import annotations

import os

from _cjk_mpl import setup_cjk
from _closure_draw import draw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_closure_CN")

L = {
    "title_a": "(a) 走廊—时间图：起点占用",
    "title_b": r"(b) 预约依赖图与预约影响集 $\mathrm{Cl}(\mathrm{Src})$",
    "lane": {"es": r"$e^\star$", "e2": r"$e_2$", "e3": r"$e_3$"},
    "time": "时间",
    "block": "阻断时段",
    "seed_tag": "r1 与阻断时段重叠 → 起点",
    "done_tag": "已完成",
    "closure": r"$\mathrm{Cl}(\mathrm{Src})$",
    "seed": "起点",
    "outside": "r6：只有指向集内的边，\n从起点不可达，\n保持原计划",
    "e_yield": "让行（同走廊、异车）",
    "e_agv": "同车后继",
    "e_job": "同工件后继",
}

if __name__ == "__main__":
    setup_cjk()
    draw(L, OUT)
