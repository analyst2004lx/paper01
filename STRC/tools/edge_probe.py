"""边集差分试探:只改闭包内一条预约,看闭包外是否被迫移动。

E2b 检验的是「实现与释放集定义是否一致」,不是「四类边是否覆盖物理耦合」。
本工具不预设耦合真值:对每个 r ∈ Cl 做一次延后,若与某个 o ∉ Cl 在同走廊上
新产生重叠,就记一条 leak——当前边集画不出来、但延后后物理上会撞车的通道。

用法(在 STRC/ 下):
    py -m tools.edge_probe              # 2 算例 × 3 种子
    py -m tools.edge_probe --full       # 与 E1 同口径 5×10
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EPS = 1e-9
_SEEDS_QUICK = [42, 7, 2024]
_SEEDS_FULL = [42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="closure edge-set leak probe")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="把闭包内预约整体后移的时长")
    ap.add_argument("--out", default="experiments/edge_probe.csv")
    return ap.parse_args()


def _instances(full: bool):
    from algorithm.clbs_bridge import CLBS_INPUT
    ext = lambda n: os.path.join(CLBS_INPUT, "ext", n)  # noqa: E731
    all_inst = [
        ("example_3x3x2", os.path.join(CLBS_INPUT, "example_3x3x2.json")),
        ("congested_8x4x4", os.path.join(CLBS_INPUT, "congested_8x4x4.json")),
        ("S8x4x4_high", ext("S8x4x4-LD21-H0.3-F0.6-A4-s42.json")),
        ("S8x4x4_funnel", ext("S8x4x4-LD11-H0.3-F0.6-A4-s42.json")),
        ("S8x4x4_mid", ext("S8x4x4-LD22-H0.3-F0.6-A4-s42.json")),
    ]
    return all_inst if full else all_inst[:2]


def _probe(reservations, closed, delay: float):
    """返回 (n_probed, n_delay_leaks, n_abut, n_near_miss, n_same_agv_leaks)。

    abut = 半开区间首尾相接(gap=0):现有让行边要求重叠,接壤不画边。
    """
    cl = set(closed)
    outside = [o for o in reservations if o not in cl]
    n_delay = n_abut = n_near = n_agv = 0
    for r in closed:
        ds, de = r.t_start + delay, r.t_end + delay
        for o in outside:
            if o.corridor != r.corridor:
                continue
            new_hit = de > o.t_start + EPS and ds < o.t_end - EPS
            old_hit = r.overlaps(o.t_start, o.t_end)
            if o.agv == r.agv:
                if new_hit and not old_hit:
                    n_agv += 1
                continue
            if new_hit and not old_hit:
                n_delay += 1
            gap = o.t_start - r.t_end
            if abs(gap) <= EPS:
                n_abut += 1
            elif 0 < gap <= delay + EPS:
                n_near += 1
    return len(closed), n_delay, n_abut, n_near, n_agv


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.repair import release_set_r2
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    seeds = _SEEDS_FULL if args.full else _SEEDS_QUICK
    rows = []
    for name, path in _instances(args.full):
        if not os.path.isfile(path):
            print(f"  skip missing {path}")
            continue
        inst = load_instance(path)
        net = Network(inst.nodes, inst.corridors, inst.lu_node)
        for seed in seeds:
            bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
            t_now = 0.35 * bundle.makespan
            cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
            dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                               t_start=t0, t_end=t1)
            closed = release_set_r2(bundle, dist)
            n_pr, n_del, n_abut, n_near, n_agv = _probe(
                bundle.reservations, closed, args.delay)
            rows.append({
                "instance": name, "seed": seed, "delay": args.delay,
                "n_closed": n_pr, "n_alive": sum(
                    1 for r in bundle.reservations if r.t_end > t_now + EPS),
                "n_delay_leaks": n_del, "n_abut": n_abut,
                "n_near_miss": n_near, "n_same_agv_leaks": n_agv,
            })
            print(f"  {name:<16} s={seed:<6} Cl={n_pr:<3} "
                  f"delay_leak={n_del:<3} abut={n_abut:<3} near={n_near:<3} agv={n_agv}")

    out = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) else args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}  ({len(rows)} rows)")

    by = defaultdict(list)
    for r in rows:
        by[r["instance"]].append(r)
    leak_pairs = sum(1 for r in rows if r["n_delay_leaks"] > 0)
    print(f"pairs with delay-leak {leak_pairs}/{len(rows)}  "
          f"total leaks {sum(r['n_delay_leaks'] for r in rows)}  "
          f"same-AGV leaks {sum(r['n_same_agv_leaks'] for r in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
