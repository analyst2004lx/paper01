# -*- coding: utf-8 -*-
"""Machine-node capacity sweep: CLBS vs OL/TS/AE over c=1..10 and inf.

Reads clbs_new/output/sens_c{1..10,inf}.csv (same protocol as tab:sens).
Two panels (S11, S21). Marker fill = uncorrected Wilcoxon p<0.05 over the
ten seeds of that cell — the dense sweep is for effect-size shape; Holm over
all intermediate cells would over-penalise and hide the trend the figure is
meant to show. Table tab:sens keeps the sparse c in {1,2,inf} with Holm.

Run: py fig_sens_capacity.py   (from paper01_SCI/CAIE/fig)
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "clbs_new")))

from _style import FS_FOOT, FS_LEG, mean, plt, save, sem  # noqa: E402

try:
    from algorithm.stats import wilcoxon_signed_rank
except Exception as exc:  # pragma: no cover
    raise SystemExit("need clbs_new on sys.path for Wilcoxon: %s" % exc)

OUT = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "clbs_new", "output"))

# Finite capacities then inf; x positions leave a gap before inf.
CAPS_FINITE = [str(i) for i in range(1, 11)]
CAPS = CAPS_FINITE + ["inf"]
XPOS = {str(i): float(i) for i in range(1, 11)}
XPOS["inf"] = 11.6

CASES = [("A funnel", "S11"), ("A high", "S21")]
# B0->OL, B0+->TS, BL->AE; relative gain (CLBS-base)/base in percent
SERIES_EN = [
    ("B0", "vs OL", "#08519c", "o", "-"),
    ("B0+", "vs TS", "#d95f02", "s", "--"),
    ("BL", "vs AE", "#1b9e77", "D", ":"),
]
SERIES_CN = [
    ("B0", "相对 OL", "#08519c", "o", "-"),
    ("B0+", "相对 TS", "#d95f02", "s", "--"),
    ("BL", "相对 AE", "#1b9e77", "D", ":"),
]
ALPHA = 0.05
HINT = "py -u -m tools.baseline_ladder --cap C --only \"A funnel,A high\" --arms B0,B2,BL --out sens_cC.csv"


def load_cap(cap: str):
    path = os.path.join(OUT, "sens_c%s.csv" % cap)
    if not os.path.isfile(path):
        raise SystemExit("missing %s\n  run: %s" % (path, HINT.replace("C", cap)))
    by = defaultdict(lambda: defaultdict(dict))
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by[r["case"]][r["arm"]][int(r["seed"])] = float(r["makespan"])
    return by


def cell_gain(by_case, arm: str):
    seeds = sorted(set(by_case[arm]) & set(by_case["B2"]))
    xa = [by_case[arm][s] for s in seeds]
    xb = [by_case["B2"][s] for s in seeds]
    rel = [(y - x) / x for x, y in zip(xa, xb)]
    p = wilcoxon_signed_rank(xb, xa)["p_value"]
    return 100.0 * mean(rel), 100.0 * sem(rel), float(p), len(seeds)


def draw(labels, ylabel, foot, stem, series=None):
    series = series or SERIES_EN
    loaded = {cap: load_cap(cap) for cap in CAPS}
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.55), sharey=True)

    for ax, (case, title) in zip(axes, CASES):
        for arm, lab, colour, marker, ls in series:
            xs, ys, es, sigs = [], [], [], []
            for cap in CAPS:
                g, e, p, n = cell_gain(loaded[cap][case], arm)
                if n < 3:
                    continue
                xs.append(XPOS[cap])
                ys.append(g)
                es.append(e)
                sigs.append(p < ALPHA)
            ax.plot(xs, ys, ls, color=colour, linewidth=1.2,
                    label=lab if title == "S11" else None, zorder=3)
            ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor=colour,
                        elinewidth=0.8, capsize=1.6, capthick=0.8,
                        alpha=0.7, zorder=3)
            for x, y, ok in zip(xs, ys, sigs):
                ax.plot([x], [y], marker, color=colour, markersize=4.4,
                        markerfacecolor=colour if ok else "white",
                        markeredgecolor=colour, markeredgewidth=1.0, zorder=4)

        # Reference capacity used in the main table / base point
        ax.axvline(2.0, color="#bbbbbb", linewidth=0.8, linestyle=":", zorder=1)
        ax.axhline(0.0, color="#444444", linewidth=0.7, zorder=2)
        # Visual break before inf
        ax.axvline(10.8, color="#cccccc", linewidth=0.6, linestyle="-", zorder=1)

        ax.set_title(title, fontsize=8.5)
        ax.set_xlabel(labels["xlabel"])
        xticks = list(range(1, 11)) + [XPOS["inf"]]
        ax.set_xticks(xticks)
        ax.set_xticklabels([str(i) for i in range(1, 11)] + [r"$\infty$"])

    axes[0].set_ylabel(ylabel)
    handles, labs = axes[0].get_legend_handles_labels()
    fig.tight_layout(rect=(0.0, 0.18, 1.0, 1.0))
    fig.legend(handles, labs, loc="lower center", ncol=3, fontsize=FS_LEG,
               handlelength=2.0, frameon=False, bbox_to_anchor=(0.5, 0.07))
    fig.text(0.5, 0.01, foot, ha="center", va="bottom",
             fontsize=FS_FOOT, color="#777777")
    save(fig, stem)


def main() -> None:
    draw(
        labels={"xlabel": "machine-node capacity $c$"},
        ylabel="$\\Delta C_{\\max}$ (%)\nnegative is better",
        foot=("10 seeds per cell, equal wall clock; error bar = SEM; "
              "filled = uncorrected Wilcoxon $p<%.2f$; "
              "dotted line = $c=2$ (table base point)" % ALPHA),
        stem="fig_sens_capacity",
        series=SERIES_EN,
    )


if __name__ == "__main__":
    main()
