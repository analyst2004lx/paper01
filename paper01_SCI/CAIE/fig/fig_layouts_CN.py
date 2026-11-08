# -*- coding: utf-8 -*-
"""布局族 A 的五种路网（中文版），输出 fig_layouts_CN。

拓扑直接由 clbs_new/tools/abc_matrix.build 生成，与主批次所用算例逐节点一致；
本脚本只负责给节点排坐标。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "clbs_new")))

from _style import FS_ANNOT, FS_LEG, FULL, plt, save, use_cjk  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from tools.abc_matrix import CASES, build  # noqa: E402

use_cjk()

C_STORE, C_MACH, C_JUNC = "#fdd49e", "#c6dbef", "white"
C_EDGE, C_ADD1, C_ADD2 = "#555555", "#d95f02", "#7570b3"


def layout(tag):
    case = next(c for c in CASES if c.get("tag") == tag)
    inst, _net, _c = build(case)
    edges = {frozenset((e["u"], e["v"])): e["time"] for e in inst.corridors}
    return inst, edges


def is_machine(n):
    return n.startswith("r")


def is_store(n):
    return n in ("v0", "w0")


def draw_node(ax, n, xy, label=None):
    x, y = xy
    if is_store(n):
        ax.add_patch(plt.Rectangle((x - 0.32, y - 0.24), 0.64, 0.48, fc=C_STORE,
                                   ec="black", lw=0.8, zorder=3))
        ax.text(x, y, label, ha="center", va="center", fontsize=FS_ANNOT, zorder=4)
    elif is_machine(n):
        ax.add_patch(plt.Rectangle((x - 0.2, y - 0.16), 0.4, 0.32, fc=C_MACH,
                                   ec="black", lw=0.7, zorder=3))
        ax.text(x, y, label, ha="center", va="center", fontsize=FS_ANNOT - 0.5,
                zorder=4)
    else:
        ax.plot([x], [y], "o", ms=4.2, mfc=C_JUNC, mec="black", mew=0.7, zorder=3)


def draw_edge(ax, a, b, color=C_EDGE, ls="-", lw=1.0, label=None, off=(0, 0.13)):
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, ls=ls, lw=lw, zorder=1)
    if label is not None:
        ax.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], label,
                ha="center", va="center", fontsize=FS_ANNOT - 0.5, color="#333333")


def fmt(t):
    return f"{t:g}"


# ---------------------------------------------------------------- 脊式
def spine_panel(ax):
    s11, e11 = layout("funnel")
    s21, e21 = layout("high")
    s22, e22 = layout("mid")
    pos = {"v0": (0.0, 0.0), "e1": (1.2, 0.0), "e2": (1.2, -0.9), "h1": (2.4, 0.0),
           "g1": (4.2, 0.0), "g2": (4.2, -0.9), "h2": (6.0, 0.0),
           "f1": (7.2, 0.0), "f2": (7.2, -0.9), "w0": (8.4, 0.0)}
    hubs = {"h1": [], "h2": []}
    for m in s22.machine_node.values():
        hub = next(h for h in hubs if frozenset((h, m)) in e22)
        hubs[hub].append(m)
    for hub, ms in hubs.items():
        hx = pos[hub][0]
        for k, m in enumerate(sorted(ms, key=lambda s: int(s[1:]))):
            pos[m] = (hx + (k - (len(ms) - 1) / 2) * 0.62, 1.35)
    assert set(pos) == set(s22.nodes), set(s22.nodes) ^ set(pos)

    spur_labelled = set()
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
            spur = [n for n in pair if is_machine(n)]
            if not spur:
                label = fmt(t)
            elif spur[0] in (min(hubs["h1"]), min(hubs["h2"], key=lambda s: int(s[1:]))) \
                    and spur[0] not in spur_labelled:
                spur_labelled.add(spur[0])
                label, off = fmt(t), (-0.17, 0.0)
        draw_edge(ax, pos[a], pos[b], color, ls, lw, label, off)

    names = {"v0": "$v_{\\mathrm{in}}$", "w0": "$v_{\\mathrm{out}}$"}
    for n in s22.nodes:
        draw_node(ax, n, pos[n], names.get(n, f"M{n[1:]}" if is_machine(n) else None))
    ax.text(0.0, -0.42, "毛坯库", ha="center", va="top", fontsize=FS_ANNOT)
    ax.text(8.4, -0.42, "成品库", ha="center", va="top", fontsize=FS_ANNOT)
    ax.text(4.2, 0.30, "中廊", ha="center", va="bottom", fontsize=FS_ANNOT)
    ax.text(2.4, -0.6, "近端枢纽", ha="center", va="center", fontsize=FS_ANNOT - 0.5)
    ax.text(6.0, -0.6, "远端枢纽", ha="center", va="center", fontsize=FS_ANNOT - 0.5)

    counts = "  ".join(f"{name} {len(i.nodes)}/{len(e)}" for name, i, e in
                       (("S11", s11, e11), ("S21", s21, e21), ("S22", s22, e22)))
    ax.text(4.2, -1.45, "节点/走廊数：" + counts, ha="center", va="top",
            fontsize=FS_ANNOT)
    ax.set_title("(a) 脊式布局 S11、S21、S22", fontsize=8.5)
    ax.set_xlim(-0.6, 9.0)
    ax.set_ylim(-1.85, 1.75)


# ---------------------------------------------------------------- 网格
def grid_panel(ax, tag, title):
    inst, edges = layout(tag)
    pos = {}
    for n in inst.nodes:
        if n.startswith("n"):
            r, c = (int(v) for v in n[1:].split("_"))
            pos[n] = (c * 1.0, -r * 1.0)
    anchor = {}
    for pair in edges:
        a, b = tuple(pair)
        for leaf, other in ((a, b), (b, a)):
            if (is_machine(leaf) or is_store(leaf)) and other in pos:
                anchor[leaf] = other
    for leaf, j in anchor.items():
        x, y = pos[j]
        if leaf == "v0":
            pos[leaf] = (x - 0.5, y + 0.5)
        elif leaf == "w0":
            pos[leaf] = (x + 0.5, y - 0.5)
        else:
            pos[leaf] = (x + 0.36, y + 0.36)
    assert set(pos) == set(inst.nodes), set(inst.nodes) ^ set(pos)

    done_grid = done_spur = False
    for pair, t in edges.items():
        a, b = sorted(pair)
        label, off = None, (0, 0.13)
        if a.startswith("n") and b.startswith("n") and not done_grid \
                and pos[a][1] == pos[b][1] == 0.0:
            label, done_grid = fmt(t), True
        elif "v0" in pair and not done_spur:
            label, done_spur, off = fmt(t), True, (-0.14, -0.12)
        draw_edge(ax, pos[a], pos[b], label=label, off=off)

    names = {"v0": "$v_{\\mathrm{in}}$", "w0": "$v_{\\mathrm{out}}$"}
    order = sorted(inst.machine_node.values(), key=lambda s: int(s[1:]))
    for n in inst.nodes:
        draw_node(ax, n, pos[n], names.get(n, f"M{n[1:]}" if is_machine(n) else None))
    ax.text(pos["v0"][0], pos["v0"][1] + 0.3, "毛坯库", ha="center", va="bottom",
            fontsize=FS_ANNOT)
    ax.text(pos["w0"][0], pos["w0"][1] - 0.3, "成品库", ha="center", va="top",
            fontsize=FS_ANNOT)
    assert len(order) == 8
    ax.text(1.5, -4.25, f"节点/走廊数：{len(inst.nodes)}/{len(edges)}",
            ha="center", va="top", fontsize=FS_ANNOT)
    ax.set_title(title, fontsize=8.5)
    ax.set_xlim(-0.95, 4.05)
    ax.set_ylim(-4.65, 1.2)


def main() -> None:
    fig = plt.figure(figsize=(FULL, 2.55))
    gs = fig.add_gridspec(1, 3, width_ratios=[9.6, 5.0, 5.0], wspace=0.04)
    axes = [fig.add_subplot(gs[0, k]) for k in range(3)]
    spine_panel(axes[0])
    grid_panel(axes[1], "low", "(b) 网格布局 GC：机器聚于远角")
    grid_panel(axes[2], "scatter", "(c) 网格布局 GD：机器分散")
    for ax in axes:
        ax.set_aspect("equal")
        ax.set_anchor("N")
        ax.axis("off")

    handles = [
        Line2D([], [], marker="o", ls="", ms=4.5, mfc=C_JUNC, mec="black",
               label="路口（容量 1）"),
        Line2D([], [], marker="s", ls="", ms=6, mfc=C_MACH, mec="black",
               label="机器节点（容量 $c$）"),
        Line2D([], [], marker="s", ls="", ms=7, mfc=C_STORE, mec="black",
               label="库区（不限）"),
        Line2D([], [], color=C_EDGE, lw=1.1, label="走廊（数字为通行时间）"),
        Line2D([], [], color=C_ADD1, lw=1.1, ls="--", label="S21、S22 增加的两端通道"),
        Line2D([], [], color=C_ADD2, lw=1.4, ls=":", label="S22 另增的中段走廊"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=6, fontsize=FS_LEG - 0.5,
               frameon=False, bbox_to_anchor=(0.5, -0.02), handletextpad=0.4,
               columnspacing=1.0)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.90, bottom=0.12)
    save(fig, "fig_layouts_CN")


if __name__ == "__main__":
    main()
