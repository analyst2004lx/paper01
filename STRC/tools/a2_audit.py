"""假设 A2 的独立审计:修复后有哪些 t_now 之前已执行完的预约被改写了。

A2 规定已完成的占用不回溯修改,所以对 R1/R2 这类有界修复,这个清单必须是空的。
e5_cross_curve 只报计数;这里把逐条 before/after 打出来,用于判断非零计数是真的
越界改写,还是审计口径本身的问题(例如同一任务两次经过同一走廊时键会合并)。

用法:
    py -m tools.a2_audit
    py -m tools.a2_audit --instance ../clbs/input/example_3x3x2.json --seeds 7
    py -m tools.a2_audit --baseline-mode ga --seeds 42,7,2024
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EPS = 1e-9


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="A2 (past immutability) audit")
    ap.add_argument("--instance", default=None)
    ap.add_argument("--seeds", default="42,7,2024")
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--baseline-mode", choices=("heuristic", "ga"),
                    default="heuristic")
    ap.add_argument("--baseline-budget", type=float, default=5.0)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    from algorithm.clbs_bridge import CLBS_INPUT, Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.repair import repair_with_strc
    from algorithm.schedule_io import (
        build_baseline,
        pick_busy_corridor,
        reservations_from_result,
    )

    inst_path = args.instance or os.path.join(CLBS_INPUT, "congested_8x4x4.json")
    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    net.check_reachability()

    total_bad = 0
    for seed in [int(x) for x in args.seeds.split(",")]:
        bundle = build_baseline(inst, net, seed=seed, mode=args.baseline_mode,
                                budget_sec=args.baseline_budget)
        t_now = args.t_now_frac * bundle.makespan
        cid, _, _, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
        dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                           t_start=t_now, t_end=bundle.makespan + 1.0)
        rep = repair_with_strc(inst, net, bundle, dist)
        if not rep.feasible or rep.result is None:
            print(f"seed={seed}: 修复失败,跳过")
            continue

        before = [r for r in bundle.reservations if r.t_end <= t_now + EPS]
        after = reservations_from_result(rep.result)
        # 先看键是否唯一;不唯一则计数本身不可信
        kb = Counter((r.corridor, r.agv, r.task) for r in before)
        dup = {k: n for k, n in kb.items() if n > 1}
        aft = {}
        for r in after:
            aft.setdefault((r.corridor, r.agv, r.task), []).append(r)

        bad = []
        for r in before:
            key = (r.corridor, r.agv, r.task)
            cand = aft.get(key, [])
            if not cand:
                bad.append((r, None))
                continue
            if not any(abs(c.t_start - r.t_start) <= EPS
                       and abs(c.t_end - r.t_end) <= EPS for c in cand):
                bad.append((r, cand[0]))

        print(f"\nseed={seed} t_now={t_now:.2f} ref_Cmax={bundle.makespan} "
              f"corridor={cid}")
        print(f"  过去预约 {len(before)} 条,重复键 {len(dup)} 组,越界 {len(bad)} 条")
        for k, n in sorted(dup.items()):
            print(f"    [重复键] {k} x{n}")
        for r, r2 in bad:
            tgt = "缺失" if r2 is None else f"[{r2.t_start:g},{r2.t_end:g})"
            print(f"    [越界] {r.task}@{r.corridor} agv={r.agv} "
                  f"[{r.t_start:g},{r.t_end:g}) -> {tgt}")
        total_bad += len(bad)

    print(f"\n合计越界 {total_bad} 条")
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
