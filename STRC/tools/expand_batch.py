"""扩种子/算例批跑:E1/E2/E3 + scale_compare,结果写入 experiments/expanded/。

用法(在 STRC/ 下):
    py -m tools.expand_batch
    py -m tools.expand_batch --seeds 42,7,2024,99,123 --budget-sec 2
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "experiments", "expanded")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STRC expanded seed/instance matrix")
    ap.add_argument("--seeds", default="42,7,2024,99,123,13,1,777,31415,8")
    ap.add_argument("--budget-sec", type=float, default=2.0)
    ap.add_argument("--t-now-frac", type=float, default=0.35)
    ap.add_argument("--skip-scale", action="store_true")
    ap.add_argument("--skip-e5", action="store_true")
    ap.add_argument("--skip-e6", action="store_true")
    ap.add_argument("--only-e5", action="store_true",
                    help="只跑 E5。用于复核 A2 越界列而不重生成其余读数")
    ap.add_argument("--out-dir", default=OUT)
    args = ap.parse_args()
    if args.only_e5:
        args.skip_scale = args.skip_e6 = True
    return args


def _instances():
    """五个算例格。

    原来只有前三个,共 3x5=15 对,而 paper01 是 100 对——评审上这是本文最弱的一处。
    后两个补的是布局维度:funnel(LD11,装卸点最小割最窄)与 mid(LD22,出口更多),
    与 high(LD21)同规模同柔性,只差走廊拓扑,故闭包规模的差异可归因于布局。
    种子默认与 paper01 的十种子表对齐,合计 5x10=50 对。
    """
    from algorithm.clbs_bridge import CLBS_INPUT
    ext = lambda n: os.path.join(CLBS_INPUT, "ext", n)  # noqa: E731
    return [
        ("example_3x3x2", os.path.join(CLBS_INPUT, "example_3x3x2.json")),
        ("congested_8x4x4", os.path.join(CLBS_INPUT, "congested_8x4x4.json")),
        ("S8x4x4_high", ext("S8x4x4-LD21-H0.3-F0.6-A4-s42.json")),
        ("S8x4x4_funnel", ext("S8x4x4-LD11-H0.3-F0.6-A4-s42.json")),
        ("S8x4x4_mid", ext("S8x4x4-LD22-H0.3-F0.6-A4-s42.json")),
    ]


def _run_e1e2e3(inst_path, inst_name, seed, t_frac, rows_e1, rows_e2, rows_e3):
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.closure import (
        assert_containment_structural,
        machine_chains_from_ops,
        spatiotemporal_closure,
        task_graph_direct,
        task_graph_impact,
        job_precedence_from_reservations,
        release_set_from_tasks,
    )
    from algorithm.disturbance import (
        Disturbance,
        schedule_still_valid_under_block,
        seed_failed_reservations,
    )
    from algorithm.repair import (
        outside_reservations_unchanged,
        release_set_r1,
        release_set_r2,
        repair_with_strc,
        repair_with_task_graph,
        replay_reroute,
    )
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
    t_now = t_frac * bundle.makespan
    cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
    dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                       t_start=t0, t_end=t1)

    # E1
    meta = {"machine_tasks": {}, "agv_tasks": {}}
    t_direct = task_graph_direct(dist, meta)
    job_succ = job_precedence_from_reservations(bundle.reservations)
    t_impact = task_graph_impact(dist, job_succ, theta=2, schedule_meta=meta)
    seeds = seed_failed_reservations(dist, bundle.reservations)
    chains = machine_chains_from_ops(bundle.result.ops)
    closure = spatiotemporal_closure(
        seeds, bundle.reservations, horizon=bundle.makespan + 1.0,
        t_now=t_now, machine_chains=chains)
    leaks = assert_containment_structural(
        closure, bundle.reservations, t_now=t_now, machine_chains=chains)
    feasible_block = schedule_still_valid_under_block(bundle.reservations, dist)
    pass_c1 = (len(t_impact) == 0 and len(seeds) > 0
               and closure.size >= len(seeds) and not feasible_block)
    rows_e1.append({
        "instance": inst_name, "seed": seed, "corridor": cid,
        "n_reservations": len(bundle.reservations),
        "n_T_impact": len(t_impact), "n_seeds": len(seeds),
        "n_closure": closure.size,
        "closure_frac": round(closure.size / max(1, len(bundle.reservations)), 4),
        "feasible_after_block": feasible_block,
        "structural_leaks": len(leaks),
        "pass_C1": pass_c1,
        "ref_makespan": bundle.makespan,
    })

    # E2
    rep = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
    outside = []
    if rep.feasible and rep.result is not None:
        outside = outside_reservations_unchanged(
            bundle.result, rep.result, closure.closed)
    rows_e2.append({
        "instance": inst_name, "seed": seed, "corridor": cid,
        "structural_leaks": len(leaks),
        "feasible": rep.feasible,
        "makespan": rep.makespan,
        "ref_makespan": bundle.makespan,
        "wall_ms": round(rep.wall_ms, 2),
        "outside_changes": len(outside),
        "pass_E2a": len(leaks) == 0,
        "pass_E2b": rep.feasible and len(outside) == 0,
    })

    # E3 no expand
    r1 = release_set_r1(bundle, dist, theta=2)
    r2 = release_set_r2(bundle, dist)
    rep1 = repair_with_task_graph(inst, net, bundle, dist, expand_on_fail=False)
    rep2 = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)
    rows_e3.append({
        "instance": inst_name, "seed": seed, "corridor": cid,
        "R1_release": len(r1), "R2_release": len(r2),
        "R1_feasible": rep1.feasible, "R2_feasible": rep2.feasible,
        "R1_makespan": rep1.makespan, "R2_makespan": rep2.makespan,
        "R1_wall_ms": round(rep1.wall_ms, 2),
        "R2_wall_ms": round(rep2.wall_ms, 2),
        "miss_on_B": len(r1) == 0 and len(r2) > 0,
        "quality_winner": (
            "R2" if rep2.feasible and not rep1.feasible else
            "R1" if rep1.feasible and not rep2.feasible else
            "tie" if rep1.feasible and rep2.feasible else "none"
        ),
    })


def _run_scale(inst_path, inst_name, seed, t_frac, budget, pop, rows):
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.closure import machine_chains_from_ops
    from algorithm.repair import repair_with_scope_escalation
    from algorithm.resolve import resolve_r0
    from algorithm.schedule_io import build_baseline
    from tools.scale_compare import (
        _future_ops_by_reservation,
        _make_dist,
        _release_covering_blocks,
        _reservations_of_ops,
    )

    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
    t_now = t_frac * bundle.makespan
    future = _future_ops_by_reservation(bundle.reservations, t_now)
    if not future:
        return
    chains = machine_chains_from_ops(bundle.result.ops)
    for phi in (0.1, 0.25, 0.5, 0.75, 1.0):
        k = min(len(future), max(1, int(math.ceil(phi * len(future)))))
        affected = set(future[:k])
        seed_res = _reservations_of_ops(bundle.reservations, affected, t_now=t_now)
        if not seed_res:
            continue
        dist = _make_dist(t_now, seed_res)
        closure = _release_covering_blocks(
            bundle.reservations, dist.extra["blocks"],
            t_now, bundle.makespan + 1.0, chains)
        rep4 = repair_with_scope_escalation(
            inst, net, bundle, dist, closure.closed)
        rep1 = resolve_r0(
            inst, net, bundle, dist,
            budget_sec=budget, seed=seed, hot=True, pop=pop)
        rows.append({
            "instance": inst_name, "seed": seed, "phi": phi,
            "n_affected_ops": k, "n_future_ops": len(future),
            "n_closure": closure.size,
            "strc_feasible": rep4.feasible,
            "strc_makespan": rep4.makespan,
            "strc_wall_ms": round(rep4.wall_ms, 2),
            "strc_scope_rounds": rep4.meta.get("scope_rounds"),
            "r0_feasible": rep1.feasible,
            "r0_makespan": rep1.makespan,
            "r0_wall_ms": round(rep1.wall_ms, 2),
            "speedup": (None if rep4.wall_ms <= 0 else
                        round(rep1.wall_ms / rep4.wall_ms, 1)),
            "ref_makespan": bundle.makespan,
        })
        print(f"  scale {inst_name} seed={seed} φ={phi:.2f} "
              f"STRC={rep4.feasible}/{rep4.wall_ms:.1f}ms "
              f"R0={rep1.feasible}/{rep1.wall_ms:.0f}ms")


def _run_e5(inst_path, inst_name, seed, t_frac, rows):
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.disturbance import Disturbance
    from algorithm.metrics import reservation_delta_before
    from algorithm.repair import repair_with_strc
    from algorithm.resolve import resolve_r0
    from algorithm.schedule_io import (
        build_baseline,
        pick_busy_corridor,
        reservations_from_result,
    )

    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
    t_now = t_frac * bundle.makespan
    cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
    dist = Disturbance(type="corridor_block", t_now=t_now, corridor=cid,
                       t_start=t0, t_end=t1)
    rep2 = repair_with_strc(inst, net, bundle, dist, expand_on_fail=False)

    def _past(rep):
        """按假设 A2,t_end <= t_now 的预约不得被改写,这里数它被改了几条。

        全局重解臂从 t=0 重新解码,不受 A2 约束,其完工时间因此只能读作参考下界;
        把越界条数与该臂的读数记在同一行,是为了让这层口径不必回到正文去找。
        """
        if not rep.feasible or rep.result is None:
            return None, None
        return reservation_delta_before(
            bundle.reservations, reservations_from_result(rep.result), t_now=t_now)

    r2_past_chg, r2_past_tot = _past(rep2)
    for bud in (0.2, 1.0, 2.0):
        rep0 = resolve_r0(inst, net, bundle, dist, budget_sec=bud,
                          seed=seed, hot=True, pop=40)
        r0_past_chg, r0_past_tot = _past(rep0)
        d2 = rep2.deviation
        d0 = rep0.deviation
        rows.append({
            "instance": inst_name, "seed": seed, "budget_sec": bud,
            "corridor": cid,
            "R0_feasible": rep0.feasible, "R0_makespan": rep0.makespan,
            "R0_wall_ms": round(rep0.wall_ms, 2),
            "R0_res_frac": (None if d0 is None or d0.reservation_total <= 0 else
                            round(d0.reservation_changed / d0.reservation_total, 3)),
            "R2_feasible": rep2.feasible, "R2_makespan": rep2.makespan,
            "R2_wall_ms": round(rep2.wall_ms, 2),
            "R2_res_frac": (None if d2 is None or d2.reservation_total <= 0 else
                            round(d2.reservation_changed / d2.reservation_total, 3)),
            "R0_past_changed": r0_past_chg, "R0_past_total": r0_past_tot,
            "R2_past_changed": r2_past_chg, "R2_past_total": r2_past_tot,
            "ref_makespan": bundle.makespan,
        })
        print(f"  e5 {inst_name} seed={seed} bud={bud} "
              f"R0 Cmax={rep0.makespan} R2 Cmax={rep2.makespan} "
              f"past R0={r0_past_chg}/{r0_past_tot} R2={r2_past_chg}/{r2_past_tot}")


def _run_e6_types(inst_path, inst_name, seed, t_frac, rows):
    """E6:扰动类型 x 边界定义。填的是覆盖矩阵里那一大片「未测」。

    为什么这一组只测边界、不测修复。四类扰动里只有走廊阻断被修复引擎正确建模
    ——阻断被注入为 Router 上的一段强制占用。降速在 block_context 里被当成整段
    阻断处理(过近似),车辆故障与机械臂故障则根本没有注入通道,重放时那台车/那台
    机器仍然可用。所以对后三类跑「可行率」得到的会是假阳性。本组因此只报**边界**:
    任务图影响域有多大、预约闭包有多大、后者是否包含前者。这恰好是覆盖矩阵要回答
    的问题——「任务图边界看不看得见这类扰动」——而不需要修复语义。

    A/B 之分按 algorithm.disturbance.TOUCHES_TASK_GRAPH:
      B 类(不碰任务图):corridor_block、corridor_slowdown
      A 类(碰任务图)  :ra_failure、agv_breakdown
    注意车辆故障被判为 A 类:它虽不改工序指派,却使该车承运的工序无法执行,
    按定义 A 的「可执行性失效」成立,且任务图上确有非空种子(经车-任务映射)。
    """
    from algorithm.clbs_bridge import Network, load_instance
    from algorithm.closure import (
        machine_chains_from_ops,
        spatiotemporal_closure,
        task_graph_impact,
        job_precedence_from_reservations,
    )
    from algorithm.disturbance import Disturbance, seed_failed_reservations
    from algorithm.repair import release_set_r1
    from algorithm.schedule_io import build_baseline, pick_busy_corridor

    inst = load_instance(inst_path)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    bundle = build_baseline(inst, net, seed=seed, mode="heuristic")
    t_now = t_frac * bundle.makespan
    chains = machine_chains_from_ops(bundle.result.ops)
    job_succ = job_precedence_from_reservations(bundle.reservations)

    cid, t0, t1, _ = pick_busy_corridor(bundle.reservations, t_now=t_now)
    cases = [
        ("corridor_block", Disturbance(
            type="corridor_block", t_now=t_now, corridor=cid,
            t_start=t0, t_end=t1)),
        ("corridor_slowdown", Disturbance(
            type="corridor_slowdown", t_now=t_now, corridor=cid,
            t_start=t0, t_end=t1, tau_mult=2.0)),
    ]

    # 车辆故障:取 t_now 之后剩余运输段最多的那辆车,避免挑到一辆已经收工的。
    fut = defaultdict(int)
    for r in bundle.reservations:
        if r.t_end > t_now:
            fut[r.agv] += 1
    if fut:
        agv = max(fut, key=lambda a: fut[a])
        cases.append(("agv_breakdown", Disturbance(
            type="agv_breakdown", t_now=t_now, agv=int(agv))))

    # 机械臂故障:取 t_now 之后剩余工序最多的那台机器,失效工序为其全部未完工序。
    mfut = defaultdict(list)
    for rec in bundle.result.ops.values():
        if getattr(rec, "pseudo", False) or rec.machine is None:
            continue
        if rec.finish > t_now:
            mfut[str(rec.machine)].append((rec.job, rec.i))
    if mfut:
        mac = max(mfut, key=lambda m: len(mfut[m]))
        cases.append(("ra_failure", Disturbance(
            type="ra_failure", t_now=t_now, machine=mac,
            extra={"failed_ops": mfut[mac]})))

    # 与 release_set_r1 内部逐字同构,否则 T_impact 与 |R1| 会来自两套 meta。
    atasks = defaultdict(list)
    for tr in bundle.result.transports:
        if tr.arrive > t_now:
            atasks[tr.agv].append(f"J{tr.job}-{tr.i}")
    meta = {
        "machine_tasks": {m: [f"J{j}-{i}" for j, i in ops]
                          for m, ops in mfut.items()},
        "agv_tasks": atasks,
    }

    n_alive = sum(1 for r in bundle.reservations if r.t_end > t_now)
    for label, dist in cases:
        t_impact = task_graph_impact(dist, job_succ, theta=2, schedule_meta=meta)
        r1 = release_set_r1(bundle, dist, theta=2)
        seeds = seed_failed_reservations(dist, bundle.reservations)
        closure = spatiotemporal_closure(
            seeds, bundle.reservations, horizon=bundle.makespan + 1.0,
            t_now=t_now, machine_chains=chains)
        cl = closure.as_set()
        rows.append({
            "instance": inst_name, "seed": seed,
            "dist_type": label, "dist_class": dist.class_label,
            "n_alive": n_alive,
            "n_T_impact": len(t_impact),
            "n_R1_release": len(r1),
            "n_seeds": len(seeds),
            "n_closure": closure.size,
            "closure_frac": round(closure.size / max(1, n_alive), 4),
            "R1_empty": len(r1) == 0,
            "R2_covers_R1": all(r in cl for r in r1),
            "R2_strictly_larger": len(cl) > len(set(r1)),
        })


def _write(path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _summarize_md(out_dir, e1, e2, e3, scale, e5) -> str:
    lines = ["# Expanded STRC matrix", ""]
    # E1
    lines += ["## E1 miss", "",
              "| instance | n | C1 pass | mean Cl | mean seeds |",
              "|---|---:|---:|---:|---:|"]
    by = defaultdict(list)
    for r in e1:
        by[r["instance"]].append(r)
    for name, rs in by.items():
        lines.append(
            f"| `{name}` | {len(rs)} | "
            f"{sum(1 for r in rs if r['pass_C1'])}/{len(rs)} | "
            f"{sum(r['n_closure'] for r in rs)/len(rs):.1f} | "
            f"{sum(r['n_seeds'] for r in rs)/len(rs):.1f} |"
        )
    # E2
    lines += ["", "## E2 containment", "",
              "| instance | E2a | E2b | feas |",
              "|---|---:|---:|---:|"]
    by = defaultdict(list)
    for r in e2:
        by[r["instance"]].append(r)
    for name, rs in by.items():
        lines.append(
            f"| `{name}` | {sum(1 for r in rs if r['pass_E2a'])}/{len(rs)} | "
            f"{sum(1 for r in rs if r['pass_E2b'])}/{len(rs)} | "
            f"{sum(1 for r in rs if r['feasible'])}/{len(rs)} |"
        )
    # E3
    lines += ["", "## E3 boundary (no expand)", "",
              "| instance | miss_B | R2 win | R1 feas | R2 feas |",
              "|---|---:|---:|---:|---:|"]
    by = defaultdict(list)
    for r in e3:
        by[r["instance"]].append(r)
    for name, rs in by.items():
        lines.append(
            f"| `{name}` | {sum(1 for r in rs if r['miss_on_B'])}/{len(rs)} | "
            f"{sum(1 for r in rs if r['quality_winner']=='R2')}/{len(rs)} | "
            f"{sum(1 for r in rs if r['R1_feasible'])}/{len(rs)} | "
            f"{sum(1 for r in rs if r['R2_feasible'])}/{len(rs)} |"
        )
    # scale
    if scale:
        lines += ["", "## Scale (STRC vs R0+)", "",
                  "| instance | φ | STRC feas | STRC ms | R0 Cmax | speedup |",
                  "|---|---:|---:|---:|---:|---:|"]
        by = defaultdict(list)
        for r in scale:
            by[(r["instance"], r["phi"])].append(r)
        for key in sorted(by, key=lambda x: (x[0], x[1])):
            rs = by[key]
            def avg(k, pred=None):
                xs = [r[k] for r in rs if r[k] is not None and (pred is None or pred(r))]
                return sum(xs) / len(xs) if xs else float("nan")
            lines.append(
                f"| `{key[0]}` | {key[1]:.2f} | "
                f"{sum(1 for r in rs if r['strc_feasible'])/len(rs):.0%} | "
                f"{avg('strc_wall_ms'):.1f} | "
                f"{avg('r0_makespan', lambda r: r['r0_feasible']):.1f} | "
                f"{avg('speedup'):.0f}× |"
            )
    if e5:
        lines += ["", "## E5 budgets", "",
                  "| instance | budget | R0 Cmax | R2 Cmax | R2 ms |",
                  "|---|---:|---:|---:|---:|"]
        by = defaultdict(list)
        for r in e5:
            by[(r["instance"], r["budget_sec"])].append(r)
        for key in sorted(by, key=lambda x: (x[0], x[1])):
            rs = by[key]
            lines.append(
                f"| `{key[0]}` | {key[1]:g} | "
                f"{sum(r['R0_makespan'] for r in rs if r['R0_feasible'])/max(1,sum(1 for r in rs if r['R0_feasible'])):.1f} | "
                f"{sum(r['R2_makespan'] for r in rs if r['R2_feasible'])/max(1,sum(1 for r in rs if r['R2_feasible'])):.1f} | "
                f"{sum(r['R2_wall_ms'] for r in rs)/len(rs):.1f} |"
            )
    path = os.path.join(out_dir, "summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _summarize_e6(out_dir, e6) -> None:
    if not e6:
        return
    lines = ["", "## E6 disturbance type x boundary", "",
             "| type | class | n | R1 empty | mean T_impact | mean |R1| |"
             " mean |Cl| | mean Cl/alive | R2 covers R1 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    by = defaultdict(list)
    for r in e6:
        by[r["dist_type"]].append(r)
    order = ["corridor_block", "corridor_slowdown", "agv_breakdown", "ra_failure"]
    for t in order:
        rs = by.get(t)
        if not rs:
            continue
        n = len(rs)
        lines.append(
            f"| `{t}` | {rs[0]['dist_class']} | {n} | "
            f"{sum(1 for r in rs if r['R1_empty'])}/{n} | "
            f"{sum(r['n_T_impact'] for r in rs)/n:.1f} | "
            f"{sum(r['n_R1_release'] for r in rs)/n:.1f} | "
            f"{sum(r['n_closure'] for r in rs)/n:.1f} | "
            f"{sum(r['closure_frac'] for r in rs)/n:.3f} | "
            f"{sum(1 for r in rs if r['R2_covers_R1'])}/{n} |"
        )
    path = os.path.join(out_dir, "summary.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    args = parse_args()
    seeds = [int(x) for x in args.seeds.split(",")]
    os.makedirs(args.out_dir, exist_ok=True)
    e1, e2, e3, scale, e5, e6 = [], [], [], [], [], []

    if not args.only_e5:
        print("=== expand_batch: E1/E2/E3 ===")
        for name, path in _instances():
            if not os.path.isfile(path):
                print(f"  skip missing {path}")
                continue
            for seed in seeds:
                print(f"  E1-3 {name} seed={seed}")
                _run_e1e2e3(path, name, seed, args.t_now_frac, e1, e2, e3)

    if not args.skip_scale:
        print("=== expand_batch: scale_compare ===")
        # 规模扫描:小例+争用例(跳过生成器 high 以控时)
        for name, path in _instances()[:2]:
            for seed in seeds:
                _run_scale(path, name, seed, args.t_now_frac,
                           args.budget_sec, 40, scale)

    if not args.skip_e5:
        print("=== expand_batch: E5 ===")
        for name, path in _instances()[:2]:
            for seed in seeds[:3]:  # 3 seeds × 3 budgets
                _run_e5(path, name, seed, args.t_now_frac, e5)

    if not args.skip_e6:
        print("=== expand_batch: E6 disturbance types ===")
        for name, path in _instances():
            if not os.path.isfile(path):
                continue
            for seed in seeds:
                _run_e6_types(path, name, seed, args.t_now_frac, e6)

    _write(os.path.join(args.out_dir, "e6_types.csv"), e6)
    _write(os.path.join(args.out_dir, "e1_miss.csv"), e1)
    _write(os.path.join(args.out_dir, "e2_containment.csv"), e2)
    _write(os.path.join(args.out_dir, "e3_boundary.csv"), e3)
    _write(os.path.join(args.out_dir, "scale_compare.csv"), scale)
    _write(os.path.join(args.out_dir, "e5_cross_curve.csv"), e5)
    md = _summarize_md(args.out_dir, e1, e2, e3, scale, e5)
    _summarize_e6(args.out_dir, e6)
    print(f"wrote summary {md}")
    print(f"E1 C1 pass {sum(1 for r in e1 if r['pass_C1'])}/{len(e1)}")
    print(f"E2b pass {sum(1 for r in e2 if r['pass_E2b'])}/{len(e2)}")
    print(f"E3 R2 feas {sum(1 for r in e3 if r['R2_feasible'])}/{len(e3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
