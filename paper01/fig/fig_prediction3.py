# -*- coding: utf-8 -*-
"""The two main effects across the three factor families (Section 5.5).

Reads clbs/output/baseline_ladder.csv, the same file the tables and the preamble
macros come from, so the figure cannot drift from the prose.

What the figure has to make decidable: not "is the gain positive on average",
which the main table already answers, but "which of these per-cell readings am I
allowed to believe".  Those are different questions, and an earlier version of
this figure conflated them -- it annotated every cell whose gain came out
positive as "harmful", which is exactly the move of treating an unresolved sign
as a finding.  With ten seeds per cell the probing effect is not significant on
eight of the ten cells, so the marker fill now carries significance and the
reader can see at a glance that one curve is evidence and the other is mostly
noise.

Marker fill alone made that point as a binary, which left the reader taking the
threshold on trust.  Each cell therefore also carries the standard error of its
mean over the ten seeds: the probing bars visibly straddle zero everywhere and
the closed-loop bars do not, which is the same conclusion shown rather than
asserted.  SEM and not a quartile because the plotted point is a mean, and the
bar must be the dispersion of the quantity actually drawn.

The shared base point.  tools/abc_matrix.py runs the base cell once, under the
name "A funnel", and it serves simultaneously as the B-family level 1.5 and the
C-family level 0.6.  Selecting family members by the leading letter of the case
name therefore dropped it from panels B and C, which left the fleet sweep
looking monotone (0.5 negative, 1.0 positive, 2.0 positive) when the full
four-point sweep alternates in sign.  The base point is now injected explicitly
into both panels at levels read off abc_matrix.BASE.

The layout family has no natural numeric level, so it is plotted against
contention strength, which is what the layout manipulation actually changes.

Run: py paper01/fig/fig_prediction3.py
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "clbs")))

from _style import (FS_ANNOT, FS_FOOT, FS_LEG, LADDER, by,  # noqa: E402
                    load_output, mark_draft, mean, plt, save, sem)

try:                                                            # noqa: E402
    from algorithm.stats import holm, wilcoxon_signed_rank
    from tools.abc_matrix import BASE
except Exception as exc:                                        # pragma: no cover
    raise SystemExit("need clbs/ on sys.path for significance and base levels: %s" % exc)

HINT = "py -u -m tools.baseline_ladder --budget 90 --seeds 42,7,2024,13,1,99,123,777,31415,8"

# Effects shown.  Both are single-factor contrasts: each holds one factor of the
# 2x2 fixed and moves the other, so each can be attributed to one mechanism.
EFFECTS = [
    ("B0", "B1", "closed loop\n(rule dispatch fixed)", "#08519c", "o", "-"),
    ("B1", "B2", "reservation-aware dispatch\n(closed loop fixed)", "#d95f02", "s", "--"),
]
PANELS = [
    ("A", "layout", "contention strength (%)"),
    ("B", "fleet-to-arm ratio", "$N_A/N_M$"),
    ("C", "flexibility", "$F$"),
]

# The base cell is shared by the three families and run once, so it carries no
# factor level in its name.  Its levels are derived from the generator's own
# base spec rather than typed, so that changing the base in abc_matrix.py moves
# this point too instead of silently misplacing it.
BASE_CELL = "A funnel"
BASE_LEVEL = {"B": BASE["na"] / BASE["nm"], "C": BASE["flex"]}
ALPHA = 0.05


def level(case: str, family: str, cont: float) -> float:
    """The x position of a cell: its factor level, or contention for family A."""
    if family == "A":
        return 100.0 * cont
    if case == BASE_CELL:
        return BASE_LEVEL[family]
    m = re.search(r"([0-9]*\.?[0-9]+)\s*$", case)
    if not m:
        raise SystemExit("case name %r has no trailing factor level; cannot place the x-axis" % case)
    return float(m.group(1))


def members(cells, fam: str):
    """Cells belonging to a family, including the base cell for B and C."""
    names = [c for (c,) in cells if str(c).split()[0] == fam]
    if fam != "A" and (BASE_CELL,) in cells and BASE_CELL not in names:
        names.append(BASE_CELL)
    return names


def cell_effect(rows_of_cell, ka: str, kb: str):
    """Paired relative gain over seeds, its spread, and a two-sided Wilcoxon p.

    Same estimator as tab/gen_tables_ladder.py, so the figure, the per-cell
    table and the preamble macros are three views of one computation.

    The spread is the standard error of that mean over the ten seeds.  It is
    reported because the panel's whole claim is about which per-cell readings
    may be believed, and until now that was carried only by the marker fill --
    a binary derived from the p value.  The bar shows the quantity the binary
    is thresholding, so a reader can see *how far* a hollow cell is from
    resolving rather than being told only that it did not.
    """
    val = {}
    for r in rows_of_cell:
        val.setdefault(r["arm"], {})[r["seed"]] = r["makespan"]
    seeds = sorted(set(val.get(ka, {})) & set(val.get(kb, {})))
    xa = [val[ka][s] for s in seeds]
    xb = [val[kb][s] for s in seeds]
    if not seeds:
        return float("nan"), 0.0, 1.0
    rel = [(y - x) / x for x, y in zip(xa, xb)]
    return (100.0 * mean(rel), 100.0 * sem(rel),
            wilcoxon_signed_rank(xb, xa)["p_value"])


def adjusted(cells, ka: str, kb: str):
    """Holm-adjusted per-cell p for one effect, keyed by cell name.

    The family is all ten cells of that effect, not the three or five cells of
    whichever panel is being drawn: the reader's question is "which of these
    readings may I believe", and they are looking at all ten of them.  Adjusting
    per panel would make a cell's fill depend on which panel it appears in,
    which for the shared base point would mean two different fills for one
    number.
    """
    names = [c for (c,) in cells]
    ps = [cell_effect(cells[(c,)], ka, kb)[2] for c in names]
    return dict(zip(names, holm(ps)))


def main() -> None:
    rows = load_output("baseline_ladder.csv", HINT)
    seeds = sorted({r["seed"] for r in rows})
    cells = by(rows, "case")
    # The protocol of Section 5.1 commits to ten seeds; anything less is a
    # draft, and says so on its face rather than in a commit message.
    if len(seeds) < 10:
        mark_draft("%d seeds, protocol wants 10" % len(seeds))
    if len(cells) < 10:
        mark_draft("%d of 10 instance cells" % len(cells))

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.45), sharey=True)
    for ax, (fam, fam_name, xlabel) in zip(axes, PANELS):
        names = members(cells, fam)
        if not names:
            ax.text(0.5, 0.5, "family %s absent" % fam, transform=ax.transAxes,
                    ha="center", va="center", fontsize=FS_ANNOT,
                    color="#999999")
            ax.set_xlabel(xlabel)
            continue
        cont = {c: cells[(c,)][0]["contention"] for c in names}
        names.sort(key=lambda c: level(c, fam, cont[c]))
        xs = [level(c, fam, cont[c]) for c in names]

        for ka, kb, label, colour, marker, ls in EFFECTS:
            adj = adjusted(cells, ka, kb)
            eff = [cell_effect(cells[(c,)], ka, kb) for c in names]
            ys = [e[0] for e in eff]
            es = [e[1] for e in eff]
            ax.plot(xs, ys, ls, color=colour, linewidth=1.2,
                    label=label if fam == "A" else None, zorder=3,
                    clip_on=False)
            # Drawn under the markers so the fill (significance) stays legible.
            # The two effects sit far apart on this axis, so no dodge is needed
            # and adding one would misplace the points against the x levels.
            ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor=colour,
                        elinewidth=0.8, capsize=1.8, capthick=0.8,
                        alpha=0.7, zorder=3, clip_on=False)
            # Fill carries significance *after* correcting over the ten cells of
            # this effect.  A hollow marker is the figure saying "this cell does
            # not license a claim about its sign", which is the whole point of
            # the panel for the probing curve -- and after correction that curve
            # is hollow throughout, which is the honest picture: ten seeds per
            # cell resolve the main effect and do not resolve this one.
            for x, y, c in zip(xs, ys, names):
                ax.plot([x], [y], marker, color=colour, markersize=4.6,
                        markerfacecolor=colour if adj[c] < ALPHA else "white",
                        markeredgecolor=colour, markeredgewidth=1.0,
                        zorder=4, clip_on=False)

        # The shared base point is a member of this sweep but is tabulated
        # under family A, so it is marked to stop a reader hunting for it.
        if fam != "A" and BASE_CELL in names:
            ax.axvline(BASE_LEVEL[fam], color="#999999", linewidth=0.7,
                       linestyle=":", zorder=1)

        ax.axhline(0, color="#444444", linewidth=0.7, zorder=2)
        ax.set_xlabel(xlabel)
        ax.set_title("%s: %s" % (fam, fam_name), fontsize=8.5)
        if fam != "A":
            ax.set_xticks(xs)

    axes[0].set_ylabel("$\\Delta C_{\\max}$ (%)\nnegative is better")
    axes[0].legend(loc="lower left", fontsize=FS_LEG, handlelength=1.8)
    # tight_layout first, then reserve a strip for the protocol line: stating the
    # correction is what makes the marker fills readable, so it must not be laid
    # on top of the axis labels.
    fig.tight_layout(rect=(0.0, 0.095, 1.0, 1.0))
    fig.text(0.995, 0.012,
             "%d seeds per cell, equal wall clock; error bar = standard error "
             "of the mean over seeds;\nfilled marker = that cell significant at "
             "$p<%.2f$, Holm-corrected over the %d cells"
             % (len(seeds), ALPHA, len(cells)),
             ha="right", va="bottom", fontsize=FS_FOOT, color="#777777")
    save(fig, "fig_prediction3")


if __name__ == "__main__":
    main()
