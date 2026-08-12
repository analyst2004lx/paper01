"""E2 包含性:E2a 结构抽检 + E2b 修复后外侧字段不变。

用法:
    py -m tools.e2_containment
    py -m tools.e2_containment --instance ../clbs/input/congested_8x4x4.json
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STRC E2: containment")
    ap.add_argument("--instance", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
    from algorithm.closure import (
        assert_containment_structural,
        machine_chains_from_ops,
        spatiotemporal_closure,
    )
    from algorithm.disturbance import Disturbance, seed_failed_reservations
    from algorithm.repair import outside_reservations_unchanged, repair_with_strc
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    inst_path = args.instance or os.path.join(CLBS_INPUT, "example_3x3x2.json")
    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    bundle = build_baseline(inst, net, seed=args.seed)
    t_now = args.t_now_frac * bundle.makespan
    cid, t0, t1, n = pick_busy_corridor(bundle.reservations, t_now=t_now)
    dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                       t_start=t0, t_end=t1)
    seeds = seed_failed_reservations(dist, bundle.reservations)
    chains = machine_chains_from_ops(bundle.result.ops)
    closure = spatiotemporal_closure(
        seeds, bundle.reservations, horizon=bundle.makespan + 1.0,
        t_now=t_now, machine_chains=chains,
    )
    leaks = assert_containment_structural(
        closure, bundle.reservations, t_now=t_now, machine_chains=chains)

    print(f"[E2a] corridor={cid} hits={n} seeds={len(seeds)} "
          f"closure={closure.size} leaks={len(leaks)}")
    if leaks:
        for x in leaks[:10]:
            print("  ", x)
        return 1
    print("[E2a] PASS")

    rep = repair_with_strc(inst, net, bundle, dist)
    print(f"[E2b] feasible={rep.feasible} Cmax {rep.makespan_ref} -> {rep.makespan} "
          f"wall={rep.wall_ms:.1f}ms")
    if not rep.feasible or rep.result is None:
        for e in rep.errors[:8]:
            print("  err:", e)
        return 1
    outside_errs = outside_reservations_unchanged(
        bundle.result, rep.result, closure.closed)
    print(f"[E2b] outside changes={len(outside_errs)}")
    if outside_errs:
        for e in outside_errs[:8]:
            print("  ", e)
        return 1
    print("[E2b] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
