"""Motivation figure: same schedule and corridor blockage; AOR inspects only the machine
layer and gets an empty scope, STRC inspects the corridor layer and gets the impact set."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from _motivate_draw import HEIGHT_RATIOS, draw_aor, draw_notes, draw_strc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_motivate")

plt.rcParams.update({"figure.dpi": 200, "pdf.fonttype": 42, "ps.fonttype": 42})

LABELS = {
    "title_aor": "(a) AOR: scoping on the operation-precedence graph",
    "title_strc": "(b) STRC: scoping on the reservation impact set",
    "machine_layer": "machine layer",
    "corridor_layer": "corridor layer",
    "machine": "machine",
    "corridor": "corridor",
    "block": "blocked",
    "check": "\u2713",
    "conflict": "vehicle $k_1$'s occupancy of corridor $e^\\star$ overlaps the blockage\n"
                "and already conflicts (AOR does not inspect this layer)",
    "aor_seed": "every operation executable \u2192 seed operation set is empty",
    "aor_verdict": "empty scope, no rescheduling deemed needed; yet the original schedule is infeasible",
    "seed": "seed",
    "impact_set": "reservation\nimpact set",
    "keep": "keeps plan",
    "done": "finished, not rewritable",
    "tag_yield": "yield",
    "tag_vehicle": "same vehicle",
    "tag_machine": "same machine",
    "lg_yield": "yield edge: on one corridor, leading vehicle's occupancy \u2192\n"
                "next vehicle's occupancy (a delayed leader holds the follower)",
    "lg_vehicle": "same-vehicle edge: a vehicle's occupancy \u2192 its next occupancy",
    "lg_job_machine": "same-job / same-machine edge: transport occupancy of an operation \u2192\n"
                      "that of the next operation of the same job or on the same machine",
    "lg_block": "blockage interval on corridor $e^\\star$ (closed to traffic)",
    "lg_seed": "seed occupancy (overlaps the blockage)",
    "lg_in": "occupancy inside the impact set (reroutable)",
    "lg_out": "occupancy outside the impact set (keeps plan)",
    "lg_done": "occupancy finished before $t_{\\mathrm{now}}$ (not rewritable)",
    "notes": "Notation: $O_{ji}$ is operation $i$ of job $j$; M1, M2 are machines; $k_1$, $k_2$, $k_3$ are vehicles "
             "($k_1$ carries job 1, $k_2$ carries job 2, $k_3$ carries another job);\n"
             "$e^\\star$, $e_2$, $e_3$ are corridors; each bar in the corridor layer is one occupancy of a corridor "
             "by a vehicle, and a thin dotted line links it to the operation it delivers to.",
}


def main() -> None:
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 7.7),
                             gridspec_kw={"height_ratios": HEIGHT_RATIOS})
    draw_aor(axes[0], LABELS)
    draw_strc(axes[1], LABELS)
    fig.tight_layout(h_pad=1.0, rect=(0, 0.05, 1, 1))
    draw_notes(fig, LABELS)
    fig.savefig(OUT + ".png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT + ".pdf", bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
