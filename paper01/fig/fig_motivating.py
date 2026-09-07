# -*- coding: utf-8 -*-
"""图 1 动机算例:常数运输时间矩阵与无冲突路由给出相反的指派次序。

数据来自 clbs/output/motivating.json,由 clbs/tools/motivating.py 用与论文同一套解码器
算出——(b) 的四个数不是示意值。(a) 的几何形状与该算例逐一对应。
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

C_FAST = "#2e7d32"      # 快臂 M1
C_SLOW = "#ef6c00"      # 慢臂 M2
C_TRUNK = "#c62828"     # 排他干道
C_GREY = "#7a7a7a"


def node(ax, x, y, label, fc="#ffffff", ec="#444444", r=0.30, fs=9, bold=False):
    ax.add_patch(Circle((x, y), r, facecolor=fc, edgecolor=ec, lw=1.4, zorder=4))
    ax.text(x, y, label, ha="center", va="center", zorder=5,
            fontsize=fs, fontweight="bold" if bold else "normal")


def edge(ax, p, q, tau, color=C_GREY, lw=1.6, ls="-", off=(0.0, 0.22), fs=8.5):
    ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=lw, ls=ls, zorder=2)
    ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], tau,
            ha="center", va="center", fontsize=fs, color=color, zorder=6,
            bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="none", alpha=0.9))


def panel_layout(ax, p) -> None:
    ax.set_title("(a) 通往快臂的唯一通路是一条排他干道",
                 fontsize=10.5, fontweight="bold", pad=10)
    ax.set_xlim(-0.6, 9.4)
    ax.set_ylim(-0.4, 5.0)
    ax.axis("off")
    ax.set_aspect("equal")

    P = {"v0": (0.9, 0.7), "v1": (2.4, 2.3), "v2": (7.0, 2.3),
         "m1": (8.5, 3.9), "m2": (0.9, 3.9), "m3": (8.5, 0.7)}

    edge(ax, P["v0"], P["v1"], "1")
    edge(ax, P["v1"], P["v2"], f"τ = {p['trunk_tau']:.0f}（排他）",
         color=C_TRUNK, lw=3.4, off=(0.0, 0.34), fs=9)
    edge(ax, P["v2"], P["m1"], "1")
    edge(ax, P["v2"], P["m3"], "1")
    edge(ax, P["v1"], P["m2"], "2", color=C_SLOW, lw=2.0)
    ax.text(0.12, 3.05, "不经过干道", ha="left", va="center",
            fontsize=8, color=C_SLOW)

    node(ax, *P["v0"], "LU", fc="#dceaf8", ec="#08519c", r=0.36, bold=True)
    node(ax, *P["v1"], "$v_1$")
    node(ax, *P["v2"], "$v_2$")
    node(ax, *P["m1"], "M1", fc="#e8f5e9", ec=C_FAST, r=0.36, bold=True)
    node(ax, *P["m2"], "M2", fc="#fff3e0", ec=C_SLOW, r=0.36, bold=True)
    node(ax, *P["m3"], "M3", fc="#f0f0f0", ec=C_GREY, r=0.36)

    ax.text(8.5, 4.48, f"快臂  t$^P$={p['proc_fast']:.0f}", ha="center",
            fontsize=8.5, color=C_FAST, fontweight="bold")
    ax.text(0.9, 4.48, f"慢臂  t$^P$={p['proc_slow']:.0f}", ha="center",
            fontsize=8.5, color=C_SLOW, fontweight="bold")
    ax.text(8.5, 0.16, f"{p['n_background']:.0f} 个只能上 M3 加工的工件",
            ha="center", va="top", fontsize=8, color=C_GREY)
    ax.text(4.7, 1.68, "只能上 M3 的工件反复穿越干道 → 让行等待",
            ha="center", fontsize=8.5, color=C_TRUNK)

    ax.text(4.4, -0.30,
            f"同一道工序的两个指派：快臂 M1 往返行程 {p['travel_M1_round']:.0f} + 加工 "
            f"{p['proc_fast']:.0f}　|　慢臂 M2 往返行程 {p['travel_M2_round']:.0f} + 加工 "
            f"{p['proc_slow']:.0f}",
            ha="center", va="center", fontsize=8.5, color="#222222",
            bbox=dict(boxstyle="round,pad=0.3", fc="#f7f7f7", ec="#999999"))


def panel_reversal(ax, d) -> None:
    ax.set_title("(b) 同一对指派：常数矩阵与无冲突路由",
                 fontsize=10.5, fontweight="bold", pad=10)
    groups = [("常数运输时间\n矩阵", "ideal"),
              ("无冲突路由", "routed")]
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
                ax.text(gx + off, -top * 0.105, "选中", ha="center", va="top",
                        fontsize=9, color=col, fontweight="bold")
        ax.text(gx, -top * 0.24, glabel, ha="center", va="top", fontsize=9.5)

    ax.text((xs[0] + xs[1]) / 2, top * 1.31,
            f"优劣对调：常数矩阵选 M{picks[0]}（快臂），无冲突路由选 M{picks[1]}（慢臂）",
            ha="center", va="center", fontsize=10, fontweight="bold", color="#111111",
            bbox=dict(boxstyle="round,pad=0.34", fc="#fff8f0", ec="#d95f02", lw=1.2))
    ax.text((xs[0] + xs[1]) / 2, top * 1.15,
            f"$C$(M1)$-$$C$(M2)：{d['M1']['ideal'] - d['M2']['ideal']:+.0f}"
            f"   →   {d['M1']['routed'] - d['M2']['routed']:+.0f}",
            ha="center", va="center", fontsize=9, color="#444444")

    ax.set_ylabel("完工时间 $C_{\\max}$", fontsize=9.5)
    ax.set_ylim(0, top * 1.44)
    ax.set_xlim(-0.70, 2.15)
    ax.set_xticks([])
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", ls=":", color="#cccccc", zorder=0)
    ax.set_axisbelow(True)


def main() -> None:
    if not os.path.exists(DATA):
        raise SystemExit(f"缺 {DATA};先在 clbs/ 下跑 py -m tools.motivating --sweep")
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.15),
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
