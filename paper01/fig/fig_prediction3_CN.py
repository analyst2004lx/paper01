# -*- coding: utf-8 -*-
"""三族主效应中文版。数据与 fig_prediction3.py 相同，输出 fig_prediction3_CN。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "clbs")))

from _style import (FS_ANNOT, FS_FOOT, FS_LEG, by,  # noqa: E402
                    load_output, mark_draft, plt, save, use_cjk)
import fig_prediction3 as src  # noqa: E402

use_cjk()

EFFECTS = [
    ("B0", "B1", "闭环\n（派车规则固定）", "#08519c", "o", "-"),
    ("B1", "B2", "预约表感知派遣\n（闭环固定）", "#d95f02", "s", "--"),
]
PANELS = [
    ("A", "布局", "争用强度（%）"),
    ("B", "车臂比", "$N_A/N_M$"),
    ("C", "柔性", "$F$"),
]


def main() -> None:
    rows = load_output("baseline_ladder.csv", src.HINT)
    seeds = sorted({r["seed"] for r in rows})
    cells = by(rows, "case")
    if len(seeds) < 10:
        mark_draft("%d seeds, protocol wants 10" % len(seeds))
    if len(cells) < 10:
        mark_draft("%d of 10 instance cells" % len(cells))

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.45), sharey=True)
    for ax, (fam, fam_name, xlabel) in zip(axes, PANELS):
        names = src.members(cells, fam)
        if not names:
            ax.text(0.5, 0.5, "族 %s 缺失" % fam, transform=ax.transAxes,
                    ha="center", va="center", fontsize=FS_ANNOT,
                    color="#999999")
            ax.set_xlabel(xlabel)
            continue
        cont = {c: cells[(c,)][0]["contention"] for c in names}
        names.sort(key=lambda c: src.level(c, fam, cont[c]))
        xs = [src.level(c, fam, cont[c]) for c in names]

        for ka, kb, label, colour, marker, ls in EFFECTS:
            adj = src.adjusted(cells, ka, kb)
            eff = [src.cell_effect(cells[(c,)], ka, kb) for c in names]
            ys = [e[0] for e in eff]
            es = [e[1] for e in eff]
            ax.plot(xs, ys, ls, color=colour, linewidth=1.2,
                    label=label if fam == "A" else None, zorder=3,
                    clip_on=False)
            ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor=colour,
                        elinewidth=0.8, capsize=1.8, capthick=0.8,
                        alpha=0.7, zorder=3, clip_on=False)
            for x, y, c in zip(xs, ys, names):
                ax.plot([x], [y], marker, color=colour, markersize=4.6,
                        markerfacecolor=colour if adj[c] < src.ALPHA else "white",
                        markeredgecolor=colour, markeredgewidth=1.0,
                        zorder=4, clip_on=False)

        if fam != "A" and src.BASE_CELL in names:
            ax.axvline(src.BASE_LEVEL[fam], color="#999999", linewidth=0.7,
                       linestyle=":", zorder=1)

        ax.axhline(0, color="#444444", linewidth=0.7, zorder=2)
        ax.set_xlabel(xlabel)
        ax.set_title("%s：%s" % (fam, fam_name), fontsize=8.5)
        if fam != "A":
            ax.set_xticks(xs)

    axes[0].set_ylabel("$\\Delta C_{\\max}$（%）\n负值更好")
    axes[0].legend(loc="lower left", fontsize=FS_LEG, handlelength=1.8)
    fig.tight_layout(rect=(0.0, 0.095, 1.0, 1.0))
    fig.text(0.995, 0.012,
             "每组 %d 个种子，同挂钟；误差棒为种子间均值标准误；\n"
             "实心标记 $=$ 该组 Holm 校正后 $p<%.2f$ 显著（族为该效应的 %d 组）"
             % (len(seeds), src.ALPHA, len(cells)),
             ha="right", va="bottom", fontsize=FS_FOOT, color="#777777")
    save(fig, "fig_prediction3_CN")


if __name__ == "__main__":
    main()
