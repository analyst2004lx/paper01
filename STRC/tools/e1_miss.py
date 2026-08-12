"""E1 门禁:走廊阻断下任务图漏报 vs 预约闭包非空。

通过条件(单次算例):
  1) |T_direct| = 0 且 |T_impact| = 0
  2) |seeds| > 0 且 |closure| >= |seeds|
  3) 原排程在阻断下不可行(仍有预约落在阻断时窗)

用法(在 STRC/ 下):
    py -m tools.e1_miss
    py -m tools.e1_miss --instance ../clbs/input/congested_8x4x4.json --seed 7
    py -m tools.e1_miss --auto-corridor   # 忽略 JSON 里的 corridor,改选最忙走廊
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, replace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STRC E1: task-graph miss vs reservation closure")
    ap.add_argument("--instance", default=None)
    ap.add_argument("--disturbance",
                    default=os.path.join(ROOT, "input", "disturbances",
                                         "corridor_block_example.json"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--mode", default="heuristic", choices=["heuristic", "ga"])
    ap.add_argument("--t-now-frac", type=float, default=0.35,
                    help="若 disturbance.t_now 相对 makespan 不合理,按此比例重设")
    ap.add_argument("--auto-corridor", action="store_true",
                    help="按未来占用最多的走廊自动生成阻断")
    ap.add_argument("--theta", type=int, default=2, help="任务图 BFS 跳数")
    ap.add_argument("--out", default=os.path.join(ROOT, "experiments", "e1_miss.csv"))
    ap.add_argument("--save-schedule", default=None,
                    help="可选:把基线排程写入 input/schedules/")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
    from algorithm.closure import (
        assert_containment_structural,
        job_precedence_from_reservations,
        machine_chains_from_ops,
        release_set_from_tasks,
        spatiotemporal_closure,
        task_graph_direct,
        task_graph_impact,
    )
    from algorithm.disturbance import (
        load_disturbance,
        schedule_still_valid_under_block,
        seed_failed_reservations,
    )
    from algorithm.schedule_io import build_baseline, pick_busy_corridor, save_schedule_bundle

    inst_path = args.instance or os.path.join(CLBS_INPUT, "example_3x3x2.json")
    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()
    feats = net.structural_features(list(inst.machine_node.values()))

    bundle = build_baseline(inst, net, seed=args.seed, mode=args.mode)
    result = bundle.result
    reservations = bundle.reservations
    if args.save_schedule:
        save_schedule_bundle(args.save_schedule, bundle)

    dist = load_disturbance(args.disturbance)
    # 对齐 t_now 到排程尺度
    t_now = dist.t_now
    if t_now <= 0 or t_now >= result.makespan:
        t_now = args.t_now_frac * result.makespan
    dist = replace(dist, t_now=float(t_now))

    if args.auto_corridor or dist.corridor is None:
        cid, t0, t1, n_hit = pick_busy_corridor(reservations, t_now=dist.t_now,
                                                prefer=dist.corridor)
        dist = replace(dist, corridor=cid, t_start=t0, t_end=t1)
    else:
        seeds_try = seed_failed_reservations(dist, reservations)
        if not seeds_try:
            cid, t0, t1, n_hit = pick_busy_corridor(reservations, t_now=dist.t_now)
            print(f"[E1] warn: corridor {dist.corridor!r} has 0 future hits; "
                  f"auto-switch to {cid} ({n_hit} hits)")
            dist = replace(dist, type="corridor_block", corridor=cid,
                           t_start=t0, t_end=t1)

    seeds = seed_failed_reservations(dist, reservations)
    chains = machine_chains_from_ops(result.ops)
    horizon = float(result.makespan) + 1.0
    closure = spatiotemporal_closure(
        seeds, reservations, horizon=horizon, t_now=dist.t_now,
        machine_chains=chains,
    )

    job_succ = job_precedence_from_reservations(reservations)
    t_direct = task_graph_direct(dist)
    t_impact = task_graph_impact(dist, job_succ, theta=args.theta)
    r1_release = release_set_from_tasks(reservations, t_impact, t_now=dist.t_now)

    feasible_after = schedule_still_valid_under_block(reservations, dist)
    leaks = assert_containment_structural(
        closure, reservations, t_now=dist.t_now, machine_chains=chains)


    pass_c1 = (
        len(t_direct) == 0
        and len(t_impact) == 0
        and len(seeds) > 0
        and closure.size >= len(seeds)
        and (not feasible_after)
    )

    row = {
        "instance": inst.name,
        "seed": args.seed,
        "mode": args.mode,
        "makespan": round(result.makespan, 4),
        "disturb_type": dist.type,
        "disturb_class": dist.class_label,
        "corridor": dist.corridor,
        "t_now": round(dist.t_now, 4),
        "t_start": dist.t_start,
        "t_end": dist.t_end,
        "n_reservations": len(reservations),
        "n_T_direct": len(t_direct),
        "n_T_impact": len(t_impact),
        "n_R1_release": len(r1_release),
        "n_seeds": len(seeds),
        "n_closure": closure.size,
        "closure_frac": round(closure.size / max(1, len(reservations)), 4),
        "feasible_after_block": feasible_after,
        "lu_min_cut": feats.get("lu_min_cut"),
        "far_group_cut": feats.get("far_group_cut"),
        "structural_leaks": len(leaks),
        "pass_C1": pass_c1,
    }

    print("=== STRC E1: task-graph miss vs reservation closure ===")
    for k, v in row.items():
        print(f"  {k}: {v}")
    print(f"  C1 verdict: {'PASS' if pass_c1 else 'FAIL'}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_header = not os.path.isfile(args.out)
    with open(args.out, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)

    detail = os.path.join(ROOT, "experiments", "e1_last.json")
    with open(detail, "w", encoding="utf-8") as f:
        json.dump({
            "row": row,
            "T_direct": sorted(t_direct),
            "T_impact": sorted(t_impact),
            "seeds": [asdict(r) for r in seeds],
            "closure_size": closure.size,
            "leaks": leaks,
        }, f, ensure_ascii=False, indent=2)
    print(f"  wrote {args.out}")
    print(f"  wrote {detail}")
    return 0 if pass_c1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
