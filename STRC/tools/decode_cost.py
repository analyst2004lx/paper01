"""测全局重解臂的响应时间下限:单次解码的耗时,以及它与一次有界修复的比值。

为什么要单独测这个。E5 里 R0+ 守不住小预算(实测 `budget_honored=False`),因为
GA 至少要跑完一代才检查终止条件,一代 = 种群规模次解码。但「一代」是配置量,
审稿人可以说把种群调小就行。**单次解码不是配置量**:任何基于解码的搜索,无论
种群多大、用不用局部搜索,每评估一个候选都要付一次解码的钱。所以

    响应时间下限 >= 一次解码

是与配置无关的下界,拿它跟一次有界修复的挂钟直接比,才是干净的对照。

用法:
    py -m tools.decode_cost
    py -m tools.decode_cost --reps 50
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_INSTANCES = [
    ("example_3x3x2", "example_3x3x2.json", None),
    ("congested_8x4x4", "congested_8x4x4.json", None),
    ("S8x4x4_high", "S8x4x4-LD21-H0.3-F0.6-A4-s42.json", "ext"),
    ("S8x4x4_funnel", "S8x4x4-LD11-H0.3-F0.6-A4-s42.json", "ext"),
    ("S8x4x4_mid", "S8x4x4-LD22-H0.3-F0.6-A4-s42.json", "ext"),
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="decode cost vs bounded repair cost")
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--pop", type=int, default=40,
                    help="仅用于换算「一代」的耗时,不影响单次解码的读数")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    import random

    from algorithm.clbs_bridge import (
        CLBS_INPUT, Network, clbs_ga, decode, load_instance,
    )
    from algorithm.disturbance import Disturbance
    from algorithm.repair import repair_with_strc
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    print(f"reps={args.reps}  seed={args.seed}  (pop={args.pop} 仅用于换算一代)")
    print(f"{'算例':<18}{'单次解码/ms':>14}{'一代/ms':>12}"
          f"{'R2 修复/ms':>13}{'解码/修复':>11}")
    rows = []
    for name, fname, sub in _INSTANCES:
        path = os.path.join(CLBS_INPUT, sub, fname) if sub else \
            os.path.join(CLBS_INPUT, fname)
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        net.check_reachability()

        rng = random.Random(args.seed)
        ma = clbs_ga.ma_min_time(inst)
        os_seq = clbs_ga.random_os(inst, rng)

        decode(inst, net, ma, os_seq, conflict_free=True, dispatch="exact")  # 预热
        ds = []
        for _ in range(args.reps):
            t0 = time.perf_counter()
            decode(inst, net, ma, os_seq, conflict_free=True, dispatch="exact")
            ds.append((time.perf_counter() - t0) * 1000.0)
        d_med = statistics.median(ds)

        bundle = build_baseline(inst, net, seed=args.seed, mode="heuristic")
        t_now = args.t_now_frac * bundle.makespan
        cid, _, _, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                           t_start=t_now, t_end=bundle.makespan + 1.0)
        repair_with_strc(inst, net, bundle, dist)  # 预热
        rs = []
        for _ in range(args.reps):
            rep = repair_with_strc(inst, net, bundle, dist)
            rs.append(rep.wall_ms)
        r_med = statistics.median(rs)

        print(f"{name:<18}{d_med:>14.2f}{d_med*args.pop:>12.0f}"
              f"{r_med:>13.2f}{d_med/r_med:>11.2f}")
        rows.append((name, d_med, r_med))

    print("\n单次解码是与搜索配置无关的下界:任何基于解码的搜索每评估一个候选都要付这笔钱。")
    ratios = [d / r for _, d, r in rows]
    print(f"解码/修复 比值区间 {min(ratios):.2f}--{max(ratios):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
