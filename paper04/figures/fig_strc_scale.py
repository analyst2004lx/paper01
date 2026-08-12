"""STRC 扰动规模对照图:读 STRC/experiments/scale_compare/scale_compare.csv。"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.abspath(os.path.join(
    HERE, "..", "..", "STRC", "experiments", "expanded", "scale_compare.csv"))
# fallback to older two-seed file
CSV_FALLBACK = os.path.abspath(os.path.join(
    HERE, "..", "..", "STRC", "experiments", "scale_compare", "scale_compare.csv"))
OUT = os.path.join(HERE, "fig_strc_scale")


def main() -> None:
    path = CSV if os.path.isfile(CSV) else CSV_FALLBACK
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    # prefer congested instance for the paper figure
    if any("strc_wall_ms" in r for r in rows):
        rows = [r for r in rows if r.get("instance") == "congested_8x4x4"]
        t_key, c_key = "strc_wall_ms", "strc_makespan"
        t1_key, c1_key = "r0_wall_ms", "r0_makespan"
        f_key, f1_key = "strc_feasible", "r0_feasible"
    else:
        t_key, c_key = "p04_wall_ms", "p04_makespan"
        t1_key, c1_key = "p01_wall_ms", "p01_makespan"
        f_key, f1_key = "p04_feasible", "p01_feasible"

    by = defaultdict(list)
    for r in rows:
        by[float(r["phi"])].append(r)

    phis = sorted(by)
    p04_t, p01_t, p04_c, p01_c = [], [], [], []
    for phi in phis:
        rs = by[phi]
        p04_t.append(sum(float(r[t_key]) for r in rs) / len(rs))
        p01_t.append(sum(float(r[t1_key]) for r in rs) / len(rs))
        p04_c.append(sum(float(r[c_key]) for r in rs if r[f_key] == "True")
                     / max(1, sum(1 for r in rs if r[f_key] == "True")))
        p01_c.append(sum(float(r[c1_key]) for r in rs if r[f1_key] == "True")
                     / max(1, sum(1 for r in rs if r[f1_key] == "True")))

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))
    ax = axes[0]
    ax.plot(phis, p04_t, "o-", label=r"STRC", color="#1f4e79")
    ax.plot(phis, p01_t, "s--", label=r"R0+ (2s)", color="#c45c26")
    ax.set_xlabel(r"affected fraction $\varphi$")
    ax.set_ylabel("wall time (ms)")
    ax.set_yscale("log")
    ax.legend(loc="best")
    ax.set_title("Response time")

    ax = axes[1]
    ax.plot(phis, p04_c, "o-", label=r"STRC", color="#1f4e79")
    ax.plot(phis, p01_c, "s--", label=r"R0+ (2s)", color="#c45c26")
    ax.set_xlabel(r"affected fraction $\varphi$")
    ax.set_ylabel(r"$C_{\max}$ (mean, feasible)")
    ax.legend(loc="best")
    ax.set_title("Makespan")

    fig.tight_layout()
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png")
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
