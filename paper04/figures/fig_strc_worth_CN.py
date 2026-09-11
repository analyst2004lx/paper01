"""E7 事后规则:释放占比 vs 稳定性降幅。读 cheap_baselines.csv,不跑新实验。"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.abspath(os.path.join(
    HERE, "..", "..", "STRC", "experiments", "cheap_baselines.csv"))
OUT = os.path.join(HERE, "fig_strc_worth_CN")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"],
    "axes.unicode_minus": False,
})

ORDER = ("example_3x3x2", "congested_8x4x4", "S8x4x4_high",
         "S8x4x4_funnel", "S8x4x4_mid")
LABEL = {
    "example_3x3x2": "3x3x2",
    "congested_8x4x4": "congested",
    "S8x4x4_high": "S8 high",
    "S8x4x4_funnel": "S8 funnel",
    "S8x4x4_mid": "S8 mid",
}
COLOR = {
    "example_3x3x2": "#4c78a8",
    "congested_8x4x4": "#c45c26",
    "S8x4x4_high": "#54a24b",
    "S8x4x4_funnel": "#b279a2",
    "S8x4x4_mid": "#eeca3b",
}

# 在本样本上选定的事后阈值,不作外推定理。
THRESH = 0.93


def pairs(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    idx = {(r["instance"], r["seed"], r["arm"]): r for r in rows}
    out = []
    for inst, seed in sorted({(r["instance"], r["seed"]) for r in rows}):
        a, b = idx.get((inst, seed, "R2")), idx.get((inst, seed, "RA"))
        if a is None or b is None:
            continue
        if str(a["feasible"]).lower() != "true" or str(b["feasible"]).lower() != "true":
            continue
        share = float(a["release_size"]) / float(a["alive_size"])
        delta = float(b["res_frac"]) - float(a["res_frac"])
        out.append((inst, seed, share, delta))
    return out


def main() -> None:
    data = pairs(CSV)
    fig, ax = plt.subplots(figsize=(5.6, 3.15))
    by = defaultdict(list)
    for inst, _seed, share, delta in data:
        by[inst].append((share, delta))
    for inst in ORDER:
        xs = [p[0] for p in by.get(inst, ())]
        ys = [p[1] for p in by.get(inst, ())]
        if not xs:
            continue
        ax.scatter(xs, ys, s=28, color=COLOR[inst], label=LABEL[inst],
                   edgecolors="0.25", linewidths=0.4, zorder=3)
    ax.axvline(THRESH, color="0.35", linestyle="--", linewidth=1.0,
               label=rf"事后阈值 ${THRESH:g}$")
    ax.set_xlabel(r"释放占比 $\mathrm{Cl}/|R^{\circ}|$")
    ax.set_ylabel("稳定性降幅 (RA $-$ R2)")
    ax.set_xlim(0.74, 1.02)
    ax.legend(loc="upper right", fontsize=7, ncol=2, framealpha=0.92)
    fig.tight_layout()
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png")
    print("wrote", OUT + ".pdf")

    lo = [d for _i, _s, sh, d in data if sh < THRESH - 1e-12]
    hi = [d for _i, _s, sh, d in data if sh >= THRESH - 1e-12]
    print("n=%d  thresh=%.2f  below n=%d mean=%.3f  above n=%d mean=%.3f"
          % (len(data), THRESH,
             len(lo), (sum(lo) / len(lo) if lo else float("nan")),
             len(hi), (sum(hi) / len(hi) if hi else float("nan"))))


if __name__ == "__main__":
    main()
