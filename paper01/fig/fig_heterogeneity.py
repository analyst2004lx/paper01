"""Figure: how the gain varies with processing-time heterogeneity.

Heterogeneity is the knob that creates the trade-off the reassignment operator
exploits: at H=0 every eligible arm takes the same time, so moving an operation
to a less congested arm costs nothing and buys nothing in duration, and the
mechanism has no trade-off left to resolve.  The prediction is that the gain
grows with H on `high` and stays flat near zero on `funnel`.
"""
from __future__ import annotations

import numpy as np

import _style as S

BASELINES = ["twostage", "nofeedback", "nostagger"]
LABEL = {"twostage": "vs two-stage", "nofeedback": "vs eval-only",
         "opendispatch": "vs open dispatch", "nostagger": "vs reassign only"}
STYLE = {"twostage": ("o", "-"), "nofeedback": ("s", "--"),
         "opendispatch": ("^", "-."), "nostagger": ("d", ":")}


def main():
    m = S.require_seeds()
    g = S.load("gains_by_seed.csv")
    g = g[g["rel_gain"].notna()]
    tags = [t for t in ["high", "funnel"] if (g["tag"] == t).any()]
    bases = [b for b in BASELINES if (g["baseline"] == b).any()]

    fig, axes = S.plt.subplots(1, len(tags), figsize=(S.FULL * 0.72, 2.25),
                               sharey=True)
    axes = np.atleast_1d(axes)

    for ax, tag in zip(axes, tags):
        sub = g[g["tag"] == tag]
        hs = sorted(sub["het"].dropna().unique())
        for b in bases:
            mus, errs = [], []
            for h in hs:
                v = sub[(sub["baseline"] == b) & (sub["het"] == h)]["rel_gain"] * 100
                mus.append(v.mean() if len(v) else np.nan)
                errs.append(v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0.0)
            mk, ls = STYLE.get(b, ("o", "-"))
            ax.errorbar(hs, mus, yerr=errs, marker=mk, ls=ls, ms=3.6,
                        elinewidth=0.7, capsize=1.8, label=LABEL.get(b, b))
        ax.axhline(0, color="0.4", lw=0.8)
        ax.set_xlabel("heterogeneity $H$")
        ax.set_title("%s congestion" % tag)
        ax.set_xticks(hs)

    axes[0].set_ylabel("makespan reduction (%)")
    axes[-1].legend(loc="best", handletextpad=0.5)
    fig.subplots_adjust(bottom=0.30)
    fig.text(0.5, 0.015, "%d seeds per point; error bars are standard errors"
             % m.get("num_seeds", 0), ha="center", fontsize=6.5, color="0.3")
    S.save(fig, "fig_heterogeneity")


if __name__ == "__main__":
    main()
