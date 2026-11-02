"""预约影响集构造示意（中英文共用绘图逻辑）。

(a) 走廊--时间图：占用画成时段条，起点占用与阻断时段重叠；
(b) 同一批占用的预约依赖图：边按类型着色，虚线框为 Cl(Src)。
r6 只有指向集内的边、从起点不可达，用来说明「集内无出边、集外保持原计划」。
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import (Circle, FancyArrowPatch,  # noqa: E402
                                FancyBboxPatch, Rectangle)

C_YIELD, C_AGV, C_JOB, C_MACH = "#c45c26", "#1f4e79", "#2e7d4f", "#6b4c7a"
C_SEED, C_IN, C_OUT, C_DONE = "#c45c26", "#1f4e79", "#b0b8c0", "#d9d9d9"

# name: (lane, t_s, t_e, vehicle)
OCC = {
    "r0": ("e2", 0.4, 1.5, "k2"),
    "r1": ("es", 2.6, 4.2, "k1"),
    "r2": ("es", 4.2, 5.4, "k2"),
    "r3": ("e2", 4.6, 5.8, "k1"),
    "r4": ("e2", 5.8, 6.9, "k3"),
    "r5": ("e3", 7.4, 8.6, "k2"),
    "r6": ("e3", 2.4, 3.6, "k3"),
}
LANE_Y = {"es": 5.0, "e2": 3.3, "e3": 1.6}
T_NOW = 2.0
BLOCK = (3.0, 4.0)
CLOSED = {"r1", "r2", "r3", "r4", "r5"}

# (src, dst, kind)
EDGES = [
    ("r1", "r2", "yield"),
    ("r1", "r3", "agv"),
    ("r3", "r4", "yield"),
    ("r2", "r5", "agv"),
    ("r3", "r5", "job"),
    ("r6", "r4", "agv"),
]
EDGE_COLOR = {"yield": C_YIELD, "agv": C_AGV, "job": C_JOB, "mach": C_MACH}


def _color(name):
    if name == "r0":
        return C_DONE
    if name == "r1":
        return C_SEED
    return C_IN if name in CLOSED else C_OUT


def draw(L: dict, out: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.6),
                             gridspec_kw={"width_ratios": [1.2, 1.0]})

    # ---- (a) corridor--time chart ----
    ax = axes[0]
    ax.set_xlim(-0.6, 10.2)
    ax.set_ylim(-0.4, 6.6)
    ax.axis("off")
    ax.set_title(L["title_a"], fontsize=9)

    for lane, y in LANE_Y.items():
        ax.text(-0.5, y, L["lane"][lane], fontsize=8.5, va="center", color="#333333")
        ax.plot([0.2, 9.8], [y, y], color="#dddddd", lw=0.8, zorder=0)
    ax.annotate("", xy=(9.9, 0.55), xytext=(0.2, 0.55),
                arrowprops=dict(arrowstyle="->", color="#666666", lw=0.9))
    ax.text(9.9, 0.15, L["time"], ha="right", fontsize=7.5, color="#555555")

    b0, b1 = BLOCK
    ax.add_patch(Rectangle((b0, LANE_Y["es"] - 0.55), b1 - b0, 1.1,
                           facecolor="none", edgecolor="#8b1e1e",
                           hatch="////", lw=1.2, zorder=5))
    ax.text((b0 + b1) / 2, LANE_Y["es"] + 0.8, L["block"], ha="center",
            fontsize=7.5, color="#8b1e1e", fontweight="bold")

    ax.plot([T_NOW, T_NOW], [0.75, 6.0], color="#444444", lw=1.0, ls="--", zorder=2)
    ax.text(T_NOW, 6.15, r"$t_{\mathrm{now}}$", ha="center", fontsize=8)

    for name, (lane, ts, te, k) in OCC.items():
        y = LANE_Y[lane]
        ax.add_patch(FancyBboxPatch(
            (ts, y - 0.28), te - ts, 0.56,
            boxstyle="round,pad=0.0,rounding_size=0.12",
            facecolor=_color(name), edgecolor="#222222", lw=0.8, zorder=3,
            linestyle=":" if name == "r0" else "-"))
        fc = "#333333" if name in ("r0", "r6") else "white"
        ax.text((ts + te) / 2, y, f"{name}·{k}", ha="center", va="center",
                fontsize=6.8, color=fc, fontweight="bold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.12", fc=_color(name), ec="none")
                if name == "r1" else None)

    ax.text(3.6, LANE_Y["es"] - 0.85, L["seed_tag"], ha="center", fontsize=6.8,
            color="#8b1e1e")
    ax.text(0.95, LANE_Y["e2"] - 0.6, L["done_tag"], ha="center", fontsize=6.5,
            color="#666666")

    # ---- (b) dependency graph + closure ----
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.4, 6.6)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.set_title(L["title_b"], fontsize=9)

    pos = {"r1": (1.6, 4.8), "r2": (4.4, 4.8), "r3": (1.6, 2.4),
           "r4": (4.4, 2.4), "r5": (3.0, 0.9), "r6": (8.0, 2.4)}

    ax.add_patch(FancyBboxPatch(
        (0.7, 0.2), 4.6, 5.35, boxstyle="round,pad=0.1,rounding_size=0.25",
        facecolor="#eef3f8", edgecolor="#1f4e79", lw=1.3, ls="--", zorder=0))
    ax.text(3.0, 5.85, L["closure"], ha="center", fontsize=8.5,
            color="#1f4e79", fontweight="bold")

    for a, b, kind in EDGES:
        ax.add_patch(FancyArrowPatch(
            pos[a], pos[b], arrowstyle="-|>", mutation_scale=11,
            color=EDGE_COLOR[kind], lw=1.4,
            linestyle="--" if kind == "mach" else "-",
            shrinkA=10, shrinkB=10, connectionstyle="arc3,rad=0.0", zorder=2))

    for name, (x, y) in pos.items():
        ax.add_patch(Circle((x, y), 0.45, facecolor=_color(name),
                            edgecolor="#222222", lw=1.0, zorder=3))
        ax.text(x, y, name, ha="center", va="center", fontsize=7.5,
                color="#333333" if name == "r6" else "white",
                fontweight="bold", zorder=4)

    ax.text(1.6, 5.32, L["seed"], ha="center", va="bottom", fontsize=6.8, color="#8b1e1e")
    ax.text(8.0, 1.25, L["outside"], ha="center", va="top", fontsize=6.8,
            color="#555555", linespacing=1.3)

    handles = [
        Line2D([0], [0], color=C_YIELD, lw=1.6, label=L["e_yield"]),
        Line2D([0], [0], color=C_AGV, lw=1.6, label=L["e_agv"]),
        Line2D([0], [0], color=C_JOB, lw=1.6, label=L["e_job"]),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(5.7, 5.9),
              bbox_transform=ax.transData,
              fontsize=6.6, frameon=False, handlelength=1.5)

    fig.tight_layout()
    fig.savefig(out + ".pdf", bbox_inches="tight")
    fig.savefig(out + ".png", dpi=200, bbox_inches="tight")
    print("wrote", out)
