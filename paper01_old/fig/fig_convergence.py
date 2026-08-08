"""Figure: what the two-stage baseline is actually optimizing.

The dashed curve is the two-stage method's own objective, computed against a
constant travel matrix.  It descends smoothly and reaches a value well below
anything the closed loop attains -- and it is not achievable: the marker at the
end of the budget is the same solution's makespan once its routes are made
conflict-free.  The vertical distance between the two is the cost of planning
against a travel time that the vehicles do not honour.

Solid curves are true makespans throughout, since those arms route every
candidate conflict-free before scoring it.  The horizontal axis is wall-clock
time rather than generations, because the arms differ by an order of magnitude
in the cost of a single evaluation.
"""
from __future__ import annotations

import numpy as np

import _style as S

ARMS = ["twostage", "nofeedback", "closed"]
LABEL = {"twostage": "two-stage (surrogate objective)",
         "nofeedback": "evaluation loop only",
         "closed": "full closed loop"}


def step_median(sub, grid):
    """Median best-so-far across seeds on a common time grid.

    A plain mean over seeds would be dominated by whichever seed happened to
    run one more generation near the end of the budget.
    """
    curves = []
    for _, s in sub.groupby("seed"):
        s = s.sort_values("sec")
        curves.append(np.interp(grid, s["sec"].values, s["best_makespan"].values,
                                left=np.nan,
                                right=s["best_makespan"].values[-1]))
    stack = np.vstack(curves)
    # 预算起点到某档第一代完成之间没有任何数据,该列整列为 NaN。直接 nanmedian
    # 会对空切片告警,而那些时刻本就不该画线:留成 NaN 让 matplotlib 断开即可。
    out = np.full(stack.shape[1], np.nan)
    have = ~np.all(np.isnan(stack), axis=0)
    out[have] = np.nanmedian(stack[:, have], axis=0)
    return out


def main():
    df = S.load("convergence.csv")
    budget = float(df["budget_sec"].iloc[0])
    grid = np.linspace(0.0, budget, 160)

    fig, ax = S.plt.subplots(figsize=(S.COL * 1.45, 2.25))
    for arm in ARMS:
        sub = df[df["arm"] == arm]
        if not len(sub):
            continue
        surrogate = bool(sub["surrogate"].iloc[0])
        y = step_median(sub, grid)
        ax.plot(grid, y, ls="--" if surrogate else "-",
                color=S.ARM_COLOR[arm], label=LABEL.get(arm, arm),
                alpha=0.95 if not surrogate else 0.8)
        if surrogate:
            true = sub.groupby("seed")["final_true_makespan"].first().median()
            ax.plot([budget], [true], marker="*", ms=9, ls="none",
                    color=S.ARM_COLOR[arm], zorder=5)
            ax.annotate("after conflict-free\nrouting is applied",
                        xy=(budget, true), xytext=(-6, 6),
                        textcoords="offset points", ha="right",
                        fontsize=6.3, color=S.ARM_COLOR[arm])
            ax.plot([budget, budget], [y[-1], true], color=S.ARM_COLOR[arm],
                    lw=0.8, ls=":", alpha=0.8)

    ax.set_xlabel("wall-clock time (s)")
    ax.set_ylabel(r"best $C_{\max}$ so far")
    ax.set_xlim(0, budget * 1.02)
    ax.legend(loc="upper right", handletextpad=0.6)
    n = df["seed"].nunique()
    ax.set_title("median over %d seeds, one instance (high congestion)" % n,
                 fontsize=6.8, color="0.3", pad=4)
    S.save(fig, "fig_convergence_closedloop")


if __name__ == "__main__":
    main()
