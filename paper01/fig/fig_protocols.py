"""Both budget conventions, side by side.

The point of this figure is that the choice of budget convention is not a detail
of the experimental setup: on the same runs, the same comparison changes size and
sometimes sign depending on whether one equalises wall-clock time or generations.
Equal generations charges nothing for a local search neighbour or for a more
expensive dispatch probe, so it flatters whichever configuration does more work
per generation; equal wall-clock time charges for it and therefore flatters
whichever configuration evaluates fastest.  Neither is neutral, which is why both
are reported.

The reference is the mechanism-richest unpriced configuration, so each row reads
as "how much better does the elaborate configuration look than this one".
Comparing the two markers in a row isolates the part of that appearance which is
an artefact of not charging for computation.
"""
import _style as S

df = S.load("protocols.csv")
m = S.meta_protocols()

order = ["twostage", "nofeedback", "opendispatch", "nostagger"]
order = [b for b in order if b in set(df["baseline"])]

PROTO = [
    ("wallclock", "equal wall-clock time", "#08519c", "o"),
    ("generations", "equal generations", "#d95f02", "s"),
]

fig, ax = S.plt.subplots(figsize=(S.COL * 1.55, 1.05 + 0.44 * len(order)))

for row, base in enumerate(order):
    y = len(order) - 1 - row
    ax.axhspan(y - 0.5, y + 0.5, color="#f2f2f2" if row % 2 else "none", lw=0)
    for k, (proto, label, color, marker) in enumerate(PROTO):
        sub = df[(df["baseline"] == base) & (df["protocol"] == proto)]
        if sub.empty:
            continue
        r = sub.iloc[0]
        off = 0.17 * (1 if k == 0 else -1)
        gain = float(r["rel_gain"])
        ax.plot([gain], [y + off], marker=marker, color=color, ms=5.2,
                ls="none", label=label if row == 0 else None, zorder=3)
        ax.plot([0, gain], [y + off, y + off], color=color, lw=1.1,
                alpha=0.55, zorder=2)
        txt = "%+.1f%%%s" % (100 * gain, S.stars(r["p_value"]))
        ax.annotate(txt, (gain, y + off), textcoords="offset points",
                    xytext=(7 if gain >= 0 else -7, 0), fontsize=7,
                    ha="left" if gain >= 0 else "right", va="center",
                    color=color)

ax.axvline(0.0, color="0.25", lw=0.9, zorder=1)
ax.set_yticks(range(len(order)))
ax.set_yticklabels([S.BASELINE_LABEL.get(b, b).replace("vs ", "")
                    for b in reversed(order)])
ax.set_ylim(-0.6, len(order) - 0.4)
ax.set_xlabel(r"relative change in $C_{\max}$ "
              r"(positive $=$ full closed loop better)")
ax.xaxis.set_major_locator(S.mticker.MultipleLocator(0.05))
ax.xaxis.set_minor_locator(S.mticker.MultipleLocator(0.025))
ax.xaxis.set_major_formatter(
    S.mticker.FuncFormatter(lambda v, _p: "%+.0f%%" % (100 * v)))
ax.grid(axis="y", visible=False)
ax.legend(loc="lower right", ncol=1)

lo, hi = ax.get_xlim()
ax.set_xlim(lo - 0.02, hi + 0.03)

fig.text(0.0, -0.02,
         "%d instances, %d seeds, paired Wilcoxon; * p<0.05, ** p<0.01, *** p<0.001"
         % (len(m.get("instances", [])), m.get("num_seeds", 0)),
         fontsize=6.6, color="0.35")
fig.subplots_adjust(bottom=0.26)
S.save(fig, "fig_protocols")
