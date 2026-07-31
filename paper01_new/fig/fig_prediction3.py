"""Figure: mechanism gain depends on whether the congestion is avoidable.

The `high` and `funnel` instances are generated so that, at equal seed and
equal heterogeneity, they differ in exactly one respect: the width of the cut
separating the load/unload station from the shop.  Everything a scheduling
decision could react to is held fixed.  If the gain of the closed loop comes
from steering decisions around contention, it must survive on `high` and
collapse on `funnel`, where the contention is one no assignment can avoid.

Each gain is paired by (heterogeneity, seed); the p-value is a two-sided
Wilcoxon signed-rank test on those pairs.  Pairing by anything coarser would
silently mix cells, which is the failure mode the batch runner guards against.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

import _style as S

BASELINES = ["twostage", "nofeedback", "opendispatch", "nostagger"]
LABEL = {
    "twostage": "integration gain\n(vs two-stage)",
    "nofeedback": "decision feedback\n(vs eval-only)",
    "opendispatch": "closed dispatch\n(vs open)",
    "nostagger": "staggering\n(vs reassign only)",
}


def main():
    m = S.require_seeds()
    g = S.load("gains_by_seed.csv")
    g = g[g["rel_gain"].notna()]
    bases = [b for b in BASELINES if (g["baseline"] == b).any()]
    if not {"high", "funnel"} <= set(g["tag"].unique()):
        raise SystemExit("this figure needs both the high and funnel cells")

    fig, ax = S.plt.subplots(figsize=(S.COL * 1.55, 2.3))
    xs = np.arange(len(bases))
    w = 0.34

    for k, tag in enumerate(["high", "funnel"]):
        mus, errs = [], []
        for b in bases:
            v = g[(g["baseline"] == b) & (g["tag"] == tag)]["rel_gain"] * 100
            mus.append(v.mean() if len(v) else np.nan)
            errs.append(v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0.0)
        ax.bar(xs + (k - 0.5) * w, mus, w, yerr=errs,
               color=S.TAG_COLOR[tag], label="%s congestion" % tag,
               error_kw=dict(lw=0.7, capsize=2, ecolor="0.3"))

    # paired test between the two structures, keyed on (heterogeneity, seed)
    for i, b in enumerate(bases):
        sub = g[g["baseline"] == b]
        hi = {(r.het, r.seed): r.rel_gain
              for r in sub[sub["tag"] == "high"].itertuples()}
        fu = {(r.het, r.seed): r.rel_gain
              for r in sub[sub["tag"] == "funnel"].itertuples()}
        keys = sorted(set(hi) & set(fu))
        if len(keys) < 3:
            continue
        a = np.array([hi[k] for k in keys])
        c = np.array([fu[k] for k in keys])
        if np.allclose(a, c):
            continue
        p = stats.wilcoxon(a, c)[1]
        top = max(np.nanmean(a), np.nanmean(c)) * 100
        ax.text(i, top + 1.1, "%s n=%d" % (S.stars(p) or "n.s.", len(keys)),
                ha="center", va="bottom", fontsize=6.2, color="0.25")

    ax.axhline(0, color="0.4", lw=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels([LABEL[b] for b in bases], fontsize=6.6)
    ax.set_ylabel("makespan reduction (%)")
    ax.legend(loc="upper right", handletextpad=0.5)
    ax.set_title("paired by (heterogeneity, seed); %d seeds x %d H levels"
                 % (m.get("num_seeds", 0), g["het"].nunique()),
                 fontsize=6.8, color="0.3", pad=4)
    ax.margins(y=0.22)
    S.save(fig, "fig_prediction3")


if __name__ == "__main__":
    main()
