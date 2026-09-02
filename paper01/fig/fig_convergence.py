# -*- coding: utf-8 -*-
"""Convergence on a shared wall-clock axis (Section 5.3).

The one thing this figure exists to show is that the open-loop curve is not
comparable to the others, because it descends towards a value that cannot be
achieved.  Drawing all arms on a common time axis and then marking where the
open-loop plan actually lands when executed makes the gap visible in one
glance; plotting against generations instead would hide it twice over, once by
equalizing a budget the arms spend at wildly different rates, and once by
letting the surrogate curve be read as if it were an objective.

So: solid lines are realized makespan throughout (B1, B2), the dashed line is a
*surrogate* the search believes (B0's open-loop objective), and the cross marks
what that plan costs once executed.  The vertical distance between the dashed
line's end and the cross is the optimism, and it is the whole argument for
evaluating inside the loop.

Output stem is fig_convergence_closedloop, which is what paper.tex includes.
Data: clbs/output/ladder_convergence.csv and ladder_cost.csv (tools/ladder_diag.py).

Run: py paper01/fig/fig_convergence.py [case name]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import (COL, FS_ANNOT, FS_LEG, by, load_output,  # noqa: E402
                    mean, plt, save, span)

HINT = "py -u -m tools.ladder_diag --budget 90 --seeds 42,7,2024"
# B0 and B0+ share one open-loop search, so their curve is one curve; showing it
# twice would suggest two searches were run.  B0+ therefore appears only as a
# second landing point on the same dashed line.
CURVES = [("B1", "#6baed6", "-", "B1  closed loop, rule dispatch"),
          ("B2", "#08519c", "-", "B2  closed loop, reservation-aware dispatch")]
LANDING = [("B0", "#525252", "X", "B0  executed"),
           ("B0+", "#969696", "P", "B0$^+$  executed")]


def step_envelope(rows):
    """Mean best-so-far across seeds on a common grid, with the seed spread.

    Each seed logs one point per generation, so the raw time stamps do not line
    up between seeds.  We hold each seed's best-so-far constant between its own
    log points (which is what best-so-far means) and average on a shared grid,
    rather than averaging the k-th generation of each seed -- the latter would
    silently compare different instants.

    Returns (t, mean, lo, hi) where lo/hi are the min and max over seeds.  This
    batch has three seeds, which cannot support a quartile; drawing one anyway
    would dress the range up as a robust interval.  The band is the full range
    and the caption says so.
    """
    per_seed = by(rows, "seed")
    tmax = max(r["t_sec"] for r in rows)
    grid = [tmax * i / 120.0 for i in range(1, 121)]
    out = []
    for t in grid:
        vals = []
        for _k, rs in per_seed.items():
            rs = sorted(rs, key=lambda r: r["t_sec"])
            cur = None
            for r in rs:
                if r["t_sec"] <= t:
                    cur = r["best"]
                else:
                    break
            if cur is not None:
                vals.append(cur)
        if vals:
            lo, hi = span(vals)
            out.append((t, mean(vals), lo, hi))
    return out


def band(ax, pts, colour):
    """Shade the seed-to-seed range behind a curve.

    Drawn at low zorder and low alpha: the figure's argument is the gap between
    the dashed surrogate and the cross, and the band must not compete with it.
    Its job is only to stop the three mean curves from being read as if they
    were noise-free.
    """
    ax.fill_between([p[0] for p in pts], [p[2] for p in pts],
                    [p[3] for p in pts], color=colour, alpha=0.13,
                    linewidth=0, zorder=1)


def main() -> None:
    want = sys.argv[1] if len(sys.argv) > 1 else None
    conv = load_output("ladder_convergence.csv", HINT)
    cost = load_output("ladder_cost.csv", HINT)
    cases = sorted({r["case"] for r in conv})
    case = want or ("A funnel" if "A funnel" in cases else cases[0])
    if case not in cases:
        raise SystemExit("算例 %r 不在收敛数据里,可选:%s" % (case, cases))
    conv = [r for r in conv if r["case"] == case]
    cost = [r for r in cost if r["case"] == case]
    seeds = sorted({r["seed"] for r in conv})

    fig, ax = plt.subplots(figsize=(COL, 2.5))

    # The surrogate curve: B0's open-loop search, believing a constant matrix.
    sur = step_envelope([r for r in conv if r["arm"] == "B0"])
    if sur:
        band(ax, sur, "#525252")
        ax.plot([p[0] for p in sur], [p[1] for p in sur], ls=(0, (3, 1.6)),
                color="#525252", linewidth=1.2,
                label="B0  open-loop objective\n(surrogate, not achievable)")

    for arm, colour, ls, label in CURVES:
        pts = step_envelope([r for r in conv if r["arm"] == arm])
        if pts:
            band(ax, pts, colour)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], ls,
                    color=colour, label=label)

    # Where the open-loop plans actually land once executed.
    tmax = max(r["t_sec"] for r in conv)
    for arm, colour, marker, label in LANDING:
        vals = [r["makespan"] for r in cost if r["arm"] == arm]
        if not vals:
            continue
        y = mean(vals)
        ax.plot([tmax], [y], marker, color=colour, markersize=7,
                markeredgecolor="white", markeredgewidth=0.7, clip_on=False,
                zorder=6, label=label)

    # Name the optimism, with an arrow, so no one has to measure it off the axis.
    b0 = mean([r["makespan"] for r in cost if r["arm"] == "B0"])
    if sur and b0 == b0:
        end = sur[-1][1]
        ax.annotate("", xy=(tmax, b0), xytext=(tmax, end),
                    arrowprops=dict(arrowstyle="<->", color="#d62728",
                                    linewidth=0.9, shrinkA=0, shrinkB=0))
        ax.text(tmax * 0.985, 0.5 * (b0 + end),
                "optimism\n%+.1f%%" % (100.0 * (b0 - end) / end),
                ha="right", va="center", fontsize=FS_ANNOT, color="#d62728",
                fontweight="bold")

    ax.set_xlabel("wall-clock time (s)")
    ax.set_ylabel("best $C_{\\max}$ so far")
    ax.set_title("%s,  %d seeds  (band: min-max over seeds)"
                 % (case, len(seeds)), fontsize=8.5)
    # Anchored short of the right edge: the executed-plan markers sit at t_max
    # and the optimism arrow runs down the right margin, so a flush-right
    # legend lands on top of the two things the figure exists to compare.
    ax.legend(loc="upper right", bbox_to_anchor=(0.90, 1.02),
              fontsize=FS_LEG, handlelength=1.9, labelspacing=0.3)
    fig.tight_layout()
    save(fig, "fig_convergence_closedloop")


if __name__ == "__main__":
    main()
