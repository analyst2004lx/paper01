"""非均匀边权扫描:只重跑 E1/E3,检验主结论对等权标定是否敏感。

三档都在原走廊 time 上乘一个因子,再重建 Network(ideal_dist 随之重算):
  lognormal  独立对数正态,几何均值归一到 1,保留平均尺度
  lu_far     离装卸点越远越慢(1 + 0.8 * d/dmax)
  split      各走廊独立取 0.5 或 2.0

用法(在 STRC/ 下):
    py -m tools.weight_sweep
    py -m tools.weight_sweep --seeds 42,7 --modes lognormal
"""
from __future__ import annotations

import argparse
import copy
import csv
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_SEEDS = [42, 7, 2024, 99, 123, 13, 1, 777, 31415, 8]
_MODES = ("lognormal", "lu_far", "split")
_MODE_SALT = {"lognormal": 11, "lu_far": 22, "split": 33}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="non-uniform corridor weights, E1/E3")
    ap.add_argument("--seeds", default=",".join(str(s) for s in _SEEDS))
    ap.add_argument("--modes", default=",".join(_MODES))
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--out", default="experiments/weight_sweep.csv")
    return ap.parse_args()


def _instances():
    from algorithm.clbs_bridge import CLBS_INPUT
    ext = lambda n: os.path.join(CLBS_INPUT, "ext", n)  # noqa: E731
    return [
        ("example_3x3x2", os.path.join(CLBS_INPUT, "example_3x3x2.json")),
        ("congested_8x4x4", os.path.join(CLBS_INPUT, "congested_8x4x4.json")),
        ("S8x4x4_high", ext("S8x4x4-LD21-H0.3-F0.6-A4-s42.json")),
        ("S8x4x4_funnel", ext("S8x4x4-LD11-H0.3-F0.6-A4-s42.json")),
        ("S8x4x4_mid", ext("S8x4x4-LD22-H0.3-F0.6-A4-s42.json")),
    ]


def _cid(u: str, v: str) -> str:
    return f"{u}|{v}" if u <= v else f"{v}|{u}"


def apply_weights(inst, mode: str, seed: int):
    """深拷贝算例并改写 corridors[].time。"""
    from algorithm.clbs_bridge import Network

    inst = copy.deepcopy(inst)
    rng = random.Random(seed + _MODE_SALT[mode] * 10007)
    net0 = Network(inst.nodes, inst.corridors, inst.lu_node)
    factors = {}
    if mode == "lognormal":
        raw = {}
        for c in inst.corridors:
            raw[_cid(c["u"], c["v"])] = rng.lognormvariate(0.0, 0.40)
        g = math.exp(sum(math.log(v) for v in raw.values()) / len(raw))
        factors = {k: v / g for k, v in raw.items()}
    elif mode == "split":
        for c in inst.corridors:
            factors[_cid(c["u"], c["v"])] = 0.5 if rng.random() < 0.5 else 2.0
    elif mode == "lu_far":
        dmax = 0.0
        dist = {}
        for c in inst.corridors:
            du = net0.ideal_dist[inst.lu_node].get(c["u"], 0.0)
            dv = net0.ideal_dist[inst.lu_node].get(c["v"], 0.0)
            d = 0.5 * (du + dv)
            dist[_cid(c["u"], c["v"])] = d
            dmax = max(dmax, d)
        for cid, d in dist.items():
            factors[cid] = 1.0 + 0.8 * (d / dmax if dmax > 0 else 0.0)
    else:
        raise ValueError(mode)
    for c in inst.corridors:
        c["time"] = float(c["time"]) * factors[_cid(c["u"], c["v"])]
    return inst


def _run_e1e3(inst, inst_name, seed, t_frac, mode, rows):
    from algorithm.clbs_bridge import Network
    from algorithm.closure import (
        machine_chains_from_ops,
        spatiotemporal_closure,
        task_graph_impact,
        job_precedence_from_reservations,
    )
    from algorithm.disturbance import (
        Disturbance,
        schedule_still_valid_under_block,
        seed_failed_reservations,
    )
    from algorithm.repair import repair_with_strc, repair_with_task_graph
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
    t_now = t_frac * bundle.makespan
    cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
    dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                       t_start=t0, t_end=t1)
    job_succ = job_precedence_from_reservations(bundle.reservations)
    t_impact = task_graph_impact(dist, job_succ, theta=2,
                                 schedule_meta={"machine_tasks": {}, "agv_tasks": {}})
    seeds = seed_failed_reservations(dist, bundle.reservations)
    chains = machine_chains_from_ops(bundle.result.ops)
    closure = spatiotemporal_closure(
        seeds, bundle.reservations, horizon=bundle.makespan + 1.0,
        t_now=t_now, machine_chains=chains)
    miss = (len(t_impact) == 0 and len(seeds) > 0
            and not schedule_still_valid_under_block(bundle.reservations, dist))
    r1 = repair_with_task_graph(inst, net, bundle, dist, expand_on_fail=False)
    r2 = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
    rows.append({
        "instance": inst_name, "seed": seed, "mode": mode,
        "n_seeds": len(seeds), "n_closure": closure.size,
        "n_T_impact": len(t_impact),
        "closure_frac": round(closure.size / max(1, len(bundle.reservations)), 4),
        "pass_C1": miss and closure.size >= len(seeds),
        "R1_feasible": r1.feasible, "R2_feasible": r2.feasible,
        "ref_makespan": bundle.makespan,
    })
    print(f"  {mode:<10} {inst_name:<16} s={seed:<6} "
          f"C1={str(miss):<5} R1={r1.feasible} R2={r2.feasible} "
          f"|Cl|={closure.size}")


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import load_instance

    seeds = [int(x) for x in args.seeds.split(",")]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    rows = []
    for mode in modes:
        print(f"=== weight mode {mode} ===")
        for name, path in _instances():
            if not os.path.isfile(path):
                print(f"  skip missing {path}")
                continue
            base = load_instance(path)
            for seed in seeds:
                inst = apply_weights(base, mode, seed)
                _run_e1e3(inst, name, seed, args.t_now_frac, mode, rows)

    out = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) else args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}  ({len(rows)} rows)")
    for mode in modes:
        rs = [r for r in rows if r["mode"] == mode]
        print("  %-10s C1 %d/%d  R1 feas %d/%d  R2 feas %d/%d"
              % (mode,
                 sum(1 for r in rs if r["pass_C1"]), len(rs),
                 sum(1 for r in rs if r["R1_feasible"]), len(rs),
                 sum(1 for r in rs if r["R2_feasible"]), len(rs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
