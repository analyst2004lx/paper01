"""Figure: what each extra millisecond per evaluation buys.

The natural chart here would be makespan against configuration, but it does not
work: makespans differ far more across instances and heterogeneity levels than
across configurations, so the between-instance spread swamps a 6\% effect even
after dividing by each instance's lower bound.  The paired statistics avoid that
by differencing within (instance, seed), and this figure plots exactly what they
test -- the paired gain over the two-stage baseline -- against the cost per
evaluation that buys it.

Read left to right: cost rises by a factor of forty, and quality does not follow.
The proposed method is the leftmost point of the loop family, and the most
expensive configuration has fallen below the baseline it was meant to improve.
"""
from __future__ import annotations

import numpy as np

import _style as S

SKIP = {"rule", "twostage"}     # 前者无搜索,后者是被减去的基准


def paired_gain(runs, arm):
    """按 (算例, 种子) 与两阶段配对,返回逐对相对改进(%)。"""
    idx = {}
    for r in runs.itertuples():
        idx.setdefault((r.instance, r.seed), {})[r.arm] = r.makespan
    out = []
    for v in idx.values():
        if "twostage" in v and arm in v and v["twostage"] > 0:
            out.append(100.0 * (v["twostage"] - v[arm]) / v["twostage"])
    return np.asarray(out)


def main():
    m = S.require_seeds()
    runs = S.load("runs.csv")
    runs = runs[runs["makespan"].notna()]

    arms = [a for a in S.ARM_ORDER
            if a not in SKIP and (runs["arm"] == a).any()]

    fig, ax = S.plt.subplots(figsize=(S.COL * 1.5, 2.45))

    xs, ys, es = [], [], []
    for a in arms:
        sub = runs[runs["arm"] == a]
        cost = sub["ms_per_eval"].dropna().mean()
        g = paired_gain(runs, a)
        xs.append(cost)
        ys.append(g.mean())
        es.append(g.std(ddof=1) / np.sqrt(len(g)))

    ax.plot(xs, ys, "-", color="0.72", lw=0.9, zorder=1)
    for a, x, y, e in zip(arms, xs, ys, es):
        ax.errorbar([x], [y], yerr=[e], fmt="o", ms=6.2, elinewidth=1.0,
                    capsize=2.4, zorder=3,
                    color=S.ARM_COLOR.get(a, "0.4"),
                    ecolor=S.ARM_COLOR.get(a, "0.4"))

    # 标注:主方法与定价档各自朝远离折线的一侧,其余交替避让
    place = {
        "opendispatch_nols": (4, 11, "left"),
        "opendispatch": (0, -15, "center"),
        "nofeedback": (6, 10, "left"),
        "nostagger": (0, -15, "center"),
        "closed": (8, 8, "left"),
        "priced": (-4, 11, "right"),
    }
    for a, x, y in zip(arms, xs, ys):
        dx, dy, ha = place.get(a, (0, 10, "center"))
        ax.annotate(S.ARM_SHORT.get(a, a), (x, y),
                    textcoords="offset points", xytext=(dx, dy), ha=ha,
                    fontsize=6.9, color=S.ARM_COLOR.get(a, "0.3"))

    ax.axhline(0, color="0.35", lw=0.9, ls="--")
    ax.annotate("two-stage baseline", (xs[0], 0), textcoords="offset points",
                xytext=(2, -11), fontsize=6.5, color="0.4")
    ax.set_xscale("log")
    ax.set_xlim(min(xs) / 1.55, max(xs) * 1.5)
    lo, hi = min(ys) - max(es) - 1.0, max(ys) + max(es) + 2.2
    ax.set_ylim(lo, hi)          # 顶部留白,免得标注压到标题
    ax.set_xlabel("cost per evaluation (ms, log scale)")
    ax.set_ylabel(r"paired $\Delta C_{\max}$ vs two-stage (\%)")
    ax.xaxis.set_major_locator(S.mticker.FixedLocator([2, 3, 5, 10, 20, 40, 80]))
    ax.xaxis.set_minor_locator(S.mticker.NullLocator())
    ax.xaxis.set_major_formatter(S.mticker.FuncFormatter(
        lambda v, _p: ("%g" % v)))
    ax.set_title("%d instances $\\times$ %d seeds, equal wall-clock budget; "
                 "higher is better" % (len(m.get("instances") or []),
                                       m.get("num_seeds", 0)),
                 fontsize=6.8, color="0.3", pad=4)
    S.save(fig, "fig_ablation")


if __name__ == "__main__":
    main()
