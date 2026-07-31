"""Figure: why the comparison protocol is not a formality.

Left: the cost of a single fitness evaluation, which differs by two orders of
magnitude across the chain because the arms do not evaluate the same object --
the two-stage arm searches against a constant travel matrix, the closed loop
routes every candidate conflict-free, and the priced variant additionally runs
a multi-label search.

Right: how many evaluations each arm therefore completes inside the *same*
wall-clock budget.  The two panels together are the argument: at equal
generations the closed loop would be handed tens of times more computation,
and at equal time the cheap surrogate is handed tens of times more search.
Neither budget is neutral, so both must be reported.
"""
from __future__ import annotations

import numpy as np

import _style as S

SKIP = {"rule"}                      # single decoding, no budget applies


def main():
    m = S.require_seeds()
    cells = S.load("cells.csv")
    cells = cells[cells["ms_per_eval"].notna() & ~cells["arm"].isin(SKIP)]
    arms = [a for a in S.ARM_ORDER if (cells["arm"] == a).any()]
    xs = np.arange(len(arms))
    colors = [S.ARM_COLOR[a] for a in arms]

    fig, (ax1, ax2) = S.plt.subplots(1, 2, figsize=(S.FULL * 0.78, 2.2))

    cost = [cells[cells["arm"] == a]["ms_per_eval"].mean() for a in arms]
    ax1.bar(xs, cost, 0.66, color=colors)
    ax1.set_yscale("log")
    ax1.set_ylabel("ms per evaluation")
    for x, v in zip(xs, cost):
        ax1.text(x, v * 1.15, ("%.2f" if v < 10 else "%.0f") % v, ha="center",
                 va="bottom", fontsize=6.2)
    ratio = max(cost) / min(cost)
    ax1.set_title(r"cost per evaluation (%.0f$\times$ span)" % ratio,
                  fontsize=7.4)

    ev = [cells[cells["arm"] == a]["mean_evals"].mean() for a in arms]
    ax2.bar(xs, ev, 0.66, color=colors)
    ax2.set_yscale("log")
    ax2.set_ylabel("evaluations within the budget")
    ax2.set_title("search performed at equal wall-clock", fontsize=7.4)

    for ax in (ax1, ax2):
        ax.set_xticks(xs)
        ax.set_xticklabels([S.ARM_SHORT[a] for a in arms], rotation=32,
                           ha="right", fontsize=6.5)
        ax.grid(axis="x", alpha=0)

    fig.subplots_adjust(bottom=0.34, wspace=0.42)
    fig.text(0.5, 0.01, "%d seeds; budget calibrated per instance from the "
             "full method's natural running time" % m.get("num_seeds", 0),
             ha="center", fontsize=6.5, color="0.3")
    S.save(fig, "fig_protocol")


if __name__ == "__main__":
    main()
