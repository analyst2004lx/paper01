"""Figure: the reproducible negative result on pricing the interface.

The two panels separate the two things a price can do.  On the left, every
configuration gets the same wall-clock budget, so a more expensive evaluation
buys fewer of them; the penalty appears the moment pricing is switched on and
is then flat over a tenfold range of theta, moving in lockstep with the cost
per evaluation.  On the right, every configuration gets the same number of
evaluations, so the cost is not charged at all -- and the penalty disappears.
Taken together the degradation is an accounting consequence of a five-fold
more expensive route search, not evidence that the price misdirects the
router.
"""
from __future__ import annotations

import numpy as np

import _style as S


def series(sub, thetas):
    """Mean and standard error of the makespan, relative to theta = 0."""
    ref = sub[sub["theta"] == 0.0]["makespan"].mean()
    mus, errs = [], []
    for t in thetas:
        v = sub[sub["theta"] == t]["makespan"]
        mus.append(100.0 * (v.mean() - ref) / ref)
        errs.append(100.0 * v.std(ddof=1) / np.sqrt(len(v)) / ref
                    if len(v) > 1 else 0.0)
    return mus, errs


def main():
    wall = S.load("theta_sweep.csv")
    gen = S.load("theta_sweep_gen.csv")

    fig, axes = S.plt.subplots(1, 2, figsize=(S.FULL * 0.86, 2.25),
                               sharey=True)
    panels = [
        (axes[0], wall, "equal wall-clock budget", True),
        (axes[1], gen, "equal number of evaluations", False),
    ]

    for ax, df, title, show_cost in panels:
        insts = list(dict.fromkeys(df["instance"]))
        ax2 = ax.twinx() if show_cost else None
        if ax2 is not None:
            ax2.grid(False)
        for inst in insts:
            sub = df[df["instance"] == inst]
            thetas = sorted(sub["theta"].unique())
            tag = sub["tag"].iloc[0]
            mus, errs = series(sub, thetas)
            ax.errorbar(thetas, mus, yerr=errs,
                        marker="o" if tag == "high" else "s", ms=4,
                        elinewidth=0.8, capsize=2,
                        color=S.TAG_COLOR.get(tag, "0.3"),
                        label="%s congestion" % tag)
            if ax2 is not None:
                cost = [sub[sub["theta"] == t]["ms_per_eval"].mean()
                        for t in thetas]
                ax2.plot(thetas, cost, ls=":", lw=0.9,
                         color=S.TAG_COLOR.get(tag, "0.3"), alpha=0.55)
        ax.axhline(0, color="0.4", lw=0.8)
        ax.set_xlabel(r"pricing strength $\theta$")
        ax.set_title(title, fontsize=7.6, pad=4)
        if ax2 is not None:
            ax2.set_ylabel("ms per evaluation (dotted)", fontsize=7,
                           color="0.45")
            ax2.tick_params(axis="y", colors="0.45", labelsize=6.5)

    axes[0].set_ylabel(r"$C_{\max}$ change vs $\theta=0$ (%)")
    axes[0].legend(loc="lower right", handletextpad=0.5)

    n_wall = wall.groupby("theta").size().min()
    n_gen = gen.groupby("theta").size().min()
    fig.text(0.0, -0.03,
             "positive is worse.  %d runs per point on the left, %d on the "
             "right; two instances, mean $\\pm$ s.e." % (n_wall, n_gen),
             fontsize=S.FS_FOOT, color="0.35")
    fig.subplots_adjust(bottom=0.28, wspace=0.32)
    S.save(fig, "fig_theta")


if __name__ == "__main__":
    main()
