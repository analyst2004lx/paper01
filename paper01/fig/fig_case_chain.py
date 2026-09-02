# -*- coding: utf-8 -*-
"""Critical-chain attribution under B0 and B2 (Sections 5.4 and 5.8).

The Gantt chart shows what changed; this shows why the change is bounded.  The
chain that determines the makespan is decomposed by what each link was waiting
for, and the two arms are shown side by side.  The expected reading is that
removing corridor waiting does not shorten the chain by the amount removed:
another constraint -- processing, or waiting for a machine -- is promoted to
binding and takes up part of the slack.  That is the dilution argument, and it
is the reason a mechanism that names one bottleneck returns less than it
appears to.

Drawn as two stacked bars (composition, so the substitution is visible as a
change in mix) plus the per-link timeline underneath (so the reader can see it
is one chain and not a histogram of unrelated events).

Data: clbs/output/case_study/*.json, written by tools/ladder_diag.py.
Run: py paper01/fig/fig_case_chain.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import COL, FS_FOOT, FS_LEG, OUTPUT, plt, save  # noqa: E402

HINT = 'py -u -m tools.ladder_diag --case-study "A funnel"'

# Order is fixed so the two bars can be compared link-kind by link-kind, and so
# the transport-related kinds sit adjacent at the bottom of every bar.  The five
# labels are the ones decoder.CriticalItem defines; none is pooled away.
KINDS = [
    ("corridor", "waiting: corridor occupied", "#d62728"),
    ("vehicle", "waiting: no vehicle free", "#fd8d3c"),
    ("machine", "waiting: arm busy", "#9ecae1"),
    ("upstream", "waiting: upstream operation", "#4292c6"),
    ("operation", "processing", "#08519c"),
]
OTHER = ("other", "other", "#cccccc")


def load_arms():
    d = os.path.join(OUTPUT, "case_study")
    files = sorted(glob.glob(os.path.join(d, "*.json")))
    if not files:
        raise SystemExit("缺少 %s/*.json\n  在 clbs/ 目录下运行:%s" % (d, HINT))
    out = {}
    for p in files:
        with open(p, encoding="utf-8") as f:
            j = json.load(f)
        if not j.get("chain"):
            raise SystemExit(
                "%s 里没有 chain 字段:请用当前版本的 tools/ladder_diag.py 重新落盘"
                % os.path.basename(p))
        out[j["arm"]] = j
    for arm in ("B0", "B2"):
        if arm not in out:
            raise SystemExit("案例数据里缺少 %s 档" % arm)
    return out


def compose(chain):
    """Total amount per attribution kind, with unknown kinds pooled honestly."""
    known = {k for k, _l, _c in KINDS}
    agg = {k: 0.0 for k, _l, _c in KINDS}
    agg[OTHER[0]] = 0.0
    for it in chain:
        k = it["kind"] if it["kind"] in known else OTHER[0]
        agg[k] += max(it["amount"], 0.0)
    return agg


def main() -> None:
    arms = load_arms()
    order = ["B0", "B2"]
    comps = {a: compose(arms[a]["chain"]) for a in order}
    kinds = KINDS + [OTHER] if any(c[OTHER[0]] > 1e-9 for c in comps.values()) \
        else KINDS

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(COL, 3.5),
                                  gridspec_kw={"height_ratios": [1.5, 1]})

    for x, arm in enumerate(order):
        bottom = 0.0
        for k, label, colour in kinds:
            v = comps[arm][k]
            if v <= 1e-9:
                continue
            ax.bar(x, v, bottom=bottom, width=0.55, color=colour,
                   edgecolor="white", linewidth=0.6,
                   label=label if x == 0 else None, zorder=3)
            if v >= 0.06 * sum(comps[arm].values()):
                ax.text(x, bottom + v / 2, "%.0f" % v, ha="center",
                        va="center", fontsize=6.2, color="white",
                        fontweight="bold", zorder=4)
            bottom += v
        ax.text(x, bottom, "  $C_{\\max}=%.0f$" % arms[arm]["makespan"],
                ha="center", va="bottom", fontsize=7, fontweight="bold")

    # The comparison the section turns on: corridor waiting removed, versus
    # makespan actually recovered.  If the second is smaller, the difference was
    # absorbed by whatever became binding instead.
    d_corr = comps["B0"]["corridor"] - comps["B2"]["corridor"]
    d_mk = arms["B0"]["makespan"] - arms["B2"]["makespan"]
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(["B0\nopen loop", "B2\nproposed"], fontsize=7)
    ax.set_ylabel("critical-chain composition\n(time units)")
    # Headroom for the legend.  At the 7pt floor the four entries are wide
    # enough to land on the B2 bar's segment labels, and a legend that covers
    # the numbers it explains is worse than a shorter bar.
    ax.set_ylim(0, 1.62 * max(sum(comps[a].values()) for a in order))
    ax.legend(loc="upper right", fontsize=FS_LEG, labelspacing=0.3)
    ax.set_title("corridor waiting removed %.0f,  makespan recovered %.0f"
                 % (d_corr, d_mk), fontsize=7.6, loc="left")

    # The chain itself, so the bars are visibly a decomposition of one path.
    colour_of = {k: c for k, _l, c in kinds}
    for y, arm in enumerate(order):
        for it in arms[arm]["chain"]:
            k = it["kind"] if it["kind"] in colour_of else OTHER[0]
            w = max(it["t_end"] - it["t_start"], 0.0)
            if w <= 0:
                continue
            ax2.broken_barh([(it["t_start"], w)], (y - 0.3, 0.6),
                            facecolors=colour_of.get(k, OTHER[2]),
                            edgecolor="white", linewidth=0.3, zorder=3)
        ax2.axvline(arms[arm]["makespan"], color="#111111", linewidth=0.7,
                    zorder=2)
    ax2.set_yticks(range(len(order)))
    ax2.set_yticklabels(["B0", "B2"], fontsize=7)
    ax2.set_ylim(len(order) - 0.5, -0.5)
    ax2.set_xlabel("time  (the chain, in place)")
    ax2.grid(axis="y", visible=False)

    fig.text(0.005, 0.005, "instance %s,  seed %s"
             % (arms["B2"]["case"], arms["B2"]["seed"]),
             fontsize=FS_FOOT, color="#777777")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    save(fig, "fig_case_chain")


if __name__ == "__main__":
    main()
