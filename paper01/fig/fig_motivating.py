# -*- coding: utf-8 -*-
"""Figure 1, motivating instance: the constant travel-time matrix and
conflict-free routing rank the same two assignments in opposite order.

Data come from clbs/output/motivating.json, computed by clbs/tools/motivating.py
with the same decoder as the paper -- the four numbers in (b) are not schematic.
The geometry in (a) matches that instance one-to-one.
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "clbs", "output", "motivating.json")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 200,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

C_FAST = "#2e7d32"      # fast arm M1
C_SLOW = "#ef6c00"      # slow arm M2
C_TRUNK = "#c62828"     # exclusive trunk
C_GREY = "#7a7a7a"

# Default (English) figure copy.  fig_motivating_CN.py passes STRINGS_CN.
STRINGS = {
    "title_a": "(a) The only path to the fast arm is an exclusive trunk",
    "trunk_tau": "τ = {tau:.0f} (exclusive)",
    "avoids_trunk": "avoids the trunk",
    "fast_arm": "fast arm  t$^P$={proc:.0f}",
    "slow_arm": "slow arm  t$^P$={proc:.0f}",
    "m3_jobs": "{n:.0f} jobs that can only\nbe processed on M3",
    "m3_yield": "Jobs that can only use M3\ncross the trunk repeatedly\n→ yielding wait",
    "two_assign": (
        "The job starts at LU, is processed, then returns (J1 only; unimpeded, no other vehicles)\n"
        "Fast arm M1: LU--$v_1$--$v_2$--M1, one way $1+{tau:.0f}+1={one1:.0f}$, "
        "round trip ${t1:.0f}$, + processing ${p1:.0f}$ $=${s1:.0f}\n"
        "Slow arm M2: LU--$v_1$--M2, one way $1+2={one2:.0f}$, "
        "round trip ${t2:.0f}$, + processing ${p2:.0f}$ $=${s2:.0f}"
    ),
    "assign_ylim_lo": -1.70,
    "assign_y": -1.08,
    "title_b": "(b) Instance $C_{\\max}$: constant matrix vs. conflict-free routing",
    "group_ideal": "constant travel-time matrix",
    "group_routed": "conflict-free routing",
    "chosen": "chosen",
    "reversal": (
        "The ranking reverses\n"
        "(instance $C_{{\\max}}$; three background jobs)\n"
        "matrix chooses M{a} (fast); routing chooses M{b} (slow)"
    ),
    "ylabel": "instance makespan $C_{\\max}$",
    "delta_y_mult": 1.18,
    "delta_x": 0.72,
    "delta_y_axes": 0.795,
    "note_y_axes": 0.745,
    "note_delta_gap": 0.08,
    "ylim_mult": 1.62,
    "reversal_fs": 8,
    "reversal_pad": 0.22,
    "reversal_ls": 1.15,
    "bars_note_at": "below_delta",
    "bars_note": "A bar is the time the last job returns to LU",
}


def node(ax, x, y, label, fc="#ffffff", ec="#444444", r=0.30, fs=9, bold=False):
    ax.add_patch(Circle((x, y), r, facecolor=fc, edgecolor=ec, lw=1.4, zorder=4))
    ax.text(x, y, label, ha="center", va="center", zorder=5,
            fontsize=fs, fontweight="bold" if bold else "normal")


def edge(ax, p, q, tau, color=C_GREY, lw=1.6, ls="-", off=(0.0, 0.22), fs=8.5):
    ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=lw, ls=ls, zorder=2)
    ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], tau,
            ha="center", va="center", fontsize=fs, color=color, zorder=6,
            bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="none", alpha=0.9))


def panel_layout(ax, p, S=None) -> None:
    S = STRINGS if S is None else S
    ax.set_title(S["title_a"],
                 fontsize=10.5, fontweight="bold", pad=10)
    ax.set_xlim(-0.6, 9.4)
    # Extra bottom room when the assignment caption is wrapped (English).
    # Localized copies may override the two coordinates.
    ylim_lo = S.get("assign_ylim_lo")
    if ylim_lo is None:
        ylim_lo = -1.05 if "\n" in S["two_assign"] else -0.4
    ax.set_ylim(ylim_lo, 5.0)
    ax.axis("off")
    ax.set_aspect("equal")

    P = {"v0": (0.9, 0.7), "v1": (2.4, 2.3), "v2": (7.0, 2.3),
         "m1": (8.5, 3.9), "m2": (0.9, 3.9), "m3": (8.5, 0.7)}

    edge(ax, P["v0"], P["v1"], "1")
    edge(ax, P["v1"], P["v2"], S["trunk_tau"].format(tau=p["trunk_tau"]),
         color=C_TRUNK, lw=3.4, off=(0.0, 0.34), fs=9)
    edge(ax, P["v2"], P["m1"], "1")
    edge(ax, P["v2"], P["m3"], "1")
    edge(ax, P["v1"], P["m2"], "2", color=C_SLOW, lw=2.0)
    ax.text(0.0, 2.85, S["avoids_trunk"], ha="left", va="center",
            fontsize=8, color=C_SLOW)

    node(ax, *P["v0"], "LU", fc="#dceaf8", ec="#08519c", r=0.36, bold=True)
    node(ax, *P["v1"], "$v_1$")
    node(ax, *P["v2"], "$v_2$")
    node(ax, *P["m1"], "M1", fc="#e8f5e9", ec=C_FAST, r=0.36, bold=True)
    node(ax, *P["m2"], "M2", fc="#fff3e0", ec=C_SLOW, r=0.36, bold=True)
    node(ax, *P["m3"], "M3", fc="#f0f0f0", ec=C_GREY, r=0.36)

    ax.text(8.5, 4.48, S["fast_arm"].format(proc=p["proc_fast"]), ha="center",
            fontsize=8.5, color=C_FAST, fontweight="bold")
    ax.text(0.9, 4.48, S["slow_arm"].format(proc=p["proc_slow"]), ha="center",
            fontsize=8.5, color=C_SLOW, fontweight="bold")
    ax.text(8.5, 0.18, S["m3_jobs"].format(n=p["n_background"]),
            ha="center", va="top", fontsize=8, color=C_GREY, linespacing=1.15)
    # English yield note is three lines: sit it in the open bay below the trunk.
    y_yield = 1.05 if "\n" in S["m3_yield"] else 1.68
    ax.text(4.7, y_yield, S["m3_yield"],
            ha="center", va="center", fontsize=8.5, color=C_TRUNK,
            linespacing=1.2,
            bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none", alpha=0.88))

    y_assign = S.get("assign_y")
    if y_assign is None:
        y_assign = -0.62 if "\n" in S["two_assign"] else -0.30
    ax.text(4.4, y_assign,
            S["two_assign"].format(
                tau=p["trunk_tau"],
                t1=p["travel_M1_round"], p1=p["proc_fast"],
                t2=p["travel_M2_round"], p2=p["proc_slow"],
                one1=p["travel_M1_round"] / 2.0,
                one2=p["travel_M2_round"] / 2.0,
                s1=p["travel_M1_round"] + p["proc_fast"],
                s2=p["travel_M2_round"] + p["proc_slow"]),
            ha="center", va="center", fontsize=8.5, color="#222222",
            linespacing=1.25,
            bbox=dict(boxstyle="round,pad=0.3", fc="#f7f7f7", ec="#999999"))


def panel_reversal(ax, d, S=None) -> None:
    S = STRINGS if S is None else S
    ax.set_title(S["title_b"],
                 fontsize=10.5, fontweight="bold", pad=10)
    groups = [(S["group_ideal"], "ideal"),
              (S["group_routed"], "routed")]
    xs = [0.0, 1.45]
    w = 0.42

    top = max(d["M1"]["routed"], d["M2"]["routed"])
    picks = []
    for gx, (glabel, key) in zip(xs, groups):
        v1, v2 = d["M1"][key], d["M2"][key]
        win = 1 if v1 <= v2 else 2
        picks.append(win)
        for off, val, col, who in ((-w / 2 - 0.02, v1, C_FAST, 1),
                                   (+w / 2 + 0.02, v2, C_SLOW, 2)):
            chosen = who == win
            ax.bar(gx + off, val, width=w, color=col, zorder=3,
                   alpha=1.0 if chosen else 0.30,
                   edgecolor="#222222" if chosen else "none",
                   linewidth=1.6 if chosen else 0)
            ax.text(gx + off, val + top * 0.02, f"{val:.0f}", ha="center",
                    va="bottom", fontsize=10.5, zorder=4,
                    fontweight="bold" if chosen else "normal",
                    color="#111111" if chosen else "#999999")
            ax.text(gx + off, top * 0.035, f"M{who}", ha="center", va="bottom",
                    fontsize=9.5, zorder=5, fontweight="bold",
                    color="#ffffff" if chosen else "#777777")
            if chosen:
                ax.plot([gx + off], [-top * 0.055], marker="^", ms=7, color=col,
                        clip_on=False, zorder=5)
                ax.text(gx + off, -top * 0.105, S["chosen"], ha="center", va="top",
                        fontsize=9, color=col, fontweight="bold")
        ax.text(gx, -top * 0.24, glabel, ha="center", va="top", fontsize=9.5)

    n_rev = S["reversal"].count("\n") + 1
    # Keep the reversal box inside panel (b); long English must wrap, not spill left.
    ax.text(0.50, 0.98, S["reversal"].format(
            a=picks[0], b=picks[1],
            c1=d["M1"]["ideal"], c2=d["M2"]["ideal"],
            c3=d["M1"]["routed"], c4=d["M2"]["routed"]),
            transform=ax.transAxes, ha="center", va="top",
            fontsize=S.get("reversal_fs", 9 if n_rev > 1 else 10),
            fontweight="bold", color="#111111",
            linespacing=S.get("reversal_ls", 1.25), clip_on=True,
            bbox=dict(boxstyle="round,pad=%s" % S.get("reversal_pad", 0.34),
                      fc="#fff8f0", ec="#d95f02", lw=1.2))
    delta_mult = S.get("delta_y_mult")
    if delta_mult is None:
        delta_mult = 1.12 if n_rev > 1 else 1.15
    delta_x = S.get("delta_x", (xs[0] + xs[1]) / 2)
    delta_y_axes = S.get("delta_y_axes")
    if delta_y_axes is not None:
        ax.text(0.50, delta_y_axes,
                f"$C$(M1)$-$$C$(M2)：{d['M1']['ideal'] - d['M2']['ideal']:+.0f}"
                f"   →   {d['M1']['routed'] - d['M2']['routed']:+.0f}",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=9, color="#444444")
    else:
        ax.text(delta_x, top * delta_mult,
                f"$C$(M1)$-$$C$(M2)：{d['M1']['ideal'] - d['M2']['ideal']:+.0f}"
                f"   →   {d['M1']['routed'] - d['M2']['routed']:+.0f}",
                ha="center", va="center", fontsize=9, color="#444444")

    ax.set_ylabel(S["ylabel"], fontsize=9.5)
    ylim_mult = S.get("ylim_mult")
    if ylim_mult is None:
        ylim_mult = 1.58 if n_rev > 1 else 1.44
    ax.set_ylim(0, top * ylim_mult)
    ax.set_xlim(-0.70, 2.15)
    note = S.get("bars_note")
    if note:
        formatted = note.format(
                c1=d["M1"]["ideal"], c2=d["M2"]["ideal"],
                c3=d["M1"]["routed"], c4=d["M2"]["routed"])
        note_at = S.get("bars_note_at", "below_axes")
        if note_at == "below_delta":
            note_y_axes = S.get("note_y_axes")
            if note_y_axes is not None:
                ax.text(0.50, note_y_axes, formatted,
                        transform=ax.transAxes, ha="center", va="top",
                        fontsize=8, color="#333333", linespacing=1.2)
            else:
                gap = S.get("note_delta_gap", 0.09)
                ax.text(delta_x, top * (delta_mult - gap),
                        formatted, ha="center", va="top",
                        fontsize=8, color="#333333", linespacing=1.2)
        elif note_at == "above_delta":
            ax.text(delta_x, top * (delta_mult + 0.06),
                    formatted, ha="center", va="bottom",
                    fontsize=8, color="#333333", linespacing=1.2)
        else:
            ax.text(0.50, -0.42, formatted,
                    transform=ax.transAxes, ha="center", va="top",
                    fontsize=7.6, color="#333333", linespacing=1.25)
    ax.set_xticks([])
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", ls=":", color="#cccccc", zorder=0)
    ax.set_axisbelow(True)


def main() -> None:
    if not os.path.exists(DATA):
        raise SystemExit(f"missing {DATA}; from clbs/ run: py -m tools.motivating --sweep")
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.90),
                             gridspec_kw={"width_ratios": [1.32, 1.0]})
    panel_layout(axes[0], d["params"])
    panel_reversal(axes[1], d)

    fig.tight_layout(w_pad=2.0)
    stem = os.path.join(HERE, "fig_motivating")
    fig.savefig(stem + ".pdf", bbox_inches="tight", pad_inches=0.08)
    if os.environ.get("CLBS_FIG_PNG", "1") != "0":
        fig.savefig(stem + ".png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote", stem + ".pdf/.png")


if __name__ == "__main__":
    main()

