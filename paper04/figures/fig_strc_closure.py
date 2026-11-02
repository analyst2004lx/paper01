"""Construction of the reservation impact set (English version)."""
from __future__ import annotations

import os

from _closure_draw import draw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_closure")

L = {
    "title_a": "(a) Corridor–time chart: seed occupancy",
    "title_b": r"(b) Reservation dependency graph and $\mathrm{Cl}(\mathrm{Src})$",
    "lane": {"es": r"$e^\star$", "e2": r"$e_2$", "e3": r"$e_3$"},
    "time": "time",
    "block": "blocked interval",
    "seed_tag": "r1 overlaps the blockage → seed",
    "done_tag": "finished",
    "closure": r"$\mathrm{Cl}(\mathrm{Src})$",
    "seed": "seed",
    "outside": "r6: only edges into the set;\nunreachable from the seed;\nkept as planned",
    "e_yield": "yielding (same corridor, other vehicle)",
    "e_agv": "same-vehicle successor",
    "e_job": "same-job successor",
}

if __name__ == "__main__":
    draw(L, OUT)
