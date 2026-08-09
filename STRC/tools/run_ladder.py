"""四级修复阶梯批跑(R0 / R0+ / R1 / R2)。

用法:
    py -m tools.run_ladder --budget-sec 1
    py -m tools.run_ladder --arms R1,R2
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STRC repair ladder batch runner")
    ap.add_argument("--instance", default=None)
    ap.add_argument("--budget-sec", type=float, default=1.0)
    ap.add_argument("--seeds", default="42,7")
    ap.add_argument("--arms", default="R0+,R1,R2")
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--out", default=os.path.join(ROOT, "experiments", "ladder.csv"))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.ladder import R_ARMS, solve_arm
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    inst_path = args.instance or os.path.join(CLBS_INPUT, "example_3x3x2.json")
    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    seeds = [int(x) for x in args.seeds.split(",")]
    arms = [a.strip() for a in args.arms.split(",")]
    for a in arms:
        if a not in R_ARMS:
            print(f"unknown arm {a}; choose from {R_ARMS}", file=sys.stderr)
            return 2

    rows = []
    print(f"ladder arms={arms} budget={args.budget_sec}s seeds={seeds}")
    for seed in seeds:
        bundle = build_baseline(inst, net, seed=seed)
        t_now = args.t_now_frac * bundle.makespan
        cid, _, _, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(
            type="corridor_block", t_now=t_now, corridor=cid,
            t_start=t_now, t_end=bundle.makespan + 1.0,
        )
        for arm in arms:
            rep = solve_arm(arm, inst, net, bundle, dist,
                            budget_sec=args.budget_sec, seed=seed)
            rows.append({
                "instance": inst.name,
                "seed": seed,
                "arm": arm,
                "corridor": cid,
                "feasible": rep.feasible,
                "makespan": rep.makespan,
                "release": rep.release_size,
                "wall_ms": round(rep.wall_ms, 2),
                "gens": rep.meta.get("generations"),
            })
            print(f"  seed={seed} {arm:3s} feas={rep.feasible} "
                  f"Cmax={rep.makespan} wall={rep.wall_ms:.1f}ms")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
