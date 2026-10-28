"""E5 权衡:预算–完工时间 vs STRC 定点。读 STRC/experiments/e5_cross_curve.csv。"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.abspath(os.path.join(
    HERE, "..", "..", "STRC", "experiments", "expanded", "e5_cross_curve.csv"))
CSV_FALLBACK = os.path.abspath(os.path.join(
    HERE, "..", "..", "STRC", "experiments", "e5_cross_curve.csv"))
OUT = os.path.join(HERE, "fig_strc_e5")


def main() -> None:
    path = CSV if os.path.isfile(CSV) else CSV_FALLBACK
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    rows = [r for r in rows if r.get("instance", "congested_8x4x4") == "congested_8x4x4"]
    by_b = defaultdict(list)
    r2_c, r2_t, r2_chg = [], [], []
    use_frac = "R2_res_frac" in rows[0]
    for r in rows:
        by_b[float(r["budget_sec"])].append(r)
        r2_c.append(float(r["R2_makespan"]))
        r2_t.append(float(r["R2_wall_ms"]))
        if use_frac:
            r2_chg.append(float(r["R2_res_frac"]))
        else:
            r2_chg.append(float(r["R2_res_changed"]) / float(r["R2_res_total"]))

    budgets = sorted(by_b)
    r0_c = [sum(float(r["R0_makespan"]) for r in by_b[b]) / len(by_b[b]) for b in budgets]
    r0_t = [sum(float(r["R0_wall_ms"]) for r in by_b[b]) / len(by_b[b]) for b in budgets]
    r2_c_mean = sum(r2_c) / len(r2_c)
    r2_t_mean = sum(r2_t) / len(r2_t)
    r2_chg_mean = sum(r2_chg) / len(r2_chg)
    if use_frac:
        r0_chg = [
            sum(float(r["R0_res_frac"]) for r in by_b[b]) / len(by_b[b])
            for b in budgets
        ]
    else:
        r0_chg = [
            sum(float(r["R0_res_changed"]) / float(r["R0_res_total"]) for r in by_b[b]) / len(by_b[b])
            for b in budgets
        ]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))
    ax = axes[0]
    ax.plot(r0_t, r0_c, "s--", color="#c45c26", label="R0+")
    for b, t, c in zip(budgets, r0_t, r0_c):
        ax.annotate(f"{b:g}s", (t, c), textcoords="offset points", xytext=(4, 2), fontsize=7)
    ax.scatter([r2_t_mean], [r2_c_mean], marker="o", s=45, color="#1f4e79", zorder=3, label="STRC")
    ax.set_xlabel("wall time (ms)")
    ax.set_ylabel(r"$C_{\max}$")
    ax.set_xscale("log")
    ax.legend(loc="best")
    ax.set_title(r"Time--makespan trade-off")

    ax = axes[1]
    ax.plot(budgets, r0_chg, "s--", color="#c45c26", label="R0+")
    ax.axhline(r2_chg_mean, color="#1f4e79", linestyle="-", label="STRC")
    ax.set_xlabel("R0+ budget (s)")
    ax.set_ylabel("fraction of reservations changed")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="best")
    ax.set_title("Schedule stability")

    fig.tight_layout()
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png")
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
