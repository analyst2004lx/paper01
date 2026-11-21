# -*- coding: utf-8 -*-
"""实验所用路网（中文版），输出 fig_strc_layouts_CN。

拓扑逐条读自实验实际加载的算例文件：主批次读 clbs/input，外部布局批次读
STRC/database/instances；本脚本只负责给节点排坐标，不手工增删走廊。
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from _cjk_mpl import setup_cjk  # noqa: E402

setup_cjk()

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CLBS_INPUT = os.path.join(ROOT, "clbs", "input")
PUB = os.path.join(ROOT, "STRC", "database", "instances")
OUT = os.path.join(HERE, "fig_strc_layouts_CN")

C_LU, C_MACH, C_JUNC = "#fdd49e", "#c6dbef", "white"
C_EDGE, C_ADD1, C_ADD2, C_GONE = "#555555", "#d95f02", "#7570b3", "#c0c0c0"
FS = 7.0


def load(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    net = d["network"]
    edges = {frozenset((c["u"], c["v"])): c["time"] for c in net["corridors"]}
    machines = {m["node"]: m["id"] for m in d["machines"]}
    return net["lu_node"], net["nodes"], edges, machines, d.get("_spec", {})


def fmt(t):
    return f"{t:g}"


def draw_node(ax, n, xy, lu, machines, size=1.0):
    x, y = xy
    if n == lu:
        w, h = 0.46 * size, 0.34 * size
        ax.add_patch(plt.Rectangle((x - w / 2, y - h / 2), w, h, fc=C_LU,
                                   ec="black", lw=0.8, zorder=3))
        ax.text(x, y, "$v_0$", ha="center", va="center", fontsize=FS, zorder=4)
    elif n in machines:
        w, h = 0.40 * size, 0.30 * size
        ax.add_patch(plt.Rectangle((x - w / 2, y - h / 2), w, h, fc=C_MACH,
                                   ec="black", lw=0.7, zorder=3))
        ax.text(x, y, f"M{machines[n]}", ha="center", va="center",
                fontsize=FS - 1.0, zorder=4)
    else:
        ax.plot([x], [y], "o", ms=3.8, mfc=C_JUNC, mec="black", mew=0.7, zorder=3)


def draw_edge(ax, a, b, color=C_EDGE, ls="-", lw=1.0, label=None, off=(0, 0.13)):
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, ls=ls, lw=lw, zorder=1)
    if label is not None:
        ax.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], label,
                ha="center", va="center", fontsize=FS - 0.5, color="#333333")


def finish(ax, title, footer, fy):
    ax.set_title(title, fontsize=8)
    ax.text(0.5, fy, footer, transform=ax.transAxes, ha="center", va="top",
            fontsize=FS - 0.5)
    ax.set_aspect("equal")
    ax.set_anchor("N")
    ax.axis("off")


def hand_panel(ax, fname, title, pos, offs):
    lu, nodes, edges, machines, _ = load(os.path.join(CLBS_INPUT, fname))
    assert set(pos) == set(nodes), set(nodes) ^ set(pos)
    for pair, t in edges.items():
        a, b = sorted(pair)
        draw_edge(ax, pos[a], pos[b], label=fmt(t), off=offs.get(pair, (0, 0.14)))
    for n in nodes:
        draw_node(ax, n, pos[n], lu, machines)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    ax.set_xlim(min(xs) - 0.5, max(xs) + 0.5)
    ax.set_ylim(min(ys) - 0.55, max(ys) + 0.45)
    finish(ax, title, f"节点/走廊数：{len(nodes)}/{len(edges)}", -0.02)


def spine_panel(ax):
    tags = {"S11": "LD11", "S21": "LD21", "S22": "LD22"}
    nets = {k: load(os.path.join(PUB, f"S8x4x4-{v}-H0.3-F0.6-A4-s42.json"))
            for k, v in tags.items()}
    lu, nodes, e22, machines, _ = nets["S22"]
    e11, e21 = nets["S11"][2], nets["S21"][2]
    pos = {"v0": (0.0, 0.0), "e1": (1.2, 0.0), "e2": (1.2, -0.9), "h1": (2.4, 0.0),
           "g1": (4.2, 0.0), "g2": (4.2, -0.9), "h2": (6.0, 0.0),
           "r1": (2.05, 1.25), "r2": (2.75, 1.25), "r3": (5.65, 1.25), "r4": (6.35, 1.25)}
    assert set(pos) == set(nodes), set(nodes) ^ set(pos)
    labelled_spur = False
    for pair, t in e22.items():
        a, b = sorted(pair)
        if pair in e11:
            color, ls, lw = C_EDGE, "-", 1.1
        elif pair in e21:
            color, ls, lw = C_ADD1, "--", 1.1
        else:
            color, ls, lw = C_ADD2, ":", 1.4
        label, off = None, (0, 0.14)
        if pair in e11:
            if not any(n in machines for n in pair):
                label = fmt(t)
            elif not labelled_spur and "r1" in pair:
                labelled_spur, label, off = True, fmt(t), (-0.2, 0.0)
        draw_edge(ax, pos[a], pos[b], color, ls, lw, label, off)
    for n in nodes:
        draw_node(ax, n, pos[n], lu, machines)
    ax.text(4.2, 0.18, "中廊", ha="center", va="bottom", fontsize=FS)
    ax.text(2.4, -0.42, "枢纽", ha="center", va="center", fontsize=FS - 0.5)
    ax.text(6.0, -0.42, "枢纽", ha="center", va="center", fontsize=FS - 0.5)
    counts = "  ".join(f"{k} {len(v[1])}/{len(v[2])}" for k, v in nets.items())
    ax.set_xlim(-0.5, 6.8)
    ax.set_ylim(-1.35, 1.7)
    finish(ax, "(c) 脊式布局 S11、S21、S22", "节点/走廊数：" + counts, -0.02)


def grid_panel(ax, fname, title):
    lu, nodes, edges, machines, spec = load(os.path.join(PUB, fname))
    rows, cols = spec["grid_rows"], spec["grid_cols"]
    pos = {f"g{r * cols + c + 1}": (c * 1.0, -r * 1.0)
           for r in range(rows) for c in range(cols)}
    assert set(pos) == set(nodes), set(nodes) ^ set(pos)
    for a, b in spec["grid_removed_edges"]:
        pa, pb = pos[f"g{a}"], pos[f"g{b}"]
        draw_edge(ax, pa, pb, color=C_GONE, ls=(0, (1.5, 1.5)), lw=0.9)
    labelled = False
    for pair, t in edges.items():
        a, b = sorted(pair)
        label = None
        if not labelled and pos[a][1] == pos[b][1] == 0.0:
            label, labelled = fmt(t), True
        draw_edge(ax, pos[a], pos[b], label=label, off=(0, 0.2))
    for n in nodes:
        draw_node(ax, n, pos[n], lu, machines, size=1.25)
    ax.set_xlim(-0.45, cols - 0.55)
    ax.set_ylim(-rows + 0.45, 0.5)
    finish(ax, title, f"节点/走廊数：{len(nodes)}/{len(edges)}", -0.03)


def main() -> None:
    fig = plt.figure(figsize=(7.2, 3.85))
    top = fig.add_gridspec(1, 3, width_ratios=[4.6, 5.8, 7.3], left=0.005,
                           right=0.995, top=0.95, bottom=0.57, wspace=0.08)
    bot = fig.add_gridspec(1, 5, width_ratios=[4, 4, 5, 5, 5], left=0.01,
                           right=0.99, top=0.53, bottom=0.11, wspace=0.12)

    hand_panel(fig.add_subplot(top[0, 0]), "example_3x3x2.json", "(a) 小例",
               {"v0": (0.0, 0.0), "c1": (1.3, 0.0), "c2": (3.0, 0.0),
                "r1": (2.15, 1.1), "r2": (3.6, 0.9), "r3": (3.6, -0.9)},
               {frozenset(("c1", "r1")): (-0.2, 0.05),
                frozenset(("r1", "c2")): (0.2, 0.05),
                frozenset(("c2", "r2")): (-0.2, 0.0),
                frozenset(("c2", "r3")): (-0.2, 0.0)})
    hand_panel(fig.add_subplot(top[0, 1]), "congested_8x4x4.json", "(b) 拥堵例",
               {"v0": (0.0, 0.0), "c1": (1.3, 0.0), "r1": (0.85, 1.2),
                "r2": (1.75, 1.2), "c2": (4.0, 0.0), "r3": (3.55, 1.2),
                "r4": (4.45, 1.2)},
               {frozenset(("c1", "r1")): (-0.2, 0.0),
                frozenset(("c1", "r2")): (0.2, 0.0),
                frozenset(("c2", "r3")): (-0.2, 0.0),
                frozenset(("c2", "r4")): (0.2, 0.0)})
    spine_panel(fig.add_subplot(top[0, 2]))

    pubs = (("S8x4x4-LyuL2-H0.3-F0.6-A4-s42.json", "(d) 布局 2"),
            ("S8x5x4-LyuL3-H0.3-F0.6-A4-s42.json", "(e) 布局 3"),
            ("S8x6x4-LyuL4-H0.3-F0.6-A4-s42.json", "(f) 布局 4"),
            ("S8x7x4-LyuL5-H0.3-F0.6-A4-s42.json", "(g) 布局 5"),
            ("S8x8x4-LyuL6-H0.3-F0.6-A4-s42.json", "(h) 布局 6"))
    for k, (fname, title) in enumerate(pubs):
        grid_panel(fig.add_subplot(bot[0, k]), fname, title)

    handles = [
        Line2D([], [], marker="s", ls="", ms=7, mfc=C_LU, mec="black", label="装卸站"),
        Line2D([], [], marker="s", ls="", ms=6, mfc=C_MACH, mec="black",
               label="机器节点"),
        Line2D([], [], marker="o", ls="", ms=4.5, mfc=C_JUNC, mec="black",
               label="路口"),
        Line2D([], [], color=C_EDGE, lw=1.1, label="走廊（数字为通行时间）"),
        Line2D([], [], color=C_ADD1, lw=1.1, ls="--", label="S21、S22 增加的出口通道"),
        Line2D([], [], color=C_ADD2, lw=1.4, ls=":", label="S22 另增的中段走廊"),
        Line2D([], [], color=C_GONE, lw=0.9, ls=(0, (1.5, 1.5)),
               label="原网格中缺失的走廊"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=FS - 0.5,
               frameon=False, bbox_to_anchor=(0.5, -0.01), handletextpad=0.4,
               columnspacing=1.0)
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png", dpi=200)
    print("wrote", OUT + ".pdf")


if __name__ == "__main__":
    main()
