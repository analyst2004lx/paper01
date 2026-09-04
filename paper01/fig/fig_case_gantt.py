# -*- coding: utf-8 -*-
"""Gantt chart of one instance under B0 and B2 (Section 5.8).

The aggregate numbers say the mechanism pays; they do not say what it does.
This figure answers that on one instance by putting arms and vehicles on one
time axis, so that a gap on an arm can be traced to the vehicle that had not
arrived yet.

The one design decision that matters: waiting is split by cause.  A gap between
two segments of the *same* transport task is a vehicle held at a stop because
the corridor ahead was occupied -- that is yielding, the delay the whole paper
is about, and it is the thing reservation-aware dispatch reroutes around.  A gap
between segments of *different* tasks is a vehicle standing idle with nothing
assigned, which is a fleet-sizing symptom rather than a contention one.  Shading
them the same colour would let the reader attribute one to the other.

Data: clbs/output/case_study/*.json, written by tools/ladder_diag.py.
Run: py paper01/fig/fig_case_gantt.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _style import (FULL, FS_ANNOT, FS_FOOT, FS_LEG,  # noqa: E402
                    FS_TICK_SM, OUTPUT, plt, save)

HINT = ('py -u -m tools.ladder_diag --case-study "A funnel"')
C_OP = "#4292c6"          # processing
C_LOADED = "#08519c"      # travel, loaded
C_EMPTY = "#9ecae1"       # travel, empty
C_YIELD = "#d62728"       # waiting because a corridor was occupied
C_IDLE = "#e8e8e8"        # waiting with nothing assigned
# Job labels on short processing bars: white vanishes against the page.
C_LABEL = "#555555"


def load_case():
    d = os.path.join(OUTPUT, "case_study")
    files = sorted(glob.glob(os.path.join(d, "*.json")))
    if not files:
        raise SystemExit("missing %s/*.json\n  from clbs/ run: %s" % (d, HINT))
    tt = {}
    for p in files:
        with open(p, encoding="utf-8") as f:
            j = json.load(f)
        tt[j["arm"]] = j
    for arm in ("B0", "B2"):
        if arm not in tt:
            raise SystemExit("case timetable is missing arm %s" % arm)
    return tt


def agv_gaps(segments):
    """Waiting intervals per vehicle, split into yielding and idle."""
    out = []
    per = {}
    for s in segments:
        per.setdefault(s["agv"], []).append(s)
    for agv, segs in per.items():
        segs.sort(key=lambda s: s["enter"])
        for a, b in zip(segs, segs[1:]):
            gap = b["enter"] - a["exit"]
            if gap <= 1e-9:
                continue
            # Same task on both sides means the vehicle was held mid-journey.
            kind = "yield" if a["task"] == b["task"] else "idle"
            out.append((agv, a["exit"], gap, kind))
    return out


def draw(ax, tt, title, xmax, arm_label="arm %s", agv_label="AGV %s",
         yield_suffix="   (yielding total %.0f time units)"):
    ops = tt["operations"]
    segs = tt["agv_segments"]
    machines = sorted({o["machine"] for o in ops})
    agvs = sorted({s["agv"] for s in segs})

    # Vehicles below arms, with a visible break: the figure's claim is that a
    # gap above is explained by something below, so the two bands must read as
    # two bands rather than one long list of rows.
    ypos, labels = {}, []
    y = 0
    for m in machines:
        ypos[("M", m)] = y
        labels.append(arm_label % m)
        y += 1
    y += 0.6
    for a in agvs:
        ypos[("A", a)] = y
        labels.append(agv_label % a)
        y += 1

    for o in ops:
        ax.broken_barh([(o["start"], o["finish"] - o["start"])],
                       (ypos[("M", o["machine"])] - 0.33, 0.66),
                       facecolors=C_OP, edgecolor="white", linewidth=0.4,
                       zorder=3)
        if o["finish"] - o["start"] >= 0.04 * xmax:
            ax.text(0.5 * (o["start"] + o["finish"]),
                    ypos[("M", o["machine"])], "J%s-%s" % (o["job"], o["i"]),
                    ha="center", va="center", fontsize=5.2, color=C_LABEL,
                    zorder=4)

    for s in segs:
        loaded = s["task"].endswith("loaded")
        ax.broken_barh([(s["enter"], max(s["exit"] - s["enter"], 1e-9))],
                       (ypos[("A", s["agv"])] - 0.3, 0.6),
                       facecolors=C_LOADED if loaded else C_EMPTY,
                       edgecolor="none", zorder=3)

    n_yield = 0
    for agv, t, gap, kind in agv_gaps(segs):
        ax.broken_barh([(t, gap)], (ypos[("A", agv)] - 0.3, 0.6),
                       facecolors=C_YIELD if kind == "yield" else C_IDLE,
                       edgecolor="none", hatch="///" if kind == "yield" else None,
                       linewidth=0.0, zorder=2)
        if kind == "yield":
            n_yield += gap

    ax.axvline(tt["makespan"], color="#111111", linewidth=1.0, zorder=6)
    # x in data, y in axes fraction: sit just above the spine, not on it.
    ax.text(tt["makespan"], 0.11, " $C_{\\max}=%.0f$" % tt["makespan"],
            fontsize=7, va="bottom", fontweight="bold",
            transform=ax.get_xaxis_transform(), clip_on=False, zorder=7)
    if tt.get("surrogate"):
        ax.axvline(tt["surrogate"], color="#d62728", linewidth=0.9,
                   linestyle=(0, (3, 1.6)), zorder=6)
        ax.text(tt["surrogate"], -0.9, "surrogate %.0f " % tt["surrogate"],
                fontsize=FS_ANNOT, color="#d62728", ha="right", va="center")

    ax.set_yticks([ypos[k] for k in ypos])
    ax.set_yticklabels(labels, fontsize=FS_TICK_SM)
    ax.set_ylim(y - 0.2, -0.8)
    ax.set_xlim(0, xmax)
    ax.set_title(title + (yield_suffix % n_yield),
                 fontsize=8.5, loc="left")
    ax.grid(axis="x", alpha=0.25)
    ax.grid(axis="y", visible=False)
    return n_yield


def main() -> None:
    tt = load_case()
    xmax = 1.06 * max(tt[a]["makespan"] for a in ("B0", "B2"))
    fig, axes = plt.subplots(2, 1, figsize=(FULL, 5.0), sharex=True)
    draw(axes[0], tt["B0"], "B0  open loop, rule dispatch", xmax)
    draw(axes[1], tt["B2"], "B2  closed loop, reservation-aware dispatch (proposed)",
         xmax)
    axes[1].set_xlabel("time")

    handles = [
        plt.Rectangle((0, 0), 1, 1, fc=C_OP, label="processing"),
        plt.Rectangle((0, 0), 1, 1, fc=C_LOADED, label="travel, loaded"),
        plt.Rectangle((0, 0), 1, 1, fc=C_EMPTY, label="travel, empty"),
        plt.Rectangle((0, 0), 1, 1, fc=C_YIELD, hatch="///",
                      label="waiting: corridor occupied"),
        plt.Rectangle((0, 0), 1, 1, fc=C_IDLE, label="waiting: unassigned"),
    ]
    axes[0].legend(handles=handles, loc="upper center", ncol=5,
                   fontsize=FS_LEG,
                   bbox_to_anchor=(0.5, 1.30), frameon=False)
    fig.text(0.005, 0.005, "instance %s,  seed %s,  contention %.1f%%"
             % (tt["B2"]["case"], tt["B2"]["seed"],
                100.0 * tt["B2"]["contention"]),
             fontsize=FS_FOOT, color="#777777")
    fig.tight_layout(rect=(0, 0.015, 1, 0.955))
    save(fig, "fig_case_gantt")


if __name__ == "__main__":
    main()
