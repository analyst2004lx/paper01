"""案例甘特:example_3x3x2 / seed42 走廊阻断下,修复前后工序时间轴。

放位意图(正文 §6 案例小节):
  在 E1/E3 统计之后,用一例把「任务图空、闭包非空、闭包内改/外侧尽量冻」落到时间轴。
  上图=扰动前原排程(标闭包工序);下图=STRC 第 1 级修复后。

用法:
  py paper04/figures/fig_strc_case.py
"""
from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig_strc_case")
STRC = os.path.abspath(os.path.join(HERE, "..", "..", "STRC"))
if STRC not in sys.path:
    sys.path.insert(0, STRC)


def _closed_ops(closure_tasks: set[str]) -> set[tuple[int, int]]:
    ops = set()
    for t in closure_tasks:
        if not t.startswith("J"):
            continue
        parts = t[1:].split("-")
        if len(parts) >= 2:
            ops.add((int(parts[0]), int(parts[1])))
    return ops


def _draw_panel(ax, result, closed_ops, *, t_now, block, title, show_legend=False):
    ops = [rec for rec in result.ops.values() if not rec.pseudo and rec.machine is not None]
    machines = sorted({rec.machine for rec in ops})
    ymap = {m: i for i, m in enumerate(machines)}
    colors = {True: "#1f4e79", False: "#b0b8c0"}  # in closure / outside

    for rec in ops:
        key = (rec.job, rec.i)
        in_cl = key in closed_ops
        y = ymap[rec.machine]
        dur = max(1e-6, rec.finish - rec.start)
        ax.barh(y, dur, left=rec.start, height=0.55,
                color=colors[in_cl], edgecolor="#222", linewidth=0.6,
                alpha=0.92, zorder=2)
        if dur >= 3.5:
            ax.text(rec.start + dur / 2, y, f"J{rec.job}-{rec.i}",
                    ha="center", va="center", fontsize=6.5,
                    color="white" if in_cl else "#222", zorder=3)

    # t_now
    ax.axvline(t_now, color="#8b1e1e", ls="--", lw=1.0, zorder=4)
    ax.text(t_now, len(machines) - 0.15, r"$t_{\mathrm{now}}$",
            ha="left", va="bottom", fontsize=7, color="#8b1e1e")

    # block window as translucent band
    cid, t0, t1 = block
    ax.axvspan(t0, t1, color="#e8a0a0", alpha=0.35, zorder=0)
    ax.text((t0 + t1) / 2, -0.85, f"block on {cid}",
            ha="center", va="top", fontsize=6.5, color="#8b1e1e")

    ax.set_yticks(list(ymap.values()))
    ax.set_yticklabels([f"M{m}" for m in machines], fontsize=8)
    ax.set_xlabel("time", fontsize=8)
    ax.set_title(title, fontsize=9)
    ax.set_ylim(-1.1, len(machines) - 0.2)
    xmax = max(rec.finish for rec in ops) * 1.05
    ax.set_xlim(0, xmax)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if show_legend:
        ax.legend(handles=[
            Patch(facecolor="#1f4e79", edgecolor="#222", label="op in Cl (released)"),
            Patch(facecolor="#b0b8c0", edgecolor="#222", label="op outside (frozen)"),
            Patch(facecolor="#e8a0a0", alpha=0.5, label="corridor block window"),
        ], loc="upper right", fontsize=6.5, frameon=False)


def main() -> None:
    from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
    from algorithm.closure import machine_chains_from_ops, spatiotemporal_closure
    from algorithm.disturbance import Disturbance, seed_failed_reservations
    from algorithm.repair import repair_with_strc
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    inst = load_instance(os.path.join(CLBS_INPUT, "example_3x3x2.json"))
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    bundle = build_baseline(inst, net, seed=42, mode="heuristic")
    t_now = 0.35 * bundle.makespan
    cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
    dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                       t_start=t0, t_end=t1)
    seeds = seed_failed_reservations(dist, bundle.reservations)
    chains = machine_chains_from_ops(bundle.result.ops)
    closure = spatiotemporal_closure(
        seeds, bundle.reservations, horizon=bundle.makespan + 1.0,
        t_now=t_now, machine_chains=chains)
    closed_ops = _closed_ops({r.task for r in closure.closed})

    rep = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
    assert rep.feasible and rep.result is not None, rep.errors[:3]

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.0), sharex=True)
    block = (cid, t0, t1)
    _draw_panel(
        axes[0], bundle.result, closed_ops,
        t_now=t_now, block=block,
        title=(f"(a) Before repair  $C_{{\\max}}={bundle.makespan:.0f}$  "
               f"|Seeds|={len(seeds)}  |Cl|={closure.size}"),
        show_legend=True,
    )
    _draw_panel(
        axes[1], rep.result, closed_ops,
        t_now=t_now, block=block,
        title=(f"(b) After STRC level-1  $C_{{\\max}}={rep.makespan:.0f}$  "
               f"wall={rep.wall_ms:.1f} ms"),
        show_legend=False,
    )
    # annotate T_impact empty
    axes[0].text(
        0.01, 0.98,
        r"$T_{\mathrm{impact}}=\varnothing$ (task graph); repair uses Cl",
        transform=axes[0].transAxes, ha="left", va="top", fontsize=7,
        color="#1f4e79",
        bbox=dict(boxstyle="round,pad=0.2", fc="#e8eef5", ec="#1f4e79", lw=0.7),
    )

    fig.tight_layout()
    fig.savefig(OUT + ".pdf")
    fig.savefig(OUT + ".png")
    print("wrote", OUT + ".pdf")
    print(f"corridor={cid} t_now={t_now:.1f} block=[{t0:.1f},{t1:.1f}) "
          f"seeds={len(seeds)} cl={closure.size} "
          f"Cmax {bundle.makespan:.0f}->{rep.makespan:.0f}")


if __name__ == "__main__":
    main()
