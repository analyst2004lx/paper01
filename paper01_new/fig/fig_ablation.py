"""Figure: the progressive ablation chain under an equal wall-clock budget.

Makespans are divided by each instance's composite lower bound so that cells
with different bounds can be pooled; the ratio is an upper bound on the
optimality gap, not the gap itself.

Two deliberate choices.  The dispatch rule is excluded from the panel: it
performs a single decoding, so an equal-time budget means nothing for it, and
its value is reported in the caption instead.  The chart is a dot plot rather
than a bar chart because the interesting range is narrow and far from zero,
where bars would either mislead or waste the axis.
"""
from __future__ import annotations

import numpy as np

import _style as S

SKIP = {"rule"}                      # no search: an equal-time budget is vacuous
MARKERS = {"low": "^", "mid": "v", "high": "o", "funnel": "s"}


def main():
    m = S.require_seeds()
    cells = S.load("cells.csv")
    cells = cells[cells["lower_bound"].notna()].copy()
    cells["ratio"] = cells["mean"] / cells["lower_bound"]

    arms = [a for a in S.ARM_ORDER
            if a not in SKIP and (cells["arm"] == a).any()]
    tags = [t for t in ["low", "mid", "high", "funnel"]
            if (cells["tag"] == t).any()]

    fig, ax = S.plt.subplots(figsize=(S.COL * 1.5, 2.35))
    ys = np.arange(len(arms))[::-1]          # chain reads top to bottom
    offs = np.linspace(-0.16, 0.16, len(tags)) if len(tags) > 1 else [0.0]

    for tag, off in zip(tags, offs):
        sub = cells[cells["tag"] == tag]
        mus, sds = [], []
        for a in arms:
            r = sub[sub["arm"] == a]["ratio"]
            mus.append(r.mean())
            sds.append(r.std(ddof=1) if len(r) > 1 else 0.0)
        ax.errorbar(mus, ys + off, xerr=sds, fmt=MARKERS.get(tag, "o"),
                    ms=4.2, lw=0, elinewidth=0.8, capsize=1.8,
                    color=S.TAG_COLOR.get(tag, "0.4"),
                    ecolor=S.TAG_COLOR.get(tag, "0.4"),
                    label="%s congestion" % S.TAG_LABEL.get(tag, tag))

    ax.set_yticks(ys)
    ax.set_yticklabels([S.ARM_SHORT[a] for a in arms])
    ax.set_xlabel(r"$C_{\max}$ / composite lower bound")
    ax.set_ylim(-0.6, len(arms) - 0.4)
    ax.grid(axis="y", alpha=0.12)

    # mark the full method so the eye finds the reference row immediately
    if "closed" in arms:
        ax.axhline(ys[arms.index("closed")], color="0.75", lw=6, alpha=0.22,
                   zorder=0)
    ax.legend(loc="lower right", handletextpad=0.4, borderaxespad=0.3)

    rule = cells[cells["arm"] == "rule"]["ratio"]
    note = ("%d seeds, equal wall-clock budget per instance" % m.get("num_seeds", 0))
    if len(rule):
        note += ";  dispatch rule (no search) at %.2f" % rule.mean()
    ax.set_title(note, fontsize=6.8, color="0.3", pad=4)
    S.save(fig, "fig_ablation")


if __name__ == "__main__":
    main()
