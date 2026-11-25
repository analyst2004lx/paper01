"""影响集的运输段补齐:实际允许改写的集合 U+ 比 Cl 多出多少。

replay_reroute 以运输段(J{j}-{i}-empty / -loaded)为单位决定是否改路,
一段只要有一条未结束占用在 Cl 内,它在 t_now 之后的全部占用都会重规划。
本工具在与 E3/E7 相同的协议(繁忙走廊单窗阻断、t_now=0.35 Cmax)上统计 |U+ \\ Cl|。

用法:py -m tools.seg_completion      (在 STRC/ 目录内)

Transport-segment completion of the impact set: how much larger the rewritable set U+ is than Cl.

replay_reroute decides rerouting per transport segment (J{j}-{i}-empty / -loaded):
if any unfinished occupation of a segment is in Cl, all its occupations after t_now are replanned.
This tool counts |U+ \\ Cl| under the E3/E7 protocol (single-window busy-corridor block, t_now=0.35 Cmax).

Usage: py -m tools.seg_completion      (inside STRC/)
"""
from __future__ import annotations

import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EPS = 1e-9


def main() -> int:
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.repair import release_set_r2
    from algorithm.schedule_io import build_baseline, pick_busy_corridor
    from tools.cheap_baselines import _SEEDS, _instances

    extra, share_cl, share_seg = [], [], []
    for name, path in _instances():
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        for seed in _SEEDS:
            b = build_baseline(inst, net, seed=seed, mode="heuristic")
            t_now = 0.35 * b.makespan
            cid, t0, t1, _ = pick_busy_corridor(b.reservations, t_now=t_now)
            dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                               t_start=t0, t_end=t1)
            cl = set(release_set_r2(b, dist))
            labels = {r.task for r in cl}
            alive = [r for r in b.reservations if r.t_end > t_now + EPS]
            useg = {r for r in alive if r.task in labels}
            extra.append(len(useg - cl))
            share_cl.append(len(cl) / len(alive))
            share_seg.append(len(useg) / len(alive))
            print(f"  {name:<16} s={seed:<6} |Cl|={len(cl):>4} |U+|={len(useg):>4} "
                  f"|R_alive|={len(alive):>4}")

    n = len(extra)
    print(f"\npairs with U+ > Cl : {sum(1 for x in extra if x > 0)}/{n}")
    print(f"|U+ \\ Cl| mean     : {st.mean(extra):.1f}   max: {max(extra)}")
    print(f"mean |Cl|/|R_alive|: {st.mean(share_cl):.2f}")
    print(f"mean |U+|/|R_alive|: {st.mean(share_seg):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
